"""
ResoFly Mk-V — RGB Lifeform Detector
=======================================
Lightweight person / upper-body detection using OpenCV Haar Cascades.
Runs entirely on CPU — no PyTorch, no ONNX, no GPU required.

Why Haar instead of YOLO?
- Zero extra dependencies (ships with OpenCV).
- ~5ms per frame on Pi 4 at 320×240.
- Good enough for *validation* (thermal is the primary sensor).
"""

import cv2
import numpy as np
import logging
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class RGBDetector:
    """
    Detect persons using Haar cascades on a downscaled RGB frame.

    Parameters
    ----------
    target_width : int
        Width to resize input frame before detection (speed vs accuracy).
    scale_factor : float
        Haar cascade ``scaleFactor`` (smaller = more detections, slower).
    min_neighbors : int
        Haar cascade ``minNeighbors`` (higher = fewer false positives).
    min_size : tuple
        Minimum detection size (w, h) in pixels at ``target_width``.
    """

    def __init__(
        self,
        target_width: int = 320,
        scale_factor: float = 1.15,
        min_neighbors: int = 4,
        min_size: tuple = (30, 60),
    ):
        self.target_width = target_width
        self.scale_factor = scale_factor
        self.min_neighbors = min_neighbors
        self.min_size = min_size

        # Load cascade classifiers (ship with OpenCV)
        self._cascades = []
        cascade_names = [
            cv2.data.haarcascades + "haarcascade_fullbody.xml",
            cv2.data.haarcascades + "haarcascade_upperbody.xml",
        ]
        for path in cascade_names:
            if Path(path).exists():
                cc = cv2.CascadeClassifier(path)
                if not cc.empty():
                    self._cascades.append((Path(path).stem, cc))
                    logger.info(f"RGBDetector: loaded {Path(path).name}")

        if not self._cascades:
            logger.warning("RGBDetector: no Haar cascades loaded — RGB validation disabled")

        self._available = len(self._cascades) > 0

    @property
    def available(self) -> bool:
        return self._available

    def detect(self, frame: np.ndarray) -> List[dict]:
        """
        Detect persons in an RGB frame.

        Parameters
        ----------
        frame : np.ndarray
            BGR or grayscale frame (any resolution).

        Returns
        -------
        list[dict]
            Each entry: ``{bbox: (x,y,w,h), confidence: float}``.
            Coordinates are in the **original** frame space (not resized).
        """
        if not self._available:
            return []

        # Convert to grayscale if needed
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        orig_h, orig_w = gray.shape[:2]

        # Resize for speed
        scale = self.target_width / orig_w
        resized = cv2.resize(
            gray,
            (self.target_width, int(orig_h * scale)),
            interpolation=cv2.INTER_AREA,
        )

        # Histogram equalization (helps in varying illumination)
        resized = cv2.equalizeHist(resized)

        all_rects = []

        for name, cascade in self._cascades:
            rects = cascade.detectMultiScale(
                resized,
                scaleFactor=self.scale_factor,
                minNeighbors=self.min_neighbors,
                minSize=self.min_size,
                flags=cv2.CASCADE_SCALE_IMAGE,
            )
            if len(rects) > 0:
                for (rx, ry, rw, rh) in rects:
                    all_rects.append((rx, ry, rw, rh, name))

        # Scale back to original coordinates and deduplicate
        detections = []
        inv_scale = 1.0 / scale

        for rx, ry, rw, rh, name in all_rects:
            x = int(rx * inv_scale)
            y = int(ry * inv_scale)
            w = int(rw * inv_scale)
            h = int(rh * inv_scale)

            # Haar doesn't give confidence per se; use relative size as proxy
            det_area = w * h
            frame_area = orig_w * orig_h
            size_ratio = det_area / frame_area
            pseudo_conf = float(np.clip(0.4 + size_ratio * 5.0, 0.3, 0.95))

            detections.append(
                {
                    "bbox": (x, y, w, h),
                    "confidence": round(pseudo_conf, 3),
                    "source": name,
                }
            )

        # NMS-like dedup (merge overlapping boxes)
        detections = self._nms(detections, iou_thresh=0.4)
        return detections

    @staticmethod
    def _nms(dets: list, iou_thresh: float = 0.4) -> list:
        """Simple greedy NMS to remove duplicate overlapping boxes."""
        if len(dets) <= 1:
            return dets

        # Sort by confidence descending
        dets = sorted(dets, key=lambda d: d["confidence"], reverse=True)
        keep = []

        while dets:
            best = dets.pop(0)
            keep.append(best)
            remaining = []
            bx, by, bw, bh = best["bbox"]

            for d in dets:
                dx, dy, dw, dh = d["bbox"]
                # IoU
                ix = max(0, min(bx + bw, dx + dw) - max(bx, dx))
                iy = max(0, min(by + bh, dy + dh) - max(by, dy))
                inter = ix * iy
                union = bw * bh + dw * dh - inter
                iou = inter / union if union > 0 else 0

                if iou < iou_thresh:
                    remaining.append(d)

            dets = remaining

        return keep
