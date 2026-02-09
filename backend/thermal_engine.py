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
    Wraps the dedicated waveshare_thermal module.
    """
    def __init__(self):
        self.available = False
        self.camera = None
        
        try:
            from waveshare_thermal import get_thermal_camera
            self.camera = get_thermal_camera()
            self.available = self.camera.is_available()
            
            if self.available:
                logger.info("Waveshare 80x62 Thermal HAT connected")
            else:
                logger.info("Waveshare Thermal HAT not available")
        except ImportError:
            logger.info("Waveshare driver not found, using dataset mode")
        except Exception as e:
            logger.warning(f"Waveshare Thermal HAT error: {e}")

    def get_frame(self):
        if not self.available or self.camera is None:
            return None
        return self.camera.get_frame()

class DetectionEngine:
    """
    Thermal hotspot detection engine optimized for low-resolution LWIR cameras.
    Tuned for 80x62 resolution but works with any grayscale frame.
    """
    def __init__(self, min_area=5, threshold_offset=35, low_res_mode=True):
        self.min_area = min_area  # Reduced for 80x62 (5 pixels = ~1% of frame)
        self.threshold_offset = threshold_offset
        self.low_res_mode = low_res_mode
        
        # Size thresholds for 80x62 resolution
        # Human at 10m distance ≈ 10-50 pixels
        # Fire/large heat source > 100 pixels
        self.life_max_area = 100 if low_res_mode else 500
        
    def process(self, frame):
        """
        Frame: 8-bit grayscale frame
        Returns: detections (list), result_metadata
        """
        if frame is None:
            return [], {}

        # 1. Enhance and Normalize
        # Adaptive CLAHE tile size based on resolution
        tile_size = (4, 4) if self.low_res_mode else (8, 8)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=tile_size)
        enhanced = clahe.apply(frame)
        
        # 2. Dynamic Thresholding
        avg = np.mean(enhanced)
        std = np.std(enhanced)
        
        # Use mean + std deviation for more adaptive threshold
        thresh_val = min(240, avg + self.threshold_offset)
        _, binary = cv2.threshold(enhanced, thresh_val, 255, cv2.THRESH_BINARY)
        
        # 3. Noise Removal (smaller kernel for low-res)
        kernel_size = 2 if self.low_res_mode else 3
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
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
                
                # Calculate confidence based on intensity differential
                intensity_diff = max_val - avg
                intensity_confidence = min(1.0, intensity_diff / 100.0)
                
                # Area-based confidence (larger = easier to detect reliably)
                area_confidence = min(0.3, area / 50.0) if self.low_res_mode else min(0.3, area / 500.0)
                
                # Combined confidence
                confidence = min(0.95, 0.4 + intensity_confidence * 0.4 + area_confidence)
                
                # Classification: LIFE (human/animal) vs FIRE (large heat source)
                detection_type = "LIFE" if area < self.life_max_area else "FIRE"
                
                detections.append({
                    "type": detection_type,
                    "confidence": float(confidence),
                    "center": (x + w//2, y + h//2),
                    "area": float(area),
                    "max_intensity": float(max_val),
                    "bbox": [int(x), int(y), int(w), int(h)]
                })
        
        return detections, {
            "count": len(detections),
            "avg_intensity": float(avg),
            "std_intensity": float(std),
            "timestamp": datetime.now().isoformat()
        }

class ThermalDetectionService:
    def __init__(self, callback, dataset_path=None):
        self.source = None
        self.engine = DetectionEngine(low_res_mode=True)  # Default to low-res for Waveshare
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
