import contextlib
import errno
import logging
import mmap
import os
import time
import zlib

import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils

try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

log = logging.getLogger(__name__)

# Status constants
EMPTY = 0
OCCUPIED = 1
DELETED = 2

#: Minimum interval between ``os.stat`` staleness checks on an already-open
#: mmap. Without throttling, every ``get()`` syscalls. Overridable per
#: instance via ``MmapCache(path, staleness_check_interval=...)``.
DEFAULT_STALENESS_CHECK_INTERVAL = 0.25  # seconds


# ---------------------------------------------------------------------------
# Sorted-placement compactor (O(N log N) vs naive O(N^2) open addressing).
#
# Rationale and correctness proof: see ``mmap-compaction-design.md``.
# In short: for linear-probing hash tables without deletions the *set* of
# occupied slots depends only on the key set and the hash, not on
# insertion order. Sorting items by their home slot and packing each
# cluster contiguously from a monotone cursor produces a valid layout
# that any reader using the same hash + linear probe can search.
# ---------------------------------------------------------------------------


def _write_slot(buf, slot, slot_size, data_bytes):
    """
    Write ``data_bytes`` into the given slot and flip the status byte to
    OCCUPIED. Caller is responsible for the slot being reachable from
    readers probing from the correct home.
    """
    off = slot * slot_size
    ld = len(data_bytes)
    buf[off + 1 : off + 1 + ld] = data_bytes
    if ld < slot_size - 1:
        buf[off + 1 + ld] = 0
    buf[off] = OCCUPIED


def _naive_probe_insert(buf, home, num_slots, slot_size, data_bytes):
    """
    Place ``data_bytes`` at the first non-OCCUPIED slot reachable from
    ``home`` via linear probing. Used as the wrap-around fallback for
    :func:`pack_sorted`.
    """
    for i in range(num_slots):
        slot = (home + i) % num_slots
        if buf[slot * slot_size] != OCCUPIED:
            _write_slot(buf, slot, slot_size, data_bytes)
            return
    raise RuntimeError("mmap cache full during sorted-placement overflow")


def pack_sorted(buf, items, num_slots, slot_size):
    """
    O(N log N) compaction placement into a zero-initialised buffer.

    :param buf: ``mmap.mmap`` or ``bytearray`` of size
        ``num_slots * slot_size``, zero-initialised. Mutated in place.
    :param items: Iterable of ``(key_bytes, data_bytes)`` tuples, where
        ``data_bytes`` is the full per-slot payload starting at ``offset+1``
        (i.e. the key, or ``key + b"\\x00" + value``). ``data_bytes`` must be
        shorter than ``slot_size`` and must start with the key bytes used to
        compute the probe home.
    :param int num_slots: Total slot count (``MmapCache.size``).
    :param int slot_size: Per-slot byte width (``MmapCache.slot_size``).

    Duplicate keys: the last occurrence wins, matching the naive rebuild's
    "insert over existing" semantics.

    Complexity: ``O(N log N)`` from the sort plus one pass of ``N`` writes.
    Wrap-around (a cluster that straddles ``num_slots``) falls back to
    linear-probe insert for just the overflow tail.
    """
    deduped = {}
    for key_bytes, data_bytes in items:
        if len(data_bytes) >= slot_size:
            raise ValueError(
                "pack_sorted: data {} does not fit in slot_size {}".format(
                    len(data_bytes), slot_size
                )
            )
        deduped[key_bytes] = data_bytes

    indexed = [(zlib.adler32(k) % num_slots, k, d) for k, d in deduped.items()]
    indexed.sort(key=lambda t: t[0])

    cursor = 0
    overflow_from = None
    for idx, (home, _k, data_bytes) in enumerate(indexed):
        if cursor < home:
            cursor = home
        if cursor >= num_slots:
            overflow_from = idx
            break
        _write_slot(buf, cursor, slot_size, data_bytes)
        cursor += 1

    if overflow_from is not None:
        for home, _k, data_bytes in indexed[overflow_from:]:
            _naive_probe_insert(buf, home, num_slots, slot_size, data_bytes)


def pack_naive(buf, items, num_slots, slot_size):
    """
    O(N^2) worst-case reference packer. Kept for parity testing against
    :func:`pack_sorted` and as a diagnostic fallback. Prefer
    ``pack_sorted`` for production rebuilds.

    Same arguments as :func:`pack_sorted`; duplicate keys resolve to
    last-wins to match ``pack_sorted``.
    """
    deduped = {}
    for key_bytes, data_bytes in items:
        if len(data_bytes) >= slot_size:
            raise ValueError(
                "pack_naive: data {} does not fit in slot_size {}".format(
                    len(data_bytes), slot_size
                )
            )
        deduped[key_bytes] = data_bytes

    for key_bytes, data_bytes in deduped.items():
        home = zlib.adler32(key_bytes) % num_slots
        _naive_probe_insert(buf, home, num_slots, slot_size, data_bytes)


