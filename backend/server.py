from fastapi import FastAPI, APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
import asyncio
import time
import glob
import cv2
import numpy as np
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Set
import uuid
from datetime import datetime, timedelta
from enum import Enum
import camera
import psutil
import random
import bluetooth_scanner
import wifi_scanner
import gps_real
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, Boolean, DateTime, CheckConstraint, select, Float, Integer, text
import thermal_pipeline
from datetime import datetime, timedelta, timezone
import json
import wifi_gps

# IST Timezone (UTC + 5:30)
IST_OFFSET = timezone(timedelta(hours=5, minutes=30))

def get_ist_time():
    return datetime.now(IST_OFFSET)
# Global Signal Cache (Zero-Lag)
signal_cache = []
signal_cache_lock = None # Initialized in startup()

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
    timestamp = Column(DateTime, default=get_ist_time)
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
    timestamp = Column(DateTime, default=get_ist_time)

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
    life = 'life'
    LIFE = 'LIFE'

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
    source: str = "none"

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
    return {"status": "success"}

@api_router.delete("/alerts")
async def delete_all_alerts(db: AsyncSession = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    """Clear all alerts from the database."""
    print(f"[DEBUG] DELETE /alerts called by {current_user.username}", flush=True)
    try:
        await db.execute(text("DELETE FROM alerts"))
        await db.commit()
        print("[DEBUG] Alerts table cleared successfully", flush=True)
        return {"status": "success", "message": "All alerts cleared"}
    except Exception as e:
        print(f"[ERROR] Failed to clear alerts: {e}", flush=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/thermal/status")
async def thermal_camera_status():
    """
    Get thermal camera status.
    Returns camera availability and source type.
    """
    try:
        from thermal_engine import WaveshareThermalSource, VideoDatasetSource
        
        # Check Waveshare hardware
        waveshare = WaveshareThermalSource()
        if waveshare.available:
            return {
                "available": True,
                "source": "waveshare_80x62",
                "resolution": "80x62",
                "mode": "live"
            }
        
        # Check dataset fallback
        dataset_path = Path(__file__).parent.parent / "dataset" / "test2.mp4"
        if dataset_path.exists():
            return {
                "available": True,
                "source": "dataset",
                "file": str(dataset_path.name),
                "path": str(dataset_path),
                "mode": "offline"
            }
        
        return {
            "available": False,
            "source": None,
            "mode": None,
            "dataset_path_checked": str(dataset_path)
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e)
        }

@api_router.get("/system/diagnostics")
async def get_system_diagnostics(token: str = Depends(oauth2_scheme)):
    """Get CPU, RAM, Temp."""
    try:
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        
        # Temp (Pi specific)
        temp = 0.0
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp = float(f.read()) / 1000.0
        except:
             # Mock temp for dev
             temp = random.uniform(40.0, 60.0)

        # Uptime
        uptime = time.time() - psutil.boot_time()

        return {
            "cpu_usage": cpu,
            "memory_usage": ram,
            "temperature": temp,
            "uptime": uptime,
            "disk_usage": psutil.disk_usage('/').percent
        }
    except Exception as e:
        logger.error(f"Diagnostics Error: {e}")
        return {"error": str(e)}

@api_router.get("/scan/bluetooth")
async def scan_bluetooth(token: str = Depends(oauth2_scheme)):
    """Returns cached signal data instantly."""
    async with signal_cache_lock:
        return signal_cache

@api_router.post("/thermal/test-alert")
async def create_test_alert(db: AsyncSession = Depends(get_db)):
    """
    Debug endpoint: Creates a test LIFE detection alert.
    Use this to verify the alert system works independently of detection.
    """
    import random
    
    try:
        test_alert = AlertDB(
            id=str(uuid.uuid4()),
            type='life',
            title='TEST LIFE DETECTED',
            message='Test thermal signature (Debug endpoint)',
            timestamp=datetime.utcnow(),
            acknowledged=False,
            lat=12.9716 + random.uniform(-0.01, 0.01),
            lon=77.5946 + random.uniform(-0.01, 0.01),
            confidence=0.85,
            max_temp=180.0
        )
        db.add(test_alert)
        await db.commit()
        
        return {
            "success": True,
            "alert_id": test_alert.id,
            "message": "Test alert created successfully"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }



import gps_real

class UnifiedGPSReader:
    def __init__(self, hardware_reader, wifi_gps_module):
        self.hardware = hardware_reader
        self.wifi = wifi_gps_module
    
    def start(self):
        if self.hardware:
            self.hardware.start()
            
    def get_data(self):
        # 1. Try Hardware GPS first
        if self.hardware:
            hw_data = self.hardware.get_data()
            if hw_data.get("latitude") and hw_data["latitude"] != 0.0:
                hw_data["source"] = "hardware"
                return hw_data
        
        # 2. Fallback to Wi-Fi Geolocation
        if self.wifi:
            wifi_data = self.wifi.get_location()
            if wifi_data.get("latitude") and wifi_data["latitude"] != 0.0:
                wifi_data["source"] = "network"
                return wifi_data
                
        # 3. Last Resort
        return {
            "latitude": 0.0, "longitude": 0.0, "altitude": 0.0,
            "accuracy": 0.0, "speed": 0.0, "heading": 0.0,
            "timestamp": datetime.utcnow(), "source": "none"
        }

# Initialize real GPS reader (Adjust port if using UART vs USB)
# Common ports: /dev/ttyUSB0, /dev/ttyACM0, /dev/serial0
# Initialize GPS infrastructure
hw_gps = None
possible_gps_ports = ['/dev/ttyUSB0', '/dev/ttyACM0', '/dev/ttyAMA0', '/dev/serial0']

for port in possible_gps_ports:
    try:
        if os.path.exists(port):
            print(f"Attempting GPS on {port}...")
            hw_gps = gps_real.GPSReader(port=port) 
            # hw_gps.start() - Handled by manager
            print(f"GPS Hardware detected on {port}")
            break
    except Exception as e:
        print(f"Warning: GPS Probe Failed on {port}: {e}")

# Create Unified GPS Manager
gps_reader = UnifiedGPSReader(
    hardware_reader=hw_gps,
    wifi_gps_module=wifi_gps.WifiGPS()
)
gps_reader.start()

if not hw_gps:
    print("Warning: No GPS hardware found. Using Network GPS fallback.")
else:
    print("GPS Hardware detected and initialized.")

@api_router.get("/gps", response_model=GPSData)
async def get_gps(current_user: UserDB = Depends(get_current_user)):
    data = gps_reader.get_data()
    # Ensure timestamp is datetime
    if isinstance(data.get("timestamp"), str):
        try:
            from dateutil.parser import parse
            data["timestamp"] = parse(data["timestamp"])
        except:
            data["timestamp"] = datetime.utcnow()
            
    return GPSData(**data)

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
        id=str(uuid.uuid4()), client_name=input.client_name, timestamp=get_ist_time()
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
            "X-Accel-Buffering": "no"
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

# --------------------------
# WebSocket Connection Manager
# --------------------------
class WebSocketConnectionManager:
    """Manages WebSocket connections for real-time alert broadcasting."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"[WS] Client connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        print(f"[WS] Client disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, data: dict):
        """Send message to all connected clients."""
        if not self.active_connections:
            return
        
        message = json.dumps(data)
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.add(connection)
        
        # Clean up disconnected
        for conn in disconnected:
            self.active_connections.discard(conn)

ws_manager = WebSocketConnectionManager()

# Global thermal pipeline (initialized in startup)
thermal_frame_pipeline = None

# --------------------------
# WebSocket Endpoint
# --------------------------
@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """Real-time alert stream via WebSocket."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, wait for client messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

# --------------------------
# Synchronized Thermal Stream
# --------------------------
@app.get("/thermal/")
async def thermal_stream():
    """
    MJPEG stream with synchronized detection.
    Each frame is processed for detection before being streamed.
    Alerts are generated at the exact moment signatures are visible.
    """
    if thermal_frame_pipeline is None:
        # Return placeholder if no pipeline
        async def placeholder():
            yield b'--frame\r\nContent-Type: text/plain\r\n\r\nNo thermal source available\r\n'
        return StreamingResponse(placeholder(), media_type="multipart/x-mixed-replace; boundary=frame")
    
    # Pre-generate a "no signal" placeholder frame
    no_signal = np.zeros((496, 640, 3), dtype=np.uint8)
    cv2.putText(no_signal, "THERMAL", (180, 220), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (0, 180, 255), 3)
    cv2.putText(no_signal, "Waiting for sensor data...", (140, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 100, 100), 1)
    _, no_signal_jpeg = cv2.imencode('.jpg', no_signal, [cv2.IMWRITE_JPEG_QUALITY, 70])
    no_signal_bytes = no_signal_jpeg.tobytes()
    
    async def generate():
        loop = asyncio.get_running_loop()
        while True:
            # Move heavy CV2/detection logic to a background thread
            # This prevents the thermal processing from "freezing" the rest of the app
            frame = await loop.run_in_executor(None, thermal_frame_pipeline.process_next)
            
            if frame is not None:
                _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                frame_bytes = jpeg.tobytes()
            else:
                # Send placeholder so browser doesn't show blank
                frame_bytes = no_signal_bytes
            
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' +
                frame_bytes +
                b'\r\n'
            )
            
            # Match sensor rate (Waveshare is ~5-6 FPS)
            # Polling faster just wastes CPU.
            await asyncio.sleep(0.2)
    
    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# Startup
