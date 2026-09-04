"""
Minion data cache plugin for the etcd key/value store, using API v3.

.. versionadded:: 3009.0

A from-scratch cache backend built around etcd v3 semantics: a flat
keyspace, native byte values, single-PUT atomicity, and lease-based
expiry. It is not a port of
:mod:`salt.cache.etcd_cache <salt.cache.etcd_cache>`, which targets the
v2 HTTP API; the two use different etcd APIs and storage and do not share
data.

Storage model
-------------

Each cache entry is a single etcd key whose value is
``salt.payload.dumps({"d": <data>, "t": <epoch>})`` -- the data and its
modification timestamp wrapped together. A single etcd PUT is atomic, so
there is no sibling timestamp key to keep consistent. The ``bank/key``
hierarchy is mapped to a key path by joining components with ``/``; prefix
operations always use a trailing slash so bank ``foo`` does not match keys
under bank ``foobar``.

Concretely, with the default prefix, bank ``grains`` key ``minion-1`` is
stored at the etcd key ``/salt_cache/grains/minion-1`` and its value is the
msgpack-encoded ``{"d": <data>, "t": <epoch>}`` envelope as raw bytes (not
base64). To inspect the cache directly::

    etcdctl get --prefix /salt_cache/

The v2 :mod:`salt.cache.etcd_cache <salt.cache.etcd_cache>` driver shares
the default ``/salt_cache`` prefix, but the etcd v2 and v3 APIs use
independent keyspaces, so the two do not collide even on the same cluster.
No other Salt etcd integration (the ``etcd`` execution module, state, or
SDB) writes under this prefix.

Setup
-----

Install the etcd3-py client::

    pip install etcd3-py

Enable as the master's data cache::

    cache: etcd3

Optional configuration (defaults shown)::

    etcd.host: 127.0.0.1
    etcd.port: 2379
    etcd.username: null
    etcd.password: null
    etcd.ca: null
    etcd.client_cert: null
    etcd.client_key: null
    etcd.path_prefix: /salt_cache

A profile may be used instead of top-level options by setting
``etcd.cache_profile: my_etcd_config`` on the master and placing the
``etcd.*`` keys under ``my_etcd_config``.

Behaviour notes
---------------

- ``store(bank, key, data, expires=N)`` with a positive ``expires``
  attaches the key to an etcd v3 lease with that TTL in seconds; etcd
  deletes the key when the lease expires. This is used by
  :mod:`salt.auth` for token expiry, so expired tokens are reaped by etcd
  rather than persisting until a manual flush.
- ``list`` and ``contains`` follow :mod:`salt.cache.localfs` semantics:
  ``list(bank)`` returns the immediate children (direct keys and immediate
  sub-bank names), which is what callers such as
  :func:`salt.utils.master._get_cached_minion_data` expect from
  ``cache.list('minions')``.
- ``flush`` returns ``True`` on success, matching
  :mod:`salt.cache.redis_cache`.
- The driver refuses to initialize if ``etcd.path_prefix`` resolves to an
  empty or root path, so a misconfiguration cannot turn a bank flush into
  a range-delete at the cluster root.

Deploying on a shared etcd cluster
----------------------------------

This cache can run against an etcd cluster shared with other tenants
(Patroni, Kubernetes, etc.). Recommended practice:

- **Scope access with etcd RBAC.** The ``etcd.path_prefix`` check is only
  a fat-finger guard; the real isolation boundary is a prefix-scoped etcd
  role::

      etcdctl role add salt-cache
      etcdctl role grant-permission salt-cache --prefix=true readwrite /salt_cache/
      etcdctl user add salt-master
      etcdctl user grant-role salt-master salt-cache

- **Use TLS in production.** Set ``etcd.ca``, ``etcd.client_cert`` and
  ``etcd.client_key`` so cache traffic and credentials are not in the
  clear.
- **Point at the cluster, not a single node** (a TCP load balancer or DNS
  round-robin), so the master survives a single etcd node failing.
- **Confirm auto-compaction is enabled** and **monitor the DB quota**.
  Each ``store`` adds a revision; without compaction the steady-state
  write rate (one revision per minion check-in) grows the DB without
  bound.
- **Multi-master Salt** benefits from etcd's linearizable reads: multiple
  masters sharing this cache see a consistent view without extra
  coordination.

Migrating from the v2 etcd cache
--------------------------------

The v2 API uses a store isolated from v3, so the v3 cache cannot read v2
data (and cannot interfere with it). Because the master cache is
ephemeral and repopulates as minions check in, migration is just: install
``etcd3-py``, change ``cache: etcd`` to ``cache: etcd3``, and restart the
master. Old v2 keys are orphaned in the v2 store; remove them with
``ETCDCTL_API=2 etcdctl rm --recursive /salt_cache`` if desired.

The one user-visible behaviour change is ``list``: the v2 driver returned
recursive leaf names, so ``cache.list('minions')`` produced
``['data', 'data', ...]``; this driver returns the immediate children
(``['minion-1', 'minion-2', ...]``).

Value-size limit
----------------

etcd's default ``--max-request-bytes`` is 1.5 MiB per request. Grains,
mine returns, tokens and minion keys are well under this, but a large
pillar tree may exceed it, in which case ``store`` raises
``SaltCacheError`` wrapping ``etcdserver: request is too large``. Raise
the etcd flag (up to ~10 MiB) or use ``localfs``/``redis`` for very large
pillar.
"""

