"""Shared domain types, results, and error codes for the cache service."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ErrorCode(str, Enum):
    """Error codes returned via result objects (never raised for normal flow)."""

    INVALID_TENANT = "INVALID_TENANT"
    INVALID_KEY = "INVALID_KEY"
    VALUE_TOO_LARGE = "VALUE_TOO_LARGE"
    INVALID_TTL = "INVALID_TTL"
    CAPACITY_EXCEEDED = "CAPACITY_EXCEEDED"
    NOT_FOUND = "NOT_FOUND"


class TtlUnit(str, Enum):
    """Supported TTL granularity for v1."""

    HOURS = "hours"
    DAYS = "days"


@dataclass(frozen=True)
class Ttl:
    """A time-to-live expressed as an integer amount of a single unit."""

    amount: int
    unit: TtlUnit


@dataclass(frozen=True)
class Entry:
    """A stored cache entry plus the metadata needed for TTL and accounting."""

    value: str
    created_at: int  # epoch ms
    expires_at: Optional[int]  # epoch ms, None = never expires
    byte_size: int  # bytes counted toward capacity (key + value)


@dataclass(frozen=True)
class UsageSnapshot:
    """A point-in-time view of storage usage."""

    key_count: int
    byte_count: int


@dataclass(frozen=True)
class SetResult:
    ok: bool
    created: bool = False
    expires_at: Optional[int] = None
    error: Optional[ErrorCode] = None


@dataclass(frozen=True)
class GetResult:
    hit: bool
    value: Optional[str] = None
    expires_at: Optional[int] = None
    error: Optional[ErrorCode] = None


@dataclass(frozen=True)
class DeleteResult:
    deleted: bool
    error: Optional[ErrorCode] = None


@dataclass(frozen=True)
class StatsResult:
    key_count: int
    byte_count: int
    set_count: int
    get_count: int
    delete_count: int
    hit_count: int
    miss_count: int
    rejected_count: int
    expired_count: int
