# MmapCache — Index + Heap Extension Brief

## Purpose of this document

This document describes the storage work needed to support Raft consensus
persistence in Salt master clusters.  The Raft implementation lives in
`salt/cluster/consensus/` on the `consensus` worktree/branch.  That code
defines a `BaseStorage` abstract interface (`salt/cluster/consensus/raft/log.py`)
that needs a production-grade implementation backed by Salt's mmap
infrastructure.

**Do not implement the storage adapter in the `consensus` branch.**
Implement it here, in the `mmapcache` branch, as an extension to
`salt/utils/mmap_cache.py` and a new `salt/cache/mmap_cache.py` backend.
The `consensus` branch will then depend on this work landing first.

---

## Background: current state of MmapCache

`salt/utils/mmap_cache.py` already exists in this worktree.  It is a
fixed-size open-addressing hash table backed by a single memory-mapped file.

**Current slot layout** (each slot is `slot_size` bytes):

```
[STATUS: 1 byte][DATA: slot_size-1 bytes]
```

`DATA` holds `KEY\x00VALUE` packed into the fixed slot.  This works for
small, uniform records (resource SRNs → minion mappings) but cannot handle
variable-size payloads efficiently (grains dicts, job returns, Raft log
entries).

---

## Required extension: Index + Heap architecture

Extend `MmapCache` to support a **secondary heap file** for variable-size
data.  The index file remains a fixed-size hash table; each slot gains
pointer fields that locate the record's bytes inside the heap.

### New index slot layout

```
Offset  Size  Field
------  ----  -----
0       1     STATUS  (EMPTY=0, OCCUPIED=1, DELETED=2)
1       N     KEY     (null-terminated, N = key_size bytes, fixed per cache)
1+N     8     OFFSET  (uint64 LE, byte offset into heap file)
1+N+8   4     LENGTH  (uint32 LE, byte length of record in heap)
1+N+12  8     MTIME   (uint64 LE, unix timestamp ns, for staleness/TTL)
1+N+20  R     RESERVED / padding to slot_size
```

`key_size` is a constructor parameter (default 64 bytes), so `slot_size`
must be at least `1 + key_size + 20`.  Recommended default: `key_size=64`,
`slot_size=96`.

### Heap file layout

The heap is a flat binary file.  Records are appended sequentially.  There
is no per-record header — the index slot's `LENGTH` field delimits each
record.  Deleted/superseded records become unreachable garbage; they are
reclaimed during `atomic_rebuild`.

```
[record_0_bytes][record_1_bytes][record_2_bytes]...
```

The heap file path is `<index_path>.heap` by convention (or passed
explicitly as `heap_path=`).

### Updated `MmapCache` constructor

```python
MmapCache(
    path,                    # index file path (existing)
    size=1_000_000,          # number of index slots (existing)
    slot_size=96,            # bytes per index slot (updated default)
    key_size=64,             # max key length in bytes (new)
    heap_path=None,          # defaults to path + ".heap" (new)
    staleness_check_interval=0.25,  # existing
)
```

When `heap_path` is `None` the implementation appends `.heap` to `path`.

### Updated public API

All existing methods (`put`, `get`, `delete`, `contains`, `list_items`,
`atomic_rebuild`) keep their signatures.  Behaviour changes:

- **`put(key, value)`** — serialises `value` to bytes (caller's
  responsibility; pass `bytes`), appends to heap, writes index slot with
  offset+length.  If key already exists and new value fits in the existing
  heap region, overwrite in place; otherwise append and update pointer.
- **`get(key, default=None)`** — reads index slot to find offset+length,
  returns `bytes` read from heap mmap at that region.  Returns `default` if
  not found.
- **`delete(key)`** — marks index slot `DELETED`; heap bytes become
  unreachable garbage (reclaimed at next `atomic_rebuild`).
- **`atomic_rebuild(iterator)`** — writes a new temp index + new temp heap,
  packs heap contiguously (defragmentation), then atomically swaps both
  files.  Use a two-phase rename: swap heap first, then index, so readers
  always have a consistent pair.
- **`get_stats()`** — add `heap_size_bytes` and `heap_live_bytes` fields.

