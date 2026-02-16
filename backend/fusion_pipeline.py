"""
ResoFly Mk-V — Fusion Pipeline (Orchestrator)
===============================================
Main pipeline that ties together:
  1. Thermal frame acquisition
  2. Thermal hotspot detection
  3. RGB frame acquisition & person detection
  4. Sensor fusion (IoU validation)
  5. Centroid tracking (persistent IDs)
  6. Alert management (dedup / cooldown)
  7. Frame annotation (visual output)

Designed to be a drop-in replacement for thermal_pipeline.ThermalFramePipeline.
"""

import cv2
import numpy as np
import time
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, List
from dataclasses import dataclass

from thermal_detector import ThermalDetector
from rgb_detector import RGBDetector
from fusion_engine import FusionEngine
from tracker import Tracker
from alert_manager import AlertManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Structures (compatible with server.py on_detection_event)
# ---------------------------------------------------------------------------

@dataclass
class FusedHotspot:
    """A single fused detection for the event callback."""
    track_id: int
    estimated_temp: float
    confidence: float
    validation_type: str
    bbox: tuple  # (x,y,w,h)
    persistence: int


@dataclass
class DetectionEvent:
    """Alert event — compatible with server.py."""
    hotspots: List[FusedHotspot]
    timestamp: datetime
    frame_number: int
    total_count: int


# ---------------------------------------------------------------------------
# Frame Sources (reused from thermal_pipeline)
# ---------------------------------------------------------------------------