@app.on_event("startup")
async def startup():
    global signal_cache_lock
    signal_cache_lock = asyncio.Lock()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 1. Create or Update Default Admin (separate try block)
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
            
            await db.commit()
            print("Admin user ready", flush=True)
    except Exception as e:
        print(f"Warning: Could not setup admin user: {e}", flush=True)
    
    # 2. Log System Startup (separate try block, optional)
    try:
        async with AsyncSessionLocal() as db:
            startup_alert = AlertDB(
                id=str(uuid.uuid4()),
                type='info',
                title='System Online',
                message='ResoFly Backend started successfully.',
                timestamp=get_ist_time(),
                acknowledged=False,
                lat=0.0,
                lon=0.0,
                confidence=1.0,
                max_temp=0.0
            )
            db.add(startup_alert)
            await db.commit()
            print("Startup alert logged", flush=True)
    except Exception as e:
        print(f"Warning: Could not log startup alert: {e}", flush=True)
            
    # 3. Initialize Synchronized Thermal Pipeline
    # Priority: Live Waveshare HAT > Dataset video fallback
    source = None
    
    # Try Waveshare Thermal HAT first
    try:
        waveshare_source = thermal_pipeline.WaveshareSource()
        if waveshare_source.is_available():
            source = waveshare_source
            print("[THERMAL] ✓ Waveshare 80x62 Thermal HAT detected — using LIVE feed", flush=True)
        else:
            print("[THERMAL] Waveshare HAT not available, checking dataset fallback...", flush=True)
    except Exception as e:
        import traceback
        print(f"[THERMAL] Waveshare init error: {e}", flush=True)
        traceback.print_exc()
    
    # Fallback to dataset video
    if source is None:
        dataset_video = Path(__file__).parent.parent / "dataset" / "test2.mp4"
        print(f"[THERMAL] Looking for dataset at: {dataset_video}", flush=True)
        print(f"[THERMAL] Dataset exists: {dataset_video.exists()}", flush=True)
        if dataset_video.exists():
            source = thermal_pipeline.VideoSource(str(dataset_video))
            print("[THERMAL] Using dataset video as thermal source", flush=True)
    
    if source is not None:
        
        # Capture the main event loop for thread-safe scheduling
        main_loop = asyncio.get_running_loop()

        # Detection callback - creates alerts and broadcasts via WebSocket
        def on_detection_event(event: thermal_pipeline.DetectionEvent):
            print(f"[DEBUG] on_detection_event CALLED! Frame: {event.frame_number}, Hotspots: {len(event.hotspots)}", flush=True)
            """Handle detection event - save to DB and broadcast."""
            # Get GPS (Default to 0.0 if no lock)
            lat = 0.0
            lon = 0.0
            
            if gps_reader:
                gps_data = gps_reader.get_data()
                # Check if we have a valid fix (non-zero)
                if gps_data.get('latitude') and gps_data.get('latitude') != 0.0:
                    lat, lon = gps_data['latitude'], gps_data['longitude']
            
            # Create alert in database - schedule on the running event loop SAFELY
            async def save_and_broadcast():
                try:
                    async with AsyncSessionLocal() as db:
                        for hotspot in event.hotspots:
                            # Use track_id if available, else standard index
                            obj_id = hotspot.track_id if hotspot.track_id is not None else 0
                            
                            # Unique GPS offset based on ID (consistent position for same ID)
                            person_lat = lat + ((obj_id % 10) * 0.0005)
                            person_lon = lon + ((obj_id % 10) * 0.0003)
                            
                            alert_id = str(uuid.uuid4())
                            
                            alert = AlertDB(
                                id=alert_id,
                                type='LIFE',
                                title=f'PERSON #{obj_id} DETECTED',
                                message=f"New target tracked (ID: {obj_id}, {hotspot.estimated_temp:.0f}°C, {int(hotspot.confidence*100)}%)",
                                timestamp=event.timestamp,
                                acknowledged=False,
                                lat=person_lat,
                                lon=person_lon,
                                confidence=hotspot.confidence,
                                max_temp=hotspot.estimated_temp
                            )
                            db.add(alert)
                            
                            # Broadcast each alert via WebSocket
                            alert_data = {
                                "id": alert_id,
                                "type": "LIFE",
                                "title": f"PERSON #{obj_id}",
                                "confidence": hotspot.confidence,
                                "max_temp": hotspot.estimated_temp,
                                "estimated_temp": hotspot.estimated_temp,
                                "lat": person_lat,
                                "lon": person_lon,
                                "timestamp": event.timestamp.isoformat(),
                                "frame": event.frame_number,
                                "track_id": obj_id,
                                "total_count": event.total_count
                            }
                            await ws_manager.broadcast(alert_data)
                        
                        await db.commit()
                        print(f"[ALERT] Saved {len(event.hotspots)} detections to DB", flush=True)
                    
                    print(f"[THERMAL] ✓ {len(event.hotspots)} alerts sent for frame {event.frame_number}")
                except Exception as e:
                    print(f"[THERMAL] Error in save_and_broadcast: {e}")
            
            # Schedule on the main loop from the thermal thread
            try:
                if main_loop.is_running():
                    asyncio.run_coroutine_threadsafe(save_and_broadcast(), main_loop)
                else:
                     print("[ERROR] Main loop is closed, cannot save alert", flush=True)
            except Exception as e:
                 print(f"[ERROR] Could not schedule alert task: {e}", flush=True)
        
        # Create the unified pipeline
        global thermal_frame_pipeline
        thermal_frame_pipeline = thermal_pipeline.ThermalFramePipeline(
            source=source,
            on_detection=on_detection_event
        )
        print("[THERMAL] Synchronized pipeline initialized", flush=True)
    else:
        print("[THERMAL] No thermal source available (no HAT, no dataset), detection disabled", flush=True)
        thermal_frame_pipeline = None

    # 4. Start background monitor loops
    asyncio.create_task(background_monitor())
    asyncio.create_task(signal_monitor_loop())

async def signal_monitor_loop():
    """Continuous background scanning for signals (Zero-Lag Architecture)."""
    global signal_cache
    print("[SIGNAL] Background scanner initialized", flush=True)
    while True:
        try:
            loop = asyncio.get_running_loop()
            
            # Run scans in parallel
            bt_task = loop.run_in_executor(None, bluetooth_scanner.get_bluetooth_devices)
            wifi_task = loop.run_in_executor(None, wifi_scanner.get_wifi_devices)
            
            bt_devices, wifi_devices = await asyncio.gather(bt_task, wifi_task)
            
            # Prepare result
            now = datetime.now()
            for d in bt_devices: d['type'] = 'bluetooth'
            for d in wifi_devices: d['type'] = 'wifi'
            
            all_devices = bt_devices + wifi_devices
            all_devices.sort(key=lambda x: x.get('rssi', -100), reverse=True)
            
            # Atomic update of global cache
            async with signal_cache_lock:
                signal_cache = all_devices
            
            # Short sleep between scans to prevent 100% CPU on hardware bus
            # Hardware scan already takes ~8s, this just adds a breath
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"[SIGNAL] Background loop error: {e}", flush=True)
            await asyncio.sleep(5)

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
