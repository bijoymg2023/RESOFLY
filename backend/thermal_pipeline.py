"""
Synchronized Thermal Detection Pipeline (ResoFly Mk-IV)
=======================================================
Robust, high-accuracy thermal detection optimized for Raspberry Pi 4 (80x62 Sensor).
Features:
- Adaptive Thresholding (Mean + Offset)
- Morphological Noise Reduction
- Unique Hotspot Tracking (Centroid)
- Smart Alert Logic (Persistence + Cooldowns)
"""

import cv2
import numpy as np
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Callable, Dict
from dataclasses import dataclass, field

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
    
    # Shape metrics
    circularity: float = 0.0
    aspect_ratio: float = 0.0
    
    # Tracking info
    track_id: Optional[int] = None
    is_confirmed: bool = False  # Passed persistence check?
    first_seen: float = 0.0
    last_seen: float = 0.0
    max_temp_seen: float = 0.0
    
    def to_dict(self):
        return {
            "x": self.x, "y": self.y, "w": self.width, "h": self.height,
            "temp": self.estimated_temp, "conf": self.confidence,
            "id": self.track_id
        }


@dataclass
class DetectionEvent:
    """Alert event with full metadata."""
    hotspots: List[Hotspot]
    timestamp: datetime
    frame_number: int
    total_count: int


# ============ CONFIGURATION ============

# Human body detection threshold (Lower than 37°C due to distance/clothing)
HUMAN_TEMP_THRESHOLD_C = 28.0 

# ============ TEMPERATURE HELPER ============

def intensity_to_temperature(intensity: float, min_temp: float = 15.0, max_temp: float = 45.0) -> float:
    """Map 0-255 pixel intensity to estimated temperature."""
    normalized = intensity / 255.0
    return min_temp + normalized * (max_temp - min_temp)

def temperature_to_intensity(temp: float, min_temp: float = 15.0, max_temp: float = 45.0) -> int:
    """Convert temperature to pixel intensity."""
    normalized = (temp - min_temp) / (max_temp - min_temp)
    return int(np.clip(normalized * 255, 0, 255))

HUMAN_TEMP_INTENSITY = temperature_to_intensity(HUMAN_TEMP_THRESHOLD_C)


# ============ FRAME SOURCES ============

