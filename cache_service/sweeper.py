"""Background sweeper that periodically reclaims expired entries.

Runs on its own daemon thread, independent of the read/write path. Lazy
expiration in the engine guarantees correctness between sweeps; the sweeper's job
is to reclaim memory for keys that are never read again.
"""

from __future__ import annotations

import threading

from .config import DEFAULT_SWEEP_INTERVAL_SECONDS
from .engine import CacheEngine


class Sweeper:
    def __init__(
        self,
        engine: CacheEngine,
        interval_seconds: float = DEFAULT_SWEEP_INTERVAL_SECONDS,
        batch_size: int = 1000,
    ) -> None:
        self._engine = engine
        self._interval = interval_seconds
        self._batch_size = batch_size
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="cache-sweeper", daemon=True
        )
        self._thread.start()

    def stop(self, timeout: float | None = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def run_once(self) -> int:
        """Run a single sweep pass, draining all currently-expired entries."""
        total = 0
        while True:
            removed = self._engine.purge_expired(self._batch_size)
            total += removed
            if removed < self._batch_size:
                break
        return total

    def _run(self) -> None:
        # Wait first, then sweep, so startup is cheap.
        while not self._stop.wait(self._interval):
            try:
                self.run_once()
            except Exception:  # noqa: BLE001 - sweeper must never crash the thread
                # A real deployment would log here via the metrics/logging stack.
                continue
