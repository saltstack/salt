import logging
import os

log = logging.getLogger(__name__)


class PkiIndex:
    """
    A memory-mapped hash table for O(1) minion ID lookup.
    Wraps the generic MmapCache.
    """

    def __init__(self, opts):
        """
        Initialize the PKI index.
        """
        self.opts = opts
        self.enabled = opts.get("pki_index_enabled", False)
        size = opts.get("pki_index_size", 1000000)
        slot_size = opts.get("pki_index_slot_size", 128)

        if "cluster_id" in opts and opts["cluster_id"]:
            pki_dir = opts["cluster_pki_dir"]
        else:
            pki_dir = opts.get("pki_dir", "")

        # Index lives in cachedir instead of etc
        cachedir = opts.get("cachedir", "/var/cache/salt/master")
        index_path = os.path.join(cachedir, ".pki_index.mmap")

        import salt.utils.mmap_cache  # pylint: disable=import-outside-toplevel

        self._cache = salt.utils.mmap_cache.MmapCache(
            index_path, size=size, slot_size=slot_size
        )

    def open(self, write=False):
        """
        Open the index.
        """
        if not self.enabled:
            return False
        return self._cache.open(write=write)

    def close(self):
        """
        Close the index.
        """
        self._cache.close()

    def add(self, mid, state="accepted"):
        """
        Add a minion to the index.
        """
        if not self.enabled:
            return False
        return self._cache.put(mid, value=state)

    def delete(self, mid):
        """
        Delete a minion from the index.
        """
        if not self.enabled:
            return False
        return self._cache.delete(mid)

    def contains(self, mid):
        """
        Check if a minion is in the index.
        """
        if not self.enabled:
            return None
        return self._cache.contains(mid)

    def list(self):
        """
        List all minions in the index.
        """
        if not self.enabled:
            return []
        return self._cache.list_keys()

    def list_by_state(self, state):
        """
        List minions with a specific state.
        """
        if not self.enabled:
            return []
        return [mid for mid, s in self._cache.list_items() if s == state]

    def list_items(self):
        """
        List all minion/state pairs.
        """
        if not self.enabled:
            return []
        return self._cache.list_items()

    def rebuild(self, iterator):
        """
        Rebuild the index atomically.
        """
        if not self.enabled:
            return False
        return self._cache.atomic_rebuild(iterator)
