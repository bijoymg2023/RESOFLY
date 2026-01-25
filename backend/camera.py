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
        self.last_frame_time = 0
        self.running = True
        self.cap = None
        
        # Start background poller
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()
        print(f"Initializing Proxy Camera to: {self.url}")

    def _update_loop(self):
        """Runs in a separate thread to continuously fetch frames using requests (Lower Latency)."""
        import requests
        print(f"Proxy Thread Started. Target: {self.url}")
        
        while self.running:
            try:
                # Open the stream with a longer timeout for initial connection
                stream = requests.get(self.url, stream=True, timeout=10)
                if stream.status_code == 200:
                    print(f"Connected to Camera: {self.url}")
                    bytes_data = bytes()
                    last_frame_received = time.time()
                    
                    # Iterate over chunks
                # Iterate over chunks with larger buffer for speed
                    for chunk in stream.iter_content(chunk_size=16384):
                        if not self.running: break
                        bytes_data += chunk
                        
                        # Find JPEG markers (Start: 0xFFD8, End: 0xFFD9)
                        while True:
                            a = bytes_data.find(b'\xff\xd8')
                            b = bytes_data.find(b'\xff\xd9')
                            
                            if a != -1 and b != -1:
                                # Found a complete frame
                                jpg = bytes_data[a:b+2]
                                bytes_data = bytes_data[b+2:] # Keep remainder
                                
                                self.frame = jpg
                                self.last_frame_time = time.time()
                                last_frame_received = time.time()
                            else:
                                break # Need more data
                        
                        # Prevent buffer bloat if no end marker found
                        if len(bytes_data) > 1000000:
                            bytes_data = bytes()
                        
                        # Heartbeat check
                        if time.time() - last_frame_received > 10:
                            print("Stream heartbeat timeout (10s). Forcing reconnect...")
                            stream.close()
                            break
                else:
                    print(f"Stream returned status: {stream.status_code}")
                    time.sleep(1)
                    
            except Exception as e:
                print(f"Stream Read Error: {e}")
                time.sleep(2)
                
    async def get_frame(self):
        # Return latest frame if available AND recent (<5.0s old)
        # Increased to 5.0s because tunnel lag can be high
        if self.frame and (time.time() - self.last_frame_time < 5.0):
            return self.frame
        
        # If frame is stale or missing, return mock
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
