"""
events/event_manager.py — Centralized event detection and tracking.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Optional

from models.node import MonitoringEvent, RNState


class EventManager:
    """
    Tracks and maintains a history of monitoring events (e.g. reboots).
    """

    def __init__(self, max_history: int = 1000) -> None:
        self._max_history = max_history
        self._events: list[MonitoringEvent] = []
        self._lock = threading.Lock()

    def check_reboot(
        self, previous: Optional[RNState], current: RNState
    ) -> Optional[MonitoringEvent]:
        """
        Compare previous and current state to detect a reboot.
        A reboot is detected if the uptime drops significantly.

        If a reboot is detected, returns a MonitoringEvent.
        Otherwise returns None.
        """
        if previous is None:
            return None

        # Uptime reset check
        if current.uptime_seconds < previous.uptime_seconds:
            # Uptime dropped, indicating a reboot
            event = MonitoringEvent(
                event_type="REBOOT_DETECTED",
                cu_name=current.cu_name,
                rn_name=current.rn_name,
                timestamp=datetime.now(timezone.utc).isoformat(),
                details=(
                    f"Uptime dropped from {previous.uptime_display} "
                    f"to {current.uptime_display}"
                ),
            )
            self.add_event(event)
            return event

        return None

    def add_event(self, event: MonitoringEvent) -> None:
        """Add a new event to the in-memory log, rotating if necessary."""
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._max_history:
                self._events.pop(0)

    def get_recent_events(self, limit: int = 50) -> list[MonitoringEvent]:
        """Return the most recent events."""
        with self._lock:
            return self._events[-limit:]
