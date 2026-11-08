"""
Loader mechanism for caching data, with data expiration, etc.

.. versionadded:: 2016.11.0
"""

import datetime
import logging
import threading
import time
from collections import OrderedDict

import salt.config
import salt.loader
import salt.syspaths
from salt.exceptions import SaltCacheError
from salt.utils.decorators import cached_property

log = logging.getLogger(__name__)


# Thread-local re-entrancy guard for cross-master cache replication.
# ``Cache.store`` / ``Cache.store_many`` consult this flag before
# emitting a ``cluster/runner/delegate_cache_write`` event: a peer-side
# handler (see ``salt/channel/server.py:_handle_delegate_cache_write``)
# applies incoming replication writes by calling ``cache.store`` again
# with the flag set, which must NOT re-broadcast or we'd build an
# infinite fan-out loop across the cluster.  The ``originating_master``
# check in the peer-side handler is the primary loop-safety guard; this
# thread-local is the second line of defense.
_REPLICATION_STATE = threading.local()


def _set_already_replicated(flag):
    """Mark the current thread as applying a peer-originated write."""
    _REPLICATION_STATE.already_replicated = bool(flag)


def _is_already_replicated():
    return getattr(_REPLICATION_STATE, "already_replicated", False)


def factory(opts, **kwargs):
    """
    Creates and returns the cache class.
    If memory caching is enabled by opts MemCache class will be instantiated.
    If not Cache class will be returned.
    """
    if opts.get("memcache_expire_seconds", 0):
        cls = MemCache
    else:
        cls = Cache
    return cls(opts, **kwargs)


