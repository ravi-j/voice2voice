"""Storage backend abstraction. Swap the in-memory impl for a persistent/sharded one later."""

from __future__ import annotations

from typing import List, Optional, Protocol, Tuple

from ..types import Entry, UsageSnapshot

# (tenant_id, key, entry) tuples describing expired entries.
ExpiredEntry = Tuple[str, str, Entry]


class StorageBackend(Protocol):
    """Physical storage of entries, partitioned by tenant.

    Implementations are not responsible for capacity accounting, TTL policy, or
    locking semantics beyond their own structural integrity; the engine drives
    those concerns.
    """

    def read(self, tenant_id: str, key: str) -> Optional[Entry]:
        ...

    def write(self, tenant_id: str, key: str, entry: Entry) -> None:
        ...

    def remove(self, tenant_id: str, key: str) -> bool:
        """Remove a key. Returns True if a key was removed."""
        ...

    def collect_expired(self, now_ms: int, limit: int) -> List[ExpiredEntry]:
        """Return up to `limit` entries that have expired as of `now_ms`.

        Returns a materialized snapshot so the caller can remove them safely
        under per-tenant locks without mutating during iteration.
        """
        ...

    def snapshot(self) -> UsageSnapshot:
        ...
