"""Public facade and factory for the multi-tenant cache service.

``CacheService`` is the only surface callers need: set / get / delete / exists /
stats, plus lifecycle control for the background sweeper. Everything beneath it
(storage, capacity, clock, metrics, eviction) is injectable for testing and future
extension.
"""

from __future__ import annotations

from typing import Optional

from .capacity import CapacityTracker
from .clock import Clock, SystemClock
from .config import CacheLimits, DEFAULT_SWEEP_INTERVAL_SECONDS
from .engine import CacheEngine
from .locks import LockManager
from .metrics import MetricsSink, NoopMetricsSink
from .policy import EvictionPolicy, RejectPolicy
from .storage.backend import StorageBackend
from .storage.memory import InMemoryStore
from .sweeper import Sweeper
from .ttl import TtlResolver
from .types import DeleteResult, GetResult, SetResult, StatsResult, Ttl
from .validator import Validator


class CacheService:
    def __init__(self, engine: CacheEngine, sweeper: Sweeper) -> None:
        self._engine = engine
        self._sweeper = sweeper

    # ----------------------------------------------------------- public API
    def set(
        self, tenant_id: str, key: str, value: str, ttl: Optional[Ttl] = None
    ) -> SetResult:
        return self._engine.set(tenant_id, key, value, ttl)

    def get(self, tenant_id: str, key: str) -> GetResult:
        return self._engine.get(tenant_id, key)

    def delete(self, tenant_id: str, key: str) -> DeleteResult:
        return self._engine.delete(tenant_id, key)

    def exists(self, tenant_id: str, key: str) -> bool:
        return self._engine.exists(tenant_id, key)

    def stats(self) -> StatsResult:
        return self._engine.stats()

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        self._sweeper.start()

    def stop(self) -> None:
        self._sweeper.stop()

    def sweep_now(self) -> int:
        """Trigger an immediate sweep pass (useful for tests/ops)."""
        return self._sweeper.run_once()

    def __enter__(self) -> "CacheService":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()


def create_cache_service(
    limits: Optional[CacheLimits] = None,
    *,
    storage: Optional[StorageBackend] = None,
    clock: Optional[Clock] = None,
    metrics: Optional[MetricsSink] = None,
    eviction_policy: Optional[EvictionPolicy] = None,
    sweep_interval_seconds: float = DEFAULT_SWEEP_INTERVAL_SECONDS,
    sweep_batch_size: int = 1000,
) -> CacheService:
    """Wire up a CacheService with sensible defaults.

    All collaborators are overridable for testing or future backends.
    """
    limits = limits or CacheLimits()
    storage = storage or InMemoryStore()
    clock = clock or SystemClock()
    metrics = metrics or NoopMetricsSink()
    eviction_policy = eviction_policy or RejectPolicy()

    engine = CacheEngine(
        storage=storage,
        capacity=CapacityTracker(limits),
        validator=Validator(limits),
        ttl_resolver=TtlResolver(),
        clock=clock,
        locks=LockManager(),
        metrics=metrics,
        eviction_policy=eviction_policy,
    )
    sweeper = Sweeper(
        engine,
        interval_seconds=sweep_interval_seconds,
        batch_size=sweep_batch_size,
    )
    return CacheService(engine, sweeper)
