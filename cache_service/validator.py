"""Centralized validation of tenant, key, value, and TTL inputs."""

from __future__ import annotations

from typing import Optional

from .config import CacheLimits
from .types import ErrorCode, Ttl, TtlUnit


class Validator:
    """Enforces the data constraints defined in the requirements document."""

    def __init__(self, limits: CacheLimits) -> None:
        self._limits = limits

    def validate_tenant(self, tenant_id: str) -> Optional[ErrorCode]:
        if not isinstance(tenant_id, str) or not tenant_id:
            return ErrorCode.INVALID_TENANT
        return None

    def validate_key(self, key: str) -> Optional[ErrorCode]:
        if not isinstance(key, str) or not key:
            return ErrorCode.INVALID_KEY
        if len(key) > self._limits.max_key_chars:
            return ErrorCode.INVALID_KEY
        return None

    def validate_value(self, value: str) -> Optional[ErrorCode]:
        if not isinstance(value, str):
            return ErrorCode.VALUE_TOO_LARGE
        if len(value.encode("utf-8")) > self._limits.max_value_bytes:
            return ErrorCode.VALUE_TOO_LARGE
        return None

    def validate_ttl(self, ttl: Optional[Ttl]) -> Optional[ErrorCode]:
        if ttl is None:
            return None
        if not isinstance(ttl.unit, TtlUnit):
            return ErrorCode.INVALID_TTL
        if not isinstance(ttl.amount, int) or isinstance(ttl.amount, bool):
            return ErrorCode.INVALID_TTL
        if ttl.amount <= 0:
            return ErrorCode.INVALID_TTL
        return None
