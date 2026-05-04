"""
Cache data in memory-mapped files (index + heap architecture).

.. versionadded:: 3009.0

The ``mmap_cache`` module is a drop-in replacement for the ``localfs`` cache
backend.  It stores cache data in a pair of memory-mapped files per bank:

* **index file** — a fixed-size open-addressing hash table that maps keys to
  heap pointers.
* **heap file** — a flat binary append-log that holds the serialized values.

This layout gives O(1) reads and O(1) appends, which makes it well-suited for
high-frequency workloads such as Raft log persistence.

Configuration (all optional, can be set in ``/etc/salt/master``):

.. code-block:: yaml

    cache: mmap_cache

    # Number of index slots per bank (default: 1 000 000)
    mmap_cache_size: 1000000

    # Bytes per index slot; must be >= 1 + mmap_cache_key_size + 20
    mmap_cache_slot_size: 96

    # Maximum key length in bytes
    mmap_cache_key_size: 64

The ``bank`` concept maps directly to a sub-directory of ``cachedir``.  One
``MmapCache`` instance (index + heap pair) is created per ``(cachedir, bank)``
and kept alive in a module-level registry for the lifetime of the process.
"""

import logging
import os

import msgpack

import salt.utils.mmap_cache
import salt.utils.path
from salt.exceptions import SaltCacheError

# Use raw msgpack directly rather than salt.payload for serialisation.
# salt.payload.loads wraps msgpack with gc.disable/enable, an ext_hook
# closure, and a full decode_embedded_strs walk — making it ~12x slower than
# msgpack.unpackb on typical cache payloads.  The cache layer only stores
# plain Python dicts; it never needs datetime/Constant extension types.
_PACK_OPTS = {"use_bin_type": True}
_UNPACK_OPTS = {"raw": False}

log = logging.getLogger(__name__)

__func_alias__ = {"list_": "list", "flush_": "flush"}

# Module-level registry: (cachedir, bank) → (tuning_tuple, MmapCache).
# When ``__opts__`` mmap tuning changes (e.g. tests patch opts after an early
# cache miss vs hit), evict and rebuild so we never reuse an ``MmapCache``
# sized for stale configuration over the same bank directory.
_caches = {}

# Default tuning knobs (overridable via opts)
_DEFAULT_SIZE = 1_000_000
_DEFAULT_SLOT_SIZE = 96
_DEFAULT_KEY_SIZE = 64


def _mmap_tuning_tuple():
    """Return the effective mmap index tuning from ``__opts__``."""
    return (
        __opts__.get("mmap_cache_size", _DEFAULT_SIZE),
        __opts__.get("mmap_cache_slot_size", _DEFAULT_SLOT_SIZE),
        __opts__.get("mmap_cache_key_size", _DEFAULT_KEY_SIZE),
    )


def _unlink_mmap_bank_files(index_path, *, strict_remove=False):
    """
    Remove mmap cache files for one bank (index + heap segments + roster + lock).

    ``strict_remove=False`` (default): log and continue on ``OSError`` — used when
    evicting a stale registry entry after ``__opts__`` tuning changes.

    ``strict_remove=True``: propagate ``OSError`` — used by ``flush_``.

    Returns ``True`` if at least one file was present and removed.
    """

    removed = False

    def _rm(path):
        nonlocal removed
        if not os.path.exists(path):
            return
        try:
            os.remove(path)
            removed = True
        except OSError as exc:
            if strict_remove:
                raise SaltCacheError(
                    f'Error removing cache file "{path}": {exc}'
                ) from exc
            log.warning("Could not remove mmap cache file %s", path, exc_info=True)

    seg = 0
    while True:
        heap_p = index_path + ".heap" if seg == 0 else index_path + ".heap." + str(seg)
        if not os.path.exists(heap_p):
            break
        _rm(heap_p)
        seg += 1

    for tail in (".roster", ".lock"):
        _rm(index_path + tail)
    _rm(index_path)
    return removed


def __cachedir(kwargs=None):
    if kwargs and "cachedir" in kwargs:
        return kwargs["cachedir"]
    return __opts__.get("cachedir", salt.syspaths.CACHE_DIR)


def init_kwargs(kwargs):
    """
    Return the canonical keyword arguments for this cache driver.
    """
    return {"cachedir": __cachedir(kwargs)}


