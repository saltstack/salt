import copy
import logging
import time

import salt.cache
import salt.utils.vault.helpers as hlp
import salt.utils.vault.leases as leases
from salt.utils.vault.exceptions import VaultConfigExpired, VaultLeaseExpired

log = logging.getLogger(__name__)


def _get_config_cache(opts, context, cbank, ckey="config"):
    """
    Factory for VaultConfigCache to get around some
    chicken-and-egg problems
    """
    config = None
    if cbank in context and ckey in context[cbank]:
        config = context[cbank][ckey]
    else:
        cache = salt.cache.factory(opts)
        if cache.contains(cbank, ckey):
            # expiration check is done inside the class
            config = cache.fetch(cbank, ckey)
        elif opts.get("cache", "localfs") != "localfs":
            local_opts = copy.copy(opts)
            local_opts["cache"] = "localfs"
            cache = salt.cache.factory(local_opts)
            if cache.contains(cbank, ckey):
                # expiration check is done inside the class
                config = cache.fetch(cbank, ckey)

    return VaultConfigCache(
        context,
        cbank,
        ckey,
        opts,
        init_config=config,
        flush_exception=VaultConfigExpired,
    )


def _get_cache_backend(config, opts):
    if config["cache"]["backend"] == "session":
        return None
    if config["cache"]["backend"] in ["localfs", "disk", "file"]:
        # cache.Cache does not allow setting the type of cache by param
        local_opts = copy.copy(opts)
        local_opts["cache"] = "localfs"
        return salt.cache.factory(local_opts)
    # this should usually resolve to localfs as well on minions,
    # but can be overridden by setting cache in the minion config
    return salt.cache.factory(opts)


def _get_cache_bank(opts, force_local=False, connection=True, session=False):
    minion_id = None
    # force_local is necessary because pillar compilation would otherwise
    # leak tokens between master and minions
    if not force_local and hlp._get_salt_run_type(opts) in [
        hlp.SALT_RUNTYPE_MASTER_IMPERSONATING,
        hlp.SALT_RUNTYPE_MASTER_PEER_RUN,
    ]:
        minion_id = opts["grains"]["id"]
    prefix = "vault" if minion_id is None else f"minions/{minion_id}/vault"
    if session:
        return prefix + "/connection/session"
    if connection:
        return prefix + "/connection"
    return prefix


class CommonCache:
    """
    Base class that unifies context and other cache backends.
    """

    def __init__(
        self, context, cbank, cache_backend=None, ttl=None, flush_exception=None
    ):
        self.context = context
        self.cbank = cbank
        self.cache = cache_backend
        self.ttl = ttl
        self.flush_exception = flush_exception

    def _ckey_exists(self, ckey, flush=True):
        if self.cbank in self.context and ckey in self.context[self.cbank]:
            return True
        if self.cache is not None:
            if not self.cache.contains(self.cbank, ckey):
                return False
            if self.ttl is not None:
                updated = self.cache.updated(self.cbank, ckey)
                if int(time.time()) - updated >= self.ttl:
                    if flush:
                        log.debug(
                            "Cached data in %s/%s outdated, flushing.", self.cbank, ckey
                        )
                        self.flush()
                    return False
            return True
        return False

    def _get_ckey(self, ckey, flush=True):
        if not self._ckey_exists(ckey, flush=flush):
            return None
        if self.cbank in self.context and ckey in self.context[self.cbank]:
            return self.context[self.cbank][ckey]
        if self.cache is not None:
            return (
                self.cache.fetch(self.cbank, ckey) or None
            )  # account for race conditions
        raise RuntimeError("This code path should not have been hit.")

    def _store_ckey(self, ckey, value):
        if self.cache is not None:
            self.cache.store(self.cbank, ckey, value)
        if self.cbank not in self.context:
            self.context[self.cbank] = {}
        self.context[self.cbank][ckey] = value

    def _flush(self, ckey=None):
        if not ckey and self.flush_exception is not None:
            # Flushing caches in Vault often requires an orchestrated effort
            # to ensure leases/sessions are terminated instead of left open.
            raise self.flush_exception()
        if self.cache is not None:
            self.cache.flush(self.cbank, ckey)
        if self.cbank in self.context:
            if ckey is None:
                self.context.pop(self.cbank)
            else:
                self.context[self.cbank].pop(ckey, None)
        # also remove sub-banks from context to mimic cache behavior
        if ckey is None:
            for bank in list(self.context):
                if bank.startswith(self.cbank):
                    self.context.pop(bank)

    def _list(self):
        ckeys = []
        if self.cbank in self.context:
            ckeys += list(self.context[self.cbank])
        if self.cache is not None:
            ckeys += self.cache.list(self.cbank)
        return set(ckeys)


