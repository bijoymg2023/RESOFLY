import cv2
import numpy as np
import time
import asyncio
from abc import ABC, abstractmethod

class BaseCamera(ABC):
    @abstractmethod
    async def get_frame(self):
        """Returns a jpeg encoded frame bytes"""
        pass

class MockCamera(BaseCamera):
    def __init__(self):
        self.width = 320
        self.height = 240
        # Create a base hotspot that moves
        self.x = 80
        self.y = 60
        self.dx = 2
        self.dy = 2

    async def get_frame(self):
        # Create a simulated thermal image
        # 1. Generate base noise
        frame = np.random.randint(20, 40, (self.height, self.width), dtype=np.uint8)
        
        # 2. Add a filtered hotspot
        # Update position
        self.x += self.dx
        self.y += self.dy
        if self.x <= 10 or self.x >= self.width-10: self.dx *= -1
        if self.y <= 10 or self.y >= self.height-10: self.dy *= -1
        
        # Draw hotspot (simulating a heat source)
        cv2.circle(frame, (self.x, self.y), 25, (255), -1)
        
        # Blur to look like thermal data
        frame = cv2.GaussianBlur(frame, (35, 35), 0)
        
        # Apply colormap (Inferno is good for thermal)
        heatmap = cv2.applyColorMap(frame, cv2.COLORMAP_INFERNO)
        
        # Simulate processing time
        await asyncio.sleep(0.05) 
        
        # Encode as JPEG
        ret, jpeg = cv2.imencode('.jpg', heatmap)
        return jpeg.tobytes()

import os

class RealCamera(BaseCamera):
    def __init__(self, source=None):
        self.mock_fallback = None
        
        # Determine source from arg or env
        if source is None:
            source = os.environ.get("CAMERA_SOURCE", 0)
        
        # Try to confirm integer index
        if isinstance(source, str) and source.isdigit():
            source = int(source)
            
        print(f"Initializing RealCamera with source: {source}")
        
        try:
            # Attempt 1: V4L2 backend (Best for Pi)
            self.video = cv2.VideoCapture(source, cv2.CAP_V4L2)
            if not self.video.isOpened():
                 print(f"Failed to open source {source} with V4L2. Trying default backend...")
                 self.video = cv2.VideoCapture(source)
                 
            # FORCE MJPG (Crucial for Pi Cams to work fast via USB)
            self.video.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
            self.video.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.video.set(cv2.CAP_PROP_FPS, 30)
            
            if not self.video.isOpened():
                raise Exception("Could not open video source")
                
        except Exception as e:
            print(f"CAMERA INIT ERROR: {e}. Switching to MOCK mode.")
            self.mock_fallback = MockCamera()
            self.video = None
    def __del__(self):
        if self.video and self.video.isOpened():
            self.video.release()

    async def get_frame(self):
        if self.mock_fallback:
             return await self.mock_fallback.get_frame()

        # Read frame in a separate thread to avoid blocking the event loop
        # This is CRITICAL for concurrent performance (GPS + Video)
        if self.video and self.video.isOpened():
            success, frame = await asyncio.to_thread(self.video.read)
            if success and frame is not None:
                # Encode
                ret, jpeg = cv2.imencode('.jpg', frame)
                if ret:
                    return jpeg.tobytes()
        
        # If we reach here, reading failed. Re-try opening or just return mock?
        # Let's return empty bytes so frontend handles it, OR return mock temporarily.
        print("Camera read failed. Returning reconnecting placeholder...")
        return b''