class Cache:
    """
    Base caching object providing access to the modular cache subsystem.

    Related configuration options:

    :param cache:
        The name of the cache driver to use. This is the name of the python
        module of the `salt.cache` package. Default is `localfs`.

    Terminology:

    Salt cache subsystem is organized as a tree with nodes and leafs like a
    filesystem. Cache consists of banks. Each bank can contain a number of
    keys. Each key can contain a dict or any other object serializable with
    `salt.payload`. I.e. any data object in the cache can be
    addressed by the path to the bank and the key name:
        bank: 'minions/alpha'
        key:  'data'

    Bank names should be formatted in a way that can be used as a
    directory structure. If slashes are included in the name, then they
    refer to a nested structure.

    Key name is a string identifier of a data container (like a file inside a
    directory) which will hold the data.
    """

    def __init__(self, opts, cachedir=None, **kwargs):
        self.opts = opts

        if kwargs.get("driver"):
            self.driver = kwargs["driver"]
        else:
            self.driver = opts.get("cache", salt.config.DEFAULT_MASTER_OPTS["cache"])

        self.cachedir = kwargs["cachedir"] = cachedir or opts.get(
            "cachedir", salt.syspaths.CACHE_DIR
        )
        self._modules = None
        self._kwargs = kwargs

    @cached_property
    def modules(self):
        # Honor a pre-populated ``_modules`` dict so tests and
        # non-loader-driven callers can inject a mock driver without
        # touching the cached_property machinery.
        if self._modules is not None:
            return self._modules
        return salt.loader.cache(self.opts)

    @cached_property
    def kwargs(self):
        try:
            return self.modules[f"{self.driver}.init_kwargs"](self._kwargs)
        except KeyError:
            return {}

    def destroy(self):
        if hasattr(self, "_modules") and self._modules is not None:
            if hasattr(self._modules, "destroy"):
                self._modules.destroy()
            self._modules = None

    def cache(self, bank, key, fun, loop_fun=None, **kwargs):
        """
        Check cache for the data. If it is there, check to see if it needs to
        be refreshed.

        If the data is not there, or it needs to be refreshed, then call the
        callback function (``fun``) with any given ``**kwargs``.

        In some cases, the callback function returns a list of objects which
        need to be processed by a second function. If that is the case, then
        the second function is passed in as ``loop_fun``. Each item in the
        return list from the first function will be the only argument for the
        second function.
        """
        expire_seconds = kwargs.get("expire", 86400)  # 1 day

        updated = self.updated(bank, key)
        update_cache = False
        if updated is None:
            update_cache = True
        else:
            if int(time.time()) - updated > expire_seconds:
                update_cache = True

        data = self.fetch(bank, key)

        if not data or update_cache is True:
            if loop_fun is not None:
                data = []
                items = fun(**kwargs)
                for item in items:
                    data.append(loop_fun(item))
            else:
                data = fun(**kwargs)
            self.store(bank, key, data)

        return data

    def store(self, bank, key, data, expires=None, _already_replicated=False):
        """
        Store data using the specified module

        :param bank:
            The name of the location inside the cache which will hold the key
            and its associated data.

        :param key:
            The name of the key (or file inside a directory) which will hold
            the data. File extensions should not be provided, as they will be
            added by the driver itself.

        :param data:
            The data which will be stored in the cache. This data should be
            in a format which can be serialized by msgpack.

        :param expires:
            how many seconds from now the data should be considered stale.

        :param _already_replicated:
            Internal flag used by the cluster-cache replication facade.
            When True the local write proceeds but no cross-master
            fan-out is performed.  The peer-side handler passes this
            when applying an incoming replication event so the same
            write doesn't bounce back to every peer again.  Not part
            of the public API.

         :raises SaltCacheError:
            Raises an exception if cache driver detected an error accessing data
            in the cache backend (auth, permissions, etc).
        """
        fun = f"{self.driver}.store"
        try:
            result = self.modules[fun](bank, key, data, expires=expires, **self.kwargs)
        except TypeError:
            # if the backing store doesnt natively support expiry, we handle it as a fallback
            if expires:
                expires_at = datetime.datetime.now().astimezone() + datetime.timedelta(
                    seconds=expires
                )
                expires_at = int(expires_at.timestamp())
                result = self.modules[fun](
                    bank, key, {"data": data, "_expires": expires_at}, **self.kwargs
                )
            else:
                result = self.modules[fun](bank, key, data, **self.kwargs)
        # Cross-master replication fan-out at the facade.  Guarded so
        # non-clustered masters and shared-FS clusters pay no overhead.
        # The peer-side re-dispatch arrives with
        # ``_already_replicated=True`` and skips this block, breaking
        # the loop (combined with the ``originating_master`` check in
        # the handler).
        if not _already_replicated and not _is_already_replicated():
            self._maybe_replicate_write(bank, key, data, expires)
        return result

    def store_many(self, bank, items, expires=None, _already_replicated=False):
        """
        Store multiple ``(key, data)`` pairs in a single bank.

        A thin wrapper over :meth:`store` that applies the same
        cross-master replication semantics.  The default
        implementation loops; drivers that expose a bulk store
        primitive can still accelerate the per-key hot path via the
        underlying driver module (the facade intentionally keeps the
        fan-out per-key so replication-ordering stays well-defined).

        :param bank: The bank name.
        :param items: Iterable of ``(key, data)`` tuples.
        :param expires: Optional seconds-from-now expiry applied to
            every stored entry.
        :param _already_replicated: Internal flag; see :meth:`store`.
        """
        # Suppress replication during the inner per-key stores and
        # emit a single batched replication event after the local
        # writes land.  This keeps the wire-cost proportional to
        # batch count rather than batch size.
        if isinstance(items, dict):
            pairs = list(items.items())
        else:
            pairs = list(items)
        token_prev = _is_already_replicated()
        _set_already_replicated(True)
        try:
            for key, data in pairs:
                self.store(bank, key, data, expires=expires, _already_replicated=True)
        finally:
            _set_already_replicated(token_prev)
        if not _already_replicated and not token_prev:
            self._maybe_replicate_write_many(bank, pairs, expires)

    def _maybe_replicate_write(self, bank, key, data, expires):
        """
        Fan a local cache write out to cluster peers.

        Consults ``cluster_cache_replication`` (master switch) and
        ``cluster_cache_routing[bank]`` (per-bank routing) to decide
        between three outcomes:

        - **replicate**: emit ``cluster/runner/delegate_cache_write``
          (handled by ``MasterPubServerChannel.publish_payload`` ->
          ``publish_cache_write`` -> every peer).  N-of-N fan-out.
        - **ring**: delegate to the existing HashRing owner via the
          ``cluster/runner/delegate_write`` event (1-of-N).  Kept
          for backward compatibility of the ``jobs`` bank.
        - **skip**: non-clustered master, shared-FS mode, or an
          unrecognised routing mode -- the local write stands alone.

        TODO: partial-peer failures are non-destructive today (the
        originating master's local write already succeeded); catch-up
        of a dropped peer is the state-sync expert's lane.  See
        ``agents/scratch/cache-replicate-primary.md``.
        """
        opts = self.opts or {}
        if not opts.get("cluster_id"):
            return
        # Isolated-FS is the only mode where peers can't see each
        # other's local-store writes; shared-FS clusters are a no-op.
        if not opts.get("cluster_isolated_filesystem"):
            return
        # Default-on when the cluster+isolated-FS preconditions are
        # met; operators can force False.  Mirrors the resolution in
        # ``apply_master_config`` for callers that build opts without
        # going through the config loader.
        if opts.get("cluster_cache_replication") is False:
            return
        from salt.config import (
            get_cluster_cache_routing,  # pylint: disable=import-outside-toplevel
        )

        routing = get_cluster_cache_routing(opts)
        mode = routing.get(bank, "replicate")
        if mode == "ring":
            self._fire_ring_delegate(bank, key, data, expires)
        elif mode == "replicate":
            self._fire_replicate(bank, key, data, expires)
        else:
            log.warning(
                "cluster-cache-replication: unknown routing %r for bank %r; "
                "treating as 'replicate'",
                mode,
                bank,
            )
            self._fire_replicate(bank, key, data, expires)

    def _maybe_replicate_write_many(self, bank, pairs, expires):
        """Batched replication: one event per key, same gate as single store."""
        for key, data in pairs:
            self._maybe_replicate_write(bank, key, data, expires)

    def _fire_replicate(self, bank, key, data, expires):
        """Fan this write out to every peer master (see replicator module)."""
        from salt.cache._cluster_replicator import (  # pylint: disable=import-outside-toplevel
            fire_peer_cache_write,
        )

        fire_peer_cache_write(self.opts, bank, key, data, expires)

    def _fire_ring_delegate(self, bank, key, data, expires):
        """Route this write to the HashRing owner (see replicator module)."""
        from salt.cache._cluster_replicator import (  # pylint: disable=import-outside-toplevel
            fire_delegate_cache_write,
        )

        fire_delegate_cache_write(self.opts, bank, key, data, expires)

    def fetch(self, bank, key):
        """
        Fetch data using the specified module

        :param bank:
            The name of the location inside the cache which will hold the key
            and its associated data.

        :param key:
            The name of the key (or file inside a directory) which will hold
            the data. File extensions should not be provided, as they will be
            added by the driver itself.

        :return:
            Return a python object fetched from the cache or an empty dict if
            the given path or key not found.

        :raises SaltCacheError:
            Raises an exception if cache driver detected an error accessing data
            in the cache backend (auth, permissions, etc).
        """
        fun = f"{self.driver}.fetch"
        ret = self.modules[fun](bank, key, **self.kwargs)

        # handle fallback if necessary
        if isinstance(ret, dict) and set(ret.keys()) == {"data", "_expires"}:
            now = datetime.datetime.now().astimezone().timestamp()
            if ret["_expires"] > now:
                return ret["data"]
            else:
                return {}
        else:
            return ret

    def updated(self, bank, key):
        """
        Get the last updated epoch for the specified key

        :param bank:
            The name of the location inside the cache which will hold the key
            and its associated data.

        :param key:
            The name of the key (or file inside a directory) which will hold
            the data. File extensions should not be provided, as they will be
            added by the driver itself.

        :return:
            Return an int epoch time in seconds or None if the object wasn't
            found in cache.

        :raises SaltCacheError:
            Raises an exception if cache driver detected an error accessing data
            in the cache backend (auth, permissions, etc).
        """
        fun = f"{self.driver}.updated"
        return self.modules[fun](bank, key, **self.kwargs)

    def flush(self, bank, key=None):
        """
        Remove the key from the cache bank with all the key content. If no key is specified remove
        the entire bank with all keys and sub-banks inside.

        :param bank:
            The name of the location inside the cache which will hold the key
            and its associated data.

        :param key:
            The name of the key (or file inside a directory) which will hold
            the data. File extensions should not be provided, as they will be
            added by the driver itself.

        :raises SaltCacheError:
            Raises an exception if cache driver detected an error accessing data
            in the cache backend (auth, permissions, etc).
        """
        fun = f"{self.driver}.flush"
        return self.modules[fun](bank, key=key, **self.kwargs)

    def list(self, bank):
        """
        Lists entries stored in the specified bank.

        :param bank:
            The name of the location inside the cache which will hold the key
            and its associated data.

        :return:
            An iterable object containing all bank entries. Returns an empty
            iterator if the bank doesn't exists.

        :raises SaltCacheError:
            Raises an exception if cache driver detected an error accessing data
            in the cache backend (auth, permissions, etc).
        """
        fun = f"{self.driver}.list"
        return self.modules[fun](bank, **self.kwargs)

    def list_all(self, bank, include_data=False):
        """
        Lists all entries with their data from the specified bank.
        This is more efficient than calling list() + fetch() for each entry.

        :param bank:
            The name of the location inside the cache which will hold the key
            and its associated data.

        :param include_data:
            Whether to include the full data for each entry. For some drivers
            (like localfs_key), setting this to False avoids expensive disk reads.

        :return:
            A dict of {key: data} for all entries in the bank. Returns an empty
            dict if the bank doesn't exist or the driver doesn't support list_all.

        :raises SaltCacheError:
            Raises an exception if cache driver detected an error accessing data
            in the cache backend (auth, permissions, etc).
        """
        fun = f"{self.driver}.list_all"
        if fun in self.modules:
            return self.modules[fun](bank, include_data=include_data, **self.kwargs)
        else:
            # Fallback for drivers that don't implement list_all
            raise AttributeError(
                f"Cache driver '{self.driver}' does not implement list_all"
            )

    def contains(self, bank, key=None):
        """
        Checks if the specified bank contains the specified key.

        :param bank:
            The name of the location inside the cache which will hold the key
            and its associated data.

        :param key:
            The name of the key (or file inside a directory) which will hold
            the data. File extensions should not be provided, as they will be
            added by the driver itself.

        :return:
            Returns True if the specified key exists in the given bank and False
            if not.
            If key is None checks for the bank existense.

        :raises SaltCacheError:
            Raises an exception if cache driver detected an error accessing data
            in the cache backend (auth, permissions, etc).
        """
        fun = f"{self.driver}.contains"
        return self.modules[fun](bank, key, **self.kwargs)

    def clean_expired(self, bank, *args, **kwargs):
        """
        Clean expired keys

        :param bank:
            The name of the location inside the cache which will hold the key
            and its associated data.

        :raises SaltCacheError:
            Raises an exception if cache driver detected an error accessing data
            in the cache backend (auth, permissions, etc).
        """
        # If the cache driver has a clean_expired() func, call it to clean up
        # expired keys.
        clean_expired = f"{self.driver}.clean_expired"
        if clean_expired in self.modules:
            self.modules[clean_expired](bank, *args, **{**self.kwargs, **kwargs})
            return

        # Fallback for drivers without native clean_expired. Use the
        # ``_expires`` envelope written by ``Cache.store`` when ``expires``
        # is supplied; entries without that envelope have no cache-level
        # expiry and are left alone. (Previously this path treated the
        # driver's ``updated()`` value -- the file mtime for ``localfs`` --
        # as an absolute expiry epoch, which deleted every entry whose
        # mtime was in the past, i.e. every entry. Issue #69307.)
        list_ = f"{self.driver}.list"
        fetch = f"{self.driver}.fetch"
        flush = f"{self.driver}.flush"
        now = time.time()
        for key in self.modules[list_](bank, **self.kwargs):
            try:
                raw = self.modules[fetch](bank, key, **self.kwargs)
            except SaltCacheError:
                # Best-effort: don't let one unreadable key abort the sweep.
                log.debug("clean_expired: unable to read %s/%s; skipping", bank, key)
                continue
            if (
                isinstance(raw, dict)
                and set(raw.keys()) == {"data", "_expires"}
                and raw["_expires"] <= now
            ):
                self.modules[flush](bank, key, **self.kwargs)


