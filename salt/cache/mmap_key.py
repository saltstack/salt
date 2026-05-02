"""
mmap-native PKI key cache backend.

.. versionadded:: 3009.0

Replaces ``localfs_key`` as the ``keys.cache_driver`` when higher performance
is needed.  Unlike ``localfs_key``, this backend stores everything — minion
IDs, key state, and public key material — in a pair of memory-mapped files
per bank.  There is no filesystem fallback and no dual code path.

On-heap record layout for the ``keys`` bank::

    [STATE: 1 byte][PUB: variable bytes]

State byte values::

    0x01  accepted
    0x02  pending
    0x03  rejected

All other banks (``denied_keys``, ``master_keys``) store raw bytes in the
heap with no state prefix.

The ``master_keys`` bank stores private key material (PEM files).  A separate
``MmapCache`` instance is used for ``master_keys`` so that its permissions can
be locked down independently.

Configuration (all optional, can be set in ``/etc/salt/master``):

.. code-block:: yaml

    keys.cache_driver: mmap_key

    # Slots in the minion key index (default: 1 000 000)
    mmap_key_size: 1000000

    # Bytes per index slot (default: 96)
    mmap_key_slot_size: 96

    # Maximum minion ID length in bytes (default: 64)
    mmap_key_id_size: 64
"""

import logging
import os

import salt.utils.files
import salt.utils.mmap_cache
import salt.utils.path
import salt.utils.stringutils
from salt.exceptions import SaltCacheError
from salt.utils.verify import valid_id

log = logging.getLogger(__name__)

__func_alias__ = {"list_": "list", "flush_": "flush"}

# State byte encoding for the keys bank heap prefix
_STATE_ACCEPTED = 0x01
_STATE_PENDING = 0x02
_STATE_REJECTED = 0x03

_STATE_TO_BYTE = {
    "accepted": _STATE_ACCEPTED,
    "pending": _STATE_PENDING,
    "rejected": _STATE_REJECTED,
}
_BYTE_TO_STATE = {v: k for k, v in _STATE_TO_BYTE.items()}

# Separate index files per bank
_BANK_INDEX_NAME = {
    "keys": ".mmap_keys.idx",
    "denied_keys": ".mmap_denied.idx",
    "master_keys": ".mmap_master.idx",
}

_DEFAULT_SIZE = 1_000_000
_DEFAULT_SLOT_SIZE = 96
_DEFAULT_ID_SIZE = 64

# Module-level registry: (cachedir, bank) → MmapCache
_caches: dict = {}


def init_kwargs(kwargs):
    """
    Return canonical kwargs; mirrors ``localfs_key.init_kwargs``.
    """
    if "pki_dir" in kwargs:
        cachedir = kwargs["pki_dir"]
    elif __opts__.get("cluster_id"):
        cachedir = __opts__["cluster_pki_dir"]
    else:
        cachedir = __opts__["pki_dir"]
    user = kwargs.get("user", __opts__.get("user"))
    return {"cachedir": cachedir, "user": user}


def get_storage_id(kwargs):
    """
    Return a unique identifier for this cache driver instance.
    """
    return ("mmap_key", kwargs.get("cachedir", __opts__.get("pki_dir", "")))


def _get_cache(bank, cachedir):
    """
    Return (or create) the ``MmapCache`` instance for *bank* under *cachedir*.
    """
    key = (cachedir, bank)
    if key not in _caches:
        if bank not in _BANK_INDEX_NAME:
            raise SaltCacheError(f"mmap_key: unrecognised bank {bank!r}")
        os.makedirs(cachedir, exist_ok=True)
        index_path = os.path.join(cachedir, _BANK_INDEX_NAME[bank])
        size = __opts__.get("mmap_key_size", _DEFAULT_SIZE)
        slot_size = __opts__.get("mmap_key_slot_size", _DEFAULT_SLOT_SIZE)
        id_size = __opts__.get("mmap_key_id_size", _DEFAULT_ID_SIZE)
        _caches[key] = salt.utils.mmap_cache.MmapCache(
            path=index_path,
            size=size,
            slot_size=slot_size,
            key_size=id_size,
        )
    return _caches[key]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _encode_key_entry(state, pub):
    """Pack state byte + pub key bytes for the ``keys`` bank heap."""
    state_byte = _STATE_TO_BYTE.get(state)
    if state_byte is None:
        raise SaltCacheError(f"mmap_key: unknown key state {state!r}")
    return bytes([state_byte]) + salt.utils.stringutils.to_bytes(pub)


