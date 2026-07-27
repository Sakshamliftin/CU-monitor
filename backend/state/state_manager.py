"""
state/state_manager.py — Thread-safe in-memory state store.

Maintains the latest ``RNState`` for every Radio Node, keyed by
``(cu_name, rn_name)``.  All public methods are protected by a
``threading.Lock`` so they are safe to call from the
``ThreadPoolExecutor`` workers.
"""

from __future__ import annotations

import threading
from typing import Optional

from models.node import RNState


class StateManager:
    """In-memory store for current RN states."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: dict[tuple[str, str], RNState] = {}

    def get_previous(self, cu_name: str, rn_name: str) -> Optional[RNState]:
        """
        Return the most recently stored state for a given RN,
        or ``None`` if it hasn't been polled yet.
        """
        with self._lock:
            return self._store.get((cu_name, rn_name))

    def update(self, state: RNState) -> None:
        """Store or overwrite the state for a given RN."""
        with self._lock:
            self._store[(state.cu_name, state.rn_name)] = state

    def get_all(self) -> list[RNState]:
        """
        Return a snapshot of every known RN state.

        The returned list is a shallow copy, safe to iterate outside
        the lock.
        """
        with self._lock:
            return list(self._store.values())