import logging
import time

import salt.payload
import salt.utils.etcd_util
from salt.exceptions import SaltCacheError

# salt.utils.etcd_util imports cleanly without etcd3-py; HAS_ETCD_V3 reports
# whether the etcd3-py library is actually available.
HAS_ETCD = salt.utils.etcd_util.HAS_ETCD_V3

_DEFAULT_PATH_PREFIX = "/salt_cache"

log = logging.getLogger(__name__)

# Module-level singletons populated by _init_client() on first use. ``client``
# is a configured etcd3-py client (etcd3.Client), not the EtcdClientV3 wrapper.
client = None
path_prefix = None

__virtualname__ = "etcd3"
__func_alias__ = {"ls": "list"}


def __virtual__():
    """
    Only load if the etcd3-py library is available.
    """
    if not HAS_ETCD:
        return (
            False,
            "Please install etcd3-py to use the etcd3 data cache driver",
        )
    return __virtualname__


def init_kwargs(kwargs):
    """
    Cache-plugin hook; no per-instance state is needed, so this always
    returns an empty dict (parity with :mod:`salt.cache.redis_cache`).
    """
    return {}


def _init_client():
    """
    Build the etcd v3 client once and cache it at module level.

    Connection handling (profile resolution, auth, TLS) is reused from
    :class:`salt.utils.etcd_util.EtcdClientV3`; we then operate on the
    configured etcd3-py client directly. The wrapper's read/write layer
    applies a msgpack codec and has neither lease nor keys-only support,
    none of which suits a cache that serializes with :mod:`salt.payload`
    and lists large banks.
    """
    global client, path_prefix
    if client is not None:
        return

    raw_prefix = __opts__.get("etcd.path_prefix", _DEFAULT_PATH_PREFIX)
    stripped = (raw_prefix or "").strip("/")
    if not stripped:
        raise SaltCacheError(
            "etcd3 cache: etcd.path_prefix must resolve to a non-empty path "
            f"(got {raw_prefix!r}). An empty or root prefix would let flush() "
            "prefix-delete keys outside Salt's namespace; refusing to "
            "initialize."
        )
    path_prefix = "/" + stripped

    profile = __opts__.get("etcd.cache_profile")
    # Resolve the (optionally profile-scoped) etcd config and force the v3
    # client regardless of the deprecated ``etcd.require_v2`` flag, so the
    # user does not have to set a "require v2" option to use the v3 cache.
    conf = dict(
        salt.utils.etcd_util._get_etcd_opts(  # pylint: disable=protected-access
            __opts__, profile
        )
    )
    conf["etcd.require_v2"] = False
    log.info(
        "etcd3 cache: initializing client (path_prefix=%s, profile=%s)",
        path_prefix,
        profile,
    )
    client = salt.utils.etcd_util.EtcdClientV3(conf, has_etcd_opts=True).client


def _value_key(bank, key):
    if bank:
        return f"{path_prefix}/{bank}/{key}"
    return f"{path_prefix}/{key}"


def _bank_prefix(bank):
    # The trailing slash matters: prefix-scanning ``{prefix}/foo`` without it
    # would also match ``{prefix}/foobar/...``. An empty bank is the
    # root-listing case used by salt.runners.cache.migrate via
    # ``cache.list("")``; scan from ``{path_prefix}/`` directly.
    if bank:
        return f"{path_prefix}/{bank}/"
    return f"{path_prefix}/"


def _pack(data):
    """Wrap ``data`` with its modification timestamp for storage."""
    return salt.payload.dumps({"d": data, "t": int(time.time())})


def _unpack(raw):
    """Inverse of :func:`_pack`; return ``(data, timestamp)``."""
    obj = salt.payload.loads(raw)
    return obj["d"], obj["t"]


def _range(key, prefix=False, keys_only=False, limit=0):
    """
    Issue an etcd range request and return its key/value pairs as a list
    (etcd3-py returns ``None`` for an empty result).
    """
    return client.range(key, prefix=prefix, keys_only=keys_only, limit=limit).kvs or []