def _decode_key_entry(raw):
    """
    Unpack a ``keys`` bank heap entry.

    Returns ``{"state": str, "pub": str}`` or ``None`` on corrupt data.
    """
    if not raw or len(raw) < 2:
        return None
    state_byte = raw[0] if isinstance(raw[0], int) else ord(raw[0])
    state = _BYTE_TO_STATE.get(state_byte)
    if state is None:
        return None
    pub = raw[1:].decode("utf-8", errors="replace")
    return {"state": state, "pub": pub}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _check_id(bank, key):
    """Raise SaltCacheError when *key* is not a valid minion_id for key banks."""
    if bank in ("keys", "denied_keys") and not valid_id(__opts__, key):
        raise SaltCacheError(f"mmap_key: {key!r} is not a valid minion_id")


def store(bank, key, data, cachedir, **kwargs):
    """
    Store *data* for *bank*/*key*.

    ``keys`` bank expects ``{"state": str, "pub": str}``.
    ``denied_keys`` bank expects a list; the first element is stored.
    ``master_keys`` bank expects a raw string or bytes.
    """
    _check_id(bank, key)
    cache = _get_cache(bank, cachedir)

    if bank == "keys":
        if not isinstance(data, dict) or "state" not in data or "pub" not in data:
            raise SaltCacheError(
                f"mmap_key: keys bank requires {{state, pub}} dict, got {type(data)}"
            )
        raw = _encode_key_entry(data["state"], data["pub"])

    elif bank == "denied_keys":
        # data is a list; store the first (and typically only) entry
        if isinstance(data, list):
            raw = salt.utils.stringutils.to_bytes(data[0] if data else "")
        else:
            raw = salt.utils.stringutils.to_bytes(data)

    elif bank == "master_keys":
        raw = salt.utils.stringutils.to_bytes(data)

    else:
        raise SaltCacheError(f"mmap_key: unrecognised bank {bank!r}")

    if not cache.put(key, raw):
        raise SaltCacheError(f"mmap_key: failed to write bank={bank!r} key={key!r}")


def fetch(bank, key, cachedir, **kwargs):
    """
    Return the stored value for *bank*/*key*.

    ``keys`` bank returns ``{"state": str, "pub": str}`` or ``None``.
    ``denied_keys`` returns a list of one pub key string, or ``{}``.
    ``master_keys`` returns the raw PEM string, or ``{}``.
    """
    _check_id(bank, key)
    cache = _get_cache(bank, cachedir)
    raw = cache.get(key, default=None)

    if raw is None or raw is True:
        return {} if bank != "keys" else None

    if isinstance(raw, str):
        raw = raw.encode("utf-8")

    if bank == "keys":
        entry = _decode_key_entry(raw)
        return entry  # may be None on corrupt data

    elif bank == "denied_keys":
        return [raw.decode("utf-8", errors="replace").rstrip("\x00")]

    elif bank == "master_keys":
        return raw.decode("utf-8", errors="replace").rstrip("\x00")

    return {}


def updated(bank, key, cachedir, **kwargs):
    """
    Return the Unix timestamp (int) of the last write for *bank*/*key*,
    or ``None`` if not found.
    """
    _check_id(bank, key)
    cache = _get_cache(bank, cachedir)
    mtime = cache.get_mtime(key)
    return int(mtime) if mtime is not None else None


