"""
scheduler/scheduler.py — Periodic task scheduler.

Runs ``MonitorService.poll_all()`` at a configurable interval in a
daemon background thread.  Starts / stops cleanly with the FastAPI
lifespan.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from monitoring.monitor_service import MonitorService

logger = logging.getLogger(__name__)


class Scheduler:
    """
    Simple interval-based scheduler.

    Runs a callback every ``interval_sec`` seconds in a background
    daemon thread.
    """

    def __init__(self, interval_sec: int, monitor: MonitorService) -> None:
        self._interval = interval_sec
        self._monitor = monitor
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the scheduler background thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Scheduler is already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="monitor-scheduler",
        )
        self._thread.start()
        logger.info(
            "Scheduler started — polling every %d seconds", self._interval,
        )

    def stop(self) -> None:
        """Signal the scheduler thread to stop and wait for it."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            logger.info("Scheduler stopped")

    def _run_loop(self) -> None:
        """Internal loop: poll → sleep → repeat."""
        while not self._stop_event.is_set():
            try:
                self._monitor.poll_all()
            except Exception:
                logger.exception("Unhandled error in poll cycle")
            # Sleep in small increments so we can respond to stop quickly.
            for _ in range(self._interval * 10):
                if self._stop_event.is_set():
                    return
                time.sleep(0.1)
