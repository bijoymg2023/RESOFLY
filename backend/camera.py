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
    def __init__(self): pass
    async def get_frame(self): return None

class StreamProxyCamera(BaseCamera):
    """
    Standard MJPEG Proxy. 
    Connects to localhost:8080 and simply forwards the latest frame.
    Robust and simple.
    """
    def __init__(self, url="http://127.0.0.1:8080/mjpeg"):
        self.url = url
        self.frame = None
        self.running = True
        
        # Start background poller
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()
        print(f"Initializing Robust Proxy Camera to: {self.url}")

    def _update_loop(self):
        print(f"Proxy Thread Started. Target: {self.url}")
        
        while self.running:
            try:
                # Open stream (timeout 5s to allow connection)
                with requests.get(self.url, stream=True, timeout=5) as r:
                    if r.status_code == 200:
                        print(f"Connected to Camera: {self.url}")
                        bytes_data = bytes()
                        
                        # Read chunks
                        for chunk in r.iter_content(chunk_size=4096):
                            if not self.running: break
                            bytes_data += chunk
                            
                            # Find MJPEG Frame Boundaries
                            a = bytes_data.find(b'\xff\xd8')
                            b = bytes_data.find(b'\xff\xd9')
                            
                            if a != -1 and b != -1:
                                # Found a full frame
                                self.frame = bytes_data[a:b+2]
                                
                                # Move buffer forward
                                bytes_data = bytes_data[b+2:]
                                
                                # Prevent buffer from growing infinitely if corrupt
                                if len(bytes_data) > 100000:
                                    bytes_data = bytes()
                    else:
                        print(f"Camera returned status: {r.status_code}")
                        time.sleep(2)
                        
            except Exception as e:
                # print(f"Stream Retry: {e}")
                time.sleep(1)
                
    async def get_frame(self):
        # Return whatever frame we have. No timeout logic to prevent flickering.
        return self.frame

    def __del__(self):
        self.running = False

# Global Singleton
camera_instance = None 

def get_camera(type='rgb'):
    global camera_instance
    if camera_instance is None:
        camera_instance = StreamProxyCamera()
    return camera_instance

def capture_fresh_frame(stream_url="http://127.0.0.1:8080/mjpeg"):
    """
    Connects to the stream, grabs one frame cleanly, and returns JPEG bytes.
    Uses OpenCV which handles buffering/sync better than raw sockets.
    """
    try:
        cap = cv2.VideoCapture(stream_url)
        if not cap.isOpened():
            print(f"Error: Could not open stream {stream_url}")
            return None
            
        # Try to grab a frame
        ret, frame = cap.read()
        cap.release()
        
        if not ret or frame is None:
            print("Error: Could not read frame from capture")
            return None
            
        # Convert to JPEG bytes
        success, buffer = cv2.imencode('.jpg', frame)
        if not success:
            return None
            
        return buffer.tobytes()
    except Exception as e:
        print(f"Capture Exception: {e}")
        return None


# ========================================
# Pi Camera (RGB) Support
# ========================================

class PiCamera(BaseCamera):
    """
    Native Pi Camera using picamera2 library.
    Falls back gracefully if not available.
    """
    def __init__(self, resolution=(1280, 720), framerate=30):
        self.resolution = resolution
        self.framerate = framerate
        self.camera = None
        self.available = False
        self.frame = None
        self.running = True
        
        try:
            from picamera2 import Picamera2
            self.camera = Picamera2()
            config = self.camera.create_preview_configuration(
                main={"size": resolution, "format": "RGB888"}
            )
            self.camera.configure(config)
            self.camera.start()
            self.available = True
            print(f"Pi Camera initialized at {resolution}")
            
            # Start background capture thread
            self.thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.thread.start()
            
        except ImportError:
            print("picamera2 not available - Pi Camera disabled")
        except Exception as e:
            print(f"Pi Camera init error: {e}")
    
    def _capture_loop(self):
        """Background thread to continuously capture frames."""
        while self.running and self.available:
            try:
                # Capture frame as numpy array
                frame = self.camera.capture_array()
                
                # Convert RGB to BGR for OpenCV
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                # Encode as JPEG
                success, buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if success:
                    self.frame = buffer.tobytes()
                    
                time.sleep(1.0 / self.framerate)
                
            except Exception as e:
                print(f"Pi Camera capture error: {e}")
                time.sleep(0.5)
    
    async def get_frame(self):
        return self.frame
    
    def is_available(self):
        return self.available
    
    def __del__(self):
        self.running = False
        if self.camera:
            try:
                self.camera.stop()
            except:
                pass


# RGB Camera Singleton
rgb_camera_instance = None

def get_rgb_camera():
    """Get RGB camera instance (Pi Camera)."""
    global rgb_camera_instance
    if rgb_camera_instance is None:
        rgb_camera_instance = PiCamera()
    return rgb_camera_instance


async def generate_rgb_stream():
    """Generator for MJPEG stream from Pi Camera."""
    camera = get_rgb_camera()
    
    while True:
        frame = await camera.get_frame()
        
        if frame:
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
            )
        else:
            # Send placeholder if no frame available
            yield (
                b'--frame\r\n'
                b'Content-Type: text/plain\r\n\r\n'
                b'Waiting for camera...\r\n'
            )
        
        await asyncio.sleep(0.033)  # ~30 FPS
