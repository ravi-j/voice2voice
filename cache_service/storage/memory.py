"""In-memory storage backend (v1).

Layout: ``{tenant_id: {key: Entry}}`` for O(1) per-key access and natural tenant
isolation. Structural mutations of the top-level tenant map are guarded by an
internal lock; per-key read-modify-write consistency is provided by the engine's
per-tenant locks.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from ..types import Entry, UsageSnapshot
from .backend import ExpiredEntry


class InMemoryStore:
    def __init__(self) -> None:
        self._data: Dict[str, Dict[str, Entry]] = {}
        self._struct_lock = threading.Lock()

    def read(self, tenant_id: str, key: str) -> Optional[Entry]:
        tenant = self._data.get(tenant_id)
        if tenant is None:
            return None
        return tenant.get(key)

    def write(self, tenant_id: str, key: str, entry: Entry) -> None:
        tenant = self._data.get(tenant_id)
        if tenant is None:
            with self._struct_lock:
                tenant = self._data.setdefault(tenant_id, {})
        tenant[key] = entry

    def remove(self, tenant_id: str, key: str) -> bool:
        tenant = self._data.get(tenant_id)
        if tenant is None:
            return False
        existed = tenant.pop(key, None) is not None
        if existed and not tenant:
            with self._struct_lock:
                # Re-check emptiness under lock before dropping the submap.
                if tenant_id in self._data and not self._data[tenant_id]:
                    del self._data[tenant_id]
        return existed

    def collect_expired(self, now_ms: int, limit: int) -> List[ExpiredEntry]:
        expired: List[ExpiredEntry] = []
        # Snapshot tenant ids first to avoid holding the lock during iteration.
        tenant_ids = list(self._data.keys())
        for tenant_id in tenant_ids:
            tenant = self._data.get(tenant_id)
            if tenant is None:
                continue
            for key, entry in list(tenant.items()):
                if entry.expires_at is not None and entry.expires_at <= now_ms:
                    expired.append((tenant_id, key, entry))
                    if len(expired) >= limit:
                        return expired
        return expired

    def snapshot(self) -> UsageSnapshot:
        key_count = 0
        byte_count = 0
        for tenant in list(self._data.values()):
            for entry in list(tenant.values()):
                key_count += 1
                byte_count += entry.byte_size
        return UsageSnapshot(key_count=key_count, byte_count=byte_count)
