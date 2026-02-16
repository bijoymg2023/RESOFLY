"""
ResoFly Mk-V — Sensor Fusion Engine
======================================
Maps thermal bounding boxes into RGB coordinate space and validates
detections using IoU overlap.

Validation categories:
- FUSED_VALIDATED  — Thermal hotspot confirmed by RGB person detection.
- THERMAL_ONLY     — Thermal hotspot with no RGB match (still possibly valid).
- RGB_ONLY         — RGB detection with no thermal signature (rare).
"""

import numpy as np
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


class FusionEngine:
    """
    Fuses thermal and RGB detections.

    Parameters
    ----------
    thermal_res : tuple
        (width, height) of the thermal detection frame.
    rgb_res : tuple
        (width, height) of the RGB detection frame.
    iou_threshold : float
        Minimum IoU to consider a thermal+RGB pair as "fused".
    """

    def __init__(
        self,
        thermal_res: Tuple[int, int] = (80, 62),
        rgb_res: Tuple[int, int] = (640, 480),
        iou_threshold: float = 0.3,
    ):
        self.thermal_w, self.thermal_h = thermal_res
        self.rgb_w, self.rgb_h = rgb_res
        self.iou_threshold = iou_threshold

        # Pre-compute scale factors
        self.scale_x = self.rgb_w / self.thermal_w
        self.scale_y = self.rgb_h / self.thermal_h

    def set_resolutions(self, thermal_res, rgb_res):
        """Update resolutions at runtime (e.g. after first frame)."""
        self.thermal_w, self.thermal_h = thermal_res
        self.rgb_w, self.rgb_h = rgb_res
        self.scale_x = self.rgb_w / self.thermal_w
        self.scale_y = self.rgb_h / self.thermal_h

    # ------------------------------------------------------------------
    def project_thermal_to_rgb(self, bbox) -> tuple:
        """
        Scale a thermal bounding box to RGB coordinate space.

        Parameters
        ----------
        bbox : tuple
            (x, y, w, h) in thermal pixel space.

        Returns
        -------
        tuple
            (x, y, w, h) in RGB pixel space.
        """
        x, y, w, h = bbox
        return (
            int(x * self.scale_x),
            int(y * self.scale_y),
            int(w * self.scale_x),
            int(h * self.scale_y),
        )

    # ------------------------------------------------------------------
    def fuse(
        self,
        thermal_dets: List[dict],
        rgb_dets: List[dict],
    ) -> List[dict]:
        """
        Fuse thermal and RGB detections.

        Parameters
        ----------
        thermal_dets : list[dict]
            From ``ThermalDetector.detect()``.
        rgb_dets : list[dict]
            From ``RGBDetector.detect()``.

        Returns
        -------
        list[dict]
            Unified detection list with ``validation_type`` field.
        """
        fused: List[dict] = []
        used_rgb = set()

        # --- Pass 1: Match each thermal detection to an RGB detection ---
        for td in thermal_dets:
            projected = self.project_thermal_to_rgb(td["bbox"])

            best_iou = 0.0
            best_idx = -1

            for j, rd in enumerate(rgb_dets):
                if j in used_rgb:
                    continue
                iou = self._compute_iou(projected, rd["bbox"])
                if iou > best_iou:
                    best_iou = iou
                    best_idx = j

            if best_iou >= self.iou_threshold and best_idx >= 0:
                # FUSED — thermal + RGB agree
                used_rgb.add(best_idx)
                rd = rgb_dets[best_idx]

                # Merge confidence: weighted average
                merged_conf = td["confidence"] * 0.6 + rd["confidence"] * 0.4

                fused.append(
                    {
                        "bbox": projected,  # Use projected (RGB-scale) box
                        "centroid": td.get("centroid", (0, 0)),
                        "max_temp": td.get("max_temp", 0),
                        "confidence": round(merged_conf, 3),
                        "validation_type": "FUSED_VALIDATED",
                        "iou": round(best_iou, 3),
                        "thermal_bbox": td["bbox"],
                        "rgb_bbox": rd["bbox"],
                    }
                )
            else:
                # THERMAL_ONLY
                fused.append(
                    {
                        "bbox": projected,
                        "centroid": td.get("centroid", (0, 0)),
                        "max_temp": td.get("max_temp", 0),
                        "confidence": round(td["confidence"] * 0.7, 3),
                        "validation_type": "THERMAL_ONLY",
                        "thermal_bbox": td["bbox"],
                    }
                )

        # --- Pass 2: Remaining RGB-only detections ---
        for j, rd in enumerate(rgb_dets):
            if j in used_rgb:
                continue
            x, y, w, h = rd["bbox"]
            fused.append(
                {
                    "bbox": rd["bbox"],
                    "centroid": (int(x + w / 2), int(y + h / 2)),
                    "max_temp": 0.0,
                    "confidence": round(rd["confidence"] * 0.5, 3),
                    "validation_type": "RGB_ONLY",
                    "rgb_bbox": rd["bbox"],
                }
            )

        return fused

    # ------------------------------------------------------------------
    @staticmethod
    def _compute_iou(box_a, box_b) -> float:
        """
        Compute IoU between two (x, y, w, h) boxes.
        """
        ax, ay, aw, ah = box_a
        bx, by, bw, bh = box_b

        # Intersection
        ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
        iy = max(0, min(ay + ah, by + bh) - max(ay, by))
        inter = ix * iy

        # Union
        area_a = aw * ah
        area_b = bw * bh
        union = area_a + area_b - inter

        return inter / union if union > 0 else 0.0
