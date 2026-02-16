"""
ResoFly Mk-V — Alert Manager
==============================
Manages alert state per tracked object.
Prevents duplicate alerts using per-ID cooldowns.
Formats Socket.IO event payloads.
"""

import time
import logging
from datetime import datetime
from typing import List, Optional, Callable

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Controls when alerts fire and formats payloads.

    Parameters
    ----------
    cooldown_seconds : float
        Minimum time between re-alerts for the same ID.
    require_validation : str or None
        If set, only alert when validation_type matches (e.g. "FUSED_VALIDATED").
        Set to None to alert on any confirmed detection.
    persistence_threshold : int
        Minimum persistence frames before allowing alert.
    """

    def __init__(
        self,
        cooldown_seconds: float = 300.0,
        require_validation: Optional[str] = None,
        persistence_threshold: int = 3,
    ):
        self.cooldown = cooldown_seconds
        self.require_validation = require_validation
        self.persistence_threshold = persistence_threshold

        # {object_id: last_alert_timestamp}
        self._alert_history: dict = {}

    def check_and_emit(self, tracked_objects: dict, frame_number: int) -> List[dict]:
        """
        Check all tracked objects and return alert payloads for those
        that qualify.

        Parameters
        ----------
        tracked_objects : dict
            Output of ``Tracker.update()`` — {id: TrackedObject}.
        frame_number : int
            Current frame counter.

        Returns
        -------
        list[dict]
            List of alert payloads ready for Socket.IO / DB.
        """
        now = time.time()
        alerts = []

        for oid, obj in tracked_objects.items():
            # 1. Must be persistent enough
            if obj.persistence < self.persistence_threshold:
                continue

            # 2. Must not have already alerted (unless cooldown expired)
            if obj.alert_sent:
                last = self._alert_history.get(oid, 0)
                if (now - last) < self.cooldown:
                    continue

            # 3. Optionally require RGB validation
            if self.require_validation:
                if obj.validation_type != self.require_validation:
                    continue

            # --- FIRE ALERT ---
            obj.alert_sent = True
            self._alert_history[oid] = now

            payload = self._format_payload(obj, frame_number)
            alerts.append(payload)
            logger.info(
                f"ALERT #{obj.object_id}: "
                f"type={obj.validation_type}, "
                f"temp={obj.max_temp:.1f}°C, "
                f"conf={obj.confidence:.0%}"
            )

        # Garbage-collect old entries
        self._cleanup(now)

        return alerts

    def _format_payload(self, obj, frame_number: int) -> dict:
        """Format a single alert payload."""
        return {
            "id": obj.object_id,
            "type": "LIFEFORM_DETECTED",
            "validation": obj.validation_type,
            "max_temp": round(obj.max_temp, 1),
            "confidence": round(obj.confidence * 100, 1),
            "persistence": obj.persistence,
            "frame": frame_number,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _cleanup(self, now: float):
        """Remove stale entries from alert history."""
        stale = [
            k for k, v in self._alert_history.items()
            if (now - v) > self.cooldown * 2
        ]
        for k in stale:
            del self._alert_history[k]
