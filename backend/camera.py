import cv2
import numpy as np
import time
import asyncio
import threading
import requests
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
        # Create a blank frame for fallback
        return b''

class StreamProxyCamera(BaseCamera):
    """
    Proxies the MJPEG stream from the external C++ driver running on localhost:8080.
    Uses a background thread to prevent blocking the main asyncio loop.
    OPTIMIZED FOR LOW LATENCY.
    """
    def __init__(self, url="http://127.0.0.1:8080/mjpeg"):
        self.url = url
        self.frame = None
        self.last_frame_time = 0
        self.running = True
        self.cap = None
        
        # Start background poller
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()
        print(f"Initializing Proxy Camera to: {self.url}")

    def _update_loop(self):
        """Runs in a separate thread to continuously fetch frames using requests (Lower Latency)."""
        print(f"Proxy Thread Started. Target: {self.url}")
        
        while self.running:
            try:
                # Open the stream with timeout
                with requests.get(self.url, stream=True, timeout=5) as stream:
                    if stream.status_code != 200:
                        print(f"Stream returned status: {stream.status_code}")
                        time.sleep(1)
                        continue

                    print(f"Connected to Camera: {self.url}")
                    bytes_data = bytes()
                    
                    # Iterate over chunks with larger buffer for speed
                    # 16KB chunks reduce loop overhead
                    for chunk in stream.iter_content(chunk_size=16384):
                        if not self.running: break
                        bytes_data += chunk
                        
                        # Find JPEG End Marker (0xFFD9)
                        b = bytes_data.find(b'\xff\xd9')
                        
                        if b != -1:
                            # Search backwards for Start Marker (0xFFD8) before End Marker
                            a = bytes_data.rfind(b'\xff\xd8', 0, b)
                            
                            if a != -1:
                                # Found a complete frame
                                jpg = bytes_data[a:b+2]
                                
                                # Update current frame
                                self.frame = jpg
                                self.last_frame_time = time.time()
                                
                                # CRITICAL FOR LATENCY:
                                # Drop the entire buffer after finding a frame.
                                # We don't care about old frames. We only want the LATEST.
                                bytes_data = bytes()
                            else:
                                # Start marker not found, clear buffer if too big to prevent memory leak
                                if len(bytes_data) > 100000:
                                    bytes_data = bytes()
                        
                        # Safety buffer limit
                        if len(bytes_data) > 200000:
                            bytes_data = bytes()

            except Exception as e:
                # print(f"Stream Read Error: {e}")
                time.sleep(1)
                
    async def get_frame(self):
        # Return latest frame if available AND recent (<2.0s old)
        if self.frame and (time.time() - self.last_frame_time < 2.0):
            return self.frame
        
        # If frame is stale or missing, return empty or mock
        return None

    def __del__(self):
        self.running = False

# Global Singleton
thermal_instance = None 

def get_camera(type='thermal'):
    global thermal_instance
    
    if thermal_instance is None:
        # We attempt to use the Proxy Camera (Connecting to the C++ App)
        thermal_instance = StreamProxyCamera()
             
    return thermal_instance
