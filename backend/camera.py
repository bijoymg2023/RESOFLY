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
        self.width = 160
        self.height = 120
        # Create a base hotspot that moves
        self.x = 80
        self.y = 60
        self.dx = 2
        self.dy = 2

    async def get_frame(self):
        # Create a blank thermal image (simulated)
        # 16-bit simpler simulation using 8-bit heatmap for MJPEG
        
        # 1. Generate base noise
        frame = np.random.randint(20, 40, (self.height, self.width), dtype=np.uint8)
        
        # 2. Add a filtered hotspot
        # Update position
        self.x += self.dx
        self.y += self.dy
        if self.x <= 10 or self.x >= self.width-10: self.dx *= -1
        if self.y <= 10 or self.y >= self.height-10: self.dy *= -1
        
        # Draw hotspot (simulating a heat source)
        cv2.circle(frame, (self.x, self.y), 15, (255), -1)
        
        # Blur to look like thermal data
        frame = cv2.GaussianBlur(frame, (15, 15), 0)
        
        # Apply colormap (Inferno is good for thermal)
        heatmap = cv2.applyColorMap(frame, cv2.COLORMAP_INFERNO)
        
        # Simulate processing time of direct sensor reading
        await asyncio.sleep(0.05) # ~20 FPS
        
        # Encode as JPEG
        ret, jpeg = cv2.imencode('.jpg', heatmap)
        return jpeg.tobytes()

# Global singleton
camera_instance = MockCamera()

def get_camera():
    return camera_instance