class VaultCache(CommonCache):
    """
    Encapsulates session and other cache backends for a single domain
    like secret path metadata. Uses a single cache key.
    """

    def __init__(
        self, context, cbank, ckey, cache_backend=None, ttl=None, flush_exception=None
    ):
        super().__init__(
            context,
            cbank,
            cache_backend=cache_backend,
            ttl=ttl,
            flush_exception=flush_exception,
        )
        self.ckey = ckey

    def exists(self, flush=True):
        """
        Check whether data for this domain exists
        """
        return self._ckey_exists(self.ckey, flush=flush)

    def get(self, flush=True):
        """
        Return the cached data for this domain or None
        """
        return self._get_ckey(self.ckey, flush=flush)

    def flush(self, cbank=False):
        """
        Flush the cache for this domain
        """
        return self._flush(self.ckey if not cbank else None)

    def store(self, value):
        """
        Store data for this domain
        """
        return self._store_ckey(self.ckey, value)


class VaultConfigCache(VaultCache):
    """
    Handles caching of received configuration
    """

    def __init__(
        self,
        context,
        cbank,
        ckey,
        opts,
        cache_backend_factory=_get_cache_backend,
        init_config=None,
        flush_exception=None,
    ):  # pylint: disable=super-init-not-called
        self.context = context
        self.cbank = cbank
        self.ckey = ckey
        self.opts = opts
        self.config = None
        self.cache = None
        self.ttl = None
        self.cache_backend_factory = cache_backend_factory
        self.flush_exception = flush_exception
        if init_config is not None:
            self._load(init_config)

    def exists(self, flush=True):
        """
        Check if a configuration has been loaded and cached
        """
        if self.config is None:
            return False
        return super().exists(flush=flush)

    def get(self, flush=True):
        """
        Return the current cached configuration
        """
        if self.config is None:
            return None
        return super().get(flush=flush)

    def flush(self, cbank=True):
        """
        Flush all connection-scoped data
        """
        if self.config is None:
            log.warning(
                "Tried to flush uninitialized configuration cache. Skipping flush."
            )
            return
        # flush the whole connection-scoped cache by default
        super().flush(cbank=cbank)
        self.config = None
        self.cache = None
        self.ttl = None

    def _load(self, config):
        if self.config is not None:
            if (
                self.config["cache"]["backend"] != "session"
                and self.config["cache"]["backend"] != config["cache"]["backend"]
            ):
                self.flush()
        self.config = config
        self.cache = self.cache_backend_factory(self.config, self.opts)
        self.ttl = self.config["cache"]["config"]

    def store(self, value):
        """
        Reload cache configuration, then store the new Vault configuration,
        overwriting the existing one.
        """
        self._load(value)
        super().store(value)


