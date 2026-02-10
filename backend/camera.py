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
    
    Optimizations for smooth streaming:
    - 1280x720 @ 30fps for sharp image
    - JPEG quality 70 for good visual/bandwidth balance
    - 32KB read chunks to minimize syscalls per frame
    - asyncio.Event to notify consumers immediately when a new frame arrives
    - Greedy frame parsing to always show the freshest frame
    """
    def __init__(self, resolution=(1280, 720), framerate=30):
        self.resolution = resolution
        self.framerate = framerate
        self.frame = None
        self.running = True
        self.available = False
        self.process = None
        self.lock = threading.Lock()
        self._frame_seq = 0          # Monotonic frame counter
        self._frame_event = asyncio.Event()  # Signals new frame to async consumers
        self._loop = None            # Event loop reference for cross-thread signaling
        
        # Check if rpicam-vid is available
        import shutil
        if shutil.which("rpicam-vid"):
            self.available = True
            print(f"RpicamCamera initialized at {resolution} @ {framerate}fps (smooth stream)")
            
            # Start video streaming thread
            self.thread = threading.Thread(target=self._stream_loop, daemon=True)
            self.thread.start()
        else:
            print("rpicam-vid not found - Pi Camera disabled")
    
    def _signal_new_frame(self):
        """Thread-safe signaling to async consumers that a new frame is ready."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._frame_event.set)

    def _stream_loop(self):
        """Background thread to continuously stream video using rpicam-vid."""
        import subprocess
        
        while self.running and self.available:
            try:
                # rpicam-vid with optimized settings for smooth streaming:
                # - 1280x720: sharp HD image
                # - quality 70: good visual with reasonable bandwidth
                # - exposure sport: faster shutter for motion clarity
                # - denoise off: skip post-processing for lower latency
                # - flush: forces stdout flush per frame
                cmd = [
                    "rpicam-vid",
                    "-t", "0",
                    "--width", str(self.resolution[0]),
                    "--height", str(self.resolution[1]),
                    "--framerate", str(self.framerate),
                    "--codec", "mjpeg",
                    "--quality", "70",
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
                
                print("rpicam-vid stream started (smooth HD mode)")
                
                # Read MJPEG frames from stdout
                buffer = b''
                while self.running and self.process.poll() is None:
                    # Read 32KB chunks - fewer syscalls, each read gets
                    # a meaningful chunk of a JPEG frame (~30-60KB at 720p q70)
                    chunk = self.process.stdout.read(32768)
                    if not chunk:
                        break
                    
                    buffer += chunk
                    
                    # GREEDY FRAME PARSING:
                    # Find the LAST complete frame in the buffer.
                    # This ensures we always show the freshest frame.
                    
                    last_frame_end = buffer.rfind(b'\xff\xd9')
                    
                    if last_frame_end != -1:
                        packet_end = last_frame_end + 2
                        
                        # Search backwards for start of this frame
                        frame_start = buffer.rfind(b'\xff\xd8', 0, last_frame_end)
                        
                        if frame_start != -1:
                            # Extract the latest complete frame
                            new_frame = buffer[frame_start:packet_end]
                            
                            with self.lock:
                                self.frame = new_frame
                                self._frame_seq += 1
                            
                            # Signal async consumers immediately
                            self._signal_new_frame()
                            
                            # Discard processed data (keep only the tail for next frame)
                            buffer = buffer[packet_end:]
                        else:
                            # Partial buffer - discard if too large
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
    
    async def wait_for_frame(self, timeout=0.1):
        """Wait for a NEW frame to arrive, with timeout.
        Returns the frame if available, None on timeout."""
        # Store the event loop reference for cross-thread signaling
        if self._loop is None:
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
    
    Uses event-driven frame delivery for smooth streaming:
    - Waits for new frames via asyncio.Event (no fixed sleep)
    - Yields immediately when a new frame arrives
    - Falls back to polling at 30fps if events aren't working
    """
    camera = get_rgb_camera()
    last_seq = -1
    
    while True:
        # Wait for a new frame (event-driven, up to 50ms timeout)
        frame = await camera.wait_for_frame(timeout=0.05)
        
        if frame:
            # Only yield if this is a genuinely new frame
            with camera.lock:
                current_seq = camera._frame_seq
            
            if current_seq != last_seq:
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
                )
                last_seq = current_seq
            else:
                # Same frame, short sleep to avoid busy-spinning
                await asyncio.sleep(0.01)
        else:
            yield (
                b'--frame\r\n'
                b'Content-Type: text/plain\r\n\r\n'
                b'Waiting for camera...\r\n'
            )
            await asyncio.sleep(0.1)  # Longer wait when no camera
