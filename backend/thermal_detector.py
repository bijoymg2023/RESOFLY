"""
ResoFly Mk-V — Thermal Detector (Optimised)
=============================================
Detects thermal hotspots on 80×62 (or upscaled) grayscale frames.
Pipeline: Blur → Adaptive Threshold → Morphology → Contour → Filter → Refine.

Optimisations for Raspberry Pi 4:
- Pre-allocated morphology kernels (no per-frame allocation)
- uint8 operations throughout (no float32 intermediates)
- Temperature-variance filtering (rejects low-contrast blobs)
- Convex hull bbox refinement (tighter boxes)
- Aspect-ratio and solidity filtering (rejects noise)
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
    min_temp_variance : float
        Minimum intensity std-dev inside a contour ROI.
        Rejects flat / low-contrast blobs that aren't real hotspots.
    min_solidity : float
        Minimum solidity (area / convex hull area). Rejects irregular noise.
    """

    def __init__(
        self,
        min_area: int = 40,
        max_area: int = 5000,
        blur_ksize: int = 5,
        std_multiplier: float = 3.0,
        morph_ksize: int = 3,
        min_temp_variance: float = 5.0,
        min_solidity: float = 0.3,
    ):
        self.min_area = min_area
        self.max_area = max_area
        self.blur_ksize = blur_ksize
        self.std_multiplier = std_multiplier
        self.min_temp_variance = min_temp_variance
        self.min_solidity = min_solidity

        # Pre-allocate morphology kernels (avoid per-frame allocation)
        self._morph_kernel_open = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (morph_ksize, morph_ksize)
        )
        self._morph_kernel_close = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (morph_ksize + 2, morph_ksize + 2)
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

        # 1. Gaussian Blur (reduces sensor noise)
        blurred = cv2.GaussianBlur(gray, (self.blur_ksize, self.blur_ksize), 0)

        # 2. Adaptive Threshold = mean + k*σ
        mean_val = float(np.mean(blurred))
        std_val = float(np.std(blurred))
        thresh = mean_val + self.std_multiplier * std_val
        thresh = max(thresh, HUMAN_INTENSITY_FLOOR)
        thresh = min(thresh, 245.0)

        _, binary = cv2.threshold(
            blurred, int(thresh), 255, cv2.THRESH_BINARY
        )

        # 3. Morphological clean-up
        #    Open: remove small noise specks
        #    Close: fill small gaps inside blobs
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, self._morph_kernel_open)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, self._morph_kernel_close)

        # 4. Contour extraction
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        detections = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_area or area > self.max_area:
                continue

            # --- Convex hull bbox refinement ---
            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            solidity = area / hull_area if hull_area > 0 else 0

            # Reject low-solidity (fragmented / irregular noise)
            if solidity < self.min_solidity:
                continue

            # Use hull bounding rect for tighter box
            x, y, w, h = cv2.boundingRect(hull)
            ar = w / h if h > 0 else 0

            # Reject extremely thin strips (noise)
            if ar > 4.0 or ar < 0.25:
                continue

            # --- Temperature analysis inside contour ROI ---
            roi = gray[y: y + h, x: x + w]
            if roi.size == 0:
                continue

            max_val = float(np.max(roi))
            roi_std = float(np.std(roi))
            max_temp = intensity_to_temp(max_val)

            # Reject low-variance regions (uniform background picked up by threshold)
            if roi_std < self.min_temp_variance:
                continue

            # Skip if below human-threshold
            if max_temp < HUMAN_TEMP_MIN_C:
                continue

            temp_dev = max_temp - HUMAN_TEMP_MIN_C

            # Confidence: temp × 0.4 + area × 0.25 + solidity × 0.2 + variance × 0.15
            norm_temp = min(1.0, temp_dev / 10.0)
            norm_area = min(1.0, area / 300.0)
            norm_var = min(1.0, roi_std / 30.0)

            conf = (
                norm_temp * 0.4
                + norm_area * 0.25
                + solidity * 0.2
                + norm_var * 0.15
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
