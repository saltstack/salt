import logging
import os

import salt.utils.mmap_cache

log = logging.getLogger(__name__)


class PkiIndex:
    """
    A memory-mapped hash table for O(1) minion ID lookup.
    Wraps the generic MmapCache.
    """

    def __init__(self, opts):
        self.opts = opts
        self.enabled = opts.get("pki_index_enabled", False)
        size = opts.get("pki_index_size", 1000000)
        slot_size = opts.get("pki_index_slot_size", 64)
        index_path = os.path.join(opts.get("pki_dir", ""), ".pki_index.mmap")
        self._cache = salt.utils.mmap_cache.MmapCache(
            index_path, size=size, slot_size=slot_size
        )

    def open(self, write=False):
        if not self.enabled:
            return False
        return self._cache.open(write=write)

    def close(self):
        self._cache.close()

    def add(self, mid, state="accepted"):
        if not self.enabled:
            return False
        return self._cache.put(mid, value=state)

    def delete(self, mid):
        if not self.enabled:
            return False
        return self._cache.delete(mid)

    def contains(self, mid):
        if not self.enabled:
            return None
        return self._cache.contains(mid)

    def list(self):
        if not self.enabled:
            return []
        return self._cache.list_keys()

    def list_by_state(self, state):
        if not self.enabled:
            return []
        return [mid for mid, s in self._cache.list_items() if s == state]

    def list_items(self):
        if not self.enabled:
            return []
        return self._cache.list_items()

    def rebuild(self, iterator):
        if not self.enabled:
            return False
        return self._cache.atomic_rebuild(iterator)
