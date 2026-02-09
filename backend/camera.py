import cv2
import numpy as np
import os
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
# Pi Camera (RGB) Support using rpicam-still
# ========================================

class RpicamCamera(BaseCamera):
    """
    Pi Camera using rpicam-still subprocess.
    More reliable than picamera2 on newer Pi OS.
    """
    def __init__(self, resolution=(640, 480), framerate=10):
        self.resolution = resolution
        self.framerate = framerate
        self.frame = None
        self.running = True
        self.available = False
        self.temp_file = "/tmp/resofly_stream.jpg"
        
        # Check if rpicam-still is available
        import shutil
        if shutil.which("rpicam-still"):
            self.available = True
            print(f"RpicamCamera initialized at {resolution}")
            
            # Start background capture thread
            self.thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.thread.start()
        else:
            print("rpicam-still not found - Pi Camera disabled")
    
    def _capture_loop(self):
        """Background thread to continuously capture frames using rpicam-still."""
        import subprocess
        
        while self.running and self.available:
            try:
                # Capture frame using rpicam-still
                # -t 1: timeout 1ms (instant)
                # -n: no preview
                # --width/--height: resolution
                cmd = [
                    "rpicam-still",
                    "-o", self.temp_file,
                    "-t", "1",
                    "--width", str(self.resolution[0]),
                    "--height", str(self.resolution[1]),
                    "-n"
                ]
                subprocess.run(cmd, capture_output=True, timeout=5)
                
                # Read the captured image
                if os.path.exists(self.temp_file):
                    with open(self.temp_file, "rb") as f:
                        self.frame = f.read()
                
                # Control frame rate
                time.sleep(1.0 / self.framerate)
                
            except subprocess.TimeoutExpired:
                print("rpicam-still timeout")
                time.sleep(1)
            except Exception as e:
                print(f"RpicamCamera capture error: {e}")
                time.sleep(0.5)
    
    async def get_frame(self):
        return self.frame
    
    def is_available(self):
        return self.available
    
    def __del__(self):
        self.running = False
        # Clean up temp file
        import os
        if os.path.exists(self.temp_file):
            try:
                os.remove(self.temp_file)
            except:
                pass


# RGB Camera Singleton
rgb_camera_instance = None

def get_rgb_camera():
    """Get RGB camera instance (Pi Camera via rpicam-still)."""
    global rgb_camera_instance
    if rgb_camera_instance is None:
        rgb_camera_instance = RpicamCamera()
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
