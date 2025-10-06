from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import os
import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
import hashlib
from geopy.distance import geodesic

# Configuración simple
JWT_SECRET = "clave-secreta-pediatrica-2025"
HOSPITAL_COORDS = (22.930758, -82.689342)
MAX_DISTANCE = 200

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos de datos
class UserLogin(BaseModel):
    email: str
    password: str

class UserRegister(BaseModel):
    email: str
    password: str
    full_name: str

class CheckInData(BaseModel):
    latitude: str
    longitude: str
    accuracy: str
    photo_data: str
    ip_address: str

# Base de datos simulada (luego la conectamos a PostgreSQL)
users_db = {}
attendance_db = []

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Utilidades
def hash_password(password):
    return pwd_context.hash(password)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def create_token(email):
    return jwt.encode({"email": email, "exp": datetime.utcnow() + timedelta(hours=24)}, JWT_SECRET, algorithm="HS256")

def verify_token(token):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except:
        return None

def check_distance(lat1, lon1):
    coords_1 = (float(lat1), float(lon1))
    return geodesic(coords_1, HOSPITAL_COORDS).meters

# Crear usuario administrador por defecto
users_db["rodney@admin.com"] = {
    "password": hash_password("admin123"),
    "full_name": "Rodney Admin",
    "is_admin": True
}

# Rutas principales
@app.post("/auth/register")
def register(user: UserRegister):
    if user.email in users_db:
        return {"error": "Email ya registrado"}
    
    users_db[user.email] = {
        "password": hash_password(user.password),
        "full_name": user.full_name,
        "is_admin": False
    }
    
    return {"message": "Usuario registrado exitosamente"}

@app.post("/auth/login")
def login(user: UserLogin):
    if user.email not in users_db:
        return {"error": "Credenciales inválidas"}
    
    if not verify_password(user.password, users_db[user.email]["password"]):
        return {"error": "Credenciales inválidas"}
    
    token = create_token(user.email)
    
    return {
        "access_token": token,
        "user": {
            "email": user.email,
            "full_name": users_db[user.email]["full_name"],
            "is_admin": users_db[user.email]["is_admin"]
        }
    }

@app.post("/attendance/checkin")
def check_in(data: CheckInData, token: str = Depends(lambda: None)):
    if not token:
        return {"error": "Token requerido"}
    
    user_data = verify_token(token)
    if not user_data:
        return {"error": "Token inválido"}
    
    email = user_data["email"]
    
    # Verificar ubicación
    distance = check_distance(data.latitude, data.longitude)
    if distance > MAX_DISTANCE:
        return {"error": f"Está a {distance:.0f}m del hospital. Debe estar dentro de 200m."}
    
    # Verificar si ya registró hoy
    today = datetime.now().date()
    for record in attendance_db:
        if record["email"] == email and record["date"] == today.isoformat():
            return {"error": "Ya registró asistencia hoy"}
    
    # Crear registro
    record = {
        "email": email,
        "full_name": users_db[email]["full_name"],
        "timestamp": datetime.now().isoformat(),
        "latitude": data.latitude,
        "longitude": data.longitude,
        "accuracy": data.accuracy,
        "ip_address": data.ip_address,
        "distance": distance,
        "date": today.isoformat()
    }
    
    attendance_db.append(record)
    
    return {
        "message": "Asistencia registrada exitosamente",
        "distance": distance,
        "timestamp": record["timestamp"]
    }

@app.get("/attendance/list")
def list_attendance(token: str):
    user_data = verify_token(token)
    if not user_data:
        return {"error": "Token inválido"}
    
    email = user_data["email"]
    if not users_db[email]["is_admin"]:
        return {"error": "Solo administradores pueden ver esta información"}
    
    return {"attendance": attendance_db}

@app.get("/")
def read_root():
    return {"message": "Sistema de Asistencia Pediátrica API", "status": "activo"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
