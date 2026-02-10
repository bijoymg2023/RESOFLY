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
                # Open stream (timeout 3s for fast reconnect)
                with requests.get(self.url, stream=True, timeout=3) as r:
                    if r.status_code == 200:
                        print(f"Connected to Camera: {self.url}")
                        bytes_data = bytes()
                        
                        # Read smaller chunks for lower latency
                        for chunk in r.iter_content(chunk_size=1024):
                            if not self.running: break
                            bytes_data += chunk
                            
                            # Find the LAST complete frame (skip old ones)
                            b = bytes_data.rfind(b'\xff\xd9')
                            if b != -1:
                                a = bytes_data.rfind(b'\xff\xd8', 0, b)
                                if a != -1:
                                    # Use the latest frame, discard everything before
                                    self.frame = bytes_data[a:b+2]
                                    bytes_data = bytes_data[b+2:]
                                
                                # Prevent buffer from growing
                                if len(bytes_data) > 50000:
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
# Pi Camera (RGB) Support using rpicam-vid (Optimized)
# ========================================

class RpicamCamera(BaseCamera):
    """
    Pi Camera using rpicam-vid subprocess for continuous video streaming.
    Outputs MJPEG directly to stdout for high performance (30fps+).
    """
    def __init__(self, resolution=(640, 480), framerate=30):
        self.resolution = resolution
        self.framerate = framerate
        self.frame = None
        self.running = True
        self.available = False
        self.process = None
        self.lock = threading.Lock()
        
        # Check if rpicam-vid is available
        import shutil
        if shutil.which("rpicam-vid"):
            self.available = True
            print(f"RpicamCamera (vid) initialized at {resolution} @ {framerate}fps (Stable Low Latency)")
            
            # Start video streaming thread
            self.thread = threading.Thread(target=self._stream_loop, daemon=True)
            self.thread.start()
        else:
            print("rpicam-vid not found - Pi Camera disabled")
    
    def _stream_loop(self):
        """Background thread to continuously stream video using rpicam-vid."""
        import subprocess
        
        while self.running and self.available:
            try:
                # Start rpicam-vid outputting MJPEG to stdout
                # Ultra low latency tuning:
                # - 640x480 @ 30fps
                # - exposure sport: faster shutter for motion
                # - quality 50: trade quality for speed
                # - denoise off: skip processing
                cmd = [
                    "rpicam-vid",
                    "-t", "0",
                    "--width", str(self.resolution[0]),
                    "--height", str(self.resolution[1]),
                    "--framerate", str(self.framerate),
                    "--codec", "mjpeg",
                    "--quality", "50",
                    "--exposure", "sport",
                    "--denoise", "off",
                    "--inline",            
                    "--nopreview",
                    "--flush",
                    "-o", "-"
                ]
                
                # bufsize=0 for unbuffered output
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    bufsize=0
                )
                
                print("rpicam-vid stream started (low-latency mode)")
                
                # Read MJPEG frames from stdout
                buffer = b''
                while self.running and self.process.poll() is None:
                    # Read smaller chunks more frequently for lower latency
                    chunk = self.process.stdout.read(8192)
                    if not chunk:
                        break
                    
                    buffer += chunk
                    
                    # GREEDY FRAME PARSING:
                    # Find the LAST complete frame in the buffer and discard everything before it.
                    # This ensures we always show the freshest frame and never lag behind.
                    
                    last_frame_end = buffer.rfind(b'\xff\xd9')
                    
                    if last_frame_end != -1:
                        # Found at least one frame end.
                        # Now find the start of THIS frame
                        packet_end = last_frame_end + 2
                        
                        # Search backwards for start of this frame
                        frame_start = buffer.rfind(b'\xff\xd8', 0, last_frame_end)
                        
                        if frame_start != -1:
                            # Extract the latest complete frame
                            new_frame = buffer[frame_start:packet_end]
                            
                            with self.lock:
                                self.frame = new_frame
                            
                            # DISCARD processed data and OLD frames
                            # Keep only what's after the last frame end (start of next frame)
                            buffer = buffer[packet_end:]
                        else:
                            # We have an end but no start? (partial buffer)
                            # Keep buffer as is, wait for more data?
                            # Or discard if buffer is too big to be a fragment?
                            if len(buffer) > 500000:
                                buffer = b''
                    
                    # Safety valve
                    if len(buffer) > 1000000:
                        buffer = b''
                
            except Exception as e:
                print(f"RpicamCamera stream error: {e}")
                time.sleep(1)
            finally:
                if self.process:
                    try:
                        self.process.terminate()
                        self.process.wait(timeout=1)
                    except:
                        pass
                    self.process = None
                time.sleep(0.5)  # Fast reconnect

    
    async def get_frame(self):
        with self.lock:
            return self.frame
    
    def is_available(self):
        return self.available
    
    def __del__(self):
        self.running = False
        if self.process:
            try:
                self.process.terminate()
            except:
                pass


# RGB Camera Singleton
rgb_camera_instance = None

def get_rgb_camera():
    """Get RGB camera instance (Pi Camera via rpicam-vid)."""
    global rgb_camera_instance
    if rgb_camera_instance is None:
        rgb_camera_instance = RpicamCamera()
    return rgb_camera_instance


async def generate_rgb_stream():
    """Async generator for MJPEG stream from Pi Camera."""
    camera = get_rgb_camera()
    
    while True:
        frame = await camera.get_frame()
        
        if frame:
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
            )
        else:
            yield (
                b'--frame\r\n'
                b'Content-Type: text/plain\r\n\r\n'
                b'Waiting for camera...\r\n'
            )
        
        await asyncio.sleep(0.033) # ~30 FPS (matches camera framerate, reduces CPU)
