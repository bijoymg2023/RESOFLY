"""
Synchronized Thermal Detection Pipeline
========================================
Unified frame pipeline where the same frame is used for:
1. Video display (MJPEG stream)
2. Hotspot detection
3. Alert generation

This ensures alerts appear at the exact moment thermal signatures are visible.
"""

import cv2
import numpy as np
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Callable, Set
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


# ============ DATA STRUCTURES ============

@dataclass
class Hotspot:
    """A detected thermal hotspot."""
    x: int
    y: int
    width: int
    height: int
    area: float
    max_intensity: float
    estimated_temp: float  # Estimated temperature in °C
    confidence: float


@dataclass 
class DetectionEvent:
    """Alert event with full metadata."""
    hotspots: List[Hotspot]
    timestamp: datetime
    frame_number: int
    total_count: int


# ============ TEMPERATURE NORMALIZATION ============

def intensity_to_temperature(intensity: float, min_temp: float = 15.0, max_temp: float = 45.0) -> float:
    """
    Map 0-255 pixel intensity to estimated temperature.
    
    LWIR cameras (8-14μm) measure thermal radiation.
    Hotter objects = brighter pixels (in grayscale thermal).
    
    Args:
        intensity: Pixel value 0-255
        min_temp: Minimum scene temperature (ambient cold)
        max_temp: Maximum scene temperature (body heat)
    
    Returns:
        Estimated temperature in °C
    """
    normalized = intensity / 255.0
    return min_temp + normalized * (max_temp - min_temp)


def temperature_to_intensity(temp: float, min_temp: float = 15.0, max_temp: float = 45.0) -> int:
    """Inverse: convert temperature to pixel intensity."""
    normalized = (temp - min_temp) / (max_temp - min_temp)
    return int(np.clip(normalized * 255, 0, 255))


# Human body detection threshold
# Accounts for: clothing, distance, ambient conditions
HUMAN_TEMP_THRESHOLD_C = 28.0  # Lower than 37°C due to clothing/distance
HUMAN_TEMP_THRESHOLD_INTENSITY = temperature_to_intensity(HUMAN_TEMP_THRESHOLD_C)


# ============ FRAME SOURCE ============

class VideoSource:
    """Reads frames from a video file."""
    
    def __init__(self, video_path: str):
        self.path = Path(video_path)
        self.cap = cv2.VideoCapture(str(self.path))
        self._available = self.cap.isOpened()
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 15
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    def get_frame(self) -> Optional[np.ndarray]:
        if not self._available:
            return None
        
        ret, frame = self.cap.read()
        if not ret:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
        
        return frame if ret else None
    
    def is_available(self) -> bool:
        return self._available


# ============ THERMAL DETECTOR ============

