# MmapCache — Enterprise Readiness Gap Analysis

**Branch**: `mmapcache`
**Date**: 2026-04-28
**Status of implementation**: functionally complete, benchmarked, pre-commit clean.

This document records what is required before `MmapCache` and `salt/cache/mmap_cache.py`
can be considered production-grade.  Each item includes the concrete failure mode
observed in testing, the required fix, and its expected benchmark impact.

---

## Summary table

| # | Gap | Severity | Benchmark impact |
|---|-----|----------|-----------------|
| 1 | Thread safety — `fcntl.flock` is per-process, not per-thread | **Blocker** | ~0% |
| 2 | Heap corruption is silent | **Blocker** | ~1-2% |
| 3 | Roster/index can diverge after crash | **Blocker** | ~0% |
| 4 | Key silently truncated to `key_size` | Medium | ~0% |
| 5 | Index full causes silent write loss | Medium | ~0% |
| 6 | Persistent fd paths have no failure tests | Medium | ~0% |
| 7 | Heap grows without bound between rebuilds | Medium | ~0% |
| 8 | Observability hooks absent | Low | ~0% |
| 9 | Operational documentation missing | Low | ~0% |

Seven of nine items cost nothing at runtime.  The one exception (per-entry heap CRC)
adds ~100 ns per read/write — about 1-2% overhead against current benchmarks.

---

## 1. Thread safety  [BLOCKER]

### Failure mode

`fcntl.flock` is a POSIX advisory lock applied per *process*, not per *thread*.
Two threads in the same process both pass through `_lock()` simultaneously because
neither sees the other's lock.  Observed directly:

```
# 4 threads writing "shared_key" concurrently → 1 put() returned False
1. Concurrent writers: result='value_1', errors=[2]
```

The `_roster_wfd`, `_lock_fd`, and `_heap_fd` persistent file descriptors are
shared across threads on the same `MmapCache` instance with no synchronisation.
Concurrent writes can interleave partial roster entries or corrupt the mmap
flush sequence.

### Required fix

Add a `threading.RLock` at the `MmapCache` instance level.  All write-path
methods (`put`, `delete`, `atomic_rebuild`) must acquire it before entering
`_lock()`.  Read-path methods (`get`, `get_mtime`, `list_keys`, `list_items`)
need a shared read-lock to prevent tearing during a concurrent write that
grows and re-mmaps the heap.

```python
# In __init__
self._thread_lock = threading.RLock()

# In put() / delete() / atomic_rebuild()
with self._thread_lock:
    with self._lock():   # existing fcntl path
        ...

# In get() / list_keys() / list_items()
with self._thread_lock:
    ...
```

A `threading.RLock` acquire with no contention costs ~50 ns — unmeasurable
against the 5–10 µs per-operation baseline.

### Files

- `salt/utils/mmap_cache.py` — add `threading` import, `_thread_lock` field,
  wrap all public methods.
- `tests/pytests/unit/utils/test_mmap_cache.py` — add concurrent-writer test
  (ThreadPoolExecutor, assert no data loss and no False returns under load).

---

## 2. Heap corruption is silent  [BLOCKER]

### Failure mode

If the heap file is truncated (OS crash, disk full, `SIGKILL` mid-write),
index slots still point to the now-invalid heap region.  The current code reads
whatever bytes are available, strips trailing nulls, and returns the result as a
valid value — or returns `True` (set-mode) when zero bytes are left.  The caller
has no way to detect the corruption.

```
# heap truncated to 2 bytes after a 15-byte write
3. Heap truncated: k1='v1', k2=True  ← silently wrong, should be an error
```

### Required fix

Prepend a 4-byte CRC32 checksum to every heap entry at write time.
`_read_from_heap` verifies the checksum and returns `None` on mismatch,
causing `get()` to return `default` and `list_items()` to skip the entry.
Both log an `ERROR` with the affected key and heap offset.

