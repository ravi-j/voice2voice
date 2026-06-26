"""Multi-tenant in-memory cache service (set / get / delete with TTL).

Public entry points:
    - create_cache_service(...): build a ready-to-use service.
    - CacheService: the facade with set/get/delete/exists/stats + lifecycle.
    - Ttl, TtlUnit: TTL inputs.
    - CacheLimits: configurable limits.
"""

from .config import CacheLimits
from .service import CacheService, create_cache_service
from .types import (
    DeleteResult,
    ErrorCode,
    GetResult,
    SetResult,
    StatsResult,
    Ttl,
    TtlUnit,
)

__all__ = [
    "create_cache_service",
    "CacheService",
    "CacheLimits",
    "Ttl",
    "TtlUnit",
    "ErrorCode",
    "SetResult",
    "GetResult",
    "DeleteResult",
    "StatsResult",
]
