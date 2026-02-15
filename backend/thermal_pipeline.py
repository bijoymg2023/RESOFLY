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
from typing import List, Optional, Tuple, Callable
from dataclasses import dataclass

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
    circularity: float = 0.0  # 1.0 = perfect circle (Head from top view)
    convexity: float = 0.0    # 1.0 = convex (Human), <0.8 = jagged (Noise)
    inertia: float = 0.0      # 1.0 = circle, 0.0 = line
    track_id: Optional[int] = None
    is_confirmed: bool = False # Passed probation check?


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
    
    Best possible quality from this sensor:
    - Native: 80x62 pixels (4,960 thermal pixels)
    - Display: 960x744 (12x upscale — sweet spot for quality vs bandwidth)
    - Detection: runs on 480x372 (6x) for speed
    """
    
    # Display resolution (8x upscale — standard 640x480-ish)
    OUTPUT_WIDTH = 640
    OUTPUT_HEIGHT = 496
    
    # Detection resolution (2x — fast for contour ops)
    DETECT_WIDTH = 160
    DETECT_HEIGHT = 124
    
    def __init__(self):
        self._available = False
        self.camera = None
        self.fps = 5  # Hardware limited ~5 FPS
        self.frame_count = 0  # Live = unlimited
        self._prev_frame = None  # For temporal smoothing
        
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
            
            # --- Best possible quality pipeline for 80x62 sensor ---
            
            # 1. Normalize to full 0-255 range
            frame = cv2.normalize(frame, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            
            # 2. Temporal smoothing: blend with previous frame to reduce
            #    frame-to-frame sensor noise flicker (huge quality boost)
            if self._prev_frame is not None:
                frame = cv2.addWeighted(frame, 0.6, self._prev_frame, 0.4, 0)
            self._prev_frame = frame.copy()
            
            # 3. Enhance Contrast (CLAHE) - Make people POP from background
            # Clip limit 2.0, Grid size 8x8 is standard for thermal
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            frame = clahe.apply(frame)
            
            # 4. Denoise lightly (preserve edges)
            frame = cv2.GaussianBlur(frame, (3, 3), 0)
            
            # 5. Float32 upscale to display resolution
            # CUBIC is sharper than Linear.
            fframe = frame.astype(np.float32)
            upscaled = cv2.resize(fframe, (self.OUTPUT_WIDTH, self.OUTPUT_HEIGHT),
                                  interpolation=cv2.INTER_CUBIC)
            
            # 6. Sharpening (Unsharp Mask) ENABLED for RECOGNITION
            # Enhanced strength (2.0) to make edges "pop"
            gaussian_3 = cv2.GaussianBlur(upscaled, (0, 0), 2.0)
            upscaled = cv2.addWeighted(upscaled, 2.0, gaussian_3, -1.0, 0)
            
            # 6. Convert back to uint8
            upscaled = np.clip(upscaled, 0, 255).astype(np.uint8)
            
            return upscaled
        return None
    
    def get_detect_frame(self, display_frame: np.ndarray) -> np.ndarray:
        """Downscale display frame for fast detection processing."""
        return cv2.resize(display_frame, (self.DETECT_WIDTH, self.DETECT_HEIGHT),
                          interpolation=cv2.INTER_AREA)
    
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
        self.blur_kernel = max(blur_kernel, 7)  # Larger blur for cleaner detection
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
            thresh_val = int(min(200, mean + 2.0 * std))  # Higher threshold = fewer false positives
            thresh_val = max(thresh_val, HUMAN_TEMP_THRESHOLD_INTENSITY)
        else:
            thresh_val = HUMAN_TEMP_THRESHOLD_INTENSITY
        
        # Binary threshold
        _, binary = cv2.threshold(blurred, thresh_val, 255, cv2.THRESH_BINARY)
        
        # Morphological cleanup
        # DRONE VIEW OPTIMIZATION:
        # Use smaller kernel for open/close to preserve small details
        # DO NOT DILATE heavily, or heads close together will merge into one blob.
        kernel = np.ones((3, 3), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)   # Remove noise
        # binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)  # Fill gaps (Optional, maybe skip for heads)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        hotspots = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            
            if area >= self.min_area:
                x, y, w, h = cv2.boundingRect(cnt)
                
                # --- Advanced Shape Analysis ---
                
                # 1. Circularity like before (Head detection)
                perimeter = cv2.arcLength(cnt, True)
                circularity = 0.0
                if perimeter > 0:
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                
                # 2. Convexity (Is it a smooth blob or a jagged mess?)
                # Hull = "Rubber band" around the shape
                hull = cv2.convexHull(cnt)
                hull_area = cv2.contourArea(hull)
                convexity = float(area) / hull_area if hull_area > 0 else 0.0
                
                # 3. Inertia (Is it elongated?)
                # Fit an ellipse
                inertia = 0.0
                if len(cnt) >= 5: # Need 5 points for ellipse
                    (e_center, (e_w, e_h), angle) = cv2.fitEllipse(cnt)
                    major_axis = max(e_w, e_h)
                    minor_axis = min(e_w, e_h)
                    if major_axis > 0:
                        inertia = minor_axis / major_axis
                
                # --- Temperature & Confidence ---
                
                # Get max intensity in region
                mask = np.zeros(gray.shape, dtype=np.uint8)
                cv2.drawContours(mask, [cnt], -1, 255, -1)
                max_intensity = float(np.max(gray[mask == 255]))
                estimated_temp = intensity_to_temperature(max_intensity)
                
                # Scoring Logic
                temp_diff = estimated_temp - HUMAN_TEMP_THRESHOLD_C
                confidence = min(0.95, 0.5 + (temp_diff / 15.0) * 0.45)
                
                # Boost for good shapes
                if circularity > 0.6: confidence += 0.1
                if convexity > 0.9:   confidence += 0.1  # Solid blob
                if inertia > 0.5:     confidence += 0.05 # Not a thin line
                
                # Penalize jagged noise
                if convexity < 0.7:   confidence -= 0.2
                
                confidence = max(0.1, min(1.0, confidence))
                
                hotspots.append(Hotspot(
                    x=int(x), y=int(y),
                    width=int(w), height=int(h),
                    area=float(area),
                    max_intensity=max_intensity,
                    estimated_temp=estimated_temp,
                    confidence=confidence,
                    circularity=circularity,
                    convexity=convexity,
                    inertia=inertia
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
        # min_area=25 on 160x124 detect frame (approx 100 pixels on 640x480)
        # This allows detecting people much further away (small heat blobs)
        self.detector = ThermalDetector(adaptive=True, min_area=25)
        self.tracker = CentroidTracker(max_disappeared=50, max_distance=120)
        self.on_detection = on_detection
        
        self.frame_number = 0
        self.current_frame = None
        self.current_hotspots: List[Hotspot] = []
        
        # Track which IDs we've already alerted on
        # Track timestamps for alerts to allow re-alerting
        # Dict[int, float] -> {track_id: last_alert_timestamp}
        self.alerted_ids: dict = {}
        
        # Stats
        self.detection_count = 0
        self.alert_count = 0
    
    def process_next(self) -> Optional[np.ndarray]:
        """
        Get next frame, detect hotspots, track objects, trigger alerts for NEW IDs.
        Detection runs on smaller frame for speed; boxes scaled up for display.
        """
        frame = self.source.get_frame()
        if frame is None:
            return None
        
        self.frame_number += 1
        self.current_frame = frame.copy()
        timestamp = datetime.utcnow()
        
        # 1. Detect hotspots on SMALLER frame for speed
        if hasattr(self.source, 'get_detect_frame'):
            detect_frame = self.source.get_detect_frame(frame)
            scale_x = frame.shape[1] / detect_frame.shape[1]
            scale_y = frame.shape[0] / detect_frame.shape[0]
        else:
            detect_frame = frame
            scale_x = scale_y = 1.0
        
        raw_hotspots, binary = self.detector.process(detect_frame)
        
        # Scale hotspot coordinates back to display resolution
        if scale_x != 1.0:
            for h in raw_hotspots:
                h.x = int(h.x * scale_x)
                h.y = int(h.y * scale_y)
                h.width = int(h.width * scale_x)
                h.height = int(h.height * scale_y)
        
        # 2. Prepare bounding boxes for tracker
        rects = []
        for h in raw_hotspots:
            if h.confidence >= 0.70:
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
                
                if dist < 120:  # Threshold to associate
                    if dist < min_dist:
                        min_dist = dist
                        best_match = h
            
            if best_match:
                # Assign ID to hotspot
                h = best_match
                h.track_id = object_id
                
                # --- PROBATION CHECK ---
                # Should we trust this object yet?
                # Check persistence count from tracker
                persistence = self.tracker.persistence.get(object_id, 0)
                is_confirmed = persistence >= self.tracker.probation_frames
                
                h.is_confirmed = is_confirmed
                tracked_hotspots.append(h)
                
                # Trigger Alert IF:
                # 1. New Alert Interval passed
                # 2. Object IS CONFIRMED (Passed probation)
                now = time.time()
                last_alert = self.alerted_ids.get(object_id, 0.0)
                
                if is_confirmed and (now - last_alert) > 5.0:
                    self.alerted_ids[object_id] = now
                    new_alerts.append(h)
                    self.alert_count += 1
        
        self.current_hotspots = tracked_hotspots
        
        # 5. Trigger Alerts (only for CONFIRMED objects)
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
        """Apply thermal colormap and draw clean bounding boxes on frame."""
        # Apply INFERNO colormap (purple->orange->yellow) — matches reference image
        if len(frame.shape) == 2:
            annotated = cv2.applyColorMap(frame, cv2.COLORMAP_INFERNO)
        else:
            annotated = frame.copy()
        
        # Filter for display
        # We show EVERYTHING, but style them differently based on 'confirmed' status
        visible = [h for h in hotspots if hasattr(h, 'track_id')]
        
        for h in visible:
            # Add padding
            pad = 8
            h_img, w_img = annotated.shape[:2]
            
            x = max(0, h.x - pad)
            y = max(0, h.y - pad)
            w = min(w_img - x, h.width + 2*pad)
            height = min(h_img - y, h.height + 2*pad)
            
            # --- STYLE: Confirmed vs Probation ---
            if h.is_confirmed:
                # Green = Confirmed Target
                color = (0, 255, 0)
                thickness = 2
                label = f"{h.estimated_temp:.0f}C | Life: {self._calculate_life_score(h)}%"
            else:
                # Gray = Probation (Acquiring...)
                color = (128, 128, 128)
                thickness = 1
                label = "..." # Minimal label for noise
                
                # Skip drawing noise if confidence is super low
                if h.confidence < 0.3: continue
            
            cv2.rectangle(annotated, (x, y), (x + w, y + height), color, thickness)
            
            # Draw Label (Only for confirmed or high confidence)
            if h.is_confirmed:
                (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
                cv2.rectangle(annotated, (x, y - text_h - 4), (x + text_w, y), (0,0,0), -1)
                cv2.putText(annotated, label, (x, y - 4), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
        
        # Minimal status bar
        active_targets = sum(1 for h in visible if h.is_confirmed)
        info = f"Targets: {active_targets} | Acquiring: {len(visible) - active_targets}"
        cv2.putText(annotated, info, (8, annotated.shape[0] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
        
        return annotated

    def _calculate_life_score(self, h: Hotspot) -> int:
        """Helper to scoring logic."""
        ideal_temp = 34.0
        diff = abs(h.estimated_temp - ideal_temp)
        temp_score = max(0, 100 - (diff * 4))
        
        shape_factor = 1.0
        if h.circularity > 0.6: shape_factor += 0.2
        if h.convexity > 0.9:   shape_factor += 0.1
        
        return int(min(100, temp_score * shape_factor))
    
    def get_stats(self) -> dict:
        """Return pipeline statistics."""
        return {
            "frame_number": self.frame_number,
            "detection_count": self.detection_count,
            "alert_count": self.alert_count,
            "current_hotspots": len(self.current_hotspots)
        }


# ============ ASYNC STREAM GENERATOR ============

async def generate_mjpeg_stream(pipeline: ThermalFramePipeline, fps: float = 8):
    """
    Async generator for MJPEG stream.
    
    Optimized for zero-lag streaming:
    - FPS=15 (Higher target to drain buffer faster)
    - JPEG quality 85 (visually identical to 100, ~3x smaller file size)
    - Minimal sleep to keep the stream responsive
    """
    frame_delay = 1.0 / fps
    last_jpeg = None
    
    while True:
        start = time.time()
        
        frame = pipeline.process_next()
        
        if frame is not None:
            # JPEG 80 = sweet spot for thermal clarity without huge lag
            _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            last_jpeg = jpeg
        
        if last_jpeg is not None:
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + 
                last_jpeg.tobytes() + 
                b'\r\n'
            )
        
        # Maintain target FPS
        elapsed = time.time() - start
        if elapsed < frame_delay:
            await asyncio.sleep(frame_delay - elapsed)
        else:
            await asyncio.sleep(0.01)  # Yield control even if behind


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
