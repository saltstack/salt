import logging
import mmap
import os
import zlib

import salt.utils.files
import salt.utils.stringutils

log = logging.getLogger(__name__)

# Status constants
EMPTY = 0
OCCUPIED = 1
DELETED = 2


class MmapCache:
    """
    A generic memory-mapped hash table for O(1) lookup.
    This class handles the file management and mmap lifecycle.
    """

    def __init__(self, path, size=1000000, slot_size=128):
        self.path = path
        self.size = size
        self.slot_size = slot_size
        self._mm = None
        self._ino = None

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
                    # Use truncate() to create a sparse file efficiently
                    # On most systems this creates a sparse file without writing zeros
                    # mmap will see zeros when reading unwritten regions
                    total_size = self.size * self.slot_size
                    f.truncate(total_size)
            except OSError as exc:
                log.error("Failed to initialize mmap cache file: %s", exc)
                return False
        return True

    def open(self, write=False):
        """
        Open the memory-mapped file.
        """
        if self._mm:
            # Check for staleness (Atomic Swap detection)
            try:
                if os.stat(self.path).st_ino != self._ino:
                    self.close()
                else:
                    return True
            except OSError:
                # File might be temporarily missing during a swap
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
            with salt.utils.files.fopen(self.path, mode) as f:
                self._ino = os.fstat(f.fileno()).st_ino
                # Use 0 for length to map the whole file
                self._mm = mmap.mmap(f.fileno(), 0, access=access)
            return True
        except OSError as exc:
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
            except BufferError:
                # Handle cases where buffers might still be in use
                pass
            self._mm = None
        self._ino = None

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
                    return True
                continue

            # Found an empty or deleted slot.
            # Write data FIRST, then flip status byte to ensure reader safety.
            self._mm[offset + 1 : offset + 1 + len(data)] = data
            if len(data) < self.slot_size - 1:
                self._mm[offset + 1 + len(data)] = 0
            self._mm[offset] = OCCUPIED
            return True

        log.error("Mmap cache is full!")
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
                return True
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

    def atomic_rebuild(self, iterator):
        """
        Rebuild the cache from an iterator of (key, value) or (key,)
        This populates a temporary file and swaps it in atomically.
        """
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

        lock_path = self.path + ".lock"
        tmp_path = self.path + ".tmp"

        # We use a separate lock file for the rebuild process
        with salt.utils.files.flopen(lock_path, "wb"):
            # Create temp file directly and write all data at once
            try:
                # Initialize empty file with truncate
                with salt.utils.files.fopen(tmp_path, "wb") as f:
                    total_size = self.size * self.slot_size
                    f.truncate(total_size)

                # Open for writing
                with salt.utils.files.fopen(tmp_path, "r+b") as f:
                    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_WRITE)

                    try:
                        # Bulk insert all items
                        for item in iterator:
                            if isinstance(item, (list, tuple)) and len(item) > 1:
                                key, value = item[0], item[1]
                            else:
                                key = (
                                    item[0] if isinstance(item, (list, tuple)) else item
                                )
                                value = None

                            key_bytes = salt.utils.stringutils.to_bytes(key)
                            val_bytes = (
                                salt.utils.stringutils.to_bytes(value)
                                if value is not None
                                else b""
                            )

                            data = key_bytes
                            if value is not None:
                                data += b"\x00" + val_bytes

                            if len(data) > self.slot_size - 1:
                                log.warning("Data too long for slot: %s", key)
                                continue

                            # Find slot using same hash function
                            h = zlib.adler32(key_bytes) % self.size
                            for i in range(self.size):
                                slot = (h + i) % self.size
                                offset = slot * self.slot_size

                                if mm[offset] != OCCUPIED:
                                    # Write data then status (reader-safe order)
                                    mm[offset + 1 : offset + 1 + len(data)] = data
                                    if len(data) < self.slot_size - 1:
                                        mm[offset + 1 + len(data)] = 0
                                    mm[offset] = OCCUPIED
                                    break
                    finally:
                        mm.close()

                # Close current mmap before replacing file
                self.close()

                # Atomic swap
                os.replace(tmp_path, self.path)
                return True
            except Exception:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                raise