def flush_(bank, key=None, cachedir=None, **kwargs):
    """
    Remove *key* from *bank*, or wipe the entire *bank* if *key* is ``None``.
    """
    if cachedir is None:
        cachedir = __opts__.get("pki_dir", "")

    if key is not None:
        _check_id(bank, key)

    cache = _get_cache(bank, cachedir)

    if key is None:
        # Wipe the whole bank: close and delete the mmap files.
        cache_key = (cachedir, bank)
        c = _caches.pop(cache_key, None)
        if c is not None:
            c.close()
        index_name = _BANK_INDEX_NAME.get(bank)
        if index_name:
            base = os.path.join(cachedir, index_name)
            # Collect all files to remove: fixed suffixes plus any numbered
            # heap segments (.heap.1, .heap.2, …).
            paths_to_remove = [base + s for s in ("", ".heap", ".lock", ".roster")]
            seg_id = 1
            while True:
                seg = f"{base}.heap.{seg_id}"
                if not os.path.exists(seg):
                    break
                paths_to_remove.append(seg)
                seg_id += 1
            for p in paths_to_remove:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except OSError as exc:
                    raise SaltCacheError(f"mmap_key: error removing {p!r}: {exc}")
        return True

    return cache.delete(key)


def list_(bank, cachedir, **kwargs):
    """
    Return all keys in *bank*.
    """
    cache = _get_cache(bank, cachedir)
    return cache.list_keys()


def contains(bank, key, cachedir, **kwargs):
    """
    Return ``True`` if *bank* contains *key*.
    """
    if key is not None:
        _check_id(bank, key)
    if key is None:
        # Bank-level existence check: does the index file exist?
        index_name = _BANK_INDEX_NAME.get(bank)
        if not index_name:
            return False
        return os.path.exists(os.path.join(cachedir, index_name))

    cache = _get_cache(bank, cachedir)
    return cache.contains(key)


def rebuild_from_localfs(opts):
    """
    One-time migration: scan the legacy pki directory layout and load all
    existing keys into the mmap backend.

    Safe to call repeatedly — already-present keys are overwritten in-place.
    Returns ``(accepted, pending, rejected, denied)`` counts.
    """
    if opts.get("cluster_id"):
        pki_dir = opts["cluster_pki_dir"]
    else:
        pki_dir = opts.get("pki_dir", "")

    cachedir = pki_dir  # mmap_key stores alongside pki files

    state_dirs = {
        "minions": "accepted",
        "minions_pre": "pending",
        "minions_rejected": "rejected",
    }

    counts = {"accepted": 0, "pending": 0, "rejected": 0, "denied": 0}

    for dir_name, state in state_dirs.items():
        dir_path = os.path.join(pki_dir, dir_name)
        if not os.path.isdir(dir_path):
            continue
        try:
            with os.scandir(dir_path) as it:
                for entry in it:
                    if not entry.is_file() or entry.is_symlink():
                        continue
                    if entry.name.startswith("."):
                        continue
                    try:
                        with salt.utils.files.fopen(entry.path, "r") as fh_:
                            pub = fh_.read()
                        store(
                            "keys", entry.name, {"state": state, "pub": pub}, cachedir
                        )
                        counts[state] += 1
                    except (OSError, SaltCacheError) as exc:
                        log.warning(
                            "mmap_key migrate: skipping %s: %s", entry.path, exc
                        )
        except OSError as exc:
            log.error("mmap_key migrate: cannot scan %s: %s", dir_path, exc)

    denied_path = os.path.join(pki_dir, "minions_denied")
    if os.path.isdir(denied_path):
        try:
            with os.scandir(denied_path) as it:
                for entry in it:
                    if not entry.is_file() or entry.is_symlink():
                        continue
                    try:
                        with salt.utils.files.fopen(entry.path, "r") as fh_:
                            pub = fh_.read()
                        store("denied_keys", entry.name, [pub], cachedir)
                        counts["denied"] += 1
                    except (OSError, SaltCacheError) as exc:
                        log.warning(
                            "mmap_key migrate denied: skipping %s: %s", entry.path, exc
                        )
        except OSError as exc:
            log.error("mmap_key migrate denied: cannot scan %s: %s", denied_path, exc)

    log.info("mmap_key migrate complete: %s", counts)
    return counts