The heap file should be opened as a second `mmap.mmap` alongside the index
mmap and kept open between calls (same staleness-check lifecycle as the
index mmap).

---

## New cache backend: `salt/cache/mmap_cache.py`

Implement a `salt.cache` backend module (following the existing pattern of
`salt/cache/localfs.py`) that wraps `MmapCache` with the Index + Heap
extension.

The `salt.cache` interface methods to implement:

```python
def store(bank, key, data, cachedir):    ...
def fetch(bank, key, cachedir):          ...
def updated(bank, key, cachedir):        ...
def flush(bank, key, cachedir):          ...  # delete one key
def list(bank, cachedir):                ...
def contains(bank, key, cachedir):       ...
```

One `MmapCache` instance per `bank` (lazily constructed, cached in a
module-level dict keyed by `(cachedir, bank)`).  Data is serialised with
`salt.payload` (msgpack) before being handed to `MmapCache.put`, and
deserialised with `salt.payload` in `fetch`.

`updated` reads the `MTIME` field from the index slot directly (no heap
read needed) and returns it as a Unix timestamp float.

---

## Raft-specific requirements the storage must satisfy

The `BaseStorage` interface the Raft consensus layer needs:

```python
class BaseStorage:
    def save_state(self, term, voted_for): ...   # called on every term/vote change
    def load_state(self):                  ...   # returns {"term": int, "voted_for": str|None}
    def save_log(self, entries):           ...   # full rewrite (truncation/recovery)
    def append_log(self, entry):           ...   # single O(1) append (hot path)
    def load_log(self):                    ...   # returns list[LogEntry] in index order
    def save_snapshot(self, data, index, term): ...
    def load_snapshot(self):               ...   # returns {"data": bytes, "index": int, "term": int} | None
```

A `SaltCacheStorage(BaseStorage)` class should live in
`salt/cluster/consensus/raft/storage.py` (on the `consensus` branch, once
this work lands).  It will use `salt.cache` with the mmap backend via:

```python
import salt.cache
cache = salt.cache.factory(opts)   # uses opts["cache"] = "mmap_cache"
```

Key mapping:

| Raft field       | bank               | key                     |
|------------------|--------------------|-------------------------|
| term + voted_for | `cluster/raft`     | `state`                 |
| log entry N      | `cluster/raft/log` | `<N>` (zero-padded int) |
| snapshot         | `cluster/raft`     | `snapshot`              |

`append_log` uses `cache.store(bank, key, data)` — the mmap backend makes
this O(1) heap-append + index slot write, which is the performance
requirement.

`load_log` fetches all keys from `cluster/raft/log`, sorts by integer key
value, and reconstructs `LogEntry` namedtuples.  This is only called on
startup (recovery path), so a full bank scan is acceptable.

`save_state` **must** call `cache.store` synchronously and durably —
`currentTerm` and `votedFor` are the two Raft safety-critical fields that
must survive a crash.  Ensure `mmap.flush()` + `os.fsync()` on the heap
write before returning.

---

## Suggested implementation order

1. Extend `MmapCache` slot layout with offset/length/mtime fields and add
   the heap file (`mmap_cache.py`).  Update `atomic_rebuild` to defragment
   both files atomically.

2. Write unit tests for the extended `MmapCache` (index+heap round-trip,
   overwrite-in-place, grow-appends-to-heap, atomic rebuild defragments).

3. Implement `salt/cache/mmap_cache.py` backend.

4. Write unit/functional tests for the cache backend (store/fetch/updated/
   flush/list round-trips, cross-process reads via two `MmapCache` instances
   on the same file).

5. Signal to the `consensus` branch that `SaltCacheStorage` can now be
   written against `salt.cache` with `cache = "mmap_cache"` in opts.

---

## Files to create / modify

| File | Action |
|------|--------|
| `salt/utils/mmap_cache.py` | Extend with heap file support |
| `salt/cache/mmap_cache.py` | New `salt.cache` backend module |
| `tests/pytests/unit/utils/test_mmap_cache.py` | Extend existing tests |
| `tests/pytests/unit/cache/test_mmap_cache.py` | New cache backend tests |

Do **not** touch anything under `salt/cluster/` — that belongs to the
`consensus` branch.
