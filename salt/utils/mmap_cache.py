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
                    # Write in chunks to avoid memory issues for very large caches
                    chunk_size = 1024 * 1024  # 1MB
                    total_size = self.size * self.slot_size
                    written = 0
                    while written < total_size:
                        to_write = min(chunk_size, total_size - written)
                        f.write(b"\x00" * to_write)
                        written += to_write
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
        if not self.open(write=False):
            return []

        ret = []
        for slot in range(self.size):
            offset = slot * self.slot_size
            if self._mm[offset] == OCCUPIED:
                existing_data = self._mm[offset + 1 : offset + self.slot_size]
                null_pos = existing_data.find(b"\x00")
                key_bytes = (
                    existing_data[:null_pos]
                    if null_pos != -1
                    else existing_data.rstrip(b"\x00")
                )
                ret.append(salt.utils.stringutils.to_unicode(key_bytes))
        return ret

    def atomic_rebuild(self, iterator):
        """
        Rebuild the cache from an iterator of (key, value) or (key,)
        This populates a temporary file and swaps it in atomically.
        """
        lock_path = self.path + ".lock"
        tmp_path = self.path + ".tmp"

        # We use a separate lock file for the rebuild process
        with salt.utils.files.flopen(lock_path, "wb"):
            # Create a fresh tmp cache
            tmp_cache = MmapCache(tmp_path, size=self.size, slot_size=self.slot_size)
            if not tmp_cache.open(write=True):
                return False

            try:
                for item in iterator:
                    if isinstance(item, (list, tuple)) and len(item) > 1:
                        tmp_cache.put(item[0], item[1])
                    else:
                        # Set behavior
                        mid = item[0] if isinstance(item, (list, tuple)) else item
                        tmp_cache.put(mid)

                tmp_cache.close()

                # Close current mmap before replacing file
                self.close()

                # Atomic swap
                os.replace(tmp_path, self.path)
                return True
            finally:
                tmp_cache.close()
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