def store(bank, key, data, expires=None):
    """
    Store ``data`` at ``bank/key`` as a single etcd key.

    :param bank: Bank path. May contain ``/`` for nested banks.
    :param key: Leaf key name within the bank.
    :param data: Anything serializable by :mod:`salt.payload`.
    :param expires: If a positive integer, the key is attached to an etcd
        v3 lease with that TTL in seconds and etcd deletes it on expiry.
        ``None``, ``0`` or a negative value stores without a lease.
    :returns: ``None`` on success.
    :raises salt.exceptions.SaltCacheError: On any etcd or serialization
        error.
    """
    _init_client()
    etcd_key = _value_key(bank, key)
    try:
        payload = _pack(data)
        if expires and int(expires) > 0:
            lease = client.Lease(ttl=int(expires))
            lease.grant()
            client.put(etcd_key, payload, lease=lease.ID)
        else:
            client.put(etcd_key, payload)
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(
            f"etcd3 cache: error writing key {etcd_key}: {exc}"
        ) from exc


def fetch(bank, key):
    """
    Return the data stored at ``bank/key``, or ``{}`` on a miss (the cache
    contract every Salt backend honours).

    :raises salt.exceptions.SaltCacheError: On any etcd or deserialization
        error.
    """
    _init_client()
    etcd_key = _value_key(bank, key)
    try:
        kvs = _range(etcd_key)
        if not kvs:
            return {}
        return _unpack(kvs[0].value)[0]
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(
            f"etcd3 cache: error reading key {etcd_key}: {exc}"
        ) from exc


def flush(bank, key=None):
    """
    Remove ``bank/key``, or the entire ``bank`` (and sub-banks) when
    ``key`` is ``None``, via a single etcd delete.

    :returns: ``True`` on success, including the no-op case where nothing
        was deleted (idempotent; matches :mod:`salt.cache.redis_cache`).
    :raises salt.exceptions.SaltCacheError: On any etcd error.
    """
    _init_client()
    try:
        if key is None:
            client.delete_range(_bank_prefix(bank), prefix=True)
        else:
            client.delete_range(_value_key(bank, key))
        return True
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(
            f"etcd3 cache: error flushing bank={bank} key={key}: {exc}"
        ) from exc


def ls(bank):
    """
    Return the immediate children of ``bank``: direct keys plus immediate
    sub-bank names, deduplicated. Matches :mod:`salt.cache.localfs`.

    Uses a keys-only range scan, so listing a large bank does not transfer
    the stored values.

    :param bank: Bank path. The empty bank ``""`` lists the top-level bank
        names (the :func:`salt.runners.cache.migrate` case).
    :returns: A ``list`` of child names; ``[]`` for an empty or nonexistent
        bank.
    :raises salt.exceptions.SaltCacheError: On any etcd error.
    """
    _init_client()
    prefix = _bank_prefix(bank)
    try:
        seen = set()
        result = []
        for kv in _range(prefix, prefix=True, keys_only=True):
            # etcd returns keys as bytes; the first path component after the
            # bank prefix is either a direct key name or an immediate
            # sub-bank name (deeper nesting collapses to the same name).
            first = kv.key.decode("utf-8")[len(prefix) :].split("/", 1)[0]
            if first and first not in seen:
                seen.add(first)
                result.append(first)
        return result
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(f"etcd3 cache: error listing bank {bank}: {exc}") from exc


def contains(bank, key):
    """
    Return whether ``bank/key`` exists, or -- when ``key`` is ``None`` --
    whether anything exists under the bank prefix (matching
    :mod:`salt.cache.localfs`'s ``os.path.isdir(bank)`` semantic).

    :raises salt.exceptions.SaltCacheError: On any etcd error.
    """
    _init_client()
    try:
        if key is None:
            target = _bank_prefix(bank)
            return bool(_range(target, prefix=True, keys_only=True, limit=1))
        return bool(_range(_value_key(bank, key), keys_only=True, limit=1))
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(
            f"etcd3 cache: error checking bank={bank} key={key}: {exc}"
        ) from exc


def updated(bank, key):
    """
    Return the Unix-epoch timestamp at which ``bank/key`` was last stored,
    or ``None`` on a miss.

    :raises salt.exceptions.SaltCacheError: On any etcd error.
    """
    _init_client()
    etcd_key = _value_key(bank, key)
    try:
        kvs = _range(etcd_key)
        if not kvs:
            return None
        return _unpack(kvs[0].value)[1]
    except Exception as exc:  # pylint: disable=broad-except
        raise SaltCacheError(
            f"etcd3 cache: error reading timestamp for {etcd_key}: {exc}"
        ) from exc