**On-heap record format (new)**:

```
[CRC32: 4 bytes LE][VALUE: length bytes]
```

The `LENGTH` field in the index slot continues to record the value length only
(not including the 4-byte prefix).  `_append_to_heap` prepends the CRC;
`_read_from_heap` strips and verifies it.  `_overwrite_in_heap` recomputes the
CRC when overwriting in place.

`atomic_rebuild` verifies each entry as it copies it, skipping corrupt records
and logging a warning (rather than aborting the entire rebuild).

**Benchmark impact**: `zlib.crc32` on a 200-byte payload costs ~100 ns
(hardware-accelerated).  This adds ~1-2% to `put` and `get` latency at current
throughput levels.  Make verification opt-in via `verify_checksums=True`
constructor parameter (default `True`; can be disabled for maximum throughput
in trusted environments).

### Files

- `salt/utils/mmap_cache.py` — update `_append_to_heap`, `_read_from_heap`,
  `_overwrite_in_heap`, `atomic_rebuild`.
- `tests/pytests/unit/utils/test_mmap_cache.py` — test that a truncated heap
  returns `default` (not corrupt data), and that `atomic_rebuild` skips corrupt
  entries.
- `tests/pytests/unit/utils/test_mmap_cache_errors.py` — test CRC mismatch
  detection.

---

## 3. Roster / index divergence after crash  [BLOCKER]

### Failure mode

The write sequence for a new key is:

1. Acquire `fcntl` lock
2. Write heap bytes
3. Write index slot + set STATUS = OCCUPIED
4. Update header counters (`occupied_count`, `high_water_mark`)
5. `mmap.flush()`
6. Release lock
7. `_roster_append(slot)` — appends to roster file

Step 7 happens *outside* the lock.  A crash or `SIGKILL` between steps 6 and 7
leaves the entry queryable via `get()` (index is consistent) but invisible to
`list_keys()` and `list_items()` (roster does not contain the slot).

Also observed: deleting the roster file makes all keys invisible:

```
2. Roster deleted: list_keys=[]  ← 2 keys exist in index, none returned
```

### Required fix

**Recovery on `open()`**: when opening a writable cache, compare the roster
entry count against `occupied_count` from the header.  If they differ, rebuild
the roster from the index (O(high_water_mark) scan — bounded and fast).

```python
def _roster_recover(self):
    """Rebuild roster from index if counts diverge."""
    occupied, _, hwm = self._read_header()
    slots = []
    for slot in range(1, min(hwm + 2, self.size)):
        if self._mm[slot * self.slot_size] == OCCUPIED:
            slots.append(slot)
    if len(slots) != occupied:
        # Header is also wrong; trust the scan
        struct.pack_into(_OFFSET_FMT, self._mm, _HDR_OCCUPIED_OFF, len(slots))
    # Atomically replace the roster
    data = struct.pack(f"<{len(slots)}I", *slots) if slots else b""
    tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(self.roster_path))
    with os.fdopen(tmp_fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, self.roster_path)
```

Call `_roster_recover()` at the end of `open(write=True)` if
`len(self._roster_read()) != occupied_count`.

**Move roster append inside the lock**: append the roster entry before releasing
`fcntl.flock` so crash between steps 6 and 7 cannot occur.  The persistent
`_roster_wfd` already makes this cheap.

### Files

- `salt/utils/mmap_cache.py` — add `_roster_recover`, call from `open(write=True)`,
  move `_roster_append` call to inside `_lock()` context in `put()`.
- `tests/pytests/unit/utils/test_mmap_cache_errors.py` — test recovery when
  roster is deleted or truncated.

---

## 4. Silent key truncation  [MEDIUM]

### Failure mode

Keys longer than `key_size` are silently truncated at the byte level:

```
# key_size=32, key length=64
4. Long key: get(full)='v', get(truncated)='v'  ← both find the same slot
```

