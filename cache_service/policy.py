"""Eviction policy abstraction.

v1 ships a reject-on-full policy (no eviction). Swapping in LRU/LFU later means
implementing this Protocol and wiring it into the capacity check; the engine and
storage stay unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class EvictionAction(str, Enum):
    REJECT = "REJECT"
    EVICT = "EVICT"  # reserved for future LRU/LFU policies


@dataclass(frozen=True)
class CapacityContext:
    delta_keys: int
    delta_bytes: int
    key_count: int
    byte_count: int
    max_keys: int
    max_bytes: int


@dataclass(frozen=True)
class EvictionDecision:
    action: EvictionAction


class EvictionPolicy(Protocol):
    def on_capacity_exceeded(self, ctx: CapacityContext) -> EvictionDecision:
        ...


class RejectPolicy:
    """Default v1 policy: never evict; reject the write."""

    def on_capacity_exceeded(self, ctx: CapacityContext) -> EvictionDecision:
        return EvictionDecision(action=EvictionAction.REJECT)
