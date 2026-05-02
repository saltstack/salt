import contextlib
import errno
import logging
import mmap
import os
import struct
import tempfile
import threading
import time

import xxhash

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

# Status constants for data slots
EMPTY = 0
OCCUPIED = 1
DELETED = 2

# Slot 0 is a metadata header; its STATUS byte carries this magic so it is
# never treated as EMPTY/OCCUPIED/DELETED by the hash-table logic.
_HEADER_MAGIC = 0xAB

# Index slot field layout (relative to slot start, for data slots 1…size-1):
#   0            : STATUS  (1 byte)
#   1            : KEY     (key_size bytes, null-padded)
#   1+key_size   : OFFSET  (uint64 LE — byte offset into heap file)
#   1+key_size+8 : LENGTH  (uint32 LE — byte length of heap record)
#   1+key_size+12: MTIME   (uint64 LE — unix timestamp in nanoseconds)
#   1+key_size+20: padding to slot_size
#
# Header slot 0 layout (same slot_size, different semantics):
#   0  : MAGIC            (1 byte = _HEADER_MAGIC)
#   1  : occupied_count   (uint64 LE)
#   9  : deleted_count    (uint64 LE)
#   17 : high_water_mark  (uint64 LE) — highest data-slot index ever written
#   25 : (reserved / zero)

_OFFSET_FMT = "<Q"  # uint64
_LENGTH_FMT = "<I"  # uint32
_MTIME_FMT = "<Q"  # uint64

_OFFSET_SIZE = 8
_LENGTH_SIZE = 4
_MTIME_SIZE = 8
_FIXED_OVERHEAD = 1 + _OFFSET_SIZE + _LENGTH_SIZE + _MTIME_SIZE  # 21 bytes

# Heap segmentation
# -----------------
# The 8-byte OFFSET field encodes both the segment ID and the within-segment
# byte offset in a single uint64:
#
#   bits 63-48 : segment ID  (uint16, 0-65535)
#   bits 47- 0 : byte offset within that segment (uint48, up to ~281 TB)
#
# Segment 0 is the original ".heap" file; subsequent segments are named
# ".heap.1", ".heap.2", etc.  Existing on-disk offsets that were written
# before segmentation have zero in the top 16 bits, so they are read as
# segment 0 — fully backward-compatible.
_SEG_ID_SHIFT = 48  # segment ID sits in the top 16 bits
_SEG_OFF_MASK = (1 << 48) - 1  # bottom 48 bits = within-segment offset

# Default segment size cap: 1 GiB.  When the active segment reaches this
# limit the next append rolls to a new segment.
DEFAULT_MAX_SEGMENT_BYTES = 1 * 1024 * 1024 * 1024  # 1 GiB

# Per-entry heap record format when verify_checksums=True (the default):
#   [XXH3-64: 8 bytes LE][VALUE: length bytes]
# The LENGTH field in the index slot always records the value length only;
# the 8-byte hash prefix is transparent to callers.
# xxHash XXH3-64 is ~2.5x faster than zlib.crc32 on modern hardware via SIMD,
# has 64-bit output (lower collision probability than 32-bit CRC32), and uses
# a better diffusion function than the zip/ethernet CRC polynomial.
_CRC_FMT = "<Q"
_CRC_SIZE = 8

# Header field byte offsets within slot 0
_HDR_OCCUPIED_OFF = 1
_HDR_DELETED_OFF = 9
_HDR_HWM_OFF = 17
_HDR_MIN_SLOT_SIZE = 25  # minimum slot_size to hold all header fields

# Roster file: a packed array of uint32 slot indices for OCCUPIED slots.
# Rebuilt atomically alongside the index.
#
# On-disk format per entry: uint32 LE slot index.
# A value of _ROSTER_TOMBSTONE marks a deleted/invalid entry; _roster_read
# skips tombstones.  This lets _roster_remove do a single 4-byte in-place
# overwrite instead of a full file rewrite.
_ROSTER_ENTRY_FMT = "<I"  # uint32 — slot index
_ROSTER_ENTRY_SIZE = 4
_ROSTER_TOMBSTONE = 0xFFFFFFFF  # sentinel for logically-deleted roster entries


def _min_slot_size(key_size):
    return max(_FIXED_OVERHEAD + key_size, _HDR_MIN_SLOT_SIZE)


