import cv2
import numpy as np
import time
import threading
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class ThermalSource:
    """Base class for thermal data input"""
    def get_frame(self):
        raise NotImplementedError

class VideoDatasetSource(ThermalSource):
    """Reads thermal data from a video file (simulated dataset)"""
    def __init__(self, video_path):
        self.cap = cv2.VideoCapture(str(video_path))
        if not self.cap.isOpened():
            logger.error(f"Could not open video dataset: {video_path}")
        
    def get_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            # Loop video
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
        
        if ret:
            # Convert to grayscale if it's 3-channel
            if len(frame.shape) == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            return frame
        return None

class WaveshareThermalSource(ThermalSource):
    """
    Hardware driver for Waveshare 80x62 Thermal Camera HAT.
    Note: Requires spidev and potentially vendor library.
    This is a design-ready implementation.
    """
    def __init__(self):
        self.available = False
        try:
            # Placeholder for actual hardware init
            # import smbus or spidev
            # self.bus = ...
            logger.info("Waveshare 80x62 Thermal HAT initialized (Driver Placeholder)")
            self.available = True
        except Exception as e:
            logger.warning(f"Waveshare Thermal HAT not found: {e}")

    def get_frame(self):
        if not self.available:
            return None
        # In a real scenario, this would read 80x62 raw pixels
        # return raw_pixels.reshape(62, 80)
        return None

class DetectionEngine:
    def __init__(self, min_area=10, threshold_offset=40):
        self.min_area = min_area
        self.threshold_offset = threshold_offset # Values above background mean
        
    def process(self, frame):
        """
        Frame: 8-bit grayscale frame
        Returns: detections (list), result_metadata
        """
        if frame is None:
            return [], {}

        # 1. Enhance and Normalize
        # Apply CLAHE for better local contrast in low-res thermal
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(frame)
        
        # 2. Dynamic Thresholding
        # Instead of fixed 200, use background mean + offset
        avg = np.mean(enhanced)
        thresh_val = min(240, avg + self.threshold_offset)
        _, binary = cv2.threshold(enhanced, thresh_val, 255, cv2.THRESH_BINARY)
        
        # 3. Noise Removal (Morphology)
        kernel = np.ones((3,3), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        
        # 4. Blob Detection
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        detections = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area >= self.min_area:
                x, y, w, h = cv2.boundingRect(cnt)
                
                # Get max intensity inside contour
                mask = np.zeros(enhanced.shape, dtype=np.uint8)
                cv2.drawContours(mask, [cnt], -1, 255, -1)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(enhanced, mask=mask)
                
                detections.append({
                    "type": "LIFE" if area < 500 else "FIRE", # Simple size categorization
                    "confidence": float(min(0.95, 0.5 + (area / 1000.0))),
                    "center": (x + w//2, y + h//2),
                    "area": float(area),
                    "max_intensity": float(max_val),
                    "bbox": [int(x), int(y), int(w), int(h)]
                })
        
        return detections, {
            "count": len(detections),
            "avg_intensity": float(avg),
            "timestamp": datetime.now().isoformat()
        }

class ThermalDetectionService:
    def __init__(self, callback, dataset_path=None):
        self.source = None
        self.engine = DetectionEngine()
        self.callback = callback
        self.running = False
        self.thread = None
        
        # Select source
        hw = WaveshareThermalSource()
        if hw.available:
            self.source = hw
        elif dataset_path:
            self.source = VideoDatasetSource(dataset_path)
            
    def start(self):
        if not self.running and self.source:
            self.running = True
            self.thread = threading.Thread(target=self._worker, daemon=True)
            self.thread.start()
            logger.info("Thermal Detection Service Started")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def _worker(self):
        last_process_time = 0
        while self.running:
            # Throttle detection to ~5 FPS to save CPU on Pi
            now = time.time()
            if now - last_process_time < 0.2:
                time.sleep(0.01)
                continue
            
            frame = self.source.get_frame()
            if frame is not None:
                detections, metadata = self.engine.process(frame)
                if detections:
                    self.callback(detections, metadata)
                last_process_time = now
            else:
                time.sleep(1.0) # Wait for source if no frame