class WaveshareSource:
    """Live thermal source from Waveshare 80×62 HAT."""

    OUTPUT_WIDTH = 512
    OUTPUT_HEIGHT = 396
    NATIVE_WIDTH = 80
    NATIVE_HEIGHT = 62
    DETECT_WIDTH = 160  # 2× native for better contours
    DETECT_HEIGHT = 124

    def __init__(self):
        self._available = False
        self.camera = None
        self.fps = 8
        try:
            from waveshare_thermal import get_thermal_camera
            self.camera = get_thermal_camera()
            self._available = self.camera.is_available()
            if self._available:
                logger.info("WaveshareSource: Live thermal camera connected")
        except Exception:
            logger.warning("WaveshareSource: Driver not available")

    def get_frame(self) -> Optional[np.ndarray]:
        if not self._available or self.camera is None:
            return None
        frame = self.camera.get_frame()
        if frame is None:
            return None
        frame = cv2.normalize(frame, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        return cv2.resize(
            frame,
            (self.OUTPUT_WIDTH, self.OUTPUT_HEIGHT),
            interpolation=cv2.INTER_CUBIC,
        )

    def get_detect_frame(self, display_frame: np.ndarray) -> np.ndarray:
        return cv2.resize(
            display_frame,
            (self.DETECT_WIDTH, self.DETECT_HEIGHT),
            interpolation=cv2.INTER_AREA,
        )

    def is_available(self) -> bool:
        return self._available

    def get_max_temperature(self) -> Optional[float]:
        return self.camera.get_max_temperature() if self.camera else None


class VideoSource:
    """Dataset video fallback."""

    def __init__(self, video_path: str):
        self.cap = cv2.VideoCapture(str(video_path))
        self._available = self.cap.isOpened()

    def get_frame(self) -> Optional[np.ndarray]:
        if not self._available:
            return None
        ret, frame = self.cap.read()
        if not ret:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
        if ret and len(frame.shape) == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return frame

    def is_available(self) -> bool:
        return self._available


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

class FusionPipeline:
    """
    Multi-sensor lifeform detection pipeline.

    Can work in two modes:
    - **Full fusion**: thermal + RGB (when Pi Camera is available).
    - **Thermal-only**: gracefully degrades if no RGB camera.

    Parameters
    ----------
    thermal_source
        Frame source for thermal data (WaveshareSource or VideoSource).
    rgb_camera
        Optional RpicamCamera instance from camera.py.
    on_detection : callable or None
        Callback invoked with DetectionEvent on new alerts.
    require_rgb_validation : bool
        If True, only FUSED_VALIDATED detections trigger alerts.
        If False, THERMAL_ONLY detections also trigger alerts.
    """

    def __init__(
        self,
        thermal_source,
        rgb_camera=None,
        on_detection: Optional[Callable] = None,
        require_rgb_validation: bool = False,
    ):
        self.thermal_source = thermal_source
        self.rgb_camera = rgb_camera
        self.on_detection = on_detection

        # --- Sub-modules ---
        self.thermal_det = ThermalDetector(
            min_area=40,
            max_area=5000,
            blur_ksize=5,
            std_multiplier=3.0,
            min_temp_variance=5.0,   # Reject flat/uniform blobs
            min_solidity=0.3,        # Reject fragmented noise
        )
        self.rgb_det = RGBDetector(target_width=320)
        self.fusion = FusionEngine(
            thermal_res=(160, 124),
            rgb_res=(640, 480),
            iou_threshold=0.3,
        )
        self.tracker = Tracker(
            max_disappeared=8,
            max_distance=60,
            persistence_threshold=5,
            bbox_alpha=0.4,          # EMA smoothing factor
            min_movement=3.0,        # Skip update if < 3px movement
        )
        self.alert_mgr = AlertManager(
            cooldown_seconds=300.0,
            require_validation="FUSED_VALIDATED" if require_rgb_validation else None,
            persistence_threshold=5,
        )

        self.frame_number = 0
        self.current_hotspots = []

        # Cached RGB frame (updated async from camera thread)
        self._last_rgb_frame: Optional[np.ndarray] = None
        self._rgb_frame_time: float = 0.0

        # --- Single-writer/multi-reader frame cache ---
        self._jpeg_lock = threading.Lock()
        self._current_jpeg: Optional[bytes] = None
        self._capture_thread: Optional[threading.Thread] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False

        # Camera reader → processor bridge
        self._raw_lock = threading.Lock()
        self._latest_raw: Optional[np.ndarray] = None
        self._target_fps = 20  # User requested faster/smoother (20 FPS)
        self._raw_seq = 0           # increments on each new camera frame
        self._last_processed_seq = 0  # last seq the processor consumed

        # Detection cadence
        self._detect_interval = 4  # detect every 4th frame (5 Hz)
        self._cached_tracked: dict = {}
        self._cached_raw_frame: Optional[np.ndarray] = None
        self._loop_frame = 0

        # Pre-generate "no signal" placeholder JPEG
        no_signal = np.zeros((396, 512, 3), dtype=np.uint8)
        cv2.putText(no_signal, "THERMAL", (130, 180),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.8, (0, 180, 255), 3)
        cv2.putText(no_signal, "Waiting for sensor data...", (100, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 100, 100), 1)
        _, placeholder = cv2.imencode('.jpg', no_signal,
                                      [cv2.IMWRITE_JPEG_QUALITY, 70])
        self._placeholder_jpeg: bytes = placeholder.tobytes()

    # ------------------------------------------------------------------
    # Background threads
    # ------------------------------------------------------------------
    def start(self):
        """Start camera reader + frame processor threads."""
        if self._running:
            return
        self._running = True

        # Thread 1: reads SPI camera at hardware rate (~5 FPS)
        self._reader_thread = threading.Thread(
            target=self._camera_reader, daemon=True, name="thermal-reader"
        )
        self._reader_thread.start()

        # Thread 2: processes frames (colormap + detect + encode)
        self._capture_thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="thermal-process"
        )
        self._capture_thread.start()
        logger.info("FusionPipeline: reader + processor threads started")

    def stop(self):
        """Stop both threads."""
        self._running = False
        for t in (self._reader_thread, self._capture_thread):
            if t and t.is_alive():
                t.join(timeout=3.0)
        self._reader_thread = None
        self._capture_thread = None
        logger.info("FusionPipeline: threads stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def get_jpeg(self) -> bytes:
        """
        Get the latest JPEG-encoded frame (thread-safe read).
        Called by HTTP streaming generators — never touches the camera.
        """
        with self._jpeg_lock:
            return self._current_jpeg or self._placeholder_jpeg

    # ------------------------------------------------------------------
    # Thread 1: Camera reader (blocks on SPI, that's fine)
    # ------------------------------------------------------------------
    def _camera_reader(self):
        """
        Tight loop: read camera → cache raw frame.
        Blocks on SPI data_ready (~200ms) — that's expected.
        The processor thread picks up frames without waiting.
        """
        logger.info("Camera reader thread started")
        while self._running:
            try:
                raw = self.thermal_source.get_frame()
                if raw is not None:
                    with self._raw_lock:
                        self._latest_raw = raw
                        self._raw_seq += 1
            except Exception as e:
                logger.error(f"Camera reader error: {e}")
                time.sleep(0.005)  # Retry fast (5ms)

    # ------------------------------------------------------------------
    # Thread 2: Frame processor (never blocks on SPI)
    # ------------------------------------------------------------------
    def _capture_loop(self):
        """
        Picks up the latest raw frame from the reader thread,
        applies colormap + cached boxes + JPEG encode.
        Runs detection every _detect_interval new frames.
        Never blocks on SPI — processes frames the instant they're ready.
        """
        logger.info(f"Processor thread started (detect every {self._detect_interval} frames)")

        while self._running:
            # Grab latest raw frame (non-blocking)
            with self._raw_lock:
                raw = self._latest_raw
                seq = self._raw_seq

            if raw is None or seq == self._last_processed_seq:
                # No new frame from camera yet — brief sleep, reuse last JPEG
                time.sleep(0.002)  # Check very frequently (2ms)
                continue

            self._last_processed_seq = seq

            try:
                self._loop_frame += 1
                self._cached_raw_frame = raw
                self.frame_number += 1
                run_detect = (self._loop_frame % self._detect_interval == 0)

                if run_detect:
                    # Full pipeline (uses self.thermal_source.get_frame()
                    #   internally — override with cached raw)
                    frame = self._process_with_frame(raw)
                else:
                    # Light: colormap + cached boxes only
                    frame = self._annotate(raw, self._cached_tracked)

                if frame is not None:
                    _, jpeg = cv2.imencode(
                        '.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 35]
                    )
                    with self._jpeg_lock:
                        self._current_jpeg = jpeg.tobytes()
                else:
                    with self._jpeg_lock:
                        self._current_jpeg = self._placeholder_jpeg
            except Exception as e:
                logger.error(f"Processor error: {e}", exc_info=True)
                time.sleep(0.005)

    def _fast_frame(self) -> Optional[np.ndarray]:
        """
        Skip-detection frame: reuse cached raw thermal frame,
        apply colormap + redraw cached bounding boxes.
        NO camera read, NO SPI access — ~30ms vs ~300ms.
        """
        if self._cached_raw_frame is None:
            return None
        try:
            self.frame_number += 1
            return self._annotate(self._cached_raw_frame, self._cached_tracked)
        except Exception as e:
            logger.error(f"Fast frame error: {e}")
            return None

    # ------------------------------------------------------------------
    def _process_with_frame(self, full_frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Run full detect → fuse → track → alert → annotate pipeline
        on a PRE-READ raw frame (no SPI access).
        """
        try:
            now = time.time()

            # 2. Thermal detection (on downscaled frame)
            if hasattr(self.thermal_source, "get_detect_frame"):
                detect_frame = self.thermal_source.get_detect_frame(full_frame)
                sx = full_frame.shape[1] / detect_frame.shape[1]
                sy = full_frame.shape[0] / detect_frame.shape[0]
            else:
                detect_frame = full_frame
                sx = sy = 1.0

            thermal_dets, binary = self.thermal_det.detect(detect_frame)

            # Scale thermal boxes back to display coordinates
            for d in thermal_dets:
                x, y, w, h = d["bbox"]
                d["bbox"] = (int(x * sx), int(y * sy), int(w * sx), int(h * sy))
                cx, cy = d["centroid"]
                d["centroid"] = (int(cx * sx), int(cy * sy))

            # 3. RGB detection (conditional — only if thermal found something)
            rgb_dets = []
            rgb_frame = None

            if thermal_dets and self.rgb_camera is not None:
                rgb_frame = self._grab_rgb_frame()
                if rgb_frame is not None:
                    rgb_dets = self.rgb_det.detect(rgb_frame)

            # 4. Sensor fusion
            display_h, display_w = full_frame.shape[:2]  # e.g. 512×396

            if rgb_dets:
                # Update fusion engine resolutions based on actual frames
                self.fusion.set_resolutions(
                    thermal_res=(full_frame.shape[1], full_frame.shape[0]),
                    rgb_res=(rgb_frame.shape[1], rgb_frame.shape[0]),
                )
                fused_dets = self.fusion.fuse(thermal_dets, rgb_dets)

                # CRITICAL: Fusion returns bbox in RGB coordinate space.
                # We must scale them BACK to thermal display coordinates
                # so _annotate() draws them correctly on the thermal frame.
                rgb_h, rgb_w = rgb_frame.shape[:2]
                rx = display_w / rgb_w
                ry = display_h / rgb_h
                for d in fused_dets:
                    x, y, w, h = d["bbox"]
                    d["bbox"] = (int(x * rx), int(y * ry), int(w * rx), int(h * ry))
                    cx, cy = d.get("centroid", (x + w // 2, y + h // 2))
                    d["centroid"] = (int(cx * rx), int(cy * ry))
            else:
                # No RGB → mark everything as THERMAL_ONLY
                fused_dets = []
                for d in thermal_dets:
                    d["validation_type"] = "THERMAL_ONLY"
                    fused_dets.append(d)

            # 5. Tracking
            tracked = self.tracker.update(fused_dets)

            # Cache for skip-frame re-annotation
            self._cached_tracked = tracked
            alerts = self.alert_mgr.check_and_emit(tracked, self.frame_number)

            # 7. Fire callback
            if alerts and self.on_detection:
                hotspots = []
                for a in alerts:
                    obj = tracked.get(a["id"])
                    if obj:
                        hotspots.append(
                            FusedHotspot(
                                track_id=obj.object_id,
                                estimated_temp=obj.max_temp,
                                confidence=obj.confidence,
                                validation_type=obj.validation_type,
                                bbox=obj.smooth_bbox,
                                persistence=obj.persistence,
                            )
                        )
                if hotspots:
                    event = DetectionEvent(
                        hotspots=hotspots,
                        timestamp=datetime.utcnow(),
                        frame_number=self.frame_number,
                        total_count=len(tracked),
                    )
                    self.on_detection(event)

            # 8. Annotate
            self.current_hotspots = list(tracked.values())
            return self._annotate(full_frame, tracked)

        except Exception as e:
            logger.error(f"FusionPipeline error: {e}", exc_info=True)
            return None

    def process_next(self) -> Optional[np.ndarray]:
        """Backward-compat: read camera + run full pipeline."""
        full_frame = self.thermal_source.get_frame()
        if full_frame is None:
            return None
        self._cached_raw_frame = full_frame
        self.frame_number += 1
        return self._process_with_frame(full_frame)

    # ------------------------------------------------------------------
    def _grab_rgb_frame(self) -> Optional[np.ndarray]:
        """
        Get the latest RGB frame from the Pi Camera.
        Non-blocking — uses whatever frame the camera thread has cached.
        """
        if self.rgb_camera is None:
            return None
        try:
            import asyncio

            # The camera's get_frame is async, but we're in a sync context.
            # Use the cached frame directly from the camera object.
            jpeg_bytes = self.rgb_camera.frame
            if jpeg_bytes is None:
                return None

            # Decode JPEG → numpy
            arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return frame
        except Exception as e:
            logger.debug(f"RGB grab failed: {e}")
            return None

    # ------------------------------------------------------------------
    def _annotate(self, frame: np.ndarray, tracked: dict) -> np.ndarray:
        """Draw bounding boxes and HUD on the thermal frame."""
        # Apply INFERNO colormap
        if len(frame.shape) == 2:
            display = cv2.applyColorMap(frame, cv2.COLORMAP_INFERNO)
        else:
            display = frame.copy()

        confirmed_count = 0
        frame_h, frame_w = display.shape[:2]

        for oid, obj in tracked.items():
            is_conf = obj.persistence >= self.tracker.persistence_threshold
            # Use EMA-smoothed bbox for stable drawing
            x, y, w, h = obj.smooth_bbox

            # Clamp bbox to frame boundaries (safety net)
            x = max(0, min(x, frame_w - 1))
            y = max(0, min(y, frame_h - 1))
            w = min(w, frame_w - x)
            h = min(h, frame_h - y)

            # Skip degenerate boxes
            if w < 3 or h < 3:
                continue

            # Color by validation type
            if obj.validation_type == "FUSED_VALIDATED":
                color = (0, 255, 0)   # Green — highest confidence
            elif obj.validation_type == "THERMAL_ONLY" and is_conf:
                color = (0, 200, 255)  # Orange — confirmed thermal
            else:
                color = (128, 128, 128)  # Gray — probation

            thick = 2 if is_conf else 1
            cv2.rectangle(display, (x, y), (x + w, y + h), color, thick)

            if is_conf:
                confirmed_count += 1
                tag = obj.validation_type.replace("_", " ")
                label = f"#{oid} {obj.max_temp:.0f}C [{tag}]"
                cv2.putText(
                    display, label, (x, y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA,
                )

        # Status bar
        status = f"Targets: {confirmed_count} | Frame: {self.frame_number}"
        cv2.putText(
            display, status, (2, display.shape[0] - 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1, cv2.LINE_AA,
        )

        # Upscale 2x for better browser compatibility (80x62 -> 160x124)
        # INTER_NEAREST is fastest and keeps the "thermal pixel" look
        display = cv2.resize(display, (160, 124), interpolation=cv2.INTER_NEAREST)

        return display