class MmapCache:
    """
    A memory-mapped hash table backed by an index file, a heap file, and a
    roster file.

    **Index file (``path``)**

    Slot 0 is a *header* storing three uint64 counters:

    * ``occupied_count`` — number of live (OCCUPIED) data slots
    * ``deleted_count``  — number of soft-deleted (DELETED) data slots
    * ``high_water_mark`` — highest data-slot index ever written

    Data slots occupy positions ``1 … size-1``.  Each data slot stores a
    null-padded key plus a pointer (offset + length) into the heap file and
    an mtime timestamp (nanoseconds).

    **Heap file (``path + ".heap"``)**

    A flat binary append-log for variable-size values.  Deleted or superseded
    heap regions are reclaimed by ``atomic_rebuild``.

    **Roster file (``path + ".roster"``)**

    A packed array of ``uint32`` slot indices, one per live (OCCUPIED) entry.
    ``list_items()`` reads this file directly instead of scanning the full
    index, making it O(occupied) regardless of table size or fill factor.
    The roster is kept in sync by ``put()`` and ``delete()`` under the write
    lock, and rebuilt atomically by ``atomic_rebuild``.

    **Performance summary**

    * ``get`` / ``get_mtime`` / ``contains``: O(1) average (open-addressing)
    * ``put`` / ``delete``: O(1) average + one roster file append/rewrite
    * ``list`` / ``list_items``: O(occupied) — independent of table size
    * ``get_stats`` occupied+deleted counters: O(1) from header
    * ``atomic_rebuild``: O(items) to repopulate
    """

    def __init__(
        self,
        path,
        size=1_000_000,
        slot_size=96,
        key_size=64,
        heap_path=None,
        staleness_check_interval=0.25,
        verify_checksums=True,
        max_segment_bytes=DEFAULT_MAX_SEGMENT_BYTES,
    ):
        self.path = os.path.realpath(path)
        self.size = size
        self.key_size = key_size
        min_sz = _min_slot_size(key_size)
        if slot_size < min_sz:
            raise ValueError(
                f"slot_size {slot_size} is too small for key_size {key_size}; "
                f"minimum is {min_sz}"
            )
        self.slot_size = slot_size
        self.heap_path = os.path.realpath(heap_path or path + ".heap")
        self.roster_path = self.path + ".roster"

        self.verify_checksums = verify_checksums
        self.max_segment_bytes = max_segment_bytes

        self._mm = None  # index mmap (ACCESS_READ or ACCESS_WRITE)
        # Per-segment read mmaps: list indexed by segment_id.
        # Each entry is (mmap_obj | None, fd | None, size).
        self._seg_mms: list = []  # [(mm, fd, size), ...]
        self._seg_mm_stale: list = []  # [bool, ...] — True after write to seg
        self._cache_id = None
        # Size of the *active* (last) heap segment — used for append decisions.
        self._heap_size = 0
        self._roster_cache = None  # cached list of slot indices
        self._roster_mtime = None  # mtime of roster when last read
        self._roster_wfd = None  # append-mode write fd for fast roster appends
        # slot → byte offset in the roster file for O(1) tombstone writes
        self._roster_slot_offsets: dict = {}
        self._lock_fd = None  # persistent lock file fd (avoid re-open per op)
        # Per-instance RLock: fcntl is per-process; this covers threads too.
        self._thread_lock = threading.RLock()

        # Precompute data-slot field offsets (relative to slot start)
        self._key_off = 1
        self._offset_off = 1 + key_size
        self._length_off = 1 + key_size + _OFFSET_SIZE
        self._mtime_off = 1 + key_size + _OFFSET_SIZE + _LENGTH_SIZE

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Segment helpers
    # ------------------------------------------------------------------

    def _segment_path(self, seg_id):
        """Return the filesystem path for heap segment *seg_id*."""
        if seg_id == 0:
            return self.heap_path
        return f"{self.heap_path}.{seg_id}"

    def _active_segment_id(self):
        """Return the ID of the segment that should receive the next append."""
        return max(0, len(self._seg_mms) - 1)

    def _pack_offset(self, seg_id, seg_offset):
        """Pack segment ID and within-segment offset into a single uint64."""
        return (seg_id << _SEG_ID_SHIFT) | (seg_offset & _SEG_OFF_MASK)

    def _unpack_offset(self, packed):
        """Unpack a packed offset into (seg_id, seg_offset)."""
        seg_id = packed >> _SEG_ID_SHIFT
        seg_offset = packed & _SEG_OFF_MASK
        return int(seg_id), int(seg_offset)

    @property
    def _lock_path(self):
        return self.path + ".lock"

    def _lock_fd_open(self):
        """
        Return a persistent file object for the lock file, opening it once
        and keeping it alive for the lifetime of this MmapCache instance.
        This avoids an fopen + fclose on every ``put`` / ``delete`` call.
        """
        if self._lock_fd is not None:
            return self._lock_fd
        os.makedirs(os.path.dirname(self._lock_path), exist_ok=True)
        try:
            self._lock_fd = salt.utils.files.fopen(  # pylint: disable=resource-leakage
                self._lock_path, "w"
            )
        except OSError as exc:
            log.error("Cannot open lock file %s: %s", self._lock_path, exc)
            return None
        return self._lock_fd

    @contextlib.contextmanager
    def _lock(self):
        """
        Cross-platform exclusive file lock.

        The lock file fd is kept open persistently to avoid re-opening it on
        every call.  If the persistent fd cannot be obtained, falls back to a
        per-call open (same behaviour as before).
        """
        lock_f = self._lock_fd_open()
        if lock_f is None:
            # Fallback: open per-call
            os.makedirs(os.path.dirname(self._lock_path), exist_ok=True)
            with salt.utils.files.fopen(self._lock_path, "w") as _f:
                yield
            return

        fd = lock_f.fileno()
        if salt.utils.platform.is_windows():
            if msvcrt:
                try:
                    msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                    yield
                finally:
                    try:
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
            else:
                yield
        else:
            if fcntl:
                fcntl.flock(fd, fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(fd, fcntl.LOCK_UN)
            else:
                yield

    def _get_cache_id(self):
        try:
            st = os.stat(self.path)
            if st.st_ino:
                return st.st_ino
            return (st.st_mtime, st.st_ctime, st.st_size)
        except OSError:
            return None

    def _init_index_file(self):
        """Create the index file filled with zeros if it does not exist."""
        if os.path.exists(self.path):
            return True
        log.debug("Initializing new mmap index file at %s", self.path)
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            total_size = self.size * self.slot_size
            chunk = 1024 * 1024
            zeros = b"\x00" * min(chunk, total_size)
            with salt.utils.files.fopen(self.path, "wb") as f:
                written = 0
                while written < total_size:
                    to_write = min(chunk, total_size - written)
                    f.write(zeros[:to_write])
                    written += to_write
                f.flush()
                os.fsync(f.fileno())
        except OSError as exc:
            log.error("Failed to initialize index file: %s", exc)
            return False
        return True

    def _init_heap_file(self):
        """Create segment-0 heap file if it does not exist."""
        if os.path.exists(self.heap_path):
            return True
        try:
            os.makedirs(os.path.dirname(self.heap_path), exist_ok=True)
            with salt.utils.files.fopen(self.heap_path, "wb") as f:
                f.flush()
                os.fsync(f.fileno())
        except OSError as exc:
            log.error("Failed to initialize heap file: %s", exc)
            return False
        return True

    def _discover_segments(self):
        """
        Scan the filesystem for all segment files and populate ``_seg_mms``.

        Segments are named ``<heap_path>`` (seg 0), ``<heap_path>.1``,
        ``<heap_path>.2``, …  Scanning stops at the first gap.

        Returns the number of segments found (≥ 1 if segment-0 exists).
        """
        self._close_seg_mmaps()
        seg_id = 0
        while True:
            p = self._segment_path(seg_id)
            if not os.path.exists(p):
                break
            try:
                sz = os.path.getsize(p)
            except OSError:
                sz = 0
            self._seg_mms.append([None, None, sz])  # [mm, fd, size]
            self._seg_mm_stale.append(False)
            seg_id += 1
        # Ensure at least one entry (segment 0) so active_segment_id() works.
        if not self._seg_mms:
            self._seg_mms.append([None, None, 0])
            self._seg_mm_stale.append(False)
        self._heap_size = self._seg_mms[-1][2]
        return len(self._seg_mms)

    def _close_seg_mmaps(self):
        """Close all open segment mmaps and file descriptors."""
        for entry in self._seg_mms:
            mm, fd, _ = entry
            if mm is not None:
                try:
                    mm.close()
                except (BufferError, OSError):
                    pass
                entry[0] = None
            if fd is not None:
                try:
                    fd.close()
                except OSError:
                    pass
                entry[1] = None
        self._seg_mms = []
        self._seg_mm_stale = []

    # ------------------------------------------------------------------
    # Roster helpers — packed uint32 array of live slot indices
    # ------------------------------------------------------------------

    def _roster_wfd_open(self):
        """
        Return the persistent append-mode write fd for the roster file,
        opening it if not already open.  The fd is kept alive across multiple
        ``put()`` calls to avoid per-append open/close overhead.
        """
        if self._roster_wfd is not None:
            return self._roster_wfd
        try:
            self._roster_wfd = (
                salt.utils.files.fopen(  # pylint: disable=resource-leakage
                    self.roster_path, "ab"
                )
            )
        except OSError as exc:
            log.error("Cannot open roster for writing %s: %s", self.roster_path, exc)
            return None
        return self._roster_wfd

    def _roster_append(self, slot):
        """
        Append one slot index to the roster file.

        Uses a persistent open write fd to avoid per-call open/close overhead.
        Records the byte offset of the new entry in ``_roster_slot_offsets``
        so that ``_roster_remove`` can tombstone it in O(1) without re-reading.
        """
        wfd = self._roster_wfd_open()
        if wfd is None:
            return
        try:
            byte_offset = wfd.seek(0, 2)  # seek to end to get current size
            wfd.write(struct.pack(_ROSTER_ENTRY_FMT, slot))
            wfd.flush()
            self._roster_slot_offsets[slot] = byte_offset
        except OSError as exc:
            log.error("Error appending to roster %s: %s", self.roster_path, exc)
            try:
                wfd.close()
            except OSError:
                pass
            self._roster_wfd = None
        self._roster_invalidate()

    def _roster_remove(self, slot):
        """
        Tombstone *slot* in the roster file with an in-place 4-byte overwrite.

        **Fast path** (same-process delete after a ``put``): the byte offset
        of the entry was recorded by ``_roster_append`` in
        ``_roster_slot_offsets``.  We seek directly and write the tombstone
        using the persistent write fd — zero extra opens.

        **Slow path** (cross-process or after restart): scan the file for the
        entry and overwrite it.

        ``_roster_read`` skips ``_ROSTER_TOMBSTONE`` entries; they are
        compacted on the next ``atomic_rebuild``.
        """
        tombstone = struct.pack(_ROSTER_ENTRY_FMT, _ROSTER_TOMBSTONE)

        byte_offset = self._roster_slot_offsets.pop(slot, None)
        if byte_offset is not None:
            # Fast path: reuse the write fd, seek to known offset
            wfd = self._roster_wfd_open()
            if wfd is not None:
                try:
                    wfd.seek(byte_offset)
                    wfd.write(tombstone)
                    wfd.flush()
                    # seek back to end so next append lands correctly
                    wfd.seek(0, 2)
                    self._roster_invalidate()
                    return
                except OSError as exc:
                    log.error(
                        "Error tombstoning roster (fast) %s: %s",
                        self.roster_path,
                        exc,
                    )
                    try:
                        wfd.close()
                    except OSError:
                        pass
                    self._roster_wfd = None
                    # fall through to slow path

        # Slow path: open+scan+overwrite
        try:
            with salt.utils.files.fopen(self.roster_path, "r+b") as f:
                data = f.read()
                entry = struct.pack(_ROSTER_ENTRY_FMT, slot)
                idx = data.find(entry)
                if idx == -1:
                    return
                f.seek(idx)
                f.write(tombstone)
                f.flush()
        except OSError as exc:
            log.error("Error tombstoning roster %s: %s", self.roster_path, exc)
        self._roster_invalidate()

    def _roster_invalidate(self):
        """Discard the in-memory roster cache (but keep slot offset map)."""
        self._roster_cache = None
        self._roster_mtime = None

    def _roster_recover(self):
        """
        Rebuild the roster file from the index if they have diverged.

        Called on every ``open(write=True)`` after the mmap is established.
        Detects two conditions:

        1. Roster file is missing or unreadable.
        2. Live entry count in the roster does not match ``occupied_count``
           in the header (can happen after a crash between the index flush
           and the roster append).

        Recovery scans slots ``[1, high_water_mark]``, collects all OCCUPIED
        slot indices, and atomically replaces the roster file.  The header
        ``occupied_count`` is also corrected if it drifted.

        This is O(high_water_mark) — fast at startup, amortised to zero over
        subsequent operations.
        """
        occupied, _, hwm = self._read_header()
        roster = self._roster_read()

        if len(roster) == occupied:
            return  # consistent — nothing to do

        log.warning(
            "Roster/index divergence detected for %s "
            "(roster has %d entries, header says %d occupied) — rebuilding roster",
            self.path,
            len(roster),
            occupied,
        )

        slots = []
        for slot in range(1, min(hwm + 2, self.size)):
            if self._mm[slot * self.slot_size] == OCCUPIED:
                slots.append(slot)

        # Correct header if it drifted too
        if len(slots) != occupied:
            struct.pack_into(_OFFSET_FMT, self._mm, _HDR_OCCUPIED_OFF, len(slots))
            self._mm.flush()

        data = struct.pack(f"<{len(slots)}I", *slots) if slots else b""
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=os.path.dirname(self.roster_path), prefix=".roster_recover_"
            )
            try:
                with os.fdopen(tmp_fd, "wb") as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
                tmp_fd = -1
                os.replace(tmp_path, self.roster_path)
            finally:
                if tmp_fd != -1:
                    try:
                        os.close(tmp_fd)
                    except OSError:
                        pass
        except OSError as exc:
            log.error("Failed to rebuild roster for %s: %s", self.path, exc)
            return

        # Reopen the write fd against the new roster file
        if self._roster_wfd is not None:
            try:
                self._roster_wfd.close()
            except OSError:
                pass
            self._roster_wfd = None
        self._roster_slot_offsets.clear()
        self._roster_invalidate()
        log.info("Roster for %s rebuilt with %d entries", self.path, len(slots))

    def _roster_read(self):
        """
        Return a list of slot indices from the roster file.

        The result is cached in memory and invalidated whenever the roster
        file's mtime changes or when ``_roster_invalidate()`` is called
        (e.g. after a write that modifies the roster).
        """
        try:
            st = os.stat(self.roster_path)
            mtime = st.st_mtime_ns
        except OSError:
            self._roster_cache = None
            self._roster_mtime = None
            return []

        if self._roster_cache is not None and self._roster_mtime == mtime:
            return self._roster_cache

        try:
            with salt.utils.files.fopen(self.roster_path, "rb") as f:
                data = f.read()
        except OSError:
            return []

        n = len(data) // _ROSTER_ENTRY_SIZE
        if n:
            all_slots = struct.unpack_from(f"<{n}I", data)
            result = [s for s in all_slots if s != _ROSTER_TOMBSTONE]
        else:
            result = []
        self._roster_cache = result
        self._roster_mtime = mtime
        return result

    # ------------------------------------------------------------------
    # Open / close
    # ------------------------------------------------------------------

    def open(self, write=False):
        """
        Open (or re-open after a staleness check) the index mmap.

        Readers use ACCESS_READ and never acquire the lock.
        Writers use ACCESS_WRITE and are expected to hold the lock.
        """
        if self._mm:
            current_id = self._get_cache_id()
            if current_id != self._cache_id:
                self.close()
            else:
                return True

        if write:
            if not self._init_index_file():
                return False
            if not self._init_heap_file():
                return False
            mode = "r+b"
            access = mmap.ACCESS_WRITE
        else:
            if not os.path.exists(self.path):
                return False
            mode = "rb"
            access = mmap.ACCESS_READ

        try:
            with salt.utils.files.fopen(self.path, mode) as f:
                fd = f.fileno()
                self._cache_id = self._get_cache_id()
                st = os.fstat(fd)
                expected = self.size * self.slot_size
                if st.st_size != expected:
                    if not write:
                        return False
                    log.error(
                        "Index file size mismatch for %s: expected %d, got %d",
                        self.path,
                        expected,
                        st.st_size,
                    )
                    return False
                self._mm = mmap.mmap(fd, 0, access=access)

            # Stamp header magic on a fresh file
            if write and self._mm[0] != _HEADER_MAGIC:
                self._mm[0] = _HEADER_MAGIC
                self._mm.flush()

            self._discover_segments()
            self._open_all_seg_mmaps()

            if write:
                self._roster_recover()

            return True
        except OSError as exc:
            if not write and exc.errno == errno.ENOENT:
                return False
            log.error("Failed to mmap index file %s: %s", self.path, exc)
            self.close()
            return False

    def _close_mmaps_and_fds(self):
        """
        Close mmaps, heap fds, and roster write fd — but NOT the lock fd.

        Used by ``atomic_rebuild``, which holds the lock across a ``close``
        and must not close the lock fd while the lock is still held.
        """
        if self._mm:
            try:
                self._mm.close()
            except (BufferError, OSError):
                pass
            self._mm = None
        self._close_seg_mmaps()
        if self._roster_wfd is not None:
            try:
                self._roster_wfd.close()
            except OSError:
                pass
            self._roster_wfd = None
        self._cache_id = None
        self._roster_invalidate()
        self._roster_slot_offsets.clear()

    def close(self):
        """Close all mmaps and persistent fds (index, heap, roster, lock)."""
        self._close_mmaps_and_fds()
        if self._lock_fd is not None:
            try:
                self._lock_fd.close()
            except OSError:
                pass
            self._lock_fd = None

    def _open_heap_mmap(self):
        """
        (Re-)open read-only mmaps for all heap segments.

        Segments with zero size are left un-mmapped; reads fall back to
        file I/O.  Called after the index mmap is established and after
        any write that grows a segment.
        """
        for seg_id, entry in enumerate(self._seg_mms):
            if not self._seg_mm_stale[seg_id]:
                continue  # still fresh

            mm, fd, _ = entry
            if mm is not None:
                try:
                    mm.close()
                except (BufferError, OSError):
                    pass
                entry[0] = None
            if fd is not None:
                try:
                    fd.close()
                except OSError:
                    pass
                entry[1] = None

            p = self._segment_path(seg_id)
            try:
                sz = os.path.getsize(p)
            except OSError:
                sz = 0
            entry[2] = sz
            if seg_id == self._active_segment_id():
                self._heap_size = sz

            if sz > 0:
                try:
                    fd_obj = salt.utils.files.fopen(  # pylint: disable=resource-leakage
                        p, "rb"
                    )
                    mm_obj = mmap.mmap(fd_obj.fileno(), 0, access=mmap.ACCESS_READ)
                    entry[0] = mm_obj
                    entry[1] = fd_obj
                except OSError as exc:
                    log.warning("Could not mmap heap segment %s: %s", p, exc)
                    if entry[1] is not None:
                        try:
                            entry[1].close()
                        except OSError:
                            pass
                        entry[1] = None

            self._seg_mm_stale[seg_id] = False

    def _open_all_seg_mmaps(self):
        """Open mmaps for all segments unconditionally (used during open())."""
        for seg_id, entry in enumerate(self._seg_mms):
            self._seg_mm_stale[seg_id] = True  # force refresh
        self._open_heap_mmap()

    # ------------------------------------------------------------------
    # Header accessors
    # ------------------------------------------------------------------

    def _read_header(self):
        """Return (occupied, deleted, high_water_mark) from the header slot."""
        occupied = struct.unpack_from(_OFFSET_FMT, self._mm, _HDR_OCCUPIED_OFF)[0]
        deleted = struct.unpack_from(_OFFSET_FMT, self._mm, _HDR_DELETED_OFF)[0]
        hwm = struct.unpack_from(_OFFSET_FMT, self._mm, _HDR_HWM_OFF)[0]
        return occupied, deleted, hwm

    def _update_header(self, occupied_delta=0, deleted_delta=0, new_hwm=None):
        """Update header counters in-place."""
        occupied, deleted, hwm = self._read_header()
        occupied = max(0, occupied + occupied_delta)
        deleted = max(0, deleted + deleted_delta)
        if new_hwm is not None and new_hwm > hwm:
            hwm = new_hwm
        struct.pack_into(_OFFSET_FMT, self._mm, _HDR_OCCUPIED_OFF, occupied)
        struct.pack_into(_OFFSET_FMT, self._mm, _HDR_DELETED_OFF, deleted)
        struct.pack_into(_OFFSET_FMT, self._mm, _HDR_HWM_OFF, hwm)

    # ------------------------------------------------------------------
    # Slot field accessors (data slots only)
    # ------------------------------------------------------------------

    def _read_slot_key(self, offset):
        """Return the raw key bytes from a slot (strip null padding)."""
        raw = self._mm[offset + self._key_off : offset + self._key_off + self.key_size]
        null_pos = raw.find(b"\x00")
        return raw[:null_pos] if null_pos != -1 else raw

    def _read_slot_pointer(self, offset):
        """Return (heap_offset, length, mtime_ns) from a data slot."""
        base = offset + self._offset_off
        heap_offset = struct.unpack_from(_OFFSET_FMT, self._mm, base)[0]
        length = struct.unpack_from(_LENGTH_FMT, self._mm, base + _OFFSET_SIZE)[0]
        mtime_ns = struct.unpack_from(
            _MTIME_FMT, self._mm, base + _OFFSET_SIZE + _LENGTH_SIZE
        )[0]
        return heap_offset, length, mtime_ns

    def _write_slot(self, offset, key_bytes, heap_offset, length, mtime_ns):
        """Write key + pointer fields into a data slot (does NOT set STATUS)."""
        key_field = key_bytes[: self.key_size].ljust(self.key_size, b"\x00")
        self._mm[offset + self._key_off : offset + self._key_off + self.key_size] = (
            key_field
        )
        base = offset + self._offset_off
        struct.pack_into(_OFFSET_FMT, self._mm, base, heap_offset)
        struct.pack_into(_LENGTH_FMT, self._mm, base + _OFFSET_SIZE, length)
        struct.pack_into(
            _MTIME_FMT, self._mm, base + _OFFSET_SIZE + _LENGTH_SIZE, mtime_ns
        )

    # ------------------------------------------------------------------
    # Hash / slot probe  (data slots 1 … size-1)
    # ------------------------------------------------------------------

    def _hash(self, key_bytes):
        return (xxhash.xxh3_64_intdigest(key_bytes) % (self.size - 1)) + 1

    def _find_slot(self, key_bytes):
        """
        Linear probe over data slots [1, size-1] for *key_bytes*.

        Returns ``(slot_index, found)`` where *found* is ``True`` if the key
        is OCCUPIED at that slot, ``False`` if we found a free position.
        Returns ``(None, False)`` if the table is full.
        """
        h = self._hash(key_bytes)
        data_size = self.size - 1
        first_deleted = None
        for i in range(data_size):
            slot = ((h - 1 + i) % data_size) + 1
            offset = slot * self.slot_size
            status = self._mm[offset]
            if status == OCCUPIED:
                if self._read_slot_key(offset) == key_bytes:
                    return slot, True
            elif status == DELETED:
                if first_deleted is None:
                    first_deleted = slot
            else:  # EMPTY
                return (first_deleted if first_deleted is not None else slot), False
        if first_deleted is not None:
            return first_deleted, False
        return None, False

    # ------------------------------------------------------------------
    # Heap I/O
    # ------------------------------------------------------------------

    def _append_to_heap(self, value_bytes):
        """
        Append *value_bytes* to the active heap segment.

        Returns a packed uint64 encoding (segment_id, within-segment offset)
        which is stored verbatim in the index OFFSET field.

        If the active segment would exceed ``max_segment_bytes`` after the
        append, a new segment is rolled and the record is written there.

        Zero-length values still return a packed offset (segment 0, offset 0)
        without writing any bytes — the LENGTH field in the index is 0, so
        callers know to return ``True`` (presence-only) without reading the heap.
        """
        if self.verify_checksums:
            digest = xxhash.xxh3_64_intdigest(value_bytes) if value_bytes else 0
            record = struct.pack(_CRC_FMT, digest) + value_bytes if value_bytes else b""
        else:
            record = value_bytes

        if not record:
            # Zero-length entry — no heap write needed.
            seg_id = self._active_segment_id()
            return self._pack_offset(seg_id, self._heap_size)

        seg_id = self._active_segment_id()
        if self._heap_size + len(record) > self.max_segment_bytes:
            # Roll to a new segment.
            seg_id += 1
            new_path = self._segment_path(seg_id)
            try:
                with salt.utils.files.fopen(new_path, "wb") as _f:
                    pass
            except OSError as exc:
                log.error("Failed to create heap segment %s: %s", new_path, exc)
                # Fall back to the existing segment.
                seg_id -= 1
            else:
                self._seg_mms.append([None, None, 0])
                self._seg_mm_stale.append(True)
                self._heap_size = 0
                log.info("Heap rolled to new segment %d for %s", seg_id, self.heap_path)

        seg_path = self._segment_path(seg_id)
        seg_offset = self._heap_size

        try:
            with salt.utils.files.fopen(seg_path, "ab") as f:
                f.write(record)
                f.flush()
        except OSError as exc:
            log.error("Error appending to heap segment %s: %s", seg_path, exc)
            return self._pack_offset(seg_id, seg_offset)

        self._heap_size += len(record)
        self._seg_mm_stale[seg_id] = True
        if seg_id < len(self._seg_mms):
            self._seg_mms[seg_id][2] = self._heap_size

        return self._pack_offset(seg_id, seg_offset)

    def _read_from_heap(self, packed_offset, length):
        """
        Return *length* value bytes from the heap segment encoded in
        *packed_offset*.

        *packed_offset* is a uint64 whose top 16 bits are the segment ID and
        whose bottom 48 bits are the byte offset within that segment.

        When ``verify_checksums=True`` reads ``length + _CRC_SIZE`` bytes,
        verifies the XXH3-64 prefix, and returns ``None`` on mismatch.

        Uses the resident read-only mmap when available (zero-copy slice).
        Falls back to file I/O when the mmap is unavailable or stale.
        """
        seg_id, seg_offset = self._unpack_offset(packed_offset)

        # Refresh stale mmaps for this segment before reading.
        if seg_id < len(self._seg_mm_stale) and self._seg_mm_stale[seg_id]:
            self._seg_mm_stale[seg_id] = True  # will be refreshed by _open_heap_mmap
            self._open_heap_mmap()

        read_len = length + _CRC_SIZE if self.verify_checksums else length

        raw = None
        if seg_id < len(self._seg_mms):
            mm = self._seg_mms[seg_id][0]
            if mm is not None:
                try:
                    raw = bytes(mm[seg_offset : seg_offset + read_len])
                except (ValueError, OSError):
                    raw = None

        if raw is None:
            seg_path = self._segment_path(seg_id)
            try:
                with salt.utils.files.fopen(seg_path, "rb") as f:
                    f.seek(seg_offset)
                    raw = f.read(read_len)
            except OSError as exc:
                log.error("Error reading heap segment %s: %s", seg_path, exc)
                return None

        if not self.verify_checksums:
            return raw

        if len(raw) < _CRC_SIZE:
            log.error(
                "Heap record at seg=%d offset=%d in %s is truncated "
                "(%d bytes, expected %d)",
                seg_id,
                seg_offset,
                self.heap_path,
                len(raw),
                read_len,
            )
            return None

        stored_digest = struct.unpack_from(_CRC_FMT, raw, 0)[0]
        value = raw[_CRC_SIZE:]
        computed_digest = xxhash.xxh3_64_intdigest(value)
        if stored_digest != computed_digest:
            log.error(
                "Checksum mismatch for heap record at seg=%d offset=%d in %s "
                "(stored 0x%016x, computed 0x%016x) — entry is corrupt",
                seg_id,
                seg_offset,
                self.heap_path,
                stored_digest,
                computed_digest,
            )
            return None

        return value

    def _overwrite_in_heap(self, packed_offset, value_bytes):
        """
        Overwrite bytes in-place in the heap segment encoded in *packed_offset*.

        When ``verify_checksums=True`` rewrites the CRC prefix as well so the
        stored checksum stays consistent with the (possibly shorter) value.
        """
        seg_id, seg_offset = self._unpack_offset(packed_offset)
        seg_path = self._segment_path(seg_id)

        if self.verify_checksums:
            true_value = value_bytes.rstrip(b"\x00")
            digest = xxhash.xxh3_64_intdigest(true_value)
            record = struct.pack(_CRC_FMT, digest) + value_bytes
        else:
            record = value_bytes
        try:
            with salt.utils.files.fopen(seg_path, "r+b") as f:
                f.seek(seg_offset)
                f.write(record)
                f.flush()
        except OSError as exc:
            log.error("Error overwriting heap segment %s: %s", seg_path, exc)
            return False
        # Force mmap refresh on next read.
        if seg_id < len(self._seg_mm_stale):
            self._seg_mm_stale[seg_id] = True
        return True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def put(self, key, value=None):
        """
        Store *key* → *value* in the cache.

        *value* may be ``None`` (set/presence mode), a ``str``, or ``bytes``.
        Returns ``True`` on success, ``False`` on failure.

        If the key already exists and the new value fits in the existing heap
        region, the heap bytes are overwritten in-place.  Otherwise the new
        value is appended to the heap and the index pointer is updated.

        Thread-safe: acquires ``_thread_lock`` (RLock) before ``fcntl.flock``
        so that within-process threads are serialised in addition to the
        cross-process advisory lock.  ``open()`` and ``_heap_size`` update are
        also inside the thread lock to prevent TOCTOU races on ``_heap_size``.
        """
        key_bytes = salt.utils.stringutils.to_bytes(key)[: self.key_size]
        if value is None:
            val_bytes = b""
        elif isinstance(value, bytes):
            val_bytes = value
        else:
            val_bytes = salt.utils.stringutils.to_bytes(value)

        mtime_ns = time.time_ns()

        try:
            with self._thread_lock:
                if not self.open(write=True):
                    return False
                with self._lock():
                    slot, found = self._find_slot(key_bytes)
                    if slot is None:
                        log.error("Mmap cache index is full!")
                        return False

                    s_offset = slot * self.slot_size

                    if found:
                        existing_heap_off, existing_len, _ = self._read_slot_pointer(
                            s_offset
                        )
                        if len(val_bytes) <= existing_len:
                            # Pad value to existing_len; _overwrite_in_heap
                            # prepends the fresh CRC itself.
                            padded = val_bytes.ljust(existing_len, b"\x00")
                            if not self._overwrite_in_heap(existing_heap_off, padded):
                                return False
                            struct.pack_into(
                                _LENGTH_FMT,
                                self._mm,
                                s_offset + self._length_off,
                                len(val_bytes),
                            )
                            struct.pack_into(
                                _MTIME_FMT,
                                self._mm,
                                s_offset + self._mtime_off,
                                mtime_ns,
                            )
                            self._mm.flush()
                            return True
                        # Larger value — append and update pointer; roster unchanged
                        new_heap_off = self._append_to_heap(val_bytes)
                        self._write_slot(
                            s_offset, key_bytes, new_heap_off, len(val_bytes), mtime_ns
                        )
                        self._mm[s_offset] = OCCUPIED
                        self._update_header(new_hwm=slot)
                        self._mm.flush()
                        return True

                    # New key — append to heap, write slot, update roster
                    new_heap_off = self._append_to_heap(val_bytes)
                    self._write_slot(
                        s_offset, key_bytes, new_heap_off, len(val_bytes), mtime_ns
                    )
                    prior_status = self._mm[s_offset]
                    self._mm[s_offset] = OCCUPIED
                    if prior_status == DELETED:
                        self._update_header(
                            occupied_delta=1, deleted_delta=-1, new_hwm=slot
                        )
                    else:
                        self._update_header(occupied_delta=1, new_hwm=slot)
                    # Roster append is inside the lock so a crash between the
                    # index flush and roster append cannot produce divergence
                    # (Item 3 fix — see _roster_recover for open-time repair).
                    self._roster_append(slot)
                    self._mm.flush()
                    return True

        except OSError as exc:
            log.error("Error writing to mmap cache %s: %s", self.path, exc)
            return False

    def get(self, key, default=None):
        """
        Return the value stored for *key*, or *default* if not found.

        Values stored with ``value=None`` (set mode) return ``True``.
        String values are returned as ``str``; raw ``bytes`` values (stored via
        ``put(key, bytes_value)``) are returned as ``bytes``.

        Returns *default* if the heap record fails a CRC check
        (``verify_checksums=True``), logging an error.
        """
        with self._thread_lock:
            if not self.open(write=False):
                return default

            key_bytes = salt.utils.stringutils.to_bytes(key)[: self.key_size]
            h = self._hash(key_bytes)
            data_size = self.size - 1

            for i in range(data_size):
                slot = ((h - 1 + i) % data_size) + 1
                offset = slot * self.slot_size
                status = self._mm[offset]

                if status == EMPTY:
                    return default
                if status == DELETED:
                    continue
                if self._read_slot_key(offset) != key_bytes:
                    continue

                heap_off, length, _ = self._read_slot_pointer(offset)
                if length == 0:
                    return True

                raw = self._read_from_heap(heap_off, length)
                if raw is None:
                    return default

                raw = raw.rstrip(b"\x00") or b""
                if not raw:
                    return True

                try:
                    return salt.utils.stringutils.to_unicode(raw)
                except (UnicodeDecodeError, AttributeError):
                    return raw

            return default

    def get_mtime(self, key):
        """
        Return the mtime (Unix timestamp, float seconds) for *key*, or
        ``None`` if the key does not exist.

        This reads only the index — no heap access required.
        """
        with self._thread_lock:
            if not self.open(write=False):
                return None

            key_bytes = salt.utils.stringutils.to_bytes(key)[: self.key_size]
            h = self._hash(key_bytes)
            data_size = self.size - 1

            for i in range(data_size):
                slot = ((h - 1 + i) % data_size) + 1
                offset = slot * self.slot_size
                status = self._mm[offset]

                if status == EMPTY:
                    return None
                if status == DELETED:
                    continue
                if self._read_slot_key(offset) != key_bytes:
                    continue

                _, _, mtime_ns = self._read_slot_pointer(offset)
                return mtime_ns / 1e9

            return None

    def delete(self, key):
        """Mark *key* as DELETED in the index. Heap bytes become unreachable."""
        key_bytes = salt.utils.stringutils.to_bytes(key)[: self.key_size]

        try:
            with self._thread_lock:
                if not self.open(write=True):
                    return False
                with self._lock():
                    h = self._hash(key_bytes)
                    data_size = self.size - 1
                    for i in range(data_size):
                        slot = ((h - 1 + i) % data_size) + 1
                        offset = slot * self.slot_size
                        status = self._mm[offset]

                        if status == EMPTY:
                            return False
                        if status == DELETED:
                            continue
                        if self._read_slot_key(offset) != key_bytes:
                            continue

                        self._mm[offset] = DELETED
                        self._update_header(occupied_delta=-1, deleted_delta=1)
                        self._roster_remove(slot)
                        self._mm.flush()
                        return True
                return False
        except OSError as exc:
            log.error("Error deleting from mmap cache %s: %s", self.path, exc)
            return False

    def contains(self, key):
        """Return ``True`` if *key* exists in the cache."""
        return self.get(key, default=None) is not None

    def list_keys(self):
        """
        Return all keys currently in the cache.

        Uses the roster file for O(occupied) lookup, reading only the key
        field from the index (no heap access).
        """
        with self._thread_lock:
            if not self.open(write=False):
                return []
            slots = self._roster_read()
            if not slots:
                return []

            ret = []
            for slot in slots:
                if slot == 0 or slot >= self.size:
                    continue
                offset = slot * self.slot_size
                if self._mm[offset] != OCCUPIED:
                    continue
                raw = self._mm[
                    offset + self._key_off : offset + self._key_off + self.key_size
                ]
                null_pos = raw.find(b"\x00")
                key_bytes = raw[:null_pos] if null_pos != -1 else raw
                if not key_bytes:
                    continue
                try:
                    ret.append(key_bytes.decode("utf-8"))
                except UnicodeDecodeError:
                    ret.append(salt.utils.stringutils.to_unicode(key_bytes))

            return ret

    def list_items(self):
        """
        Return all ``(key, value)`` pairs currently in the cache.

        Reads slot indices from the roster file — O(occupied) regardless of
        total table size or fill factor.

        Values stored in set mode are represented as ``True``.
        """
        with self._thread_lock:
            if not self.open(write=False):
                return []
            slots = self._roster_read()
            if not slots:
                return []

            ret = []
            for slot in slots:
                if slot == 0 or slot >= self.size:
                    continue
                offset = slot * self.slot_size
                if self._mm[offset] != OCCUPIED:
                    continue

                key_bytes = self._read_slot_key(offset)
                if not key_bytes:
                    continue

                heap_off, length, _ = self._read_slot_pointer(offset)
                if length == 0:
                    value = True
                else:
                    raw = self._read_from_heap(heap_off, length)
                    if raw is None:
                        continue
                    raw = raw.rstrip(b"\x00") or b""
                    if not raw:
                        value = True
                    else:
                        try:
                            value = salt.utils.stringutils.to_unicode(raw)
                        except (UnicodeDecodeError, AttributeError):
                            value = raw

                ret.append((salt.utils.stringutils.to_unicode(key_bytes), value))

            return ret

    def get_stats(self):
        """
        Return statistics about the cache.

        ``occupied`` and ``deleted`` are read from the header in O(1).
        ``heap_live_bytes`` is computed by iterating the roster — O(occupied).

        Keys: ``occupied``, ``deleted``, ``empty``, ``total``,
        ``load_factor``, ``heap_size_bytes``, ``heap_live_bytes``.
        """
        with self._thread_lock:
            if not self.open(write=False):
                return {
                    "occupied": 0,
                    "deleted": 0,
                    "empty": 0,
                    "total": self.size - 1,
                    "load_factor": 0.0,
                    "heap_size_bytes": 0,
                    "heap_live_bytes": 0,
                }

            occupied, deleted, _ = self._read_header()
            data_size = self.size - 1
            empty = data_size - occupied - deleted

            heap_live = 0
            for slot in self._roster_read():
                if slot == 0 or slot >= self.size:
                    continue
                offset = slot * self.slot_size
                if self._mm[offset] == OCCUPIED:
                    _, length, _ = self._read_slot_pointer(offset)
                    heap_live += length

            try:
                heap_size = os.path.getsize(self.heap_path)
            except OSError:
                heap_size = 0

            return {
                "occupied": occupied,
                "deleted": deleted,
                "empty": empty,
                "total": data_size,
                "load_factor": (
                    (occupied + deleted) / data_size if data_size > 0 else 0.0
                ),
                "heap_size_bytes": heap_size,
                "heap_live_bytes": heap_live,
            }

    def atomic_rebuild(self, iterator):
        """
        Rebuild the cache from an iterator of ``(key, value)`` or ``(key,)``
        tuples.

        Writes fresh temporary index, heap, and roster files, then atomically
        swaps all three.  Roster is swapped last so readers never see a new
        roster pointing into an old index.
        """
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

        tmp_dir = os.path.dirname(self.path)
        tmp_idx_fd, tmp_idx_path = tempfile.mkstemp(dir=tmp_dir, prefix=".mmcache_idx_")
        # Rebuild always starts with a single segment; further rolls happen
        # naturally if max_segment_bytes is exceeded during the write loop.
        tmp_heap_base = tmp_idx_path + ".heap"
        tmp_roster_path = tmp_idx_path + ".roster"

        try:
            with self._thread_lock:
                with self._lock():
                    total_idx = self.size * self.slot_size
                    chunk = 1024 * 1024
                    zeros = b"\x00" * min(chunk, total_idx)
                    with os.fdopen(tmp_idx_fd, "wb") as f:
                        written = 0
                        while written < total_idx:
                            to_write = min(chunk, total_idx - written)
                            f.write(zeros[:to_write])
                            written += to_write
                        f.flush()
                        os.fsync(f.fileno())
                    tmp_idx_fd = -1

                    # seg_id and seg_pos track the current temporary segment.
                    tmp_seg_id = 0
                    tmp_seg_pos = 0  # bytes written to current tmp segment
                    tmp_heap_segs = [tmp_heap_base]  # paths of tmp heap segments
                    occupied_count = 0
                    hwm = 0
                    roster_entries = []

                    heap_f = salt.utils.files.fopen(  # pylint: disable=resource-leakage
                        tmp_heap_base, "wb"
                    )
                    try:
                        with salt.utils.files.fopen(tmp_idx_path, "r+b") as idx_f:
                            mm = mmap.mmap(idx_f.fileno(), 0, access=mmap.ACCESS_WRITE)
                            try:
                                mm[0] = _HEADER_MAGIC

                                for item in iterator:
                                    if (
                                        isinstance(item, (list, tuple))
                                        and len(item) > 1
                                    ):
                                        key, value = item[0], item[1]
                                    else:
                                        key = (
                                            item[0]
                                            if isinstance(item, (list, tuple))
                                            else item
                                        )
                                        value = None

                                    key_bytes = salt.utils.stringutils.to_bytes(key)[
                                        : self.key_size
                                    ]
                                    if value is None:
                                        val_bytes = b""
                                    elif isinstance(value, bytes):
                                        val_bytes = value
                                    else:
                                        val_bytes = salt.utils.stringutils.to_bytes(
                                            value
                                        )

                                    mtime_ns = time.time_ns()
                                    data_size = self.size - 1
                                    h = (
                                        xxhash.xxh3_64_intdigest(key_bytes) % data_size
                                    ) + 1

                                    for i in range(data_size):
                                        s = ((h - 1 + i) % data_size) + 1
                                        s_off = s * self.slot_size
                                        if mm[s_off] != OCCUPIED:
                                            if val_bytes:
                                                if self.verify_checksums:
                                                    digest = xxhash.xxh3_64_intdigest(
                                                        val_bytes
                                                    )
                                                    record = (
                                                        struct.pack(_CRC_FMT, digest)
                                                        + val_bytes
                                                    )
                                                else:
                                                    record = val_bytes
                                                # Roll segment if needed.
                                                if (
                                                    tmp_seg_pos + len(record)
                                                    > self.max_segment_bytes
                                                ):
                                                    heap_f.flush()
                                                    os.fsync(heap_f.fileno())
                                                    heap_f.close()
                                                    tmp_seg_id += 1
                                                    tmp_seg_pos = 0
                                                    new_seg_path = (
                                                        f"{tmp_heap_base}.{tmp_seg_id}"
                                                    )
                                                    tmp_heap_segs.append(new_seg_path)
                                                    heap_f = salt.utils.files.fopen(
                                                        new_seg_path, "wb"
                                                    )
                                                record_offset = self._pack_offset(
                                                    tmp_seg_id, tmp_seg_pos
                                                )
                                                heap_f.write(record)
                                                tmp_seg_pos += len(record)
                                            else:
                                                record_offset = self._pack_offset(
                                                    tmp_seg_id, tmp_seg_pos
                                                )

                                            key_field = key_bytes.ljust(
                                                self.key_size, b"\x00"
                                            )
                                            mm[
                                                s_off + 1 : s_off + 1 + self.key_size
                                            ] = key_field
                                            base = s_off + self._offset_off
                                            struct.pack_into(
                                                _OFFSET_FMT,
                                                mm,
                                                base,
                                                record_offset,
                                            )
                                            struct.pack_into(
                                                _LENGTH_FMT,
                                                mm,
                                                base + _OFFSET_SIZE,
                                                len(val_bytes),
                                            )
                                            struct.pack_into(
                                                _MTIME_FMT,
                                                mm,
                                                base + _OFFSET_SIZE + _LENGTH_SIZE,
                                                mtime_ns,
                                            )
                                            mm[s_off] = OCCUPIED
                                            occupied_count += 1
                                            if s > hwm:
                                                hwm = s
                                            roster_entries.append(s)
                                            break

                                struct.pack_into(
                                    _OFFSET_FMT,
                                    mm,
                                    _HDR_OCCUPIED_OFF,
                                    occupied_count,
                                )
                                struct.pack_into(_OFFSET_FMT, mm, _HDR_DELETED_OFF, 0)
                                struct.pack_into(_OFFSET_FMT, mm, _HDR_HWM_OFF, hwm)

                                heap_f.flush()
                                os.fsync(heap_f.fileno())
                                mm.flush()
                            finally:
                                mm.close()
                    finally:
                        try:
                            heap_f.close()
                        except OSError:
                            pass

                    # Write roster
                    with salt.utils.files.fopen(tmp_roster_path, "wb") as rf:
                        if roster_entries:
                            rf.write(
                                struct.pack(f"<{len(roster_entries)}I", *roster_entries)
                            )
                        rf.flush()
                        os.fsync(rf.fileno())

                    # Remove old extra segments (seg ≥ 1) before swapping.
                    old_extra = 1
                    while True:
                        old_p = self._segment_path(old_extra)
                        if not os.path.exists(old_p):
                            break
                        try:
                            os.remove(old_p)
                        except OSError as exc:
                            log.warning(
                                "Could not remove old heap segment %s: %s",
                                old_p,
                                exc,
                            )
                        old_extra += 1

                    # Close mmaps but keep the lock fd — still inside _lock().
                    self._close_mmaps_and_fds()

                    # Swap order: heap segments → index → roster.
                    # Extra segments get their final names before the pivot.
                    for tmp_seg_path in tmp_heap_segs[1:]:
                        seg_num = int(tmp_seg_path.split(".")[-1])
                        final_seg_path = self._segment_path(seg_num)
                        os.replace(tmp_seg_path, final_seg_path)
                    os.replace(tmp_heap_base, self.heap_path)
                    os.replace(tmp_idx_path, self.path)
                    os.replace(tmp_roster_path, self.roster_path)
                    return True

        except OSError as exc:
            log.error("Error rebuilding mmap cache %s: %s", self.path, exc)
            for p in [tmp_heap_base, tmp_idx_path, tmp_roster_path] + [
                f"{tmp_heap_base}.{i}" for i in range(1, tmp_seg_id + 1)
            ]:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except OSError:
                    pass
            return False
        finally:
            if tmp_idx_fd != -1:
                try:
                    os.close(tmp_idx_fd)
                except OSError:
                    pass
