"""
connection/interface.py — Abstract device connection interface.

All monitoring logic programs against this interface so that the
underlying transport (mock, Paramiko SSH, etc.) can be swapped
without touching business logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class DeviceConnection(ABC):
    """
    Abstract base class for device communication.

    Implementations must provide connect / execute / disconnect.
    The ``execute`` method accepts a CLI command string and returns
    the raw text output, exactly as a real device would print it.
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish a connection to the device."""

    @abstractmethod
    def execute(self, command: str) -> str:
        """
        Execute a CLI command on the connected device.

        Args:
            command: The command string (e.g. ``"show uptime"``).

        Returns:
            The raw CLI text output.
        """

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection to the device."""

    # ------------------------------------------------------------------
    # Context-manager support so callers can use ``with`` blocks.
    # ------------------------------------------------------------------
    def __enter__(self) -> DeviceConnection:
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()
