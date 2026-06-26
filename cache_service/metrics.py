"""Metrics sink abstraction so observability backends can vary."""

from __future__ import annotations

import threading
from typing import Dict, Optional, Protocol


class MetricsSink(Protocol):
    """A pluggable sink for counters and observations."""

    def increment(self, metric: str, tags: Optional[Dict[str, str]] = None) -> None:
        ...

    def observe(self, metric: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        ...


class NoopMetricsSink:
    """Discards all metrics. Default for production where an external sink is wired separately."""

    def increment(self, metric: str, tags: Optional[Dict[str, str]] = None) -> None:
        return None

    def observe(self, metric: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        return None


class InMemoryMetricsSink:
    """Thread-safe in-memory metrics, useful for tests and local inspection."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.counters: Dict[str, float] = {}
        self.observations: Dict[str, list] = {}

    def increment(self, metric: str, tags: Optional[Dict[str, str]] = None) -> None:
        with self._lock:
            self.counters[metric] = self.counters.get(metric, 0) + 1

    def observe(self, metric: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        with self._lock:
            self.observations.setdefault(metric, []).append(value)