class WaveshareSource:
    """Live thermal source from Waveshare 80x62 Thermal Camera HAT."""
    
    OUTPUT_WIDTH = 512
    OUTPUT_HEIGHT = 396
    DETECT_WIDTH = 160 # 2x native (80->160) for better contour definition
    DETECT_HEIGHT = 124
    
    def __init__(self):
        self._available = False
        self.camera = None
        self.fps = 8
        self.frame_count = 0
        
        try:
            from waveshare_thermal import get_thermal_camera
            self.camera = get_thermal_camera()
            self._available = self.camera.is_available()
            if self._available:
                logger.info("WaveshareSource: Live thermal camera connected")
        except:
            logger.warning("WaveshareSource: Driver not available")
    
    def get_frame(self) -> Optional[np.ndarray]:
        if not self._available or self.camera is None:
            return None
            
        frame = self.camera.get_frame()
        if frame is None: return None
        
        # Normalize and Enhancement Pipeline
        # 1. Normalize
        frame = cv2.normalize(frame, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        
        # 2. Upscale for Display (Smooth Cubic)
        # Upscale directly to output size for display
        display_frame = cv2.resize(frame, (self.OUTPUT_WIDTH, self.OUTPUT_HEIGHT), interpolation=cv2.INTER_CUBIC)
        
        # 3. Apply Colormap (INFERNO is best for heat)
        # display_frame = cv2.applyColorMap(display_frame, cv2.COLORMAP_INFERNO) 
        # Wait, the pipeline expects grayscale here. We colorize later.
        
        return display_frame

    def get_detect_frame(self, display_frame: np.ndarray) -> np.ndarray:
        """Downscale for detection speed."""
        return cv2.resize(display_frame, (self.DETECT_WIDTH, self.DETECT_HEIGHT), interpolation=cv2.INTER_AREA)

    def is_available(self) -> bool: return self._available
    
    def get_max_temperature(self) -> Optional[float]:
        return self.camera.get_max_temperature() if self.camera else None


class VideoSource:
    """Reads frames from a video file."""
    def __init__(self, video_path: str):
        self.cap = cv2.VideoCapture(str(video_path))
        self._available = self.cap.isOpened()
    
    def get_frame(self) -> Optional[np.ndarray]:
        if not self._available: return None
        ret, frame = self.cap.read()
        if not ret:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
        if ret and len(frame.shape) == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return frame
            
    def is_available(self) -> bool: return self._available


# ============ DETECTION LOGIC ============

class ThermalDetector:
    """
    Robust thermal hotspot detector.
    Uses Adaptive Thresholding + Morphology for clean blobs.
    """
    
    def __init__(self, min_area: int = 25):
        self.min_area = min_area
        # Kernel for morphological opening (removes small noise)
        self.morph_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        
    def process(self, frame: np.ndarray) -> Tuple[List[Hotspot], np.ndarray]:
        """Process frame -> detections."""
        
        # 1. Gaussian Blur (Reduce high-freq noise)
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        
        # 2. Adaptive Thresholding
        # Dynamic offset based on scene statistics
        mean_val = np.mean(blurred)
        std_val = np.std(blurred)
        
        # Threshold = Mean + 2.5 * StdDev (Isolates significant heat sources)
        # Clamp to avoid thresholding too low if scene is flat
        thresh_val = mean_val + 2.5 * std_val
        thresh_val = max(thresh_val, HUMAN_TEMP_INTENSITY) # Respect detection floor
        thresh_val = min(thresh_val, 240) # Allow very hot saturation
        
        _, binary = cv2.threshold(blurred, thresh_val, 255, cv2.THRESH_BINARY)
        
        # 3. Morphological Cleanup (Opening = Erode -> Dilate)
        # Removes small speckles, keeps solid blobs
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, self.morph_kernel, iterations=1)
        
        # 4. Contour Detection
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        hotspots = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            
            # Filter 1: Minimum Area
            if area < self.min_area:
                continue
                
            # Filter 2: Bounding Box
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = float(w) / h
            
            # Filter 3: Aspect Ratio sanity check
            # Humans are usually taller than wide (AR < 1.0) or squat (AR < 2.5 if lying down)
            # Eliminate extremely thin lines (noise lines)
            if aspect_ratio > 4.0 or aspect_ratio < 0.2:
                continue
            
            # Get max intensity stats
            mask = np.zeros(frame.shape, dtype=np.uint8)
            cv2.drawContours(mask, [cnt], -1, 255, -1)
            # Fast numpy masking
            roi_vals = frame[y:y+h, x:x+w]
            max_val = np.max(roi_vals) if roi_vals.size > 0 else 0
            
            estimated_temp = intensity_to_temperature(max_val)
            
            # --- CONFIDENCE SCORING ---
            # Score = (Temp / Max) * 0.5 + (Area / Ideal) * 0.3 + (Shape) * 0.2
            
            # Temp Score
            temp_score = min(1.0, (estimated_temp - HUMAN_TEMP_THRESHOLD_C) / 10.0)
            if temp_score < 0: temp_score = 0
            
            # Area Score (Bigger = Better, up to a point)
            area_score = min(1.0, area / 200.0)
            
            # Shape Score (Solid blobs > Noise)
            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            solidity = float(area) / hull_area if hull_area > 0 else 0
            
            confidence = (temp_score * 0.5) + (area_score * 0.3) + (solidity * 0.2)
            confidence = min(0.99, max(0.1, confidence))
            
            hotspots.append(Hotspot(
                x=x, y=y, width=w, height=h,
                area=area,
                max_intensity=float(max_val),
                estimated_temp=estimated_temp,
                confidence=confidence,
                aspect_ratio=aspect_ratio
            ))
            
        # Sort by confidence
        hotspots.sort(key=lambda h: h.confidence, reverse=True)
        return hotspots, binary


# ============ MAIN PIPELINE ============

from centroid_tracker import CentroidTracker

