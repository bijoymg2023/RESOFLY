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
    def __init__(self, resolution=(640, 480), framerate=30):
        self.resolution = resolution
        self.framerate = framerate
        self.frame = None
        self.frame_id = 0
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
        import fcntl
        import os
        
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
                    "--rotation", "180",
                    "--hflip",
                    "--flush",
                    "-o", "-"
                ]
                
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    bufsize=0
                )
                
                # SET NON-BLOCKING MODE
                # This is CRITICAL. It allows us to read *everything* currently in the pipe
                # without getting stuck waiting for more.
                fd = self.process.stdout.fileno()
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                
                print(f"rpicam-vid ZERO-LATENCY stream started ({self.resolution[0]}x{self.resolution[1]} @ {self.framerate}fps)")
                
                # Buffer management
                buffer = bytearray()
                
                while self.running and self.process.poll() is None:
                    # 1. DRAIN THE PIPE
                    # Keep reading until the OS says "BlockingIOError" (pipe empty)
                    # or returning None/0 bytes (EOF)
                    data_read = False
                    while True:
                        try:
                            # Read up to 1MB at a time
                            chunk = os.read(fd, 1048576)
                            if not chunk:
                                # EOF
                                break
                            buffer.extend(chunk)
                            data_read = True
                        except BlockingIOError:
                            # Pipe is empty! We have everything.
                            break
                        except Exception:
                            # Some other error?
                            break
                            
                    if not data_read:
                        # Don't burn CPU if no data came in
                        time.sleep(0.005)
                        continue
                    
                    # 2. GREEDY PARSING
                    # We now have the entire backlog in 'buffer'. 
                    # Find the LAST complete frame and discard everything before it.
                    last_end = buffer.rfind(b'\xff\xd9')
                    
                    if last_end != -1:
                        last_start = buffer.rfind(b'\xff\xd8', 0, last_end)
                        
                        if last_start != -1:
                            # Extract the absolute latest frame
                            latest_frame = bytes(buffer[last_start:last_end+2])
                            
                            with self.lock:
                                self.frame = latest_frame
                                self.frame_id += 1
                            
                            self._signal_new_frame()
                            
                            # DISCARD OLD DATA
                            # Throw away everything up to this frame.
                            # Even if there are partial bytes after (next frame starting),
                            # it's safer to just keep them.
                            # Wait, strictly speaking, we want to discard everything *before* the next start?
                            # Actually, just clearing up to the end of the current frame is fine.
                            # The non-blocking drain ensures we catch up next cycle anyway.
                            del buffer[:last_end+2]
                            
                            # Safety: if buffer is still huge (junk data?), clear it.
                            if len(buffer) > 2000000:
                                buffer = bytearray()
                        else:
                            # We have an end but no start? Junk. Clear up to end.
                            del buffer[:last_end+2]
                    
                    # Safety valve
                    if len(buffer) > 5000000:
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

    async def get_frame_with_id(self):
        """Get the latest frame and its ID for deduplication."""
        with self.lock:
            return self.frame, self.frame_id
    
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
    last_frame_id = -1
    
    while True:
        # Wait for a new frame (event-driven) instead of blind polling
        if hasattr(camera, 'wait_for_frame'):
            # Wait up to 80ms for a new frame signal (camera runs at ~15 fps = 67ms/frame)
            await camera.wait_for_frame(timeout=0.08)
        else:
            await asyncio.sleep(0.01)
            
        # Get frame data + ID
        if hasattr(camera, 'get_frame_with_id'):
            frame, current_id = await camera.get_frame_with_id()
        else:
            frame = await camera.get_frame()
            current_id = time.time() # Fallback for other camera types
        
        # DEDUPLICATION:
        # Only send if we have a NEW frame.
        if frame and current_id != last_frame_id:
            last_frame_id = current_id
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
            )
        else:
            # If no new frame, just sleep a tiny bit to prevent CPU burn
            await asyncio.sleep(0.005)