class LeptonCamera(BaseCamera):
    def __init__(self):
        try:
            import spidev
        except ImportError:
            print("ERROR: spidev module not found. Please install it: pip install spidev")
            self.spi = None
            return

        print("Initializing Direct SPI Lepton Camera...")
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0) # /dev/spidev0.0
        self.spi.max_speed_hz = 16000000 # 16 MHz
        self.spi.mode = 0b11 # SPI Mode 3
        
        # Buffer for 4 segments * 60 packets/seg * 164 bytes/packet = 39360 bytes
        # Requires spidev.bufsiz=65536 in /boot/cmdline.txt
        self.frame_msg = bytearray(39360) 

    async def get_frame(self):
         # Get frame in thread
         return await asyncio.to_thread(self._read_spi_frame)

    def _read_spi_frame(self):
        try:
            from lepton_ioctl import LeptonIOCTL
            if not hasattr(self, 'io_spi') or self.io_spi is None:
                 self.io_spi = LeptonIOCTL()
            
            # Force Re-Sync for every frame
            # This ensures we catch the start of the VoSPI stream.
            time.sleep(0.2) 
            
            # Read FULL FRAME (4 Segments) in one massive atomic transaction
            # This prevents Python pauses between segments which cause Sync Loss on Lepton 3
            total_size = 39360 
            data = self.io_spi.xfer2([0] * total_size)
            
            if not data or len(data) != total_size:
                return b''
            
            # Convert to numpy
            raw = np.frombuffer(bytearray(data), dtype=np.uint8)
            packets = raw.reshape(240, 164)
            
            # Strip headers
            payload = packets[:, 4:] 
            flat = payload.flatten()
            vals = flat.view(np.uint16)
            vals = vals.byteswap()
            
            # Reshape 120x60
            frame = vals.reshape(120, 160)
            
            # Normalize
            valid_mask = frame > 0
            if np.any(valid_mask):
                min_val = np.min(frame[valid_mask])
                max_val = np.max(frame[valid_mask])
                diff = max_val - min_val
                if diff == 0: 
                    diff = 1
                frame_norm = cv2.normalize(frame, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
            else:
                frame_norm = np.zeros((120, 160), dtype=np.uint8)
                
            heatmap = cv2.applyColorMap(frame_norm, cv2.COLORMAP_INFERNO)
            heatmap = cv2.resize(heatmap, (640, 480), interpolation=cv2.INTER_NEAREST)
            ret, jpeg = cv2.imencode('.jpg', heatmap)
            return jpeg.tobytes()
            
        except Exception as e:
            print(f"SPI Error: {e}")
            time.sleep(1) # Backoff
            return b''
            
            # Reshape to image (Lepton 3.5 is 120x160)
            # Logic: 240 packets. 2 packets per line? 
            # Packet sequence in segment: 0, 1, 2... 
            # Let's try simple reshape first.
            frame = vals.reshape(120, 160)
            
            # Normalization (Auto-AGC)
            # Find min/max excluding zeros (dead pixels or padding)
            valid_mask = frame > 0
            if np.any(valid_mask):
                min_val = np.min(frame[valid_mask])
                max_val = np.max(frame[valid_mask])
                
                # Stretch contrast
                frame_norm = cv2.normalize(frame, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
            else:
                frame_norm = np.zeros((120, 160), dtype=np.uint8)
                
            # False Color
            heatmap = cv2.applyColorMap(frame_norm, cv2.COLORMAP_INFERNO)
            
            # Upscale for display (optional, 160x120 is small)
            heatmap = cv2.resize(heatmap, (640, 480), interpolation=cv2.INTER_NEAREST)
            
            ret, jpeg = cv2.imencode('.jpg', heatmap)
            return jpeg.tobytes()
            
        except Exception as e:
            print(f"SPI Read Error: {e}")
            return b''

# Instances
thermal_instance = None # Lazy load
rgb_instance = None 

def get_camera(type='thermal'):
    global rgb_instance, thermal_instance
    if type == 'rgb':
        if rgb_instance is None:
             rgb_instance = RealCamera(source=0) # Default to 0 for Webcam
        return rgb_instance
        
    # Thermal
    if thermal_instance is None:
        # Check env or default
        val = os.environ.get("CAMERA_SOURCE", "mock")
        if val == "lepton" or val == "spi":
             thermal_instance = LeptonCamera()
        elif val.isdigit():
             thermal_instance = RealCamera(source=int(val))
        else:
             thermal_instance = MockCamera()
             
    return thermal_instance
