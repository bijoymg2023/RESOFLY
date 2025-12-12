from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timedelta
from enum import Enum
import camera
import psutil
import random
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, Boolean, DateTime, CheckConstraint, select

# Setup
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Security Config
SECRET_KEY = os.environ.get("SECRET_KEY", "resofly_secret_key_12345")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 Days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")

# Database Setup
DATABASE_URL = "sqlite+aiosqlite:///./thermo_vision.db"
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

# --------------------------
# Models & Schemas
# --------------------------

# Database Models
class UserDB(Base):
    __tablename__ = "users"
    username = Column(String, primary_key=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)

class AlertDB(Base):
    __tablename__ = "alerts"
    id = Column(String, primary_key=True, index=True)
    type = Column(String)
    title = Column(String)
    message = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    acknowledged = Column(Boolean, default=False)

class StatusCheckDB(Base):
    __tablename__ = "status_checks"
    id = Column(String, primary_key=True, index=True)
    client_name = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Pydantic Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    username: str
    is_active: bool

class AlertType(str, Enum):
    error = 'error'
    warning = 'warning'
    info = 'info'
    success = 'success'

class AlertBase(BaseModel):
    type: AlertType
    title: str
    message: str

class AlertCreate(AlertBase):
    pass

class Alert(AlertBase):
    id: str
    timestamp: datetime
    acknowledged: bool
    class Config:
        from_attributes = True

class StatusCheckCreate(BaseModel):
    client_name: str

class StatusCheck(BaseModel):
    id: str
    client_name: str
    timestamp: datetime
    class Config:
        from_attributes = True

class GPSData(BaseModel):
    latitude: float
    longitude: float
    altitude: float
    accuracy: float
    speed: float = 0.0
    heading: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SystemStatus(BaseModel):
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    temperature: float
    uptime: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# --------------------------
# Auth Utils & Dependencies
# --------------------------

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(select(UserDB).where(UserDB.username == username))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    return user

# --------------------------
# API Routes
# --------------------------
api_router = APIRouter(prefix="/api")

# 1. Auth / Public Routes
@api_router.get("/")
async def root():
    return {"message": "Hello to RESOFLY (API)"}

@api_router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserDB).where(UserDB.username == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@api_router.get("/users/me", response_model=User)
async def read_users_me(current_user: UserDB = Depends(get_current_user)):
    return User(username=current_user.username, is_active=current_user.is_active)

# 2. Protected Routes (Require Login)

@api_router.get("/alerts", response_model=List[Alert])
async def get_alerts(db: AsyncSession = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    result = await db.execute(select(AlertDB).order_by(AlertDB.timestamp.desc()).limit(50))
    return result.scalars().all()

@api_router.post("/alerts", response_model=Alert)
async def create_alert(input: AlertCreate, db: AsyncSession = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    new_alert = AlertDB(
        id=str(uuid.uuid4()),
        type=input.type,
        title=input.title,
        message=input.message,
        timestamp=datetime.utcnow(),
        acknowledged=False
    )
    db.add(new_alert)
    await db.commit()
    await db.refresh(new_alert)
    return new_alert

@api_router.patch("/alerts/{alert_id}/acknowledge", response_model=Alert)
async def acknowledge_alert(alert_id: str, db: AsyncSession = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    result = await db.execute(select(AlertDB).where(AlertDB.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.acknowledged = True
    await db.commit()
    await db.refresh(alert)
    return alert

@api_router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str, db: AsyncSession = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    result = await db.execute(select(AlertDB).where(AlertDB.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.delete(alert)
    await db.commit()
    return {"message": "Alert deleted"}

@api_router.get("/gps", response_model=GPSData)
async def get_gps(current_user: UserDB = Depends(get_current_user)):
    # Mock GPS data
    base_lat = 40.7128
    base_lng = -74.0060
    jitter = 0.0005
    return GPSData(
        latitude=base_lat + random.uniform(-jitter, jitter),
        longitude=base_lng + random.uniform(-jitter, jitter),
        altitude=50.0 + random.uniform(-1, 1),
        accuracy=random.uniform(2.0, 5.0),
        speed=random.uniform(0, 10),
        heading=random.uniform(0, 360)
    )

@api_router.get("/system-status", response_model=SystemStatus)
async def get_system_status(current_user: UserDB = Depends(get_current_user)):
    cpu = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    boot_time = psutil.boot_time()
    uptime = datetime.now().timestamp() - boot_time
    temp = 42.0 + random.uniform(-1, 2)
    return SystemStatus(
        cpu_usage=cpu, memory_usage=memory, disk_usage=disk, temperature=temp, uptime=uptime
    )

# Status Check (Keep public? Or Protected? Let's protect to be safe)
@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate, db: AsyncSession = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    new_status = StatusCheckDB(
        id=str(uuid.uuid4()), client_name=input.client_name, timestamp=datetime.utcnow()
    )
    db.add(new_status)
    await db.commit()
    await db.refresh(new_status)
    return new_status

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks(db: AsyncSession = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    result = await db.execute(select(StatusCheckDB).limit(100))
    return result.scalars().all()

# Stream (Authentication via Query Param or Cookie for img tags)
async def gen_frames():
    cam = camera.get_camera()
    while True:
        frame = await cam.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@api_router.get("/stream/thermal")
async def video_feed(token: Optional[str] = None):
    # For now, allowing public access or verify token if present
    # To enforce strict auth for stream, uncomment below:
    # if not token: raise HTTPException(401)
    # user = await get_current_user(token, ...)
    return StreamingResponse(gen_frames(), media_type="multipart/x-mixed-replace; boundary=frame")


# --------------------------
# App Application
# --------------------------
app = FastAPI(title="RESOFLY API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create Default Admin
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(UserDB).where(UserDB.username == "admin"))
        user = result.scalar_one_or_none()
        if not user:
            print("Creating default admin user...")
            hashed_pwd = get_password_hash("resofly123")
            admin_user = UserDB(username="admin", hashed_password=hashed_pwd)
            db.add(admin_user)
            await db.commit()

# Include API Router
app.include_router(api_router)

# Static Files & SPA Fallback
if os.path.exists("../dist"):
    app.mount("/assets", StaticFiles(directory="../dist/assets"), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = Path("../dist") / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse("../dist/index.html")
