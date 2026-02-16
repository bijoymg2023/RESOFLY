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
    Outputs MJPEG directly to stdout for high performance.
    Use asyncio.Event for zero-latency frame signaling.
    """
    def __init__(self, resolution=(640, 480), framerate=15):
        self.resolution = resolution
        self.framerate = framerate
        self.frame = None
        self.running = True
        self.available = False
        self.process = None
        self.lock = threading.Lock()
        self._frame_event = asyncio.Event()
        self._loop = None
        
        # Check if rpicam-vid is available
        import shutil
        if shutil.which("rpicam-vid"):
            self.available = True
            print(f"RpicamCamera initialized at {resolution} @ {framerate}fps (v1.6 Stability)")
            
            # Start video streaming thread
            self.thread = threading.Thread(target=self._stream_loop, daemon=True)
            self.thread.start()
        else:
            print("rpicam-vid not found - Pi Camera disabled")
    
    def _signal_new_frame(self):
        """Thread-safe way to signal the async event from the background thread."""
        try:
            if self._loop and not self._loop.is_closed():
                self._loop.call_soon_threadsafe(self._frame_event.set)
        except Exception:
            pass

    def _stream_loop(self):
        """Background thread to continuously stream video using rpicam-vid."""
        import subprocess
        
        while self.running and self.available:
            try:
                # rpicam-vid MJPEG to stdout
                cmd = [
                    "rpicam-vid",
                    "-t", "0",
                    "--width", str(self.resolution[0]),
                    "--height", str(self.resolution[1]),
                    "--framerate", str(self.framerate),
                    "--codec", "mjpeg",
                    "--quality", "60",
                    "--exposure", "sport",
                    "--denoise", "off",
                    "--inline",            
                    "--nopreview",
                    "--flush",
                    "-o", "-"
                ]
                
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    bufsize=0
                )
                
                print(f"rpicam-vid stable stream started ({self.resolution[0]}x{self.resolution[1]} @ {self.framerate}fps)")
                
                # Buffer management
                buffer = bytearray()
                while self.running and self.process.poll() is None:
                    # Smaller chunks for lower latency and better parsing
                    chunk = self.process.stdout.read(65536)
                    if not chunk:
                        break
                    
                    buffer.extend(chunk)
                    
                    # Find JPEG markers
                    while True:
                        start = buffer.find(b'\xff\xd8')
                        end = buffer.find(b'\xff\xd9', start)
                        
                        if start != -1 and end != -1:
                            # We have a full frame
                            jpg_frame = buffer[start:end+2]
                            
                            with self.lock:
                                self.frame = bytes(jpg_frame)
                            
                            self._signal_new_frame()
                            
                            # Remove processed frame (and any junk before it)
                            del buffer[:end+2]
                        else:
                            # Not enough data for a full frame yet
                            break
                    
                    # Safety valve (prevent memory leak if markers aren't found)
                    if len(buffer) > 1000000:
                        buffer = bytearray()
                
            except Exception as e:
                print(f"RpicamCamera stream error: {e}")
                time.sleep(2)
            finally:
                if self.process:
                    try:
                        self.process.terminate()
                        self.process.wait(timeout=1)
                    except:
                        pass
                    self.process = None
                time.sleep(1.0)

    
    async def get_frame(self):
        with self.lock:
            return self.frame
    
    async def wait_for_frame(self, timeout=0.1):
        """Wait for a new frame with timeout. Returns the frame or None."""
        # Store the event loop for cross-thread signaling
        self._loop = asyncio.get_event_loop()
        self._frame_event.clear()
        try:
            await asyncio.wait_for(self._frame_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
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
    """Async generator for MJPEG stream from Pi Camera.
    
    Uses event-driven frame delivery for smooth, low-latency streaming.
    Falls back to polling if events aren't available.
    """
    camera = get_rgb_camera()
    
    while True:
        # Wait for a new frame (event-driven) instead of blind polling
        if hasattr(camera, 'wait_for_frame'):
            frame = await camera.wait_for_frame(timeout=0.033)
        else:
            frame = await camera.get_frame()
            await asyncio.sleep(0.016)
        
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
            await asyncio.sleep(0.5)  # Don't spam when no camera
