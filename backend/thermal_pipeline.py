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
    track_id: Optional[int] = None  # Persistent object ID from tracker


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

class WaveshareSource:
    """
    Live thermal source from Waveshare 80x62 Thermal Camera HAT.
    Wraps the waveshare_thermal hardware driver for the unified pipeline.
    Upscales from native 80x62 to 640x496 for usable stream display.
    """
    
    # Output resolution (8x upscale from 80x62)
    OUTPUT_WIDTH = 640
    OUTPUT_HEIGHT = 496
    
    def __init__(self):
        self._available = False
        self.camera = None
        self.fps = 5  # Hardware limited ~5 FPS
        self.frame_count = 0  # Live = unlimited
        
        try:
            from waveshare_thermal import get_thermal_camera
            self.camera = get_thermal_camera()
            self._available = self.camera.is_available()
            if self._available:
                logger.info("WaveshareSource: Live 80x62 thermal camera connected")
            else:
                logger.info("WaveshareSource: Camera HAT not responding")
        except ImportError:
            logger.info("WaveshareSource: waveshare_thermal driver not available")
        except Exception as e:
            logger.warning(f"WaveshareSource: Init error: {e}")
    
    def get_frame(self) -> Optional[np.ndarray]:
        if not self._available or self.camera is None:
            return None
        
        frame = self.camera.get_frame()
        if frame is not None:
            # Ensure grayscale uint8
            if len(frame.shape) == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Upscale 80x62 → 640x496 with bicubic interpolation
            upscaled = cv2.resize(
                frame,
                (self.OUTPUT_WIDTH, self.OUTPUT_HEIGHT),
                interpolation=cv2.INTER_CUBIC
            )
            
            return upscaled
        return None
    
    def is_available(self) -> bool:
        return self._available
    
    def get_temperature_frame(self) -> Optional[np.ndarray]:
        """Get raw temperature data in °C (for heatmap display)."""
        if self.camera:
            return self.camera.get_temperature_frame()
        return None
    
    def get_max_temperature(self) -> Optional[float]:
        """Get max temp in current frame."""
        if self.camera:
            return self.camera.get_max_temperature()
        return None


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
            thresh_val = int(min(180, mean + 1.5 * std))  # Clamp to 180 to prevent runaway
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

from centroid_tracker import CentroidTracker

class ThermalFramePipeline:
    """
    Single source of truth for thermal frames.
    
    Provides synchronized:
    - Frame display (MJPEG)
    - Hotspot detection (with tracking)
    - Alert generation (per unique ID)
    """
    
    def __init__(self, source: VideoSource, on_detection: Optional[Callable] = None):
        self.source = source
        self.detector = ThermalDetector(adaptive=True, min_area=30)
        self.tracker = CentroidTracker(max_disappeared=10, max_distance=50)
        self.on_detection = on_detection
        
        self.frame_number = 0
        self.current_frame = None
        self.current_hotspots: List[Hotspot] = []
        
        # Track which IDs we've already alerted on
        self.alerted_ids: Set[int] = set()
        
        # Stats
        self.detection_count = 0
        self.alert_count = 0
    
    def process_next(self) -> Optional[np.ndarray]:
        """
        Get next frame, detect hotspots, track objects, trigger alerts for NEW IDs.
        """
        frame = self.source.get_frame()
        if frame is None:
            return None
        
        self.frame_number += 1
        self.current_frame = frame.copy()
        timestamp = datetime.utcnow()
        
        # 1. Detect hotspots on THIS frame
        raw_hotspots, binary = self.detector.process(frame)
        
        # 2. Prepare bounding boxes for tracker
        rects = []
        for h in raw_hotspots:
            if h.confidence >= 0.5:
                rects.append((h.x, h.y, h.width, h.height))
        
        # 3. Update Tracker
        objects = self.tracker.update(rects)
        
        # 4. Match tracked objects back to hotspots
        tracked_hotspots = []
        new_alerts = []
        
        for (object_id, centroid) in objects.items():
            # Find the hotspot that matches this centroid (closest)
            best_match = None
            min_dist = float('inf')
            
            for h in raw_hotspots:
                cx = h.x + h.width // 2
                cy = h.y + h.height // 2
                dist = np.sqrt((cx - centroid[0])**2 + (cy - centroid[1])**2)
                
                if dist < 50:  # Threshold to associate
                    if dist < min_dist:
                        min_dist = dist
                        best_match = h
            
            if best_match:
                # Assign ID to hotspot
                h = best_match
                h.track_id = object_id  # We'll need to add this field to Hotspot dataclass
                tracked_hotspots.append(h)
                
                # Check if this is a NEW object we haven't alerted on yet
                if object_id not in self.alerted_ids:
                    self.alerted_ids.add(object_id)
                    new_alerts.append(h)
                    self.alert_count += 1
        
        self.current_hotspots = tracked_hotspots
        
        # 5. Trigger Alerts (only for NEW objects)
        if new_alerts:
            self.detection_count += 1
            
            event = DetectionEvent(
                hotspots=new_alerts,
                timestamp=timestamp,
                frame_number=self.frame_number,
                total_count=len(tracked_hotspots)
            )
            
            if self.on_detection:
                self.on_detection(event)
        
        # Annotate frame
        return self._annotate(frame, self.current_hotspots)
    
    def _annotate(self, frame: np.ndarray, hotspots: List[Hotspot]) -> np.ndarray:
        """Apply thermal colormap and draw bounding boxes + IDs on frame."""
        # Apply thermal colormap for display (INFERNO: black→purple→orange→yellow)
        if len(frame.shape) == 2:
            annotated = cv2.applyColorMap(frame, cv2.COLORMAP_INFERNO)
        else:
            annotated = frame.copy()
        
        h_frame, w_frame = annotated.shape[:2]
        # Scale factor for text/lines (bigger frames = bigger text)
        scale = max(0.4, w_frame / 640.0)
        thickness = max(1, int(scale * 2))
        
        for h in hotspots:
            if not hasattr(h, 'track_id'):
                continue
                
            # Bright colors that stand out against INFERNO colormap
            color = (0, 255, 0) if h.confidence >= 0.7 else (0, 255, 255)
            
            # Draw rectangle
            cv2.rectangle(annotated, (h.x, h.y), (h.x + h.width, h.y + h.height), color, thickness)
            
            # Draw label with ID
            label = f"ID:{h.track_id} {h.estimated_temp:.0f}C"
            cv2.putText(annotated, label, (h.x, h.y - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, scale * 0.5, color, thickness)
        
        # Frame info overlay (white text with dark shadow for readability)
        info = f"Frame: {self.frame_number} | Objects: {len(hotspots)} | Alerts: {self.alert_count}"
        cv2.putText(annotated, info, (10, int(20 * scale)), cv2.FONT_HERSHEY_SIMPLEX, scale * 0.45, (0, 0, 0), thickness + 1)
        cv2.putText(annotated, info, (10, int(20 * scale)), cv2.FONT_HERSHEY_SIMPLEX, scale * 0.45, (255, 255, 255), thickness)
        
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
