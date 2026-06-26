"""Service configuration and limits."""

from __future__ import annotations

from dataclasses import dataclass

# Defaults derived directly from the requirements document.
DEFAULT_MAX_KEY_CHARS = 100
DEFAULT_MAX_VALUE_BYTES = 10 * 1024  # 10 KB
DEFAULT_MAX_KEYS = 1_000_000
DEFAULT_MAX_BYTES = 1024 ** 3  # 1 GB
DEFAULT_SWEEP_INTERVAL_SECONDS = 3600  # hourly


@dataclass(frozen=True)
class CacheLimits:
    """Hard limits enforced by the service."""

    max_key_chars: int = DEFAULT_MAX_KEY_CHARS
    max_value_bytes: int = DEFAULT_MAX_VALUE_BYTES
    max_keys: int = DEFAULT_MAX_KEYS
    max_bytes: int = DEFAULT_MAX_BYTES
