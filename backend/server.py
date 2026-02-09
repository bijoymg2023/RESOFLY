from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
import asyncio
import glob
import cv2
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
from sqlalchemy import Column, String, Boolean, DateTime, CheckConstraint, select, Float, Integer
import thermal_engine
from datetime import datetime
import json

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

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
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
    # New Detection Fields
    lat = Column(Float, default=0.0)
    lon = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)
    max_temp = Column(Float, default=0.0)

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
    lat: float
    lon: float
    confidence: float
    max_temp: float
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
    boot_time_str: str
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

@api_router.post("/token", response_model=None)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    try:
        print(f"Attempting login for user: {form_data.username}")
        # DEBUG: Print everything
        print(f"Password provided: {form_data.password}")
        
        result = await db.execute(select(UserDB).where(UserDB.username == form_data.username))
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"User {form_data.username} not found")
            return JSONResponse(status_code=401, content={"detail": "Incorrect username or password"})
            
        print(f"User found. ID: {user.username}. Hash: {user.hashed_password}")
        
        try:
            valid = verify_password(form_data.password, user.hashed_password)
        except Exception as e:
            print(f"HASH VERIFICATION CRASHED: {e}")
            return JSONResponse(status_code=500, content={"detail": f"Hash crash: {str(e)}"})

        if not valid:
            print("Password verification failed")
            return JSONResponse(status_code=401, content={"detail": "Incorrect username or password"})
        
        print("Login successful. Generating token...")
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"detail": f"Internal Login Error: {str(e)}"})

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


import gps_real

# Initialize real GPS reader (Adjust port if using UART vs USB)
# Common ports: /dev/ttyUSB0, /dev/ttyACM0, /dev/serial0
try:
    gps_reader = gps_real.GPSReader(port='/dev/ttyUSB0') 
    gps_reader.start()
    print("GPS Module Initialized")
except Exception as e:
    print(f"Warning: GPS Init Failed: {e}")
    gps_reader = None

@api_router.get("/gps", response_model=GPSData)
async def get_gps(current_user: UserDB = Depends(get_current_user)):
    if gps_reader:
         data = gps_reader.get_data()
         # Ensure timestamp is datetime
         if isinstance(data.get("timestamp"), str):
             # basic fallback if parsing failed
             data["timestamp"] = datetime.utcnow()
         return GPSData(**data)
         
    # Fallback if no GPS hardware found (return zeros instead of mock)
    return GPSData(
        latitude=0.0, longitude=0.0, altitude=0.0, 
        accuracy=0.0, speed=0.0, heading=0.0
    )

def get_pi_temperature():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp_str = f.read()
        return float(temp_str) / 1000.0
    except:
        return 0.0

@api_router.get("/system-status", response_model=SystemStatus)
async def get_system_status(current_user: UserDB = Depends(get_current_user)):
    cpu = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    boot_time = psutil.boot_time()
    boot_dt = datetime.fromtimestamp(boot_time)
    uptime = datetime.now().timestamp() - boot_time
    temp = get_pi_temperature()
    return SystemStatus(
        cpu_usage=cpu, memory_usage=memory, disk_usage=disk, temperature=temp, uptime=uptime,
        boot_time_str=boot_dt.strftime("%Y-%m-%d %H:%M:%S")
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
# Stream (Authentication via Query Param or Cookie for img tags)
async def gen_frames(camera_type='thermal'):
    cam = camera.get_camera(camera_type)
    while True:
        frame = await cam.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')



@api_router.get("/stream/rgb")
async def video_feed_rgb(token: Optional[str] = None):
    """RGB Camera Stream from Pi Camera."""
    return StreamingResponse(
        camera.generate_rgb_stream(), 
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Prevent Cloudflare/nginx buffering
            "Transfer-Encoding": "chunked"
        }
    )