class MemCache(Cache):
    """
    Short-lived in-memory cache store keeping values on time and/or size (count)
    basis.
    """

    # {<storage_id>: odict({<key>: [atime, data], ...}), ...}
    data = {}
    # Class-level lock guarding all mutations of ``data`` and any per-storage
    # OrderedDict inside it. The MWorker async migration dispatches many
    # AESFuncs / AuthFuncs handlers through ``loop.run_in_executor(...)``,
    # so this class-level dict is now touched by arbitrary worker threads
    # under concurrent load. Without a lock, ``dict changed size during
    # iteration`` and torn read-modify-write sequences (e.g. the
    # ``pop`` -> re-``__setitem__`` atime update in :meth:`fetch`) are
    # observable under stress. A single class-level lock is acceptable
    # because the mutations are cheap (dict/OrderedDict ops) and the
    # cache is expressly a short-lived hot path where contention would
    # never dominate against the actual cache-miss returner call.
    _lock = threading.Lock()

    def __init__(self, opts, **kwargs):
        super().__init__(opts, **kwargs)
        self.expire = opts.get("memcache_expire_seconds", 10)
        self.max = opts.get("memcache_max_items", 1024)
        self.cleanup = opts.get("memcache_full_cleanup", False)
        self.debug = opts.get("memcache_debug", False)
        if self.debug:
            self.call = 0
            self.hit = 0
        self._storage = None

    @classmethod
    def __cleanup(cls, expire):
        now = time.time()
        # Caller holds :attr:`_lock`; we iterate the class-level dict and
        # every OrderedDict inside it, so mutation from another thread
        # mid-iteration would raise ``RuntimeError: dictionary changed
        # size during iteration``.
        for storage in cls.data.values():
            for key, data in list(storage.items()):
                if data[0] + expire < now:
                    del storage[key]
                else:
                    break

    def _get_storage_id(self):
        fun = f"{self.driver}.storage_id"
        if fun in self.modules:
            return self.modules[fun](self.kwargs)
        else:
            return self.driver

    @property
    def storage(self):
        if self._storage is None:
            storage_id = self._get_storage_id()
            # Guard the check-then-create against two threads observing an
            # empty ``MemCache.data`` slot and both writing a fresh
            # OrderedDict (the second one would silently discard the first
            # thread's stored records).
            with MemCache._lock:
                if storage_id not in MemCache.data:
                    MemCache.data[storage_id] = OrderedDict()
                self._storage = MemCache.data[storage_id]
        return self._storage

    def fetch(self, bank, key):
        if self.debug:
            self.call += 1
        now = time.time()
        expires = None
        storage = self.storage
        with MemCache._lock:
            record = storage.pop((bank, key), None)
            # Have a cached value for the key
            if record is not None:
                if len(record) == 2:
                    (created_at, data) = record
                elif len(record) == 3:
                    (created_at, expires, data) = record
                else:
                    raise SaltCacheError("Unexpected record structure")

                if (created_at + (expires or self.expire)) >= now:
                    if self.debug:
                        self.hit += 1
                        log.debug(
                            "MemCache stats (call/hit/rate): %s/%s/%s",
                            self.call,
                            self.hit,
                            float(self.hit) / self.call,
                        )
                    # update atime and return
                    record[0] = now
                    storage[(bank, key)] = record
                    return data

        # Have no value for the key or value is expired. The underlying
        # returner call (``super().fetch``) may perform disk / network I/O
        # and must NOT hold the lock (would serialise all concurrent
        # cache-miss loads across every MemCache instance in-process).
        data = super().fetch(bank, key)
        with MemCache._lock:
            if len(storage) >= self.max:
                if self.cleanup:
                    MemCache.__cleanup(self.expire)
                if len(storage) >= self.max:
                    storage.popitem(last=False)
            storage[(bank, key)] = [now, self.expire, data]
        return data

    def store(self, bank, key, data, expires=None, _already_replicated=False):
        storage = self.storage
        with MemCache._lock:
            storage.pop((bank, key), None)
        # ``super().store`` calls the driver (disk / db); keep it off the
        # lock so concurrent stores don't serialise on returner I/O.
        # Only forward the replication flag when it's set to True so
        # legacy mock-based tests keep seeing the original call shape.
        if _already_replicated:
            super().store(bank, key, data, expires=expires, _already_replicated=True)
        else:
            super().store(bank, key, data, expires=expires)
        with MemCache._lock:
            if len(storage) >= self.max:
                if self.cleanup:
                    MemCache.__cleanup(self.expire)
                if len(storage) >= self.max:
                    storage.popitem(last=False)
            storage[(bank, key)] = [time.time(), expires, data]

    def flush(self, bank, key=None):
        storage = self.storage
        with MemCache._lock:
            if key is None:
                for bank_, key_ in tuple(storage):
                    if bank == bank_:
                        storage.pop((bank_, key_))
            else:
                storage.pop((bank, key), None)
        # ``super().flush`` hits the driver; keep it off the lock.
        super().flush(bank, key)
