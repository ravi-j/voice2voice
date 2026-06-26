"""Per-tenant lock management to serialize read-modify-write sequences per keyspace."""

from __future__ import annotations

import threading


class LockManager:
    """Hands out a stable RLock per tenant id.

    Read-modify-write sequences (set/get-expire/delete/sweep) for a given tenant
    are serialized through that tenant's lock, keeping capacity accounting and
    storage mutations consistent without a single global bottleneck.
    """

    def __init__(self) -> None:
        self._master = threading.Lock()
        self._locks: dict[str, threading.RLock] = {}

    def for_tenant(self, tenant_id: str) -> threading.RLock:
        lock = self._locks.get(tenant_id)
        if lock is not None:
            return lock
        with self._master:
            lock = self._locks.get(tenant_id)
            if lock is None:
                lock = threading.RLock()
                self._locks[tenant_id] = lock
            return lock