@api_router.get("/stream/rgb/frame")
async def rgb_single_frame(t: Optional[str] = None):
    """Returns a single JPEG frame from Pi Camera. Use ?t=timestamp for cache busting."""
    from fastapi.responses import Response
    
    rgb_camera = camera.get_rgb_camera()
    frame = await rgb_camera.get_frame()
    
    if frame:
        return Response(
            content=frame,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    else:
        # Return a 1x1 transparent pixel if no frame available
        return Response(
            content=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82',
            media_type="image/png",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0"
            }
        )


# --------------------------
# Snapshot / Gallery API
# --------------------------

CAPTURE_DIR = ROOT_DIR / "static" / "captures"
CAPTURE_DIR.mkdir(parents=True, exist_ok=True)

class CaptureResponse(BaseModel):
    url: str
    filename: str
    timestamp: str

@api_router.post("/capture", response_model=CaptureResponse)
async def capture_snapshot(current_user: UserDB = Depends(get_current_user)):
    """Captures a FRESH frame directly from the camera stream to ensure 0-lag."""
    try:
        # Use robust OpenCV capture from camera module
        frame_bytes = camera.capture_fresh_frame()
        
        if not frame_bytes:
            # Fallback or detail error
            raise HTTPException(status_code=503, detail="Could not capture frame from camera (Check service status)")

        filename = f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        filepath = CAPTURE_DIR / filename
        
        with open(filepath, "wb") as f:
            f.write(frame_bytes)
            
        # Clean up old images (Keep last 100)
        files = sorted(glob.glob(str(CAPTURE_DIR / "capture_*.jpg")))
        if len(files) > 100:
            for f in files[:-100]:
                os.remove(f)

        return CaptureResponse(
            url=f"/static/captures/{filename}",
            filename=filename,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Capture failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@api_router.get("/gallery", response_model=List[CaptureResponse])
async def get_gallery(current_user: UserDB = Depends(get_current_user)):
    """Returns list of captured images, sorted newest first."""
    files = sorted(glob.glob(str(CAPTURE_DIR / "capture_*.jpg")), reverse=True)
    response = []
    
    for f in files:
        filename = os.path.basename(f)
        # Extract timestamp from filename capture_YYYYMMDD_HHMMSS_micros.jpg
        # Or just use file mtime? Filename is safer if touched.
        try:
            ts_str = filename.replace("capture_", "").replace(".jpg", "")
            # Basic parsing or just return isoformat of mtime
            timestamp = datetime.fromtimestamp(os.path.getmtime(f)).isoformat()
        except:
            timestamp = ""
            
        response.append(CaptureResponse(
            url=f"/static/captures/{filename}",
            filename=filename,
            timestamp=timestamp
        ))
    return response


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
    
    # Create or Update Default Admin
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(UserDB).where(UserDB.username == "admin"))
            user = result.scalar_one_or_none()
            
            hashed_pwd = get_password_hash("resofly123")
            
            if not user:
                print("Creating default admin user...")
                admin_user = UserDB(username="admin", hashed_password=hashed_pwd)
                db.add(admin_user)
            else:
                user.hashed_password = hashed_pwd
            
            # 1. Log System Startup
            startup_alert = AlertDB(
                id=str(uuid.uuid4()),
                type='info',
                title='System Online',
                message='ResoFly Backend started successfully.',
                timestamp=datetime.utcnow()
            )
            db.add(startup_alert)
                
            await db.commit()
            
        # 3. Start Thermal Detection Engine
        dataset_video = Path(__file__).parent.parent / "dataset" / "test2.mp4"
        
        async def on_thermal_detection(detections, metadata):
            """Callback for detected thermal hotspots"""
            # Capture current GPS if available
            lat, lon = 0.0, 0.0
            if gps_reader:
                gps_data = gps_reader.get_data()
                lat, lon = gps_data.get('latitude', 0.0), gps_data.get('longitude', 0.0)
            
            async with AsyncSessionLocal() as db:
                for det in detections:
                    # Simple Deduplication: Don't add if a similar 'active' alert exists within 30s
                    # We check for the same type (LIFE/FIRE)
                    thirty_seconds_ago = datetime.utcnow() - timedelta(seconds=30)
                    stmt = select(AlertDB).where(
                        (AlertDB.type == det['type'].lower()) & 
                        (AlertDB.timestamp > thirty_seconds_ago) & 
                        (AlertDB.acknowledged == False)
                    )
                    recent = await db.execute(stmt)
                    if recent.scalar_one_or_none():
                        continue

                    # Create New Alert
                    conf_pct = int(det['confidence'] * 100)
                    msg = f"Thermal Signature Detected (Confidence: {conf_pct}%, Intensity: {int(det['max_intensity'])})"
                    if metadata['count'] > 1:
                        msg += f" - Target Count: {metadata['count']}"
                    
                    new_alert = AlertDB(
                        id=str(uuid.uuid4()),
                        type=det['type'].lower(), # 'life' or 'fire'
                        title=f"{det['type']} DETECTED",
                        message=msg,
                        timestamp=datetime.utcnow(),
                        acknowledged=False,
                        lat=lat,
                        lon=lon,
                        confidence=det['confidence'],
                        max_temp=det['max_intensity'] # Using intensity as proxy for temp in normalized view
                    )
                    db.add(new_alert)
                    logger.info(f"Generated REAL Thermal Alert: {det['type']} at {lat}, {lon}")
                
                await db.commit()

        # Create wrapper for async callback
        def sync_callback(detections, metadata):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(on_thermal_detection(detections, metadata))
            loop.close()

        # In a real async environment, we'd use a queue, but for Pi/FastAPI sync_callback to bridge is fine
        detection_service = thermal_engine.ThermalDetectionService(
            callback=sync_callback, 
            dataset_path=dataset_video if dataset_video.exists() else None
        )
        detection_service.start()
            
    except Exception as e:
        print(f"CRITICAL STARTUP ERROR: Could not create/update admin user. {e}")
        import traceback
        traceback.print_exc()