def get_storage_id(kwargs):
    """
    Return a unique identifier for this cache driver instance.
    """
    return ("mmap_cache", __cachedir(kwargs))


def _get_cache(bank, cachedir):
    """
    Return (or lazily create) the ``MmapCache`` instance for *bank* under
    *cachedir*.
    """
    key = (cachedir, bank)
    tuning = _mmap_tuning_tuple()
    entry = _caches.get(key)
    if entry is not None:
        old_tuning, cache_obj = entry
        if old_tuning == tuning:
            return cache_obj
        index_path = cache_obj.path
        try:
            cache_obj.close()
        except (BufferError, OSError):
            pass
        del _caches[key]
        _unlink_mmap_bank_files(index_path)

    bank_dir = salt.utils.path.join(cachedir, os.path.normpath(bank))
    os.makedirs(bank_dir, exist_ok=True)
    index_path = os.path.join(bank_dir, ".mmap_cache.idx")

    size, slot_size, key_size = tuning
    cache_obj = salt.utils.mmap_cache.MmapCache(
        path=index_path,
        size=size,
        slot_size=slot_size,
        key_size=key_size,
    )
    _caches[key] = (tuning, cache_obj)
    return cache_obj


def store(bank, key, data, cachedir, **kwargs):
    """
    Serialise *data* with msgpack and store it under *bank*/*key*.
    """
    try:
        raw = msgpack.packb(data, **_PACK_OPTS)
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(
            f"Failed to serialise cache data for bank={bank!r} key={key!r}: {exc}"
        )

    cache = _get_cache(bank, cachedir)
    if not cache.put(key, raw):
        raise SaltCacheError(
            f"Failed to write mmap cache entry bank={bank!r} key={key!r}"
        )


def fetch(bank, key, cachedir, **kwargs):
    """
    Return the deserialised value for *bank*/*key*, or ``{}`` if not found.
    """
    cache = _get_cache(bank, cachedir)
    raw = cache.get(key, default=None)

    if raw is None:
        return {}

    # set-mode entries (value=True) indicate presence without data
    if raw is True:
        return {}

    if isinstance(raw, str):
        raw = raw.encode()

    try:
        return msgpack.unpackb(raw, **_UNPACK_OPTS)
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(
            f"Failed to deserialise cache data for bank={bank!r} key={key!r}: {exc}"
        )


def updated(bank, key, cachedir, **kwargs):
    """
    Return the Unix timestamp (int seconds) of the last write for *bank*/*key*,
    or ``None`` if the key does not exist.

    This reads only the index — no heap access required.
    """
    cache = _get_cache(bank, cachedir)
    mtime = cache.get_mtime(key)
    if mtime is None:
        return None
    return int(mtime)


def flush_(bank, key=None, cachedir=None, **kwargs):
    """
    Remove *key* from *bank*, or clear the entire *bank* if *key* is ``None``.

    Clearing a bank removes the mmap files from the registry and deletes them
    from disk, mirroring ``localfs`` behaviour where ``shutil.rmtree`` removes
    the bank directory.
    """
    if cachedir is None:
        cachedir = __cachedir()

    if key is None:
        # Flush entire bank: evict from registry, remove files from disk.
        cache_key = (cachedir, bank)
        entry = _caches.pop(cache_key, None)
        if entry is not None:
            entry[1].close()

        bank_dir = salt.utils.path.join(cachedir, os.path.normpath(bank))
        if not os.path.isdir(bank_dir):
            return False

        # Remove just the mmap files, leave the directory structure intact
        # so that sub-banks are not inadvertently destroyed.
        removed = False
        index_base = os.path.join(bank_dir, ".mmap_cache.idx")
        return _unlink_mmap_bank_files(index_base, strict_remove=True)

    cache = _get_cache(bank, cachedir)
    deleted = cache.delete(key)
    return deleted


def list_(bank, cachedir, **kwargs):
    """
    Return a list of all keys stored in *bank*.
    """
    cache = _get_cache(bank, cachedir)
    return cache.list_keys()


def contains(bank, key, cachedir, **kwargs):
    """
    Return ``True`` if *bank* contains *key* (or, if *key* is ``None``,
    whether the bank itself exists at all).
    """
    if key is None:
        bank_dir = salt.utils.path.join(cachedir, os.path.normpath(bank))
        return os.path.isdir(bank_dir)

    cache = _get_cache(bank, cachedir)
    return cache.contains(key)