Two distinct logical keys that share the same first `key_size` bytes will
collide and overwrite each other without any error or warning.

### Required fix

Raise `ValueError` in `put()` and `get()` (and `delete()`, `get_mtime()`) if
the encoded key exceeds `key_size`:

```python
key_bytes = salt.utils.stringutils.to_bytes(key)
if len(key_bytes) > self.key_size:
    raise ValueError(
        f"Key {key!r} is {len(key_bytes)} bytes, exceeds key_size={self.key_size}"
    )
```

The `salt/cache/mmap_cache.py` layer should catch this and raise `SaltCacheError`.

### Files

- `salt/utils/mmap_cache.py` — add length check in `put`, `get`, `delete`,
  `get_mtime`.
- `salt/cache/mmap_cache.py` — wrap in `SaltCacheError`.
- Tests — add test for oversized key.

---

## 5. Index full causes silent write loss  [MEDIUM]

### Failure mode

When `occupied + deleted ≥ size - 1`, `put()` logs an ERROR and returns `False`.
`salt/cache/mmap_cache.py` then raises `SaltCacheError`.  The caller loses the
write with no automatic recovery path.  In a 1 M-slot default index this is
unlikely but not impossible (e.g. a bank that accumulates entries without
periodic `atomic_rebuild` / flush).

There is also no built-in trigger for `atomic_rebuild` to compact DELETED slots
and recover capacity.

### Required fix

**Automatic compaction trigger**: after `put()` finds the table full or
`load_factor > threshold` (recommended: 0.75), schedule an `atomic_rebuild`
using a background thread.  Until the rebuild completes, new writes fail fast
with a clear error.

**Load factor warning**: log a `WARNING` when `load_factor` crosses 0.5 and
0.7, giving operators time to respond before writes fail.

**Resize path**: add `new_size` parameter to `atomic_rebuild` so operators can
increase table capacity without restarting the process:

```python
cache.atomic_rebuild(cache.list_items(), new_size=2_000_000)
```

**Index-full metric**: expose `load_factor` and `slots_remaining` via
`get_stats()` (already done) and via the observability hook (see item 8).

### Files

- `salt/utils/mmap_cache.py` — `new_size` parameter on `atomic_rebuild`,
  load factor warning in `put()`.
- `salt/cache/mmap_cache.py` — surface `SaltCacheError` with actionable message
  including current load factor.
- Tests — test `atomic_rebuild(new_size=...)` doubles the table capacity.

---

## 6. Persistent fd paths lack failure tests  [MEDIUM]

### What is untested

The three persistent file descriptors introduced for performance —
`_lock_fd`, `_roster_wfd`, `_heap_fd` — each have an error fallback path:

| fd | Failure path | Covered? |
|----|-------------|---------|
| `_lock_fd` | `fopen` fails → falls back to per-call open | No |
| `_roster_wfd` | `OSError` on `write()` → closes fd, re-opens next call | No |
| `_roster_wfd` | `OSError` on `seek()` in fast-path tombstone → falls back to file scan | No |
| `_heap_fd` | `mmap` fails → falls back to `fopen` per read | No |
| `_close_mmaps_and_fds` | called from `atomic_rebuild` while `_lock_fd` is still live | Tested (regression caught during dev) |

These paths are the most dangerous in production — a transient `EMFILE` (too
many open files) or filesystem error that hits one of these fds would silently
degrade to the slower fallback (best case) or lose data (worst case).

### Required fix

Add tests using `unittest.mock.patch` to simulate `OSError` on each path and
assert correct fallback behaviour:

```python
# Example: roster wfd seek fails → slow-path tombstone used
def test_roster_remove_falls_back_to_file_scan_on_seek_error(cache):
    cache.put("k", "v")
    with patch.object(cache._roster_wfd, "seek", side_effect=OSError):
        assert cache.delete("k") is True
    assert cache.get("k") is None
```

