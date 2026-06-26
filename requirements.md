# Requirements Document: Multi-Tenant Cache Service (v1)

## 1. Overview
A multi-tenant, in-memory cache service exposing `set`, `get`, and `delete` with TTL support. Each request is associated with a tenant, and keys are isolated per tenant. The service enforces strict key/value size limits and storage caps, and runs a background sweeper to remove expired entries.

## 2. Actors
- **Tenant**: an isolated consumer of the cache. Each tenant has its own logical keyspace.
- **Caller/User**: an authenticated client acting on behalf of a tenant that issues `set`/`get`/`delete` commands.

## 3. Functional Requirements
- **FR1 Set**: store a value under a tenant-scoped key with an optional TTL. Overwrites existing value and resets metadata.
- **FR2 Get**: return the current value for a tenant-scoped key, or a miss if absent or expired.
- **FR3 Delete**: remove a tenant-scoped key; report whether a key was deleted or not found.
- **FR4 TTL**: every `set` may specify a TTL expressed in hours or days. After expiry, the key is treated as a miss.
- **FR5 Tenant isolation**: identical key names in different tenants are independent and never collide.

## 4. Data Constraints
- **Key**: string, maximum 100 characters. Empty keys are rejected.
- **Value**: string, maximum 10 KB per value.
- **TTL granularity**: hours and days only (no sub-hour granularity in v1). TTL is optional; absent TTL means no expiration.

## 5. Capacity / Storage Limits
- Maximum **1,000,000 keys total** OR **1 GB total memory**, whichever limit is reached first.
- When either cap is reached, new writes are rejected with a capacity error (no eviction in v1).
- **Open decision**: whether the 1M/1GB cap is global across all tenants or per-tenant (see Open Questions).

## 6. Expiration & Cleanup
- Background sweeper runs every **1 hour** and removes expired keys to reclaim memory.
- Reads must also treat expired-but-not-yet-swept keys as a miss (lazy expiration) to ensure correctness between sweeps.

## 7. Error Handling (expected behavior)
- Reject keys longer than 100 characters.
- Reject values larger than 10 KB.
- Reject invalid TTL units (anything other than hours/days).
- Reject writes when capacity caps are exceeded.
- Missing tenant context is rejected as an authorization/validation error.

## 8. Non-Functional Requirements
- In-memory storage for low-latency access.
- Deterministic command semantics (overwrite, miss, delete idempotency).
- Observability hooks for hit/miss counts, key count, memory usage, expired/swept counts, and rejected-write counts.

## 9. Out of Scope (v1)
- Eviction strategies (LRU/LFU).
- Persistence/durability across restarts.
- Sub-hour TTL granularity.
- Clustering/replication and full Redis protocol parity.

## 10. Open Questions
1. Are the 1M-key / 1GB-memory caps global or per-tenant?
2. Is there a per-tenant quota in addition to the global cap?
3. Should TTL accept a combined value (e.g., hours + days) or a single unit per request?
4. What transport is expected for v1 (library API vs HTTP/TCP service)?
