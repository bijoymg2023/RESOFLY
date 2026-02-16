"""
ResoFly Mk-V — Thermal Detector
=================================
Detects thermal hotspots on 80×62 (or upscaled) grayscale frames.
Pipeline: Blur → Adaptive Threshold → Morphology → Contour → Filter.
"""

import cv2
import numpy as np
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Temperature helpers
# ---------------------------------------------------------------------------

HUMAN_TEMP_MIN_C = 28.0  # Detection floor (clothing / distance)
SCENE_TEMP_RANGE = (15.0, 45.0)  # (min, max) assumed for 0-255 mapping


def intensity_to_temp(val: float) -> float:
    lo, hi = SCENE_TEMP_RANGE
    return lo + (val / 255.0) * (hi - lo)


def temp_to_intensity(temp: float) -> int:
    lo, hi = SCENE_TEMP_RANGE
    return int(np.clip((temp - lo) / (hi - lo) * 255, 0, 255))


HUMAN_INTENSITY_FLOOR = temp_to_intensity(HUMAN_TEMP_MIN_C)


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class ThermalDetector:
    """
    Detect hotspots in a grayscale thermal frame.

    Parameters
    ----------
    min_area : int
        Minimum contour area (pixels).
    max_area : int
        Maximum contour area (pixels).  Set very high to disable.
    blur_ksize : int
        Gaussian blur kernel size (must be odd).
    std_multiplier : float
        Threshold = mean + std_multiplier × σ.
    morph_ksize : int
        Kernel size for morphological open/close.
    """

    def __init__(
        self,
        min_area: int = 20,
        max_area: int = 5000,
        blur_ksize: int = 5,
        std_multiplier: float = 2.5,
        morph_ksize: int = 3,
    ):
        self.min_area = min_area
        self.max_area = max_area
        self.blur_ksize = blur_ksize
        self.std_multiplier = std_multiplier
        self.morph_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (morph_ksize, morph_ksize)
        )

    def detect(self, frame: np.ndarray) -> Tuple[List[dict], np.ndarray]:
        """
        Detect thermal hotspots.

        Parameters
        ----------
        frame : np.ndarray
            Grayscale uint8 frame (any resolution).

        Returns
        -------
        detections : list[dict]
            Each entry: ``{bbox, centroid, max_temp, area, confidence}``.
        binary : np.ndarray
            Binary mask used for detection (for debug overlay).
        """
        # Ensure grayscale
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        # 1. Gaussian Blur
        blurred = cv2.GaussianBlur(gray, (self.blur_ksize, self.blur_ksize), 0)

        # 2. Adaptive Threshold = mean + k*σ
        mean_val = float(np.mean(blurred))
        std_val = float(np.std(blurred))
        thresh = mean_val + self.std_multiplier * std_val
        thresh = max(thresh, HUMAN_INTENSITY_FLOOR)
        thresh = min(thresh, 240.0)

        _, binary = cv2.threshold(
            blurred, int(thresh), 255, cv2.THRESH_BINARY
        )

        # 3. Morphological clean-up (open removes noise, close fills gaps)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, self.morph_kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, self.morph_kernel)

        # 4. Contour extraction
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        detections = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_area or area > self.max_area:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            ar = w / h if h > 0 else 0

            # Reject extremely thin strips (noise)
            if ar > 5.0 or ar < 0.2:
                continue

            # Max intensity inside contour ROI
            roi = gray[y : y + h, x : x + w]
            max_val = float(np.max(roi)) if roi.size > 0 else 0
            max_temp = intensity_to_temp(max_val)
            temp_dev = max_temp - HUMAN_TEMP_MIN_C

            # Skip if below human-threshold
            if max_temp < HUMAN_TEMP_MIN_C:
                continue

            # Confidence: temp × 0.5 + area × 0.3 + solidity × 0.2
            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            solidity = area / hull_area if hull_area > 0 else 0

            conf = (
                min(1.0, temp_dev / 10.0) * 0.5
                + min(1.0, area / 300.0) * 0.3
                + solidity * 0.2
            )
            conf = float(np.clip(conf, 0.05, 0.99))

            cx = int(x + w / 2)
            cy = int(y + h / 2)

            detections.append(
                {
                    "bbox": (x, y, w, h),
                    "centroid": (cx, cy),
                    "max_temp": round(max_temp, 1),
                    "area": area,
                    "confidence": round(conf, 3),
                }
            )

        # Sort by confidence descending
        detections.sort(key=lambda d: d["confidence"], reverse=True)
        return detections, binary
