"""
connection/mock_connection.py — Simulated device connection.

Produces realistic CLI-like text output for ``show uptime``,
``show pci``, and ``show state`` commands.  Simulates:

* Uptime that advances with wall-clock time.
* Random reboots (~5 % chance per poll) that reset uptime.
* Random state transitions (~10 % chance per poll).
* Constant PCI assigned once on first connection.
"""

from __future__ import annotations

import logging
import random
import time
from typing import ClassVar

from connection.interface import DeviceConnection

logger = logging.getLogger(__name__)

# All possible node states
STATES = ["ACTIVE", "IDLE", "OOS", "RECOVERING"]


class _DeviceSimState:
    """
    Internal per-device simulated state.

    Shared across connection instances for the same device IP so that
    state is persistent between poll cycles (like a real device).
    """

    def __init__(self, ip: str) -> None:
        self.ip = ip
        # PCI is assigned once and never changes.
        self.pci: int = random.randint(0, 503)
        # State starts ACTIVE.
        self.state: str = "ACTIVE"
        # Uptime is measured from this epoch timestamp.
        self._boot_time: float = time.time() - random.uniform(3600, 864000)

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self._boot_time

    def maybe_reboot(self) -> None:
        """~5 % chance of simulating a reboot (uptime resets)."""
        if random.random() < 0.05:
            logger.info("SIM [%s]: Reboot triggered", self.ip)
            self._boot_time = time.time()

    def maybe_change_state(self) -> None:
        """~10 % chance of transitioning to a different state."""
        if random.random() < 0.10:
            new_state = random.choice(STATES)
            if new_state != self.state:
                logger.info(
                    "SIM [%s]: State change %s → %s",
                    self.ip, self.state, new_state,
                )
                self.state = new_state


# ------------------------------------------------------------------
# Global registry — one simulated state per device IP.
# ------------------------------------------------------------------
_device_registry: dict[str, _DeviceSimState] = {}


def _get_or_create_sim(ip: str) -> _DeviceSimState:
    if ip not in _device_registry:
        _device_registry[ip] = _DeviceSimState(ip)
    return _device_registry[ip]


class MockConnection(DeviceConnection):
    """
    Mock implementation of DeviceConnection.

    Returns realistic CLI text that the parser module can parse,
    while randomly simulating reboots and state changes.
    """

    def __init__(self, host: str, port: int = 22) -> None:
        self._host = host
        self._port = port
        self._connected = False
        self._sim: _DeviceSimState | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def connect(self) -> None:
        self._sim = _get_or_create_sim(self._host)
        # Simulate random events on each new connection (i.e. each poll).
        self._sim.maybe_reboot()
        self._sim.maybe_change_state()
        self._connected = True
        logger.debug("MockConnection connected to %s", self._host)

    def disconnect(self) -> None:
        self._connected = False
        logger.debug("MockConnection disconnected from %s", self._host)

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------
    def execute(self, command: str) -> str:
        if not self._connected or self._sim is None:
            raise RuntimeError("Not connected — call connect() first")

        cmd = command.strip().lower()

        if cmd == "show uptime":
            return self._format_uptime()
        elif cmd == "show pci":
            return self._format_pci()
        elif cmd == "show state":
            return self._format_state()
        else:
            return f"% Unknown command: {command}"

    # ------------------------------------------------------------------
    # CLI output formatters
    # ------------------------------------------------------------------
    def _format_uptime(self) -> str:
        total = int(self._sim.uptime_seconds)  # type: ignore[union-attr]
        days, remainder = divmod(total, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"System Uptime : {days} days {hours:02d}:{minutes:02d}:{seconds:02d}"

    def _format_pci(self) -> str:
        return f"PCI : {self._sim.pci}"  # type: ignore[union-attr]

    def _format_state(self) -> str:
        return f"State : {self._sim.state}"  # type: ignore[union-attr]
