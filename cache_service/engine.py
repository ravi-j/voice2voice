"""Cache engine: pure command logic wiring validation, storage, capacity, TTL, and metrics.

The engine contains no I/O or wall-clock assumptions of its own — time comes from
the injected Clock — which keeps it deterministic and easy to test.
"""

from __future__ import annotations

import threading
from typing import Optional

from .capacity import CapacityTracker
from .clock import Clock
from .locks import LockManager
from .metrics import MetricsSink
from .policy import (
    CapacityContext,
    EvictionAction,
    EvictionPolicy,
)
from .storage.backend import StorageBackend
from .ttl import TtlResolver
from .types import (
    DeleteResult,
    Entry,
    ErrorCode,
    GetResult,
    SetResult,
    StatsResult,
    Ttl,
)
from .validator import Validator


class _Counters:
    """Engine-owned deterministic counters for stats()."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.set_count = 0
        self.get_count = 0
        self.delete_count = 0
        self.hit_count = 0
        self.miss_count = 0
        self.rejected_count = 0
        self.expired_count = 0


class CacheEngine:
    def __init__(
        self,
        storage: StorageBackend,
        capacity: CapacityTracker,
        validator: Validator,
        ttl_resolver: TtlResolver,
        clock: Clock,
        locks: LockManager,
        metrics: MetricsSink,
        eviction_policy: EvictionPolicy,
    ) -> None:
        self._storage = storage
        self._capacity = capacity
        self._validator = validator
        self._ttl = ttl_resolver
        self._clock = clock
        self._locks = locks
        self._metrics = metrics
        self._policy = eviction_policy
        self._counters = _Counters()

    # ------------------------------------------------------------------ set
    def set(
        self, tenant_id: str, key: str, value: str, ttl: Optional[Ttl] = None
    ) -> SetResult:
        err = (
            self._validator.validate_tenant(tenant_id)
            or self._validator.validate_key(key)
            or self._validator.validate_value(value)
            or self._validator.validate_ttl(ttl)
        )
        if err is not None:
            self._metrics.increment("set.invalid")
            return SetResult(ok=False, error=err)

        now = self._clock.now()
        expires_at = self._ttl.resolve(now, ttl)
        byte_size = len(key.encode("utf-8")) + len(value.encode("utf-8"))

        with self._locks.for_tenant(tenant_id):
            existing = self._storage.read(tenant_id, key)
            old_bytes = existing.byte_size if existing is not None else 0
            is_new = existing is None
            delta_keys = 1 if is_new else 0
            delta_bytes = byte_size - old_bytes

            if not self._capacity.try_reserve(delta_keys, delta_bytes):
                snap = self._capacity.snapshot()
                decision = self._policy.on_capacity_exceeded(
                    CapacityContext(
                        delta_keys=delta_keys,
                        delta_bytes=delta_bytes,
                        key_count=snap.key_count,
                        byte_count=snap.byte_count,
                        max_keys=self._capacity.limits.max_keys,
                        max_bytes=self._capacity.limits.max_bytes,
                    )
                )
                # v1 RejectPolicy always rejects; future policies could evict + retry.
                if decision.action == EvictionAction.REJECT:
                    self._bump("rejected_count")
                    self._metrics.increment("set.rejected")
                    return SetResult(ok=False, error=ErrorCode.CAPACITY_EXCEEDED)

            entry = Entry(
                value=value,
                created_at=now,
                expires_at=expires_at,
                byte_size=byte_size,
            )
            self._storage.write(tenant_id, key, entry)

        self._bump("set_count")
        self._metrics.increment("set.ok")
        return SetResult(ok=True, created=is_new, expires_at=expires_at)

    # ------------------------------------------------------------------ get
    def get(self, tenant_id: str, key: str) -> GetResult:
        err = self._validator.validate_tenant(tenant_id) or self._validator.validate_key(key)
        if err is not None:
            return GetResult(hit=False, error=err)

        now = self._clock.now()
        with self._locks.for_tenant(tenant_id):
            entry = self._storage.read(tenant_id, key)
            if entry is None:
                return self._miss()
            if entry.expires_at is not None and entry.expires_at <= now:
                # Lazy expiration: reclaim now for correctness between sweeps.
                self._storage.remove(tenant_id, key)
                self._capacity.release(1, entry.byte_size)
                self._bump("expired_count")
                self._metrics.increment("get.expired")
                return self._miss()

        self._bump("get_count")
        self._bump("hit_count")
        self._metrics.increment("get.hit")
        return GetResult(hit=True, value=entry.value, expires_at=entry.expires_at)

    # --------------------------------------------------------------- delete
    def delete(self, tenant_id: str, key: str) -> DeleteResult:
        err = self._validator.validate_tenant(tenant_id) or self._validator.validate_key(key)
        if err is not None:
            return DeleteResult(deleted=False, error=err)

        with self._locks.for_tenant(tenant_id):
            entry = self._storage.read(tenant_id, key)
            if entry is None:
                self._bump("delete_count")
                self._metrics.increment("delete.miss")
                return DeleteResult(deleted=False)
            self._storage.remove(tenant_id, key)
            self._capacity.release(1, entry.byte_size)

        self._bump("delete_count")
        self._metrics.increment("delete.ok")
        return DeleteResult(deleted=True)

    # --------------------------------------------------------------- exists
    def exists(self, tenant_id: str, key: str) -> bool:
        return self.get(tenant_id, key).hit

    # ---------------------------------------------------------- purge/sweep
    def purge_expired(self, batch_size: int = 1000) -> int:
        """Remove expired entries in bounded batches. Used by the sweeper."""
        now = self._clock.now()
        removed = 0
        candidates = self._storage.collect_expired(now, batch_size)
        for tenant_id, key, snapshot_entry in candidates:
            with self._locks.for_tenant(tenant_id):
                current = self._storage.read(tenant_id, key)
                if (
                    current is not None
                    and current.expires_at is not None
                    and current.expires_at <= now
                ):
                    self._storage.remove(tenant_id, key)
                    self._capacity.release(1, current.byte_size)
                    removed += 1
        if removed:
            with self._counters.lock:
                self._counters.expired_count += removed
            self._metrics.observe("sweeper.removed", removed)
        return removed

    # ---------------------------------------------------------------- stats
    def stats(self) -> StatsResult:
        usage = self._capacity.snapshot()
        c = self._counters
        with c.lock:
            return StatsResult(
                key_count=usage.key_count,
                byte_count=usage.byte_count,
                set_count=c.set_count,
                get_count=c.get_count,
                delete_count=c.delete_count,
                hit_count=c.hit_count,
                miss_count=c.miss_count,
                rejected_count=c.rejected_count,
                expired_count=c.expired_count,
            )

    # --------------------------------------------------------------- helpers
    def _miss(self) -> GetResult:
        self._bump("get_count")
        self._bump("miss_count")
        self._metrics.increment("get.miss")
        return GetResult(hit=False)

    def _bump(self, field: str) -> None:
        with self._counters.lock:
            setattr(self._counters, field, getattr(self._counters, field) + 1)
