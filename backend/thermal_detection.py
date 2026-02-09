"""
SAR Thermal Life Detection Module
=================================
Clean, frame-driven pipeline for detecting thermal signatures.
Works with both dataset frames and live camera input.

Usage:
    detector = ThermalDetector()
    hotspots = detector.process_frame(frame)
    if hotspots:
        send_alert(hotspots)
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class Hotspot:
    """A detected thermal hotspot."""
    x: int
    y: int
    width: int
    height: int
    area: float
    max_intensity: float
    confidence: float


class ThermalDetector:
    """
    Detects thermal hotspots (humans/animals) in thermal frames.
    
    The detection pipeline:
    1. Preprocess: Normalize and blur for noise reduction
    2. Threshold: Adaptive threshold to isolate hot regions
    3. Contours: Find and filter by area
    4. Score: Assign confidence based on intensity
    """
    
    def __init__(
        self,
        threshold_value: int = 200,
        min_area: int = 40,
        blur_kernel: int = 5,
        adaptive: bool = True
    ):
        self.threshold_value = threshold_value
        self.min_area = min_area
        self.blur_kernel = blur_kernel
        self.adaptive = adaptive
    
    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Normalize and denoise the frame."""
        # Ensure grayscale
        if len(frame.shape) == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Normalize to 0-255
        frame = cv2.normalize(frame, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        
        # Gaussian blur for noise reduction
        frame = cv2.GaussianBlur(frame, (self.blur_kernel, self.blur_kernel), 0)
        
        return frame
    
    def detect(self, frame: np.ndarray) -> Tuple[List[Hotspot], np.ndarray]:
        """
        Detect thermal hotspots in a preprocessed frame.
        
        Returns:
            hotspots: List of detected hotspots
            binary: The thresholded binary image (for visualization)
        """
        # Adaptive thresholding: use frame statistics
        if self.adaptive:
            mean = np.mean(frame)
            std = np.std(frame)
            thresh_val = min(250, int(mean + 1.5 * std))
            thresh_val = max(thresh_val, 150)  # Don't go too low
        else:
            thresh_val = self.threshold_value
        
        # Binary threshold
        _, binary = cv2.threshold(frame, thresh_val, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        hotspots = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            
            if area >= self.min_area:
                x, y, w, h = cv2.boundingRect(cnt)
                
                # Get max intensity in this region
                mask = np.zeros(frame.shape, dtype=np.uint8)
                cv2.drawContours(mask, [cnt], -1, 255, -1)
                max_intensity = float(np.max(frame[mask == 255]))
                
                # Confidence based on how much hotter than threshold
                intensity_diff = max_intensity - thresh_val
                confidence = min(0.95, 0.5 + (intensity_diff / 100) * 0.45)
                
                hotspots.append(Hotspot(
                    x=int(x),
                    y=int(y),
                    width=int(w),
                    height=int(h),
                    area=float(area),
                    max_intensity=max_intensity,
                    confidence=confidence
                ))
        
        # Sort by confidence (highest first)
        hotspots.sort(key=lambda h: h.confidence, reverse=True)
        
        return hotspots, binary
    
    def process_frame(self, frame: np.ndarray) -> List[Hotspot]:
        """
        Full pipeline: preprocess + detect.
        
        Args:
            frame: Raw thermal frame (grayscale or BGR)
        
        Returns:
            List of hotspots, sorted by confidence
        """
        if frame is None:
            return []
        
        processed = self.preprocess(frame)
        hotspots, _ = self.detect(processed)
        
        return hotspots


class FrameSource:
    """Base class for frame sources."""
    
    def get_frame(self) -> Optional[np.ndarray]:
        raise NotImplementedError
    
    def is_available(self) -> bool:
        return False


class VideoSource(FrameSource):
    """Reads frames from a video file (for dataset testing)."""
    
    def __init__(self, video_path: str):
        self.path = Path(video_path)
        self.cap = cv2.VideoCapture(str(self.path))
        self._available = self.cap.isOpened()
    
    def get_frame(self) -> Optional[np.ndarray]:
        if not self._available:
            return None
        
        ret, frame = self.cap.read()
        if not ret:
            # Loop the video
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
        
        if ret and len(frame.shape) == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        return frame if ret else None
    
    def is_available(self) -> bool:
        return self._available


class CameraSource(FrameSource):
    """Reads frames from a thermal camera (placeholder for hardware)."""
    
    def __init__(self):
        self._available = False
        # TODO: Initialize actual camera hardware here
    
    def get_frame(self) -> Optional[np.ndarray]:
        # TODO: Read from actual camera
        return None
    
    def is_available(self) -> bool:
        return self._available


# ============ MAIN DETECTION LOOP ============

def run_detection_loop(
    source: FrameSource,
    on_detection: callable,
    fps: float = 5.0,
    min_confidence: float = 0.6
):
    """
    Main detection loop - runs continuously.
    
    Args:
        source: Frame source (video or camera)
        on_detection: Callback function(hotspots, frame) called when hotspots found
        fps: Processing rate (frames per second)
        min_confidence: Minimum confidence to trigger callback
    """
    import time
    
    detector = ThermalDetector(adaptive=True, min_area=40)
    frame_delay = 1.0 / fps
    
    print(f"[THERMAL] Starting detection loop at {fps} FPS")
    
    while True:
        start = time.time()
        
        frame = source.get_frame()
        if frame is not None:
            hotspots = detector.process_frame(frame)
            
            # Filter by confidence
            valid = [h for h in hotspots if h.confidence >= min_confidence]
            
            if valid:
                print(f"[THERMAL] Detected {len(valid)} hotspots (conf >= {min_confidence})")
                on_detection(valid, frame)
        
        # Maintain target FPS
        elapsed = time.time() - start
        if elapsed < frame_delay:
            time.sleep(frame_delay - elapsed)


# ============ SIMPLE TEST ============

if __name__ == "__main__":
    # Test with a video file
    import sys
    
    video_path = sys.argv[1] if len(sys.argv) > 1 else "dataset/test2.mp4"
    source = VideoSource(video_path)
    
    if not source.is_available():
        print(f"Cannot open {video_path}")
        sys.exit(1)
    
    def on_detect(hotspots, frame):
        for h in hotspots[:3]:  # Top 3 only
            print(f"  -> Hotspot: area={h.area:.0f}, intensity={h.max_intensity:.0f}, conf={h.confidence:.2f}")
    
    run_detection_loop(source, on_detect, fps=2.0)
