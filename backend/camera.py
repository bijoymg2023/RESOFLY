import cv2
import numpy as np
import time
import asyncio
import threading
import aiohttp
from abc import ABC, abstractmethod

class BaseCamera(ABC):
    @abstractmethod
    async def get_frame(self):
        """Returns a jpeg encoded frame bytes"""
        pass

class MockCamera(BaseCamera):
    """
    Simulated Thermal Camera that generates a moving heatmap.
    """
    def __init__(self):
        self.width = 320
        self.height = 240
        self.x, self.y = 80, 60
        self.dx, self.dy = 2, 2

    async def get_frame(self):
        frame = np.random.randint(20, 40, (self.height, self.width), dtype=np.uint8)
        self.x += self.dx
        self.y += self.dy
        if self.x <= 10 or self.x >= self.width-10: self.dx *= -1
        if self.y <= 10 or self.y >= self.height-10: self.dy *= -1
        cv2.circle(frame, (self.x, self.y), 25, (255), -1)
        cv2.putText(frame, "NO SIGNAL - MOCK DATA", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255), 2)
        frame = cv2.GaussianBlur(frame, (35, 35), 0)
        heatmap = cv2.applyColorMap(frame, cv2.COLORMAP_INFERNO)
        await asyncio.sleep(0.05) 
        ret, jpeg = cv2.imencode('.jpg', heatmap)
        return jpeg.tobytes()

class StreamProxyCamera(BaseCamera):
    """
    Proxies the MJPEG stream from the external C++ driver running on localhost:8080.
    Uses a background thread to prevent blocking the main asyncio loop.
    """
    def __init__(self, url="http://127.0.0.1:8080/mjpeg"):
        self.url = url
        self.lock = asyncio.Lock()
        self.frame = None
        self.running = True
        self.cap = None
        
        # Start background poller
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()
        print(f"Initializing Proxy Camera to: {self.url}")

    def _update_loop(self):
        """Runs in a separate thread to continuously fetch frames."""
        print(f"Proxy Thread Started. Target: {self.url}")
        
        while self.running:
            try:
                # 1. Connect if not connected
                if self.cap is None or not self.cap.isOpened():
                    # print(f"Connecting to {self.url}...")
                    self.cap = cv2.VideoCapture(self.url)
                    
                    # Some backends need a warm-up read to know if they are truly open
                    if self.cap.isOpened():
                         print(f"Connected to Camera: {self.url}")
                    else:
                         # Failed to open
                         # print(f"Failed to connect to {self.url}")
                         self.cap = None
                         time.sleep(2)
                         continue
                
                # 2. Read Frame
                success, frame = self.cap.read()
                
                if success:
                    # Encode to JPEG immediately
                    ret, jpeg = cv2.imencode('.jpg', frame)
                    if ret:
                        self.frame = jpeg.tobytes()
                    # Small sleep to prevent tight loop if camera fps is high? 
                    # Actually, read() blocks until frame arrives, so sleep isn't strictly needed 
                    # unless read() is non-blocking (rare).
                    # time.sleep(0.01) 
                else:
                    print("Stream closed or empty frame. Reconnecting...")
                    self.cap.release()
                    self.cap = None
                    time.sleep(1)
                    
            except Exception as e:
                print(f"Camera Thread Crash: {e}")
                if self.cap:
                    self.cap.release()
                    self.cap = None
                time.sleep(2)
                
    async def get_frame(self):
        # Return latest frame if available, else fetch from mock
        if self.frame:
            return self.frame
        
        # If no frame yet (starting up or error), return mock
        # We create a temporary mock just for a fallback frame
        return await MockCamera().get_frame()

    def __del__(self):
        self.running = False
        if self.cap:
            self.cap.release()

# Global Singleton
thermal_instance = None 

def get_camera(type='thermal'):
    global thermal_instance
    
    if thermal_instance is None:
        # We attempt to use the Proxy Camera (Connecting to the C++ App)
        thermal_instance = StreamProxyCamera()
             
    return thermal_instance
