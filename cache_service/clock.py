"""Clock abstraction so time-dependent behavior (TTL/expiry) is injectable and testable."""

from __future__ import annotations

import time
from typing import Protocol


class Clock(Protocol):
    """A source of monotonic-ish wall-clock time in epoch milliseconds."""

    def now(self) -> int:
        """Return the current time in epoch milliseconds."""
        ...


class SystemClock:
    """Default clock backed by the system wall clock."""

    def now(self) -> int:
        return int(time.time() * 1000)


class ManualClock:
    """A controllable clock for deterministic tests."""

    def __init__(self, start_ms: int = 0) -> None:
        self._now = start_ms

    def now(self) -> int:
        return self._now

    def advance(self, delta_ms: int) -> None:
        self._now += delta_ms

    def set(self, now_ms: int) -> None:
        self._now = now_ms
