"""
ResoFly Mk-V — Centroid Tracker
================================
Assigns persistent IDs to detections across frames using centroid distance.
Tracks persistence count and handles object disappearance/reappearance.
"""

from collections import OrderedDict
import numpy as np
import time
import logging

logger = logging.getLogger(__name__)


class TrackedObject:
    """Rich state for a single tracked object."""

    __slots__ = (
        "object_id", "centroid", "bbox",
        "first_seen", "last_seen",
        "persistence", "disappeared",
        "max_temp", "alert_sent",
        "validation_type", "confidence",
    )

    def __init__(self, object_id: int, centroid, bbox=(0, 0, 0, 0)):
        self.object_id = object_id
        self.centroid = centroid
        self.bbox = bbox
        self.first_seen = time.time()
        self.last_seen = time.time()
        self.persistence = 1
        self.disappeared = 0
        self.max_temp = 0.0
        self.alert_sent = False
        self.validation_type = "UNKNOWN"
        self.confidence = 0.0


class Tracker:
    """
    Centroid-based multi-object tracker.

    Parameters
    ----------
    max_disappeared : int
        Frames an object can be missing before removal.
    max_distance : float
        Max pixel distance to associate a detection with existing track.
    persistence_threshold : int
        Frames needed before a track is considered "confirmed".
    """

    def __init__(
        self,
        max_disappeared: int = 15,
        max_distance: float = 60.0,
        persistence_threshold: int = 3,
    ):
        self.next_id = 0
        self.objects: OrderedDict[int, TrackedObject] = OrderedDict()
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
        self.persistence_threshold = persistence_threshold

    # ------------------------------------------------------------------
    def register(self, centroid, bbox=(0, 0, 0, 0)) -> TrackedObject:
        obj = TrackedObject(self.next_id, centroid, bbox)
        self.objects[self.next_id] = obj
        logger.debug(f"Tracker: registered ID {self.next_id}")
        self.next_id += 1
        return obj

    def deregister(self, object_id: int):
        if object_id in self.objects:
            del self.objects[object_id]

    # ------------------------------------------------------------------
    def update(self, detections: list) -> OrderedDict:
        """
        Update tracker with new detections.

        Parameters
        ----------
        detections : list[dict]
            Each dict must have ``bbox`` (x, y, w, h) and optionally
            ``max_temp``, ``confidence``, ``validation_type``.

        Returns
        -------
        OrderedDict[int, TrackedObject]
        """
        # Compute centroids from bounding boxes
        input_centroids = []
        for d in detections:
            x, y, w, h = d["bbox"]
            input_centroids.append((int(x + w / 2), int(y + h / 2)))

        # --- No detections this frame ---
        if len(input_centroids) == 0:
            for oid in list(self.objects.keys()):
                self.objects[oid].disappeared += 1
                if self.objects[oid].disappeared > self.max_disappeared:
                    self.deregister(oid)
            return self.objects

        # --- No existing objects → register all ---
        if len(self.objects) == 0:
            for i, c in enumerate(input_centroids):
                obj = self.register(c, detections[i]["bbox"])
                self._enrich(obj, detections[i])
            return self.objects

        # --- Match existing objects to new detections ---
        object_ids = list(self.objects.keys())
        object_centroids = [self.objects[oid].centroid for oid in object_ids]

        # Distance matrix (M existing × N new)
        D = np.zeros((len(object_centroids), len(input_centroids)))
        for i, oc in enumerate(object_centroids):
            for j, ic in enumerate(input_centroids):
                D[i, j] = np.sqrt((oc[0] - ic[0]) ** 2 + (oc[1] - ic[1]) ** 2)

        # Greedy assignment (closest first)
        rows = D.min(axis=1).argsort()
        cols = D.argmin(axis=1)[rows]

        used_rows, used_cols = set(), set()

        for row, col in zip(rows, cols):
            if row in used_rows or col in used_cols:
                continue
            if D[row, col] > self.max_distance:
                continue

            oid = object_ids[row]
            obj = self.objects[oid]
            obj.centroid = input_centroids[col]
            obj.bbox = detections[col]["bbox"]
            obj.disappeared = 0
            obj.persistence += 1
            obj.last_seen = time.time()
            self._enrich(obj, detections[col])

            used_rows.add(row)
            used_cols.add(col)

        # Mark unmatched existing objects as disappeared
        for row in set(range(D.shape[0])) - used_rows:
            oid = object_ids[row]
            self.objects[oid].disappeared += 1
            if self.objects[oid].disappeared > self.max_disappeared:
                self.deregister(oid)

        # Register new unmatched detections
        for col in set(range(D.shape[1])) - used_cols:
            obj = self.register(input_centroids[col], detections[col]["bbox"])
            self._enrich(obj, detections[col])

        return self.objects

    # ------------------------------------------------------------------
    def is_confirmed(self, object_id: int) -> bool:
        obj = self.objects.get(object_id)
        return obj is not None and obj.persistence >= self.persistence_threshold

    def get_confirmed(self) -> list:
        return [
            obj
            for obj in self.objects.values()
            if obj.persistence >= self.persistence_threshold
        ]

    # ------------------------------------------------------------------
    @staticmethod
    def _enrich(obj: TrackedObject, detection: dict):
        """Copy optional metadata from detection dict to tracked object."""
        if "max_temp" in detection:
            obj.max_temp = max(obj.max_temp, detection["max_temp"])
        if "confidence" in detection:
            obj.confidence = detection["confidence"]
        if "validation_type" in detection:
            obj.validation_type = detection["validation_type"]
