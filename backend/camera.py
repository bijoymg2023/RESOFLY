import cv2
import numpy as np
import time
import asyncio
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
        frame = cv2.GaussianBlur(frame, (35, 35), 0)
        heatmap = cv2.applyColorMap(frame, cv2.COLORMAP_INFERNO)
        await asyncio.sleep(0.05) 
        ret, jpeg = cv2.imencode('.jpg', heatmap)
        return jpeg.tobytes()

class StreamProxyCamera(BaseCamera):
    """
    Proxies the MJPEG stream from the external C++ driver running on localhost:8080.
    """
    def __init__(self, url="http://localhost:8080/mjpeg"):
        self.url = url
        self.session = None
        self.stream_response = None
        print(f"Initializing Proxy Camera to: {self.url}")

    async def get_frame(self):
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # Since MJPEG is a continuous stream, we can't just "get one frame" via a library easily in one-shot
            # However, for the purpose of this architecture where 'gen_frames' calls this repeatedly, 
            # we actually want to maintain a connection.
            # BUT, the current architecture of 'server.py' calls 'get_frame()' in a loop.
            # To properly proxy, we should probably read the MJPEG stream continuously in a background task
            # and update a 'latest_frame' buffer.
            
            # Simple fallback for now: Just capture from URL using OpenCV (it handles streams natively)
            # Fetching via HTTP in python loop is slow. Let's use cv2.VideoCapture with the URL.
            return await self._get_frame_cv2()

        except Exception as e:
            print(f"Proxy Error: {e}")
            return await MockCamera().get_frame() # Fallback to mock if C++ app not running

    async def _get_frame_cv2(self):
        # We need a persistent capture object, otherwise we reconnect every frame (too slow)
        if not hasattr(self, 'cap') or self.cap is None or not self.cap.isOpened():
             print("Opening connection to C++ Stream...")
             self.cap = cv2.VideoCapture(self.url)
        
        if self.cap.isOpened():
            success, frame = self.cap.read()
            if success:
                ret, jpeg = cv2.imencode('.jpg', frame)
                return jpeg.tobytes()
        
        # If we failed
        self.cap = None 
        return await MockCamera().get_frame()

# Global Singleton
thermal_instance = None 

def get_camera(type='thermal'):
    global thermal_instance
    
    if thermal_instance is None:
        # We attempt to use the Proxy Camera (Connecting to the C++ App)
        # If the C++ App isn't running, it will automatically fall back to Mock inside the class.
        print("Using StreamProxyCamera -> localhost:8080")
        thermal_instance = StreamProxyCamera()
             
    return thermal_instance
