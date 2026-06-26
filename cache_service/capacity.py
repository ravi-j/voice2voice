"""Capacity accounting and enforcement of the 1M-key / 1GB caps.

The tracker is the single source of truth for usage counters. ``try_reserve``
atomically checks and reserves capacity so concurrent writers cannot collectively
exceed the caps. Scope is global in v1; a per-tenant scope can be added later by
instantiating one tracker per tenant without changing the engine.
"""

from __future__ import annotations

import threading

from .config import CacheLimits
from .types import UsageSnapshot


class CapacityTracker:
    def __init__(self, limits: CacheLimits) -> None:
        self._limits = limits
        self._lock = threading.Lock()
        self._key_count = 0
        self._byte_count = 0

    @property
    def limits(self) -> CacheLimits:
        return self._limits

    def try_reserve(self, delta_keys: int, delta_bytes: int) -> bool:
        """Atomically reserve capacity for a write.

        ``delta_keys`` is 1 for a new key, 0 for an overwrite. ``delta_bytes`` may
        be negative when an overwrite shrinks a value. Returns False (no change)
        when the reservation would exceed either cap.
        """
        with self._lock:
            new_keys = self._key_count + delta_keys
            new_bytes = self._byte_count + delta_bytes
            if new_keys > self._limits.max_keys:
                return False
            if new_bytes > self._limits.max_bytes:
                return False
            self._key_count = new_keys
            self._byte_count = new_bytes
            return True

    def release(self, delta_keys: int, delta_bytes: int) -> None:
        """Release previously reserved capacity (on delete or expiry)."""
        with self._lock:
            self._key_count = max(0, self._key_count - delta_keys)
            self._byte_count = max(0, self._byte_count - delta_bytes)

    def snapshot(self) -> UsageSnapshot:
        with self._lock:
            return UsageSnapshot(key_count=self._key_count, byte_count=self._byte_count)
