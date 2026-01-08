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
        # Determine source from arg or env
        if source is None:
            source = os.environ.get("CAMERA_SOURCE", 0)
            
        # If source is a string digit (e.g. "0"), convert to int for local webcam
        if isinstance(source, str) and source.isdigit():
            source = int(source)
            
        print(f"Connecting to Camera Source: {source}")
        self.video = cv2.VideoCapture(source)
        
        # Verify camera opened
        if not self.video.isOpened():
             print(f"Error: Could not open camera source {source}. Falling back to mock.")
             self.mock_fallback = MockCamera()
        else:
             self.mock_fallback = None
             # Only set resolution for local webcams (integers)
             if isinstance(source, int):
                 self.video.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                 self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    def __del__(self):
        if self.video and self.video.isOpened():
            self.video.release()

    async def get_frame(self):
        if self.mock_fallback:
             return await self.mock_fallback.get_frame()

        # Read frame
        success, frame = self.video.read()
        if not success:
            # If stream drops, try to reconnect or return empty
            return b''  
        
        # Encode
        ret, jpeg = cv2.imencode('.jpg', frame)
        return jpeg.tobytes()

# Instances
thermal_instance = MockCamera()
rgb_instance = None # Lazy load

def get_camera(type='thermal'):
    global rgb_instance
    if type == 'rgb':
        if rgb_instance is None:
             # This will trigger the env var lookup in __init__
             rgb_instance = RealCamera()
        return rgb_instance
    return thermal_instance