class LeaseCacheMixin:
    """
    Mixin for auth and lease cache that checks validity
    and acts with hydrated objects
    """

    def __init__(self, *args, **kwargs):
        self.lease_cls = kwargs.pop("lease_cls", leases.VaultLease)
        self.expire_events = kwargs.pop("expire_events", None)
        super().__init__(*args, **kwargs)

    def _check_validity(self, lease_data, valid_for=0):
        lease = self.lease_cls(**lease_data)
        try:
            # is_valid on auth classes accounts for duration and uses
            if lease.is_valid(valid_for):
                log.debug("Using cached lease.")
                return lease
        except AttributeError:
            if lease.is_valid_for(valid_for):
                log.debug("Using cached lease.")
                return lease
        if self.expire_events is not None:
            raise VaultLeaseExpired()
        return None


class VaultLeaseCache(LeaseCacheMixin, CommonCache):
    """
    Handles caching of Vault leases. Supports multiple cache keys.
    Checks whether cached leases are still valid before returning.
    """

    def get(self, ckey, valid_for=0, flush=True):
        """
        Returns valid cached lease data or None.
        Flushes cache if invalid by default.
        """
        data = self._get_ckey(ckey, flush=flush)
        if data is None:
            return data
        try:
            ret = self._check_validity(data, valid_for=valid_for)
        except VaultLeaseExpired:
            if self.expire_events is not None:
                self.expire_events(
                    tag=f"vault/lease/{ckey}/expire",
                    data={
                        "valid_for_less": (
                            valid_for
                            if valid_for is not None
                            else data.get("min_ttl") or 0
                        ),
                    },
                )
            ret = None
        if ret is None and flush:
            log.debug("Cached lease not valid anymore. Flushing cache.")
            self._flush(ckey)
        return ret

    def store(self, ckey, value):
        """
        Store a lease in cache
        """
        try:
            value = value.to_dict()
        except AttributeError:
            pass
        return self._store_ckey(ckey, value)

    def exists(self, ckey, flush=True):
        """
        Check whether a named lease exists in cache. Does not filter invalid ones,
        so fetching a reported one might still return None.
        """
        return self._ckey_exists(ckey, flush=flush)

    def flush(self, ckey=None):
        """
        Flush the lease cache or a single lease from the lease cache
        """
        return self._flush(ckey)

    def list(self):
        """
        List all cached leases. Does not filter invalid ones,
        so fetching a reported one might still return None.
        """
        return self._list()


class VaultAuthCache(LeaseCacheMixin, CommonCache):
    """
    Implements authentication secret-specific caches. Checks whether
    the cached secrets are still valid before returning.
    """

    def __init__(
        self,
        context,
        cbank,
        ckey,
        auth_cls,
        cache_backend=None,
        ttl=None,
        flush_exception=None,
    ):
        super().__init__(
            context,
            cbank,
            lease_cls=auth_cls,
            cache_backend=cache_backend,
            ttl=ttl,
            flush_exception=flush_exception,
        )
        self.ckey = ckey
        self.flush_exception = flush_exception

    def exists(self, flush=True):
        """
        Check whether data for this domain exists
        """
        return self._ckey_exists(self.ckey, flush=flush)

    def get(self, valid_for=0, flush=True):
        """
        Returns valid cached auth data or None.
        Flushes cache if invalid by default.
        """
        data = self._get_ckey(self.ckey, flush=flush)
        if data is None:
            return data
        ret = self._check_validity(data, valid_for=valid_for)
        if ret is None and flush:
            log.debug("Cached auth data not valid anymore. Flushing cache.")
            self.flush()
        return ret

    def store(self, value):
        """
        Store an auth credential in cache. Will overwrite possibly existing one.
        """
        try:
            value = value.to_dict()
        except AttributeError:
            pass
        return self._store_ckey(self.ckey, value)

    def flush(self, cbank=None):
        """
        Flush the cached auth credentials. If this is a token cache,
        flushing it will delete the whole session-scoped cache bank.
        """
        if self.lease_cls is leases.VaultToken:
            # flush the whole cbank (session-scope) if this is a token cache
            ckey = None
        else:
            ckey = None if cbank else self.ckey
        return self._flush(ckey)
