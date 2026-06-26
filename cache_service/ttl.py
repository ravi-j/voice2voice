"""TTL resolution: converts a (amount, unit) TTL into an absolute expiry timestamp."""

from __future__ import annotations

from typing import Optional

from .types import Ttl, TtlUnit

_MS_PER_HOUR = 60 * 60 * 1000
_MS_PER_DAY = 24 * _MS_PER_HOUR

# Centralized unit table; adding finer granularity later is a one-line change here.
_UNIT_TO_MS = {
    TtlUnit.HOURS: _MS_PER_HOUR,
    TtlUnit.DAYS: _MS_PER_DAY,
}


class TtlResolver:
    """Resolves a TTL relative to a given 'now' into an absolute expiry (epoch ms)."""

    def resolve(self, now_ms: int, ttl: Optional[Ttl]) -> Optional[int]:
        if ttl is None:
            return None
        return now_ms + ttl.amount * _UNIT_TO_MS[ttl.unit]
