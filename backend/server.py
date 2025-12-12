from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime
from enum import Enum
import camera
import psutil
import random
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, Boolean, DateTime, CheckConstraint

# Setup
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# SQLite Database Setup (Edge / Local)
DATABASE_URL = "sqlite+aiosqlite:///./thermo_vision.db"

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

# Database Models (SQLAlchemy)
class AlertDB(Base):
    __tablename__ = "alerts"
    id = Column(String, primary_key=True, index=True)
    type = Column(String)  # error, warning, info, success
    title = Column(String)
    message = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    acknowledged = Column(Boolean, default=False)

class StatusCheckDB(Base):
    __tablename__ = "status_checks"
    id = Column(String, primary_key=True, index=True)
    client_name = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Pydantic Schemas (API)
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

# App & Router
app = FastAPI()
api_router = APIRouter(prefix="/api")

# Dependency
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Startup Event: Create Tables
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Endpoints

# Include Router (MUST be before static catch-all)
app.include_router(api_router)

# Static Files (Frontend)
# Serve 'dist' folder at root. 
# Make sure to run 'npm run build' first!
if os.path.exists("../dist"):
    app.mount("/assets", StaticFiles(directory="../dist/assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # API routes are handled by api_router above (because it was included first? No, we need to be careful)
        # Actually, FastAPI matches in order. We should mount API first.
        # But @app.get catch-all will catch API if not careful.
        # Better strategy: Mount assets, serve index.html for root, and let API router handle /api
        
        # Check if file exists in dist
        file_path = Path("../dist") / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        
        # Fallback to index.html for SPA routing
        return FileResponse("../dist/index.html")
else:
    @api_router.get("/")
    async def root():
        return {"message": "Hello to RESOFLY (Dev Mode)"}

# Status Endpoints
@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate, db: AsyncSession = Depends(get_db)):
    new_status = StatusCheckDB(
        id=str(uuid.uuid4()),
        client_name=input.client_name,
        timestamp=datetime.utcnow()
    )
    db.add(new_status)
    await db.commit()
    await db.refresh(new_status)
    return new_status

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    result = await db.execute(select(StatusCheckDB).limit(100))
    return result.scalars().all()

# Alert Endpoints

@api_router.get("/alerts", response_model=List[Alert])
async def get_alerts(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    result = await db.execute(select(AlertDB).order_by(AlertDB.timestamp.desc()).limit(50))
    return result.scalars().all()

@api_router.post("/alerts", response_model=Alert)
async def create_alert(input: AlertCreate, db: AsyncSession = Depends(get_db)):
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
async def acknowledge_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    result = await db.execute(select(AlertDB).where(AlertDB.id == alert_id))
    alert = result.scalar_one_or_none()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.acknowledged = True
    await db.commit()
    await db.refresh(alert)
    return alert

@api_router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    result = await db.execute(select(AlertDB).where(AlertDB.id == alert_id))
    alert = result.scalar_one_or_none()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    await db.delete(alert)
    await db.commit()
    await db.delete(alert)
    await db.commit()
    return {"message": "Alert deleted"}

# Stream Endpoints

async def gen_frames():
    """Video streaming generator function."""
    cam = camera.get_camera()
    while True:
        frame = await cam.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@api_router.get("/stream/thermal")
async def video_feed():
    """Video streaming route. Put this in the src of an img tag."""
    return StreamingResponse(gen_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

# GPS & Status Endpoints

@api_router.get("/gps", response_model=GPSData)
async def get_gps():
    # Mock GPS data (Simulating movement around New York)
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
async def get_system_status():
    cpu = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    boot_time = psutil.boot_time()
    uptime = datetime.now().timestamp() - boot_time
    
    # Mock temperature on Mac (simulating Pi temp)
    # On real Pi: with open('/sys/class/thermal/thermal_zone0/temp') as f: ...
    temp = 42.0 + random.uniform(-1, 2)
    
    return SystemStatus(
        cpu_usage=cpu,
        memory_usage=memory,
        disk_usage=disk,
        temperature=temp,
        uptime=uptime
    )

# Include Router
# Router was included above

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