Also add a multi-process test (using `multiprocessing.Process`) that verifies
two separate processes can write and read from the same index+heap without
data loss — this is the primary deployment model for Salt.

### Files

- `tests/pytests/unit/utils/test_mmap_cache_errors.py` — fd failure paths.
- New `tests/pytests/functional/cache/test_mmap_cache_multiprocess.py` —
  multi-process read/write correctness under `pytest-xdist` or direct
  `multiprocessing.Process` usage.

---

## 7. Heap grows without bound between rebuilds  [MEDIUM]

### Failure mode

`delete()` marks a slot DELETED and tombstones the roster, but the heap bytes
remain.  `put()` of a new, larger value for an existing key also leaves the old
heap region as garbage.  Without periodic `atomic_rebuild`, the heap file grows
monotonically.

`get_stats()` exposes `heap_size_bytes` vs `heap_live_bytes`, so the
fragmentation ratio (`1 - live/total`) is computable.  But nothing acts on it.

### Required fix

**Expose fragmentation in `get_stats()`**: add `heap_fragmentation_ratio` key
(already computable from existing fields).

**Log a warning** when fragmentation exceeds a threshold (recommended: 0.5 —
i.e. more than half the heap is garbage):

```python
frag = 1.0 - heap_live / heap_size if heap_size > 0 else 0.0
if frag > 0.5:
    log.warning(
        "Heap fragmentation at %.0f%% for %s — consider atomic_rebuild",
        frag * 100, self.path
    )
```

**Document** the `atomic_rebuild` call pattern for operators (see item 9).

**For Raft specifically**: Raft log compaction (snapshot + log truncation) maps
directly to `atomic_rebuild` — the Raft storage adapter should call it after
every snapshot.

### Files

- `salt/utils/mmap_cache.py` — add `heap_fragmentation_ratio` to `get_stats()`,
  add fragmentation warning log.
- Docs.

---

## 8. Observability hooks  [LOW]

### What is missing

No metrics are emitted.  Operators cannot alert on:
- `load_factor > 0.7` (approaching index full)
- `heap_fragmentation_ratio > 0.5` (approaching disk pressure)
- Per-operation latency (no timing instrumentation)

### Required fix

Add an optional `metrics_callback` constructor parameter:

```python
MmapCache(
    path,
    ...,
    metrics_callback=None,   # callable(metric_name: str, value: float, tags: dict)
)
```

When set, call it after each operation:

```python
# Example emission points
if self._metrics:
    self._metrics("mmap_cache.put.latency_us", elapsed_us, {"bank": bank})
    self._metrics("mmap_cache.load_factor", load_factor, {"bank": bank})
```

This adds one `if self._metrics:` branch per operation — zero cost when
`metrics_callback=None` (the default).

Alternatively, integrate with Salt's existing `salt.utils.stats` pattern if one
exists, or leave as a callback so callers (Raft storage adapter, monitoring
tooling) can wire in Prometheus, StatsD, or OpenTelemetry as appropriate.

### Files

- `salt/utils/mmap_cache.py` — `metrics_callback` parameter, emission points.
- `salt/cache/mmap_cache.py` — thread through from `__opts__` if configured.

---

## 9. Operational documentation  [LOW]

### What is missing

The `.rst` stub at `doc/ref/cache/all/salt.cache.mmap_cache.rst` exists but
contains only `automodule`.  Operators need guidance on:

**Sizing the index**: the index cannot be resized without `atomic_rebuild`.
A rule of thumb: set `mmap_cache_size` to 10× the maximum expected number of
keys in the bank.  A 1 M-slot index at 96 bytes/slot uses 96 MB of virtual
address space (not necessarily resident RAM — the OS pages it on demand).

**Monitoring**: watch `load_factor` (alert > 0.7) and `heap_fragmentation_ratio`
(alert > 0.5) via `get_stats()`.  Wire into Salt's existing event bus or an
external metrics sink.