async def background_monitor():
    """Periodically checks system health and logs alerts."""
    while True:
        try:
            # Check every 60 seconds
            await asyncio.sleep(60) 
            
            cpu = psutil.cpu_percent(interval=None)
            disk = psutil.disk_usage('/').percent
            temp = get_pi_temperature()
            
            alerts_to_add = []
            
            if cpu > 90:
                alerts_to_add.append(("error", "High CPU Usage", f"CPU is critically high at {cpu}%"))
            elif cpu > 75:
                alerts_to_add.append(("warning", "Elevated CPU", f"CPU usage is high at {cpu}%"))
                
            if temp > 80:
                alerts_to_add.append(("error", "Overheating", f"Core temperature is {temp}°C"))
            elif temp > 70:
                alerts_to_add.append(("warning", "High Temperature", f"Core temperature is {temp}°C"))
                
            if disk > 95:
                alerts_to_add.append(("error", "Disk Full", f"Storage is {disk}% full"))
            
            if alerts_to_add:
                async with AsyncSessionLocal() as db:
                    for type_, title, msg in alerts_to_add:
                        # Check duplicate logic could go here to prevent spamming
                        new_alert = AlertDB(
                            id=str(uuid.uuid4()),
                            type=type_,
                            title=title,
                            message=msg,
                            timestamp=datetime.utcnow()
                        )
                        db.add(new_alert)
                    await db.commit()
                    
        except Exception as e:
            print(f"Monitor Loop Error: {e}")
            await asyncio.sleep(60)

# Include API Router
app.include_router(api_router)

# Static Files & SPA Fallback
if os.path.exists("../dist"):
    app.mount("/assets", StaticFiles(directory="../dist/assets"), name="assets")
    
    # Mount Dataset Videos
    if os.path.exists("../dataset"):
        app.mount("/dataset", StaticFiles(directory="../dataset"), name="dataset")
    
    # Mount Static Captures
    app.mount("/static", StaticFiles(directory=str(ROOT_DIR / "static")), name="static")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = Path("../dist") / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse("../dist/index.html")

if __name__ == "__main__":
    import uvicorn
    # Use 0.0.0.0 to listen on all interfaces
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
