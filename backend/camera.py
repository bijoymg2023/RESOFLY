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
    """
    Simulated Thermal Camera that generates a moving heatmap.
    Used when real hardware is not available or disabled.
    """
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

# Global Singleton
thermal_instance = None 

def get_camera(type='thermal'):
    """
    Returns a camera instance. 
    In this stripped-down version, it ALWAYS returns the MockCamera.
    """
    global thermal_instance
    
    if thermal_instance is None:
        print("Initializing Mock Thermal Camera (Hardware driver disabled)...")
        thermal_instance = MockCamera()
             
    return thermal_instance