**Compaction**: run `atomic_rebuild(cache.list_items())` to defragment the heap
and compact DELETED index slots.  In Raft deployments this should be triggered
after every snapshot.  For general cache use, a cron or Salt scheduled job that
calls `atomic_rebuild` when fragmentation exceeds a threshold is sufficient.

**Migration from `localfs`**: no in-place migration exists.  The simplest path
is to change `cache: mmap_cache` in master config and let the cache warm
naturally.  For Raft, populate the mmap cache from a `localfs` snapshot using:

```python
import salt.cache
old = salt.cache.factory({**opts, "cache": "localfs"})
new = salt.cache.factory({**opts, "cache": "mmap_cache"})
for key in old.list("cluster/raft/log"):
    new.store("cluster/raft/log", key, old.fetch("cluster/raft/log", key))
```

**Durability guarantees** (explicit statement needed in docs):

| Operation | Survives crash? |
|-----------|----------------|
| `store` (index mmap flush) | Yes — index is durable after `mmap.flush()` |
| `store` (heap append, no fsync) | Probably — OS write-back, but not guaranteed |
| `store` (Raft `save_state`) | Yes — must call `os.fsync(heap_fd)` explicitly |
| `delete` (tombstone) | Yes — in-place write, durable after flush |
| `atomic_rebuild` | Yes — atomic `os.replace` on all three files |
| Roster (no fsync on append) | No — may need recovery scan on restart (item 3) |

### Files

- `doc/ref/cache/all/salt.cache.mmap_cache.rst` — expand with sizing, monitoring,
  compaction, migration, and durability sections.

---

## Implementation order

Implement in this order to unblock the Raft work as early as possible:

1. **Item 3** — Move roster append inside the lock.  One-line change, zero risk.
2. **Item 1** — Add `threading.RLock`.  Required before any multi-threaded test.
3. **Item 3** — Add `_roster_recover()` called from `open(write=True)`.
4. **Item 4** — Key length check.  Trivial, prevents a class of silent bugs.
5. **Item 2** — Heap CRC.  Most complex; implement as opt-in first
   (`verify_checksums=False` default) so existing tests pass unchanged, then
   flip default to `True`.
6. **Item 6** — Tests for persistent fd failure paths and multi-process
   correctness.
7. **Item 5** — Index resize and load factor warning.
8. **Item 7** — Heap fragmentation warning and ratio in `get_stats()`.
9. **Items 8–9** — Observability and docs.

---

## What is already complete

For reference, the following are implemented, tested, and benchmarked:

- Index + heap architecture with per-slot offset/length/mtime fields
- Roster file for O(occupied) `list_keys()` / `list_items()` independent of table size
- Header slot with `occupied_count`, `deleted_count`, `high_water_mark`
- Persistent `_lock_fd`, `_roster_wfd` for amortised per-operation fd cost
- Lazy heap mmap (stale flag, re-open on first read after write)
- O(1) roster tombstone via in-memory byte-offset map (`_roster_slot_offsets`)
- Raw `msgpack.packb`/`msgpack.unpackb` replacing `salt.payload` (12× faster deserialization)
- `salt/cache/mmap_cache.py` drop-in replacement for `localfs`
- 89 unit tests, pre-commit clean (black, pylint, isort, bandit)
- Full benchmark suite showing mmap wins every operation vs localfs:

```
store_small       43k → 120k ops/s   (+181%)
store_large       31k →  96k ops/s   (+206%)
fetch_warm        52k → 162k ops/s   (+213%)
fetch_large       42k → 104k ops/s   (+148%)
updated          141k → 544k ops/s   (+285%)
list              27k →  32k ops/s    (+19%)
sequential_append 38k →  99k ops/s   (+161%)
flush_key         90k → 198k ops/s   (+119%)
bulk_store+scan  747  → 1574 ops/s   (+111%)
```
