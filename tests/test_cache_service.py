"""Tests for the multi-tenant cache service, mapping to the requirements doc."""

from __future__ import annotations

import unittest

from cache_service import CacheLimits, Ttl, TtlUnit, create_cache_service
from cache_service.clock import ManualClock
from cache_service.types import ErrorCode


def make_service(clock: ManualClock, limits: CacheLimits | None = None):
    # Large interval so the background thread never interferes; we sweep manually.
    return create_cache_service(
        limits=limits,
        clock=clock,
        sweep_interval_seconds=10_000,
        sweep_batch_size=100,
    )


class SetGetDeleteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = ManualClock(start_ms=1_000_000)
        self.svc = make_service(self.clock)

    def test_set_get_roundtrip(self) -> None:
        res = self.svc.set("t1", "k", "v")
        self.assertTrue(res.ok)
        self.assertTrue(res.created)
        got = self.svc.get("t1", "k")
        self.assertTrue(got.hit)
        self.assertEqual(got.value, "v")

    def test_get_miss(self) -> None:
        got = self.svc.get("t1", "missing")
        self.assertFalse(got.hit)
        self.assertIsNone(got.value)

    def test_overwrite_resets_value(self) -> None:
        self.svc.set("t1", "k", "v1")
        res = self.svc.set("t1", "k", "v2")
        self.assertTrue(res.ok)
        self.assertFalse(res.created)
        self.assertEqual(self.svc.get("t1", "k").value, "v2")

    def test_delete_idempotent(self) -> None:
        self.svc.set("t1", "k", "v")
        self.assertTrue(self.svc.delete("t1", "k").deleted)
        self.assertFalse(self.svc.delete("t1", "k").deleted)
        self.assertFalse(self.svc.get("t1", "k").hit)

    def test_tenant_isolation(self) -> None:
        self.svc.set("t1", "k", "a")
        self.svc.set("t2", "k", "b")
        self.assertEqual(self.svc.get("t1", "k").value, "a")
        self.assertEqual(self.svc.get("t2", "k").value, "b")


class ValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = ManualClock()
        self.svc = make_service(self.clock)

    def test_reject_empty_tenant(self) -> None:
        self.assertEqual(self.svc.set("", "k", "v").error, ErrorCode.INVALID_TENANT)

    def test_reject_long_key(self) -> None:
        res = self.svc.set("t1", "x" * 101, "v")
        self.assertEqual(res.error, ErrorCode.INVALID_KEY)

    def test_accept_max_length_key(self) -> None:
        self.assertTrue(self.svc.set("t1", "x" * 100, "v").ok)

    def test_reject_oversized_value(self) -> None:
        big = "a" * (10 * 1024 + 1)
        self.assertEqual(self.svc.set("t1", "k", big).error, ErrorCode.VALUE_TOO_LARGE)

    def test_accept_max_value(self) -> None:
        ok_value = "a" * (10 * 1024)
        self.assertTrue(self.svc.set("t1", "k", ok_value).ok)

    def test_reject_bad_ttl(self) -> None:
        res = self.svc.set("t1", "k", "v", Ttl(amount=0, unit=TtlUnit.HOURS))
        self.assertEqual(res.error, ErrorCode.INVALID_TTL)


class TtlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = ManualClock(start_ms=0)
        self.svc = make_service(self.clock)

    def test_hours_expiry(self) -> None:
        self.svc.set("t1", "k", "v", Ttl(amount=1, unit=TtlUnit.HOURS))
        self.clock.advance(59 * 60 * 1000)
        self.assertTrue(self.svc.get("t1", "k").hit)
        self.clock.advance(2 * 60 * 1000)  # cross the hour boundary
        self.assertFalse(self.svc.get("t1", "k").hit)

    def test_days_expiry(self) -> None:
        self.svc.set("t1", "k", "v", Ttl(amount=2, unit=TtlUnit.DAYS))
        self.clock.advance(2 * 24 * 60 * 60 * 1000 - 1)
        self.assertTrue(self.svc.get("t1", "k").hit)
        self.clock.advance(2)
        self.assertFalse(self.svc.get("t1", "k").hit)

    def test_no_ttl_never_expires(self) -> None:
        self.svc.set("t1", "k", "v")
        self.clock.advance(10 * 24 * 60 * 60 * 1000)
        self.assertTrue(self.svc.get("t1", "k").hit)

    def test_lazy_expiration_releases_capacity(self) -> None:
        self.svc.set("t1", "k", "v", Ttl(amount=1, unit=TtlUnit.HOURS))
        self.assertEqual(self.svc.stats().key_count, 1)
        self.clock.advance(2 * 60 * 60 * 1000)
        self.assertFalse(self.svc.get("t1", "k").hit)  # triggers lazy purge
        self.assertEqual(self.svc.stats().key_count, 0)


class CapacityTests(unittest.TestCase):
    def test_reject_when_key_cap_reached(self) -> None:
        clock = ManualClock()
        svc = make_service(clock, CacheLimits(max_keys=2))
        self.assertTrue(svc.set("t1", "a", "1").ok)
        self.assertTrue(svc.set("t1", "b", "2").ok)
        res = svc.set("t1", "c", "3")
        self.assertEqual(res.error, ErrorCode.CAPACITY_EXCEEDED)
        self.assertEqual(svc.stats().rejected_count, 1)

    def test_overwrite_does_not_consume_extra_key_slot(self) -> None:
        clock = ManualClock()
        svc = make_service(clock, CacheLimits(max_keys=1))
        self.assertTrue(svc.set("t1", "a", "1").ok)
        self.assertTrue(svc.set("t1", "a", "2").ok)  # overwrite, still 1 key

    def test_byte_cap_enforced(self) -> None:
        clock = ManualClock()
        # key "k" (1 byte) + value -> keep small cap.
        svc = make_service(clock, CacheLimits(max_bytes=10))
        self.assertTrue(svc.set("t", "k", "aaaa").ok)  # 1 + 4 = 5 bytes
        res = svc.set("t", "kk", "bbbbbbb")  # would exceed 10
        self.assertEqual(res.error, ErrorCode.CAPACITY_EXCEEDED)

    def test_delete_frees_capacity(self) -> None:
        clock = ManualClock()
        svc = make_service(clock, CacheLimits(max_keys=1))
        self.assertTrue(svc.set("t", "a", "1").ok)
        self.assertEqual(svc.set("t", "b", "2").error, ErrorCode.CAPACITY_EXCEEDED)
        self.assertTrue(svc.delete("t", "a").deleted)
        self.assertTrue(svc.set("t", "b", "2").ok)


class SweeperTests(unittest.TestCase):
    def test_sweep_removes_expired(self) -> None:
        clock = ManualClock(start_ms=0)
        svc = make_service(clock)
        svc.set("t1", "a", "1", Ttl(amount=1, unit=TtlUnit.HOURS))
        svc.set("t1", "b", "2")  # no ttl
        clock.advance(2 * 60 * 60 * 1000)
        removed = svc.sweep_now()
        self.assertEqual(removed, 1)
        self.assertEqual(svc.stats().key_count, 1)
        self.assertTrue(svc.get("t1", "b").hit)


if __name__ == "__main__":
    unittest.main()