class MmapCache:
    """
    A generic memory-mapped hash table for O(1) lookup.
    This class handles the file management and mmap lifecycle.
    """

    def __init__(
        self,
        path,
        size=1000000,
        slot_size=128,
        staleness_check_interval=DEFAULT_STALENESS_CHECK_INTERVAL,
    ):
        self.path = os.path.realpath(path)
        self.size = size
        self.slot_size = slot_size
        self._mm = None
        self._cache_id = None
        #: How often we're willing to ``os.stat`` the file to detect an
        #: atomic-swap compaction. Set to 0 to stat on every ``open()``.
        self._staleness_check_interval = staleness_check_interval
        self._last_staleness_check = 0.0

    @property
    def _lock_path(self):
        return self.path + ".lock"

    @contextlib.contextmanager
    def _lock(self):
        """
        Cross-platform file locking.
        """
        # Ensure directory exists for lock file
        os.makedirs(os.path.dirname(self._lock_path), exist_ok=True)
        with salt.utils.files.fopen(self._lock_path, "w") as lock_f:
            fd = lock_f.fileno()
            if salt.utils.platform.is_windows():
                if msvcrt:
                    # msvcrt.locking(fd, mode, nbytes)
                    # LK_LOCK: Locks the specified bytes. If the bytes cannot be locked,
                    # the program immediately tries again after 1 second and continues
                    # to do so until the bytes are locked.
                    # We lock just the first byte of the lock file.
                    try:
                        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                        yield
                    finally:
                        try:
                            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                        except OSError:
                            pass
                else:
                    # Fallback if msvcrt is somehow missing
                    yield
            else:
                if fcntl:
                    fcntl.flock(fd, fcntl.LOCK_EX)
                    try:
                        yield
                    finally:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                else:
                    # Fallback if fcntl is missing (e.g. some weird environments)
                    yield

    def _get_cache_id(self):
        """
        Return a unique identifier for the current file on disk to detect atomic swaps.
        On Unix we use st_ino. On Windows we use a combination of creation time and size,
        or better, just use st_ino if it's available and non-zero (Python 3.11+ on Windows
        usually provides it if the FS supports it).
        """
        try:
            st = os.stat(self.path)
            # Use st_ino if it's non-zero (Unix or modern Python on Windows/NTFS)
            if st.st_ino:
                return st.st_ino
            # Fallback for Windows if st_ino is 0
            return (st.st_mtime, st.st_ctime, st.st_size)
        except OSError:
            return None

    def get_content_version(self):
        """
        Return a fine-grained version token for the current file contents.

        Unlike :meth:`_get_cache_id` (which only tracks the inode and so is
        stable across in-place writes), this returns ``(st_ino, st_mtime_ns)``
        so that *any* write bumps the token — even in-place ``put`` / ``delete``
        by another process.

        Callers that maintain derived in-process views of the mmap (e.g.
        :class:`salt.utils.resource_registry._ResourceIndexStore`) use this
        token to detect cross-process mutations. Writers bump ``st_mtime_ns``
        via :meth:`_touch_mtime` on every successful ``put`` / ``delete``.

        Returns ``None`` if the file cannot be stat'd.
        """
        try:
            st = os.stat(self.path)
            return (st.st_ino, st.st_mtime_ns)
        except OSError:
            return None

    def _touch_mtime(self):
        """
        Bump the file's mtime to ``now`` without modifying contents.

        This is how writers advertise in-place mutations (``put`` / ``delete``)
        to other processes holding live mmap handles: the inode is unchanged
        (so readers keep their mmap), but :meth:`get_content_version` will
        return a fresh token, prompting any derived view to rebuild from the
        (now-updated) slots.

        Errors are swallowed: failing to bump mtime degrades cross-process
        visibility but does not corrupt data.
        """
        try:
            os.utime(self.path, None)
        except OSError:
            pass

    def _init_file(self):
        """
        Initialize the file with zeros if it doesn't exist.
        """
        if not os.path.exists(self.path):
            log.debug("Initializing new mmap cache file at %s", self.path)
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                with salt.utils.files.fopen(self.path, "wb") as f:
                    # Write zeros to the whole file to ensure it's fully allocated
                    # and consistent across different platforms (macOS/Windows).
                    # Using a 1MB chunk size for efficiency.
                    total_size = self.size * self.slot_size
                    chunk_size = 1024 * 1024
                    zeros = b"\x00" * min(chunk_size, total_size)
                    bytes_written = 0
                    while bytes_written < total_size:
                        to_write = min(chunk_size, total_size - bytes_written)
                        if to_write < chunk_size:
                            f.write(zeros[:to_write])
                        else:
                            f.write(zeros)
                        bytes_written += to_write
                    f.flush()
                    os.fsync(f.fileno())
            except OSError as exc:
                log.error("Failed to initialize mmap cache file: %s", exc)
                return False
        return True

    def open(self, write=False):
        """
        Open the memory-mapped file.
        Readers (write=False) do not use any locks.
        Writers (write=True) use file initialization if needed.

        Already-open readers pay at most one ``os.stat`` per
        ``self._staleness_check_interval`` seconds to detect an atomic-swap
        compaction (``os.replace`` bumps ``st_ino``). Hot read paths that
        call ``open()`` every op therefore do not amortise to one syscall
        per operation.
        """
        if self._mm:
            # Check for staleness (Atomic Swap detection).
            now = time.monotonic()
            interval = self._staleness_check_interval
            if interval and (now - self._last_staleness_check) < interval:
                return True
            self._last_staleness_check = now
            current_id = self._get_cache_id()
            if current_id != self._cache_id:
                self.close()
            else:
                return True

        if write:
            if not self._init_file():
                return False
            mode = "r+b"
            access = mmap.ACCESS_WRITE
        else:
            if not os.path.exists(self.path):
                return False
            mode = "rb"
            access = mmap.ACCESS_READ

        try:
            # Note: We do NOT use _lock() here for readers.
            # Atomic swap (os.replace) ensures readers see either the old file
            # or the new file, but never a partially initialized one.
            with salt.utils.files.fopen(self.path, mode) as f:
                fd = f.fileno()
                self._cache_id = self._get_cache_id()

                # Verify file size matches expected size
                st = os.fstat(fd)
                expected_size = self.size * self.slot_size
                if st.st_size != expected_size:
                    if not write:
                        # For readers, a size mismatch is a sign of a partial write
                        # (even with atomic swap, this can happen on some networked FS)
                        return False
                    log.error(
                        "MmapCache file size mismatch for %s: expected %d, got %d",
                        self.path,
                        expected_size,
                        st.st_size,
                    )
                    return False

                # Use 0 for length to map the whole file
                self._mm = mmap.mmap(fd, 0, access=access)
            return True
        except OSError as exc:
            if not write and exc.errno == errno.ENOENT:
                return False
            log.error("Failed to mmap cache file %s: %s", self.path, exc)
            self.close()
            return False

    def close(self):
        """
        Close the memory-mapped file.
        """
        if self._mm:
            try:
                self._mm.close()
            except (BufferError, OSError):
                # Handle cases where buffers might still be in use
                pass
            self._mm = None
        self._cache_id = None

    def _hash(self, key_bytes):
        """
        Calculate the hash slot for a key.
        """
        return zlib.adler32(key_bytes) % self.size

    def put(self, key, value=None):
        """
        Add a key (and optional value) to the cache.
        If value is None, we just store the key (Set-like behavior).
        If value is provided, we store it alongside the key.
        Note: The total size of (key + value) must fit in slot_size - 1.
        """
        if not self.open(write=True):
            return False

        key_bytes = salt.utils.stringutils.to_bytes(key)
        val_bytes = salt.utils.stringutils.to_bytes(value) if value is not None else b""

        # We store: [STATUS][KEY][NULL][VALUE][NULL...]
        # For simplicity in this generic version, let's just store the key and value separated by null
        # or just the key if it's a set.

        data = key_bytes
        if value is not None:
            data += b"\x00" + val_bytes

        if len(data) > self.slot_size - 1:
            log.warning("Data too long for mmap cache slot: %s", key)
            return False

        h = self._hash(key_bytes)
        # Use file locking for multi-process safety on writes
        try:
            with self._lock():
                for i in range(self.size):
                    slot = (h + i) % self.size
                    offset = slot * self.slot_size
                    status = self._mm[offset]

                    if status == OCCUPIED:
                        # Check if it's the same key
                        existing_data = self._mm[offset + 1 : offset + self.slot_size]
                        # Key is everything before first null
                        null_pos = existing_data.find(b"\x00")
                        existing_key = (
                            existing_data[:null_pos]
                            if null_pos != -1
                            else existing_data.rstrip(b"\x00")
                        )

                        if existing_key == key_bytes:
                            # Update value if needed
                            self._mm[offset + 1 : offset + 1 + len(data)] = data
                            if len(data) < self.slot_size - 1:
                                self._mm[offset + 1 + len(data)] = 0
                            self._mm.flush()
                            self._touch_mtime()
                            return True
                        continue

                    # Found an empty or deleted slot.
                    # Write data FIRST, then flip status byte to ensure reader safety.
                    self._mm[offset + 1 : offset + 1 + len(data)] = data
                    if len(data) < self.slot_size - 1:
                        self._mm[offset + 1 + len(data)] = 0
                    self._mm[offset] = OCCUPIED
                    self._mm.flush()
                    self._touch_mtime()
                    return True

            log.error("Mmap cache is full!")
            return False
        except OSError as exc:
            log.error("Error writing to mmap cache %s: %s", self.path, exc)
            return False

    def get(self, key, default=None):
        """
        Retrieve a value for a key. Returns default if not found.
        If it was stored as a set (value=None), returns the key itself to indicate presence.
        """
        if not self.open(write=False):
            return default

        key_bytes = salt.utils.stringutils.to_bytes(key)
        h = self._hash(key_bytes)

        for i in range(self.size):
            slot = (h + i) % self.size
            offset = slot * self.slot_size
            status = self._mm[offset]

            if status == EMPTY:
                return default

            if status == DELETED:
                continue

            # Occupied, check key
            existing_data = self._mm[offset + 1 : offset + self.slot_size]
            null_pos = existing_data.find(b"\x00")
            existing_key = (
                existing_data[:null_pos]
                if null_pos != -1
                else existing_data.rstrip(b"\x00")
            )

            if existing_key == key_bytes:
                # If there's no data after the key, it was stored as a set
                if (
                    len(existing_data) <= len(key_bytes) + 1
                    or existing_data[len(key_bytes)] == 0
                    and (
                        len(existing_data) == len(key_bytes) + 1
                        or existing_data[len(key_bytes) + 1] == 0
                    )
                ):
                    # This is getting complicated, let's simplify.
                    # If stored as set, we have [KEY][\x00][\x00...]
                    # If stored as kv, we have [KEY][\x00][VALUE][\x00...]
                    if null_pos != -1:
                        if (
                            null_pos == len(existing_data) - 1
                            or existing_data[null_pos + 1] == 0
                        ):
                            return True
                    else:
                        return True

                value_part = existing_data[null_pos + 1 :]
                val_null_pos = value_part.find(b"\x00")
                if val_null_pos != -1:
                    value_part = value_part[:val_null_pos]
                return salt.utils.stringutils.to_unicode(value_part)
        return default

    def delete(self, key):
        """
        Remove a key from the cache.
        """
        if not self.open(write=True):
            return False

        key_bytes = salt.utils.stringutils.to_bytes(key)
        h = self._hash(key_bytes)

        try:
            with self._lock():
                for i in range(self.size):
                    slot = (h + i) % self.size
                    offset = slot * self.slot_size
                    status = self._mm[offset]

                    if status == EMPTY:
                        return False

                    if status == DELETED:
                        continue

                    existing_data = self._mm[offset + 1 : offset + self.slot_size]
                    null_pos = existing_data.find(b"\x00")
                    existing_key = (
                        existing_data[:null_pos]
                        if null_pos != -1
                        else existing_data.rstrip(b"\x00")
                    )

                    if existing_key == key_bytes:
                        self._mm[offset] = DELETED
                        self._mm.flush()
                        self._touch_mtime()
                        return True
            return False
        except OSError as exc:
            log.error("Error deleting from mmap cache %s: %s", self.path, exc)
            return False

    def contains(self, key):
        """
        Check if a key exists.
        """
        res = self.get(key, default=None)
        return res is not None

    def list_keys(self):
        """
        Return all keys in the cache.
        """
        return [item[0] for item in self.list_items()]

    def list_items(self):
        """
        Return all (key, value) pairs in the cache.
        If it's a set, value will be True.
        """
        if not self.open(write=False):
            return []

        ret = []
        mm = self._mm
        slot_size = self.slot_size

        for slot in range(self.size):
            offset = slot * slot_size
            if mm[offset] == OCCUPIED:
                # Get the slot data.
                # mm[offset:offset+slot_size] is relatively fast.
                slot_data = mm[offset + 1 : offset + slot_size]

                # Use C-based find for speed
                null_pos = slot_data.find(b"\x00")

                if null_pos == -1:
                    key_bytes = slot_data
                    value = True
                else:
                    key_bytes = slot_data[:null_pos]

                    value = True
                    # Check if there is data after the null
                    if null_pos < len(slot_data) - 1 and slot_data[null_pos + 1] != 0:
                        val_data = slot_data[null_pos + 1 :]
                        val_null_pos = val_data.find(b"\x00")
                        if val_null_pos == -1:
                            value_bytes = val_data
                        else:
                            value_bytes = val_data[:val_null_pos]

                        if value_bytes:
                            value = salt.utils.stringutils.to_unicode(value_bytes)

                ret.append((salt.utils.stringutils.to_unicode(key_bytes), value))
        return ret

    def get_stats(self):
        """
        Return statistics about the cache state.
        Returns dict with: {occupied, deleted, empty, total, load_factor}
        """
        if not self.open(write=False):
            return {
                "occupied": 0,
                "deleted": 0,
                "empty": 0,
                "total": self.size,
                "load_factor": 0.0,
            }

        counts = {"occupied": 0, "deleted": 0, "empty": 0}
        mm = self._mm
        slot_size = self.slot_size

        for slot in range(self.size):
            offset = slot * slot_size
            status = mm[offset]
            if status == OCCUPIED:
                counts["occupied"] += 1
            elif status == DELETED:
                counts["deleted"] += 1
            else:  # EMPTY
                counts["empty"] += 1

        counts["total"] = self.size
        counts["load_factor"] = (
            (counts["occupied"] + counts["deleted"]) / self.size
            if self.size > 0
            else 0.0
        )
        return counts

    def _normalize_iterator(self, iterator):
        """
        Consume ``iterator`` and yield normalised ``(key_bytes, data_bytes)``
        pairs ready for slot packing. Items that don't fit in a single slot
        are skipped with a warning, matching the previous rebuild behaviour.
        """
        for item in iterator:
            if isinstance(item, (list, tuple)) and len(item) > 1:
                key, value = item[0], item[1]
            else:
                key = item[0] if isinstance(item, (list, tuple)) else item
                value = None

            key_bytes = salt.utils.stringutils.to_bytes(key)
            if value is None:
                data = key_bytes
            else:
                val_bytes = salt.utils.stringutils.to_bytes(value)
                data = key_bytes + b"\x00" + val_bytes

            if len(data) > self.slot_size - 1:
                log.warning("Data too long for slot: %s", key)
                continue
            yield key_bytes, data

    def atomic_rebuild(self, iterator, strategy="sorted"):
        """
        Rebuild the cache from an iterator of ``(key, value)`` or ``(key,)``.
        Populates a temporary file and atomically swaps it in via
        ``os.replace`` so active readers continue to see the pre-swap file
        until their next staleness check.

        :param iterator: Source of ``(key, value)`` / ``(key,)`` items.
        :param str strategy: ``"sorted"`` (default, O(N log N), see
            :func:`pack_sorted`) or ``"naive"`` (O(N^2) worst case, kept for
            parity testing and as a diagnostic fallback).
        :returns: ``True`` on success, ``False`` on I/O error.
        """
        if strategy not in ("sorted", "naive"):
            raise ValueError("strategy must be 'sorted' or 'naive'")

        os.makedirs(os.path.dirname(self.path), exist_ok=True)

        import tempfile

        tmp_dir = os.path.dirname(self.path)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=tmp_dir, prefix=".rebuild_")

        packer = pack_sorted if strategy == "sorted" else pack_naive

        try:
            with self._lock():
                # Materialise items once so we can log count and hand them
                # to the packer (which needs random access for sorting).
                items = list(self._normalize_iterator(iterator))

                with os.fdopen(tmp_fd, "wb") as f:
                    total_size = self.size * self.slot_size
                    chunk_size = 1024 * 1024
                    zeros = b"\x00" * min(chunk_size, total_size)
                    bytes_written = 0
                    while bytes_written < total_size:
                        to_write = min(chunk_size, total_size - bytes_written)
                        if to_write < chunk_size:
                            f.write(zeros[:to_write])
                        else:
                            f.write(zeros)
                        bytes_written += to_write
                    f.flush()
                    os.fsync(f.fileno())
                tmp_fd = None  # os.fdopen closed it

                with salt.utils.files.fopen(tmp_path, "r+b") as f:
                    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_WRITE)
                    try:
                        packer(mm, items, self.size, self.slot_size)
                        mm.flush()
                    finally:
                        mm.close()
                    os.fsync(f.fileno())

                self.close()
                os.replace(tmp_path, self.path)
                return True
        except OSError as exc:
            log.error("Error rebuilding mmap cache %s: %s", self.path, exc)
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            return False
        finally:
            if tmp_fd is not None:
                try:
                    os.close(tmp_fd)
                except OSError:
                    pass