class ThermalDetector:
    """Detects thermal hotspots in frames."""
    
    def __init__(
        self,
        min_area: int = 40,
        blur_kernel: int = 5,
        adaptive: bool = True
    ):
        self.min_area = min_area
        self.blur_kernel = blur_kernel
        self.adaptive = adaptive
    
    def process(self, frame: np.ndarray) -> Tuple[List[Hotspot], np.ndarray]:
        """
        Process frame and return hotspots + binary mask.
        
        Returns:
            hotspots: List of detected hotspots
            binary: Thresholded binary image
        """
        # Ensure grayscale
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame.copy()
        
        # Normalize
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        
        # Denoise
        blurred = cv2.GaussianBlur(gray, (self.blur_kernel, self.blur_kernel), 0)
        
        # Adaptive threshold based on frame statistics
        if self.adaptive:
            mean = np.mean(blurred)
            std = np.std(blurred)
            thresh_val = int(min(250, mean + 1.5 * std))
            thresh_val = max(thresh_val, HUMAN_TEMP_THRESHOLD_INTENSITY)
        else:
            thresh_val = HUMAN_TEMP_THRESHOLD_INTENSITY
        
        # Binary threshold
        _, binary = cv2.threshold(blurred, thresh_val, 255, cv2.THRESH_BINARY)
        
        # Morphological cleanup
        kernel = np.ones((3, 3), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        hotspots = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            
            if area >= self.min_area:
                x, y, w, h = cv2.boundingRect(cnt)
                
                # Get max intensity in region
                mask = np.zeros(gray.shape, dtype=np.uint8)
                cv2.drawContours(mask, [cnt], -1, 255, -1)
                max_intensity = float(np.max(gray[mask == 255]))
                
                # Estimate temperature
                estimated_temp = intensity_to_temperature(max_intensity)
                
                # Confidence based on temperature differential
                temp_diff = estimated_temp - HUMAN_TEMP_THRESHOLD_C
                confidence = min(0.95, 0.5 + (temp_diff / 15.0) * 0.45)
                confidence = max(0.1, confidence)
                
                hotspots.append(Hotspot(
                    x=int(x), y=int(y),
                    width=int(w), height=int(h),
                    area=float(area),
                    max_intensity=max_intensity,
                    estimated_temp=estimated_temp,
                    confidence=confidence
                ))
        
        # Sort by confidence
        hotspots.sort(key=lambda h: h.confidence, reverse=True)
        
        return hotspots, binary


# ============ UNIFIED FRAME PIPELINE ============

class ThermalFramePipeline:
    """
    Single source of truth for thermal frames.
    
    Provides synchronized:
    - Frame display (MJPEG)
    - Hotspot detection
    - Alert generation
    """
    
    def __init__(self, source: VideoSource, on_detection: Optional[Callable] = None):
        self.source = source
        self.detector = ThermalDetector(adaptive=True, min_area=40)
        self.on_detection = on_detection
        
        self.frame_number = 0
        self.current_frame = None
        self.current_hotspots: List[Hotspot] = []
        
        # Alert throttling (prevent flooding)
        self.alert_cooldown = 3.0  # seconds
        self.last_alert_time = 0
        
        # Stats
        self.detection_count = 0
        self.alert_count = 0
    
    def process_next(self) -> Optional[np.ndarray]:
        """
        Get next frame, detect hotspots, trigger alerts if needed.
        
        Returns:
            Annotated frame ready for display, or None if no frame
        """
        frame = self.source.get_frame()
        if frame is None:
            return None
        
        self.frame_number += 1
        self.current_frame = frame.copy()
        timestamp = datetime.utcnow()
        
        # Detect on THIS frame
        self.current_hotspots, binary = self.detector.process(frame)
        
        # Filter high-confidence detections
        valid = [h for h in self.current_hotspots if h.confidence >= 0.6]
        
        if valid:
            self.detection_count += 1
            
            # Check cooldown
            now = time.time()
            if (now - self.last_alert_time) >= self.alert_cooldown:
                self.last_alert_time = now
                self.alert_count += 1
                
                # Create detection event
                event = DetectionEvent(
                    hotspots=valid[:3],  # Top 3
                    timestamp=timestamp,
                    frame_number=self.frame_number,
                    total_count=len(valid)
                )
                
                # Trigger callback (async-safe)
                if self.on_detection:
                    self.on_detection(event)
        
        # Annotate frame with bounding boxes
        return self._annotate(frame, self.current_hotspots)
    
    def _annotate(self, frame: np.ndarray, hotspots: List[Hotspot]) -> np.ndarray:
        """Draw bounding boxes on frame."""
        annotated = frame.copy()
        
        for h in hotspots:
            # Color based on confidence (green=high, yellow=medium, red=low)
            if h.confidence >= 0.7:
                color = (0, 255, 0)  # Green
            elif h.confidence >= 0.5:
                color = (0, 255, 255)  # Yellow
            else:
                color = (0, 165, 255)  # Orange
            
            # Draw rectangle
            cv2.rectangle(annotated, (h.x, h.y), (h.x + h.width, h.y + h.height), color, 2)
            
            # Draw label
            label = f"{h.estimated_temp:.0f}C ({h.confidence:.0%})"
            cv2.putText(annotated, label, (h.x, h.y - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        
        # Frame info overlay
        info = f"Frame: {self.frame_number} | Detections: {len(hotspots)} | Alerts: {self.alert_count}"
        cv2.putText(annotated, info, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return annotated
    
    def get_stats(self) -> dict:
        """Return pipeline statistics."""
        return {
            "frame_number": self.frame_number,
            "detection_count": self.detection_count,
            "alert_count": self.alert_count,
            "current_hotspots": len(self.current_hotspots)
        }


# ============ ASYNC STREAM GENERATOR ============

async def generate_mjpeg_stream(pipeline: ThermalFramePipeline, fps: float = 15):
    """
    Async generator for MJPEG stream.
    
    Each frame is:
    1. Fetched from source
    2. Processed for detection
    3. Annotated with bounding boxes
    4. Encoded as JPEG
    5. Yielded for HTTP streaming
    """
    frame_delay = 1.0 / fps
    
    while True:
        start = time.time()
        
        frame = pipeline.process_next()
        
        if frame is not None:
            # Encode as JPEG
            _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + 
                jpeg.tobytes() + 
                b'\r\n'
            )
        
        # Maintain target FPS
        elapsed = time.time() - start
        if elapsed < frame_delay:
            await asyncio.sleep(frame_delay - elapsed)


# ============ TEST ============

if __name__ == "__main__":
    import sys
    
    video_path = sys.argv[1] if len(sys.argv) > 1 else "dataset/test2.mp4"
    
    source = VideoSource(video_path)
    if not source.is_available():
        print(f"Cannot open {video_path}")
        sys.exit(1)
    
    def on_detect(event: DetectionEvent):
        print(f"[ALERT] Frame {event.frame_number}: {event.total_count} hotspots")
        for h in event.hotspots:
            print(f"  -> {h.estimated_temp:.1f}°C, conf={h.confidence:.0%}")
    
    pipeline = ThermalFramePipeline(source, on_detection=on_detect)
    
    print("Processing frames... (Ctrl+C to stop)")
    while True:
        frame = pipeline.process_next()
        if frame is not None:
            cv2.imshow("Thermal Detection", frame)
            if cv2.waitKey(66) & 0xFF == ord('q'):  # ~15 FPS
                break
    
    cv2.destroyAllWindows()
    print(f"Stats: {pipeline.get_stats()}")
