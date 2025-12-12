
import cv2
import numpy as np
import asyncio
from abc import ABC, abstractmethod

# NOTE: This module requires 'pylepton' to be installed on the Raspberry Pi
# pip install pylepton
try:
    from pylepton import Lepton
except ImportError:
    print("Warning: pylepton not found. This module will fail if used without hardware.")
    Lepton = None

class BaseCamera(ABC):
    @abstractmethod
    async def get_frame(self):
        """Returns a jpeg encoded frame bytes"""
        pass

class LeptonCamera(BaseCamera):
    def __init__(self, device="/dev/spidev0.0"):
        self.device = device
        self.heatmap_min = 0 # 273.15 Kelvin (0C) (approx raw value depends on Lepton mode)
        self.heatmap_max = 0 
        
    async def get_frame(self):
        if Lepton is None:
            # Fallback if drivers missing
            return b''

        # Capture from Lepton (Blocking I/O, better to run in thread executor if high load)
        # For simplicity in this demo, we run it directly.
        try:
            with Lepton(self.device) as l:
                a, _ = l.capture()
                
                # Lepton 3.5 gives 160x120 16-bit radiometric data (centikelvin)
                # Normalize for display (8-bit)
                # Dynamic Range Scaling
                cv2.normalize(a, a, 0, 65535, cv2.NORM_MINMAX)
                np.right_shift(a, 8, a) # Shift to 8-bit
                w_img = np.uint8(a)
                
                # Apply colormap
                heatmap = cv2.applyColorMap(w_img, cv2.COLORMAP_INFERNO)
                
                # Encode
                ret, jpeg = cv2.imencode('.jpg', heatmap)
                return jpeg.tobytes()
        except Exception as e:
            print(f"Error capturing Lepton frame: {e}")
            return b''

# Use this instance in server.py
# from camera_real import LeptonCamera
# cam = LeptonCamera()