class ThermalFramePipeline:
    """
    Orchestrates detection, tracking, and alerting.
    Integration point for Server.
    """
    
    def __init__(self, source, on_detection: Optional[Callable] = None):
        self.source = source
        self.detector = ThermalDetector(min_area=20) # 20px on 160x124 grid
        self.tracker = CentroidTracker(max_disappeared=10, max_distance=60)
        self.on_detection = on_detection
        
        self.frame_number = 0
        self.current_hotspots = []
        
        # --- TRACKING MEMORY ---
        # Stores history for ID persistence
        # { track_id: { 'first_seen': ts, 'last_alert': ts, 'max_temp': val, 'confirmed': bool } }
        self.track_memory = {} 
        
    def process_next(self) -> Optional[np.ndarray]:
        """Main loop step: Get Frame -> Detect -> Track -> Alert."""
        try:
            full_frame = self.source.get_frame() # 512x396
            if full_frame is None: return None
            
            self.frame_number += 1
            timestamp = datetime.utcnow()
            now_ts = time.time()
            
            # 1. Detection (Downscaled)
            if hasattr(self.source, 'get_detect_frame'):
                detect_frame = self.source.get_detect_frame(full_frame)
                scale_x = full_frame.shape[1] / detect_frame.shape[1]
                scale_y = full_frame.shape[0] / detect_frame.shape[0]
            else:
                detect_frame = full_frame
                scale_x = scale_y = 1.0
                
            raw_hotspots, _ = self.detector.process(detect_frame)
            
            # Scale coordinates back to full frame
            rects = []
            for h in raw_hotspots:
                h.x = int(h.x * scale_x)
                h.y = int(h.y * scale_y)
                h.width = int(h.width * scale_x)
                h.height = int(h.height * scale_y)
                rects.append((h.x, h.y, h.width, h.height))
                
            # 2. Update Tracker
            # CentroidTracker returns {id: (cx, cy)}
            objects = self.tracker.update(rects)
            
            tracked_hotspots = []
            new_alerts = []
            
            # 3. Associate Hotspots with IDs
            # We need to map the raw hotspots to the track IDs based on distance
            # to preserve the rich metadata (temp, confidence)
            
            used_hotspots = set()
            
            for obj_id, centroid in objects.items():
                # Find closest raw hotspot
                best_h = None
                min_dist = 99999
                
                for i, h in enumerate(raw_hotspots):
                    if i in used_hotspots: continue
                    cx, cy = h.x + h.width//2, h.y + h.height//2
                    dist = np.sqrt((cx - centroid[0])**2 + (cy - centroid[1])**2)
                    
                    if dist < 50 and dist < min_dist: # Association threshold
                        min_dist = dist
                        best_h = h
                        best_h_idx = i
                
                # --- MEMORY UPDATE ---
                mem = self.track_memory.setdefault(obj_id, {
                    'first_seen': now_ts,
                    'last_alert': 0,
                    'max_temp': 0,
                    'persistence': 0,
                    'confirmed': False
                })
                
                final_hotspot = None
                
                if best_h:
                    # Found live match
                    used_hotspots.add(best_h_idx)
                    best_h.track_id = obj_id
                    
                    # Update Memory
                    mem['max_temp'] = max(mem['max_temp'], best_h.estimated_temp)
                    mem['persistence'] += 1
                    
                    final_hotspot = best_h
                else:
                    # Lost visual but tracker holding it (probation)
                    # Create a "Ghost" hotspot from last known pos?
                    # For now, we skip ghosts in visual output to clean up display
                    continue
                
                # --- CONFIRMATION LOGIC ---
                # Must be seen for 3+ consecutive frames to be real
                if mem['persistence'] >= 3:
                    mem['confirmed'] = True
                    final_hotspot.is_confirmed = True
                
                # --- ALERT LOGIC ---
                # 1. Must be Confirmed
                # 2. Cooldown: > 60s since last alert OR significant temp rise (+2C)
                
                if mem['confirmed']:
                    time_since = now_ts - mem['last_alert']
                    temp_gain = final_hotspot.estimated_temp - (mem['max_temp'] - 2.0) # Approx check
                    
                    should_alert = False
                    
                    # Initial Alert
                    if mem['last_alert'] == 0:
                        should_alert = True
                    
                    # Cooldown Expired (Re-alert)
                    elif time_since > 60.0:
                        should_alert = True
                        
                    # Significant Temp Rise (Urgent update)
                    elif final_hotspot.estimated_temp > (mem['max_temp'] + 2.0):
                        should_alert = True
                    
                    if should_alert:
                        mem['last_alert'] = now_ts
                        mem['max_temp'] = final_hotspot.estimated_temp # Update baseline
                        new_alerts.append(final_hotspot)
                
                tracked_hotspots.append(final_hotspot)

            # Cleanup Memory for dead IDs
            active_ids = set(objects.keys())
            for tid in list(self.track_memory.keys()):
                if tid not in active_ids:
                    del self.track_memory[tid]

            self.current_hotspots = tracked_hotspots
            
            # 4. Trigger Events
            if new_alerts and self.on_detection:
                event = DetectionEvent(
                    hotspots=new_alerts,
                    timestamp=timestamp,
                    frame_number=self.frame_number,
                    total_count=len(tracked_hotspots)
                )
                self.on_detection(event)

            # 5. Annotate
            return self._annotate(full_frame, tracked_hotspots)

        except Exception as e:
            logger.error(f"Pipeline Error: {e}")
            import traceback
            traceback.print_exc()
            return None # Fail safe

    def _annotate(self, frame: np.ndarray, hotspots: List[Hotspot]) -> np.ndarray:
        """Draw bounding boxes and UI on frame."""
        # Convert to BGR if needed
        if len(frame.shape) == 2:
            display = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            # Optional: Apply thermal colormap
            display = cv2.applyColorMap(frame, cv2.COLORMAP_INFERNO)
        else:
            display = frame.copy()
            
        for h in hotspots:
            # Color: Green (Confirmed), Yellow (Probation)
            color = (0, 255, 0) if h.is_confirmed else (0, 255, 255)
            thick = 2 if h.is_confirmed else 1
            
            # Draw Box
            cv2.rectangle(display, (h.x, h.y), (h.x + h.width, h.y + h.height), color, thick)
            
            # Draw Label
            label = f"#{h.track_id} {h.estimated_temp:.0f}C"
            cv2.putText(display, label, (h.x, h.y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
            
        # Status Bar
        count = sum(1 for h in hotspots if h.is_confirmed)
        cv2.putText(display, f"Targets: {count}", (10, display.shape[0]-10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
        return display

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
