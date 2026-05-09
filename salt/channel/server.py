"""
Encapsulate the different transports available to Salt.

This includes server side transport, for the ReqServer and the Publisher
"""

import asyncio
import collections
import errno
import hashlib
import hmac
import logging
import os
import pathlib
import random
import string
import time
import zlib

import tornado.ioloop

import salt.cache
import salt.cluster.consensus.rpc
import salt.crypt
import salt.master
import salt.payload
import salt.transport
import salt.transport.frame
import salt.transport.tcp
import salt.utils.channel
import salt.utils.event
import salt.utils.minions
import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import SaltDeserializationError
from salt.utils.cache import CacheCli

log = logging.getLogger(__name__)


def _get_crypticle(opts, key_string, key_size=192, serial=0):
    """
    Get appropriate Crypticle class based on configuration.

    Returns TLSAwareCrypticle if TLS optimization is enabled, otherwise
    returns standard Crypticle.

    Args:
        opts: Configuration dictionary
        key_string: AES key string
        key_size: Key size in bits (default: 192)
        serial: Serial number (default: 0)

    Returns:
        Crypticle or TLSAwareCrypticle instance
    """
    if opts.get("disable_aes_with_tls", False):
        return salt.crypt.TLSAwareCrypticle(opts, key_string, key_size, serial)
    else:
        return salt.crypt.Crypticle(opts, key_string, key_size, serial)


def _cluster_is_ready(opts):
    """
    Return ``True`` if this master may serve minion/CLI requests.

    For non-cluster masters this is always ``True``.  For cluster members it
    returns ``True`` only after the Raft ``MembershipStateMachine`` has
    committed a CONFIG entry listing this node as a voter and
    ``SMaster.secrets["cluster_ready"]["event"]`` has been set.
    """
    if not opts.get("cluster_id"):
        return True
    import salt.master  # pylint: disable=import-outside-toplevel

    entry = salt.master.SMaster.secrets.get("cluster_ready")
    if entry is None:
        return False
    return entry["event"].is_set()


def _transport_has_builtin_router(transport):
    """
    Return ``True`` when *transport*'s ``pre_fork`` already starts a process
    that accepts external connections and dispatches them to pool workers.

    ZeroMQ's ``pre_fork`` adds ``zmq_device_pooled`` for that purpose, so
    :class:`PoolRoutingChannel` does not need to spawn its own router.
    Other transports (TCP, WebSockets) bind the external socket but rely on
    a separate process to serve it — :class:`PoolRoutingChannel.pre_fork`
    spawns ``_run_pool_router`` for that case.
    """
    module = getattr(transport.__class__, "__module__", "") or ""
    return module.startswith("salt.transport.zeromq")


def cluster_pub_matches_fingerprint(opts, cluster_pub):
    """
    Verify a received cluster public key against a pinned fingerprint.

    When ``opts["cluster_pub_fingerprint"]`` is set, the joining master
    requires the ``cluster_pub`` it receives in a
    ``cluster/peer/discover-reply`` to hash to that value (SHA-256 hex
    digest of the PEM bytes, case-insensitive). When the option is unset
    this function returns ``True`` unconditionally, which is the
    trust-on-first-contact behavior documented for deployments that share
    ``cluster_pki_dir`` over a filesystem.

    ``cluster_pub`` may be a ``str`` (PEM text) or ``bytes``.

    Returns ``True`` on match (or when no fingerprint is pinned) and
    ``False`` on mismatch.
    """
    pinned = opts.get("cluster_pub_fingerprint")
    if not pinned:
        return True
    if isinstance(cluster_pub, str):
        pub_bytes = cluster_pub.encode()
    else:
        pub_bytes = cluster_pub
    digest = hashlib.sha256(pub_bytes).hexdigest()
    return hmac.compare_digest(digest.lower(), str(pinned).lower())


class ReqServerChannel:
    """
    ReqServerChannel handles request/reply messages from ReqChannels.
    """

    @classmethod
    def factory(cls, opts, **kwargs):
        """
        Return the appropriate server channel for the configured transport.

        Two mutually exclusive code paths exist, selected here at startup:

        1. **Pooled** (``worker_pools_enabled=True``, the default):
           Returns a :class:`PoolRoutingChannel` that sits in front of the
           external transport.  Incoming requests are routed to per-pool IPC
           RequestServers and dispatched to MWorkers.  Clear-text ``_auth``
           uses that IPC path when connected; before IPC clients exist it is
           handled inline (same semantics as the non-pooled channel).

        2. **Non-pooled** (``worker_pools_enabled=False``, legacy):
           Returns a plain :class:`ReqServerChannel` whose
           :meth:`handle_message` intercepts ``_auth`` inline (before the
           payload ever reaches a worker) and handles it directly via
           :meth:`_auth`.  All other commands are forwarded to the single
           worker pool via ``payload_handler``.

        These paths are mutually exclusive at runtime; ``_auth`` is not run
        twice for a single request.
        """
        if "master_uri" not in opts and "master_uri" in kwargs:
            opts["master_uri"] = kwargs["master_uri"]

        # Handle worker pool routing if enabled.
        # PoolRoutingChannel is now the default implementation when
        # worker_pools_enabled=True. We only wrap if we are NOT already a
        # pool-specific server (to avoid recursion).
        if opts.get("worker_pools_enabled", True) and not opts.get("pool_name"):
            from salt.config.worker_pools import get_worker_pools_config

            worker_pools = get_worker_pools_config(opts)
            if worker_pools:
                # Wrap the standard transport in the routing channel
                external_opts = opts.copy()
                external_opts["worker_pools_enabled"] = False
                import salt.transport.base

                transport = salt.transport.base.request_server(external_opts, **kwargs)
                return PoolRoutingChannel(opts, transport, worker_pools)

        import salt.transport.base

        transport = salt.transport.base.request_server(opts, **kwargs)
        return cls(opts, transport)

    @classmethod
    def compare_keys(cls, key1, key2):
        """
        Normalize and compare two keys

        Returns:
            bool: ``True`` if the keys match, otherwise ``False``
        """
        return salt.crypt.clean_key(key1) == salt.crypt.clean_key(key2)

    def __init__(self, opts, transport):
        self.opts = opts
        self.transport = transport
        self.cache = salt.cache.Cache(opts, driver=self.opts["keys.cache_driver"])
        self.event = salt.utils.event.get_master_event(
            self.opts, self.opts["sock_dir"], listen=False
        )
        self.master_key = salt.crypt.MasterKeys(self.opts)

        (pathlib.Path(self.opts["cachedir"]) / "sessions").mkdir(exist_ok=True)
        self.sessions = {}

    @property
    def aes_key(self):
        if self.opts.get("cluster_id", None):
            return salt.master.SMaster.secrets["cluster_aes"]["secret"].value
        return salt.master.SMaster.secrets["aes"]["secret"].value

    def session_key(self, minion):
        """
        Returns a session key for the given minion id.
        """
        now = time.time()
        if minion in self.sessions:
            if now - self.sessions[minion][0] < self.opts["publish_session"]:
                return self.sessions[minion][1]

        path = pathlib.Path(self.opts["cachedir"]) / "sessions" / minion
        try:
            if now - path.stat().st_mtime > self.opts["publish_session"]:
                salt.crypt.Crypticle.write_key(path)
        except FileNotFoundError:
            salt.crypt.Crypticle.write_key(path)

        self.sessions[minion] = (
            path.stat().st_mtime,
            salt.crypt.Crypticle.read_key(path),
        )
        return self.sessions[minion][1]

    def pre_fork(self, process_manager, *args, **kwargs):
        """
        Do anything necessary pre-fork. Since this is on the master side this will
        primarily be bind and listen (or the equivalent for your network library)
        """
        import salt.master

        if "secrets" not in kwargs:
            kwargs["secrets"] = salt.master.SMaster.secrets
        if hasattr(self.transport, "pre_fork"):
            self.transport.pre_fork(process_manager, *args, **kwargs)

    def post_fork(self, payload_handler, io_loop, **kwargs):
        """
        Do anything you need post-fork. This should handle all incoming payloads
        and call payload_handler. You will also be passed io_loop, for all of your
        asynchronous needs
        """
        import salt.master

        if self.opts["pub_server_niceness"] and not salt.utils.platform.is_windows():
            log.info(
                "setting Publish daemon niceness to %i",
                self.opts["pub_server_niceness"],
            )
            os.nice(self.opts["pub_server_niceness"])
        self.io_loop = io_loop
        self.crypticle = _get_crypticle(self.opts, self.aes_key)
        # other things needed for _auth
        # Create the event manager
        self.event = salt.utils.event.get_master_event(
            self.opts, self.opts["sock_dir"], listen=False, io_loop=io_loop
        )
        self.auto_key = salt.daemons.masterapi.AutoKey(self.opts)
        # only create a con_cache-client if the con_cache is active
        if self.opts["con_cache"]:
            self.cache_cli = CacheCli(self.opts)
        else:
            self.cache_cli = False
            # Make an minion checker object
            self.ckminions = salt.utils.minions.CkMinions(self.opts)
        self.master_key = salt.crypt.MasterKeys(self.opts)
        self.payload_handler = payload_handler
        if hasattr(self.transport, "post_fork"):
            self.transport.post_fork(self.handle_message, io_loop, **kwargs)

    async def handle_message(self, payload):
        """
        Handle an incoming request payload (non-pooled / legacy path only).

        This method is only active when ``worker_pools_enabled=False``.  In
        that configuration this channel owns the external transport socket and
        processes every request inline.

        ``_auth`` handling
        ------------------
        When the payload command is ``_auth`` this method calls
        :meth:`_auth` directly and returns the result without forwarding the
        payload to any worker.  This is the **only** place ``_auth`` executes
        in the non-pooled path.

        All other commands are forwarded to a worker via ``payload_handler``
        (i.e. :meth:`~salt.master.MWorker._handle_payload`).

        See :meth:`factory` for the full description of the two mutually
        exclusive request paths and why ``_auth`` is always executed exactly
        once.
        """
        nonce = None
        if (
            not isinstance(payload, dict)
            or "enc" not in payload
            or "load" not in payload
        ):
            log.warning("bad load received on socket")
            return "bad load"
        try:
            version = int(payload.get("version", 0))
        except ValueError:
            version = 0

        # Enforce minimum authentication protocol version to prevent downgrade attacks
        minimum_version = self.opts.get("minimum_auth_version", 0)
        if minimum_version > 0 and version < minimum_version:
            load = payload.get("load")
            if isinstance(load, dict):
                minion_id = load.get("id", "unknown minion")
            else:
                minion_id = "unknown minion"
            log.warning(
                "Rejected authentication attempt from minion '%s' using "
                "protocol version %d (minimum required: %d)",
                minion_id,
                version,
                minimum_version,
            )
            return "bad load"

        try:
            payload = self._decode_payload(payload, version)
        except Exception as exc:  # pylint: disable=broad-except
            exc_type = type(exc).__name__
            if exc_type == "AuthenticationError":
                log.debug(
                    "Minion failed to auth to master. Since the payload is "
                    "encrypted, it is not known which minion failed to "
                    "authenticate. It is likely that this is a transient "
                    "failure due to the master rotating its public key."
                )
            else:
                log.error("Bad load from minion: %s: %s", exc_type, exc)
            return "bad load"

        # TODO helper functions to normalize payload?
        if not isinstance(payload, dict) or not isinstance(payload.get("load"), dict):
            log.error(
                "payload and load must be a dict. Payload was: %s",
                payload,
            )
            return "payload and load must be a dict"

        try:
            id_ = payload["load"].get("id", "")
            if "\0" in id_:
                log.error("Payload contains an id with a null byte: %s", payload)
                return "bad load: id contains a null byte"
        except TypeError:
            log.error("Payload contains non-string id: %s", payload)
            return f"bad load: id {id_} is not a string"

        sign_messages = False
        if version > 1:
            sign_messages = True

        if payload["enc"] == "aes":
            nonce = None
            if version > 1:
                nonce = payload["load"].pop("nonce", None)

            # Check validity of message ttl and id's match
            if version > 2:
                if self.opts["request_server_ttl"] > 0:
                    ttl = time.time() - payload["load"]["ts"]
                    if ttl > self.opts["request_server_ttl"]:
                        log.warning(
                            "Received request from %s with expired ttl: %d > %d",
                            payload["load"]["id"],
                            ttl,
                            self.opts["request_server_ttl"],
                        )
                        return "bad load"

                if payload["id"] != payload["load"]["id"]:
                    log.warning(
                        "Request id mismatch. Found '%s' but expected '%s'",
                        payload["load"]["id"],
                        payload["id"],
                    )
                    return "bad load"
                if not salt.utils.verify.valid_id(self.opts, payload["load"]["id"]):
                    log.warning(
                        "Request contains invalid minion id '%s'", payload["load"]["id"]
                    )
                    return "bad load"
                if not self.validate_token(payload, required=True):
                    return "bad load"
            # The token won't always be present in the payload for and
            # below, but if it is we always wanto validate it.
            elif not self.validate_token(payload, required=False):
                return "bad load"

        # TODO: test
        try:
            # intercept the "_auth" commands, since the main daemon shouldn't know
            # anything about our key auth
            if (
                payload["enc"] == "clear"
                and payload.get("load", {}).get("cmd") == "_auth"
            ):
                # Store time at the beginning of serving _auth call
                # to calculate duration of the call with master_stats
                start = time.time()
                ret = self._auth(payload["load"], sign_messages, version)
                if self.opts.get("master_stats", False):
                    await self.payload_handler({"cmd": "_auth", "_start": start})
                return ret

            # Block non-_auth requests until this node is a committed Raft voter.
            if not _cluster_is_ready(self.opts):
                log.debug(
                    "Cluster not ready yet — deferring request from %s",
                    payload.get("load", {}).get("id", "unknown"),
                )
                return {"enc": "clear", "load": {"ret": False, "cluster_retry": True}}

            # Take the payload_handler function that was registered when we created the channel
            # and call it, returning control to the caller until it completes

            ret, req_opts = await self.payload_handler(payload)

            req_fun = req_opts.get("fun", "send")
            if req_fun == "send_clear":
                return ret
            elif req_fun == "send":
                if version > 2:
                    return _get_crypticle(self.opts, self.session_key(id_)).dumps(
                        ret, nonce
                    )
                else:
                    return self.crypticle.dumps(ret, nonce)
            elif req_fun == "send_private":
                return self._encrypt_private(
                    ret,
                    req_opts["key"],
                    req_opts["tgt"],
                    nonce,
                    sign_messages,
                    payload.get("enc_algo", salt.crypt.OAEP_SHA1),
                    payload.get("sig_algo", salt.crypt.PKCS1v15_SHA1),
                )
            log.error("Unknown req_fun %s", req_fun)
            # always attempt to return an error to the minion
            return "Server-side exception handling payload"

        except Exception as e:  # pylint: disable=broad-except
            # always attempt to return an error to the minion
            log.error("Some exception handling a payload from minion", exc_info=True)
            return "Some exception handling minion payload"

    def _encrypt_private(
        self,
        ret,
        dictkey,
        target,
        nonce=None,
        sign_messages=True,
        encryption_algorithm=salt.crypt.OAEP_SHA1,
        signing_algorithm=salt.crypt.PKCS1v15_SHA1,
    ):
        """
        The server equivalent of ReqChannel.crypted_transfer_decode_dictentry
        """
        # encrypt with a specific AES key
        try:
            key = salt.crypt.Crypticle.generate_key_string()
            pcrypt = _get_crypticle(self.opts, key)
            pub = self.cache.fetch("keys", target)
            if not isinstance(pub, dict) or "pub" not in pub:
                log.error(
                    "No pub key found for target %s, its pub key was likely deleted mid-request.",
                    target,
                )
                return self.crypticle.dumps({})

            pub = salt.crypt.PublicKey.from_str(pub["pub"])
        except Exception as exc:  # pylint: disable=broad-except
            log.error(
                'Corrupt or missing public key "%s": %s',
                target,
                exc,
                exc_info_on_loglevel=logging.DEBUG,
            )
            return self.crypticle.dumps({})
        pret = {}
        pret["key"] = pub.encrypt(key, encryption_algorithm)
        if ret is False:
            ret = {}
        if sign_messages:
            if nonce is None:
                return {"error": "Nonce not included in request"}
            tosign = salt.payload.dumps(
                {"key": pret["key"], "pillar": ret, "nonce": nonce}
            )
            signed_msg = {
                "data": tosign,
                "sig": self.master_key.sign(tosign, algorithm=signing_algorithm),
            }
            pret[dictkey] = pcrypt.dumps(signed_msg)
        else:
            pret[dictkey] = pcrypt.dumps(ret)
        return pret

    def _update_aes(self):
        """
        Check to see if a fresh AES key is available and update the components
        of the worker
        """
        import salt.master

        key = "aes"
        if self.opts.get("cluster_id", None):
            key = "cluster_aes"

        if (
            salt.master.SMaster.secrets[key]["secret"].value
            != self.crypticle.key_string
        ):
            self.crypticle = _get_crypticle(
                self.opts, salt.master.SMaster.secrets[key]["secret"].value
            )
            return True
        return False

    def _decode_payload(self, payload, version):
        # we need to decrypt it
        if payload["enc"] == "aes":
            if version > 2:
                if salt.utils.verify.valid_id(self.opts, payload["id"]):
                    payload["load"] = _get_crypticle(
                        self.opts,
                        self.session_key(payload["id"]),
                    ).loads(payload["load"])
                else:
                    raise SaltDeserializationError("Encountered invalid id")
            else:
                try:
                    payload["load"] = self.crypticle.loads(payload["load"])
                except salt.crypt.AuthenticationError:
                    if not self._update_aes():
                        raise
                    payload["load"] = self.crypticle.loads(payload["load"])
        return payload

    def validate_token(self, payload, required=True):
        """
        Validate the token (tok) and minion id (id) in the payload. If the
        payload and token exist they will be validated even if required is
        False.

        When required is False and either the tok or id is not found in the
        load, this check will pass.

        This method has a side effect of removing the 'tok' key from the load
        so that it is not passed along to request handlers.
        """
        tok = payload["load"].pop("tok", None)
        id_ = payload["load"].get("id", None)
        if tok is not None and id_ is not None:
            if "cluster_id" in self.opts and self.opts["cluster_id"]:
                pki_dir = self.opts["cluster_pki_dir"]
            else:
                pki_dir = self.opts.get("pki_dir", "")
            try:
                pub_path = salt.utils.verify.clean_join(pki_dir, "minions", id_)
            except salt.exceptions.SaltValidationError:
                log.warning("Invalid minion id: %s", id_)
                return False
            try:
                pub = salt.crypt.PublicKey.from_file(pub_path)
            except OSError:
                log.warning(
                    "Salt minion claiming to be %s attempted to communicate with "
                    "master, but key could not be read and verification was denied.",
                    id_,
                )
                return False
            try:
                if pub.decrypt(tok) != b"salt":
                    log.error("Minion token did not validate: %s", id_)
                    return False
            except ValueError as err:
                log.error("Unable to decrypt token: %s", err)
                return False
        elif required:
            return False
        return True

    def _auth(self, load, sign_messages=False, version=0):
        """
        Authenticate a minion by delegating to :class:`salt.master.AuthFuncs`.

        The implementation lives in :mod:`salt.master` so that auth can run
        in a dedicated worker pool.  This method threads the channel's
        existing state (cache, event manager, master key, session cache,
        auto-accept config, con_cache client, ckminions) into the
        ``AuthFuncs`` handler so that callers (and tests) that monkey-patch
        attributes on the channel see those changes reflected in the auth
        handler without having to construct a new ``AuthFuncs`` themselves.
        """
        af = salt.master.AuthFuncs.__new__(salt.master.AuthFuncs)
        af.opts = self.opts
        af.cache = self.cache
        af.event = self.event
        af.master_key = self.master_key
        af.sessions = self.sessions
        af.auto_key = getattr(self, "auto_key", None)
        af.cache_cli = getattr(self, "cache_cli", False)
        af.ckminions = getattr(self, "ckminions", None)
        return af._auth(load, sign_messages, version)

    def close(self):
        self.transport.close()
        if self.event is not None:
            self.event.destroy()


class PoolRoutingChannel:
    """
    Request channel that routes incoming messages to per-pool worker processes
    using transport-native IPC (the pooled path).

    This class is returned by :meth:`ReqServerChannel.factory` when
    ``worker_pools_enabled=True`` (the default).  It is mutually exclusive
    with the plain :class:`ReqServerChannel` — only one of the two is ever
    active for a given master process.

    Architecture::

        External Transport → PoolRoutingChannel → RequestClient (IPC) →
        Pool RequestServer (IPC) → MWorkers

    ``_auth`` handling
    ------------------
    Under a fully started master, ``_auth`` is looked up in the routing table
    and forwarded to the mapped pool's IPC RequestServer, then handled in a
    worker by :meth:`~salt.master.MWorker._handle_clear` →
    :meth:`~salt.master.ClearFuncs._auth`.

    If the pool's IPC client is not connected yet (e.g. tests calling
    :meth:`handle_message` without ``post_fork``), clear-text ``_auth`` is
    handled inline with the same logic as :meth:`ReqServerChannel.handle_message`.

    See :meth:`ReqServerChannel.factory` for the authoritative description of
    the two mutually exclusive paths.

    Key advantages over the legacy single-pool design:
    - No multiprocessing.Queue overhead
    - Uses transport-native IPC (ZeroMQ/TCP/WebSocket)
    - Clean separation of concerns
    - Works across all transports without transport modifications
    """

    def __init__(self, opts, transport, worker_pools):
        """
        Initialize the pool routing channel.

        Args:
            opts: Master configuration options
            transport: The external transport instance (port 4506)
            worker_pools: Dict of pool configurations {pool_name: config}
        """
        self.opts = opts
        self.transport = transport
        self.worker_pools = worker_pools
        self.pool_clients = {}  # pool_name -> RequestClient
        self.pool_servers = {}  # pool_name -> RequestServer
        self.io_loop = None
        self.event = None
        self.router = None
        self.crypticle = None
        self.master_key = None
        self.auto_key = None

        (pathlib.Path(self.opts["cachedir"]) / "sessions").mkdir(exist_ok=True)
        self.sessions = {}

        # Defer CacheCli/CkMinions construction: ``salt.cache.Cache`` holds locks and
        # breaks pickling ``PoolRoutingChannel`` into ``MWorker`` on Windows (spawn).
        # Workers delegate to per-pool ``ReqServerChannel`` and never need this state.
        self.cache = None
        self.cache_cli = False
        self.ckminions = None

        # Build routing table for command-based routing
        self._build_routing_table()

        log.info(
            "PoolRoutingChannel initialized with pools: %s",
            list(worker_pools.keys()),
        )

    def _ensure_auth_support(self):
        """Lazily init key-cache state needed for inline clear-text ``_auth`` only."""
        if self.cache is not None:
            return
        self.cache = salt.cache.Cache(self.opts, driver=self.opts["keys.cache_driver"])
        if self.opts["con_cache"]:
            self.cache_cli = CacheCli(self.opts)
        else:
            self.cache_cli = False
            self.ckminions = salt.utils.minions.CkMinions(self.opts)

    def _build_routing_table(self):
        """
        Build command-to-pool routing table from configuration.

        Exactly one pool must include ``"*"`` in its commands and becomes
        :attr:`default_pool`.  Pool configuration is validated during master
        startup (see
        :func:`salt.config.worker_pools.validate_worker_pools_config`), so
        this method only translates the validated layout into the lookup
        table used at routing time.
        """
        self.command_to_pool = {}
        self.default_pool = None

        for pool_name, config in self.worker_pools.items():
            for cmd in config.get("commands", []):
                if cmd == "*":
                    self.default_pool = pool_name
                else:
                    self.command_to_pool[cmd] = pool_name

        if self.worker_pools and not self.default_pool:
            raise ValueError(
                "Worker pool configuration must have exactly one pool with "
                "catchall ('*') in its commands."
            )

    @property
    def aes_key(self):
        if self.opts.get("cluster_id", None):
            return salt.master.SMaster.secrets["cluster_aes"]["secret"].value
        return salt.master.SMaster.secrets["aes"]["secret"].value

    def session_key(self, minion):
        """
        Returns a session key for the given minion id.
        """
        now = time.time()
        if minion in self.sessions:
            if now - self.sessions[minion][0] < self.opts["publish_session"]:
                return self.sessions[minion][1]

        path = pathlib.Path(self.opts["cachedir"]) / "sessions" / minion
        try:
            if now - path.stat().st_mtime > self.opts["publish_session"]:
                salt.crypt.Crypticle.write_key(path)
        except FileNotFoundError:
            salt.crypt.Crypticle.write_key(path)

        self.sessions[minion] = (
            path.stat().st_mtime,
            salt.crypt.Crypticle.read_key(path),
        )
        return self.sessions[minion][1]

    def _update_aes(self):
        """
        Check to see if a fresh AES key is available and update the components
        of the worker
        """
        key = "aes"
        if self.opts.get("cluster_id", None):
            key = "cluster_aes"

        if (
            salt.master.SMaster.secrets[key]["secret"].value
            != self.crypticle.key_string
        ):
            self.crypticle = _get_crypticle(
                self.opts, salt.master.SMaster.secrets[key]["secret"].value
            )
            return True
        return False

    def pre_fork(self, process_manager, *args, **kwargs):
        """
        Pre-fork setup: Initialize external transport and create RequestServer
        for each worker pool on IPC.
        """
        import salt.master
        import salt.transport.base
        from salt.utils.channel import create_server_transport

        # Pass secrets if not present (critical for decryption in routing)
        if "secrets" not in kwargs:
            kwargs["secrets"] = salt.master.SMaster.secrets

        # Setup external transport (this binds the actual network ports 4505/4506)
        if hasattr(self.transport, "pre_fork"):
            self.transport.pre_fork(process_manager, *args, **kwargs)

        # Create a RequestServer for each pool on IPC
        for pool_name, config in self.worker_pools.items():
            # Create pool-specific opts for IPC
            pool_opts = self.opts.copy()
            pool_opts["pool_name"] = pool_name
            # Disable worker pools for internal routing to avoid circular dependency
            pool_opts["worker_pools_enabled"] = False

            # Configure IPC for this pool
            if pool_opts.get("ipc_mode") == "tcp":
                # TCP IPC mode: use unique port per pool
                base_port = pool_opts.get("tcp_master_workers", 4515)
                port_offset = zlib.adler32(pool_name.encode()) % 1000
                pool_opts["ret_port"] = base_port + port_offset
                log.info(
                    "Pool '%s' RequestServer using TCP IPC on port %d",
                    pool_name,
                    pool_opts["ret_port"],
                )
            else:
                # Standard IPC mode: use unique socket per pool
                sock_dir = pool_opts.get("sock_dir", "/tmp/salt")
                os.makedirs(sock_dir, exist_ok=True)
                pool_opts["workers_ipc_name"] = f"workers-{pool_name}.ipc"
                log.debug(
                    "Pool '%s' RequestServer using IPC socket: %s",
                    pool_name,
                    pool_opts["workers_ipc_name"],
                )

            # Create RequestServer for this pool using transport factory
            try:
                pool_transport = create_server_transport(pool_opts)
                # We wrap it in a minimal ReqServerChannel for compatibility
                pool_server = ReqServerChannel(pool_opts, pool_transport)
                pool_server.pre_fork(process_manager, *args, **kwargs)
                self.pool_servers[pool_name] = pool_server
                log.info("Created RequestServer for pool '%s'", pool_name)
            except Exception as exc:  # pylint: disable=broad-except
                log.error(
                    "Failed to create RequestServer for pool '%s': %s", pool_name, exc
                )
                raise

        # Transports without a built-in pooled router (e.g. ``salt.transport.tcp``)
        # leave the bound external socket without an ``accept`` loop because
        # MWorker's ``post_fork`` only sets up its IPC pool socket.  ZeroMQ
        # avoids this with ``zmq_device_pooled``; TCP/WS need an equivalent
        # router process here.  The forked process inherits the already-bound
        # socket from ``self.transport.pre_fork`` above.
        if not _transport_has_builtin_router(self.transport):
            process_manager.add_process(
                self._run_pool_router,
                kwargs={"secrets": kwargs.get("secrets")},
                name="PoolRouter",
            )

        log.info(
            "PoolRoutingChannel pre_fork complete for %d pools", len(self.worker_pools)
        )

    def _run_pool_router(self, secrets=None):
        """
        Routing-process entry point for transports without a built-in router.

        Inherits the bound external socket from ``pre_fork``, runs an asyncio
        event loop, and dispatches incoming requests to pool MWorkers via the
        per-pool IPC RequestClients set up by :meth:`post_fork` (no
        ``pool_name`` branch).
        """
        if secrets is not None:
            import salt.master  # pylint: disable=import-outside-toplevel

            salt.master.SMaster.secrets = secrets

        io_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(io_loop)
        try:
            self.post_fork(self.handle_and_route_message, io_loop)
            io_loop.run_forever()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            try:
                io_loop.stop()
            except Exception:  # pylint: disable=broad-except
                pass
            io_loop.close()

    def post_fork(self, payload_handler, io_loop, **kwargs):
        """
        Post-fork setup in the routing process.

        This is where we:
        1. Set up the master infrastructure (crypticle, events, keys)
        2. Create RequestClient connections to each pool's RequestServer
        3. Connect the external transport to our routing handler
        """
        pool_name = kwargs.get("pool_name")
        if pool_name:
            # We are in an MWorker process for a specific pool.
            # Delegate to the pool's RequestServer.
            if pool_name in self.pool_servers:
                pool_server = self.pool_servers[pool_name]
                return pool_server.post_fork(payload_handler, io_loop, **kwargs)
            else:
                log.error("Pool '%s' not found in pool_servers", pool_name)
                return

        import salt.master
        from salt.utils.channel import create_request_client

        self.io_loop = io_loop

        # Routing process only (not pool workers): needs cache-backed auth helpers.
        self._ensure_auth_support()

        # Setup master infrastructure (same as ReqServerChannel)
        if (
            self.opts.get("pub_server_niceness")
            and not salt.utils.platform.is_windows()
        ):
            log.debug(
                "setting Publish daemon niceness to %i",
                self.opts["pub_server_niceness"],
            )
            os.nice(self.opts["pub_server_niceness"])

        # Create event manager for the routing process
        self.event = salt.utils.event.get_master_event(
            self.opts, self.opts["sock_dir"], listen=False, io_loop=io_loop
        )

        # Set up crypticle for payload decryption during routing
        self.crypticle = _get_crypticle(self.opts, self.aes_key)

        self.master_key = salt.crypt.MasterKeys(self.opts)

        # Create RequestClient for each pool (connects to pool's IPC RequestServer)
        for pool_name in self.worker_pools.keys():
            # Create pool-specific opts matching the pool's RequestServer
            pool_opts = self.opts.copy()
            pool_opts["pool_name"] = pool_name
            # Disable worker pools for internal routing to avoid circular dependency
            pool_opts["worker_pools_enabled"] = False

            if pool_opts.get("ipc_mode") == "tcp":
                # TCP IPC: connect to pool's port
                base_port = pool_opts.get("tcp_master_workers", 4515)
                port_offset = zlib.adler32(pool_name.encode()) % 1000
                pool_opts["ret_port"] = base_port + port_offset
                pool_opts["master_uri"] = f"tcp://127.0.0.1:{pool_opts['ret_port']}"
                log.debug(
                    "Pool '%s' client connecting to TCP port %d",
                    pool_name,
                    pool_opts["ret_port"],
                )
            else:
                # IPC socket: connect to pool's socket
                pool_opts["workers_ipc_name"] = f"workers-{pool_name}.ipc"
                ipc_path = os.path.join(
                    self.opts["sock_dir"], pool_opts["workers_ipc_name"]
                )
                pool_opts["master_uri"] = f"ipc://{ipc_path}"
                log.debug(
                    "Pool '%s' client connecting to IPC socket: %s",
                    pool_name,
                    pool_opts["workers_ipc_name"],
                )

            try:
                # Use our dedicated request client factory for routing
                client = create_request_client(pool_opts, io_loop)
                self.pool_clients[pool_name] = client
                log.info("Created RequestClient for pool '%s'", pool_name)
            except Exception as exc:  # pylint: disable=broad-except
                log.error(
                    "Failed to create RequestClient for pool '%s': %s", pool_name, exc
                )
                raise

        # Connect external transport to our routing handler
        if hasattr(self.transport, "post_fork"):
            self.transport.post_fork(self.handle_and_route_message, io_loop, **kwargs)

        log.info(
            "PoolRoutingChannel post_fork complete with %d pool clients",
            len(self.pool_clients),
        )

    def _req_channel_auth_delegate(self):
        """
        Build a minimal :class:`ReqServerChannel` view for running
        :meth:`ReqServerChannel._auth` with this channel's opts, keys, and
        cache (used when pool IPC clients are not connected yet).
        """
        ch = ReqServerChannel.__new__(ReqServerChannel)
        ch.opts = self.opts
        ch.transport = self.transport
        ch.cache = self.cache
        ch.event = self.event
        ch.master_key = self.master_key
        ch.sessions = self.sessions
        ch.auto_key = getattr(self, "auto_key", None)
        ch.cache_cli = getattr(self, "cache_cli", False)
        ch.ckminions = getattr(self, "ckminions", None)
        ch.crypticle = getattr(self, "crypticle", None)
        return ch

    async def _handle_clear_auth_local(self, payload, version):
        """
        Run clear-text ``_auth`` the same way :meth:`ReqServerChannel.handle_message`
        does, without forwarding to a worker pool (no IPC client yet).
        """
        self._ensure_auth_support()
        proxy = self._req_channel_auth_delegate()
        try:
            payload = ReqServerChannel._decode_payload(proxy, payload, version)
        except Exception as exc:  # pylint: disable=broad-except
            exc_type = type(exc).__name__
            if exc_type == "AuthenticationError":
                log.debug(
                    "Minion failed to auth to master. Since the payload is "
                    "encrypted, it is not known which minion failed to "
                    "authenticate. It is likely that this is a transient "
                    "failure due to the master rotating its public key."
                )
            else:
                log.error("Bad load from minion: %s: %s", exc_type, exc)
            return "bad load"

        if not isinstance(payload, dict) or not isinstance(payload.get("load"), dict):
            log.error(
                "payload and load must be a dict. Payload was: %s",
                payload,
            )
            return "payload and load must be a dict"

        try:
            id_ = payload["load"].get("id", "")
            if "\0" in id_:
                log.error("Payload contains an id with a null byte: %s", payload)
                return "bad load: id contains a null byte"
        except TypeError:
            log.error("Payload contains non-string id: %s", payload)
            return f"bad load: id {id_} is not a string"

        sign_messages = version > 1

        if (
            payload.get("enc") == "clear"
            and payload.get("load", {}).get("cmd") == "_auth"
        ):
            start = time.time()
            ret = ReqServerChannel._auth(proxy, payload["load"], sign_messages, version)
            if self.opts.get("master_stats", False) and getattr(
                self, "payload_handler", None
            ):
                await self.payload_handler({"cmd": "_auth", "_start": start})
            return ret

        log.error("clear-auth local handler called for non-auth payload: %s", payload)
        return {"error": "Internal routing error", "success": False}

    async def handle_and_route_message(self, payload):
        """
        Route an incoming request to the appropriate worker pool (pooled path).

        Determines the target pool by inspecting the ``cmd`` field of the
        payload load (decrypting first if the load is encrypted), looks it up
        in the routing table, then forwards the raw payload to that pool's
        IPC RequestServer via a RequestClient.

        Clear-text ``_auth`` is normally routed like any other command. When
        no IPC client exists for the target pool yet (e.g. functional tests
        that call :meth:`handle_message` without a full ``post_fork``), it is
        handled inline using the same logic as :meth:`ReqServerChannel.handle_message`.

        See :class:`PoolRoutingChannel` and :meth:`ReqServerChannel.factory`
        for the full explanation of the two mutually exclusive request paths.
        """
        if (
            not isinstance(payload, dict)
            or "enc" not in payload
            or "load" not in payload
        ):
            log.warning("bad load received on socket")
            return "bad load"
        try:
            version = int(payload.get("version", 0))
        except ValueError:
            version = 0

        # Enforce minimum authentication protocol version to prevent downgrade attacks
        minimum_version = self.opts.get("minimum_auth_version", 0)
        if minimum_version > 0 and version < minimum_version:
            load = payload.get("load")
            if isinstance(load, dict):
                minion_id = load.get("id", "unknown minion")
            else:
                minion_id = "unknown minion"
            log.warning(
                "Rejected authentication attempt from minion '%s' using "
                "protocol version %d (minimum required: %d)",
                minion_id,
                version,
                minimum_version,
            )
            return "bad load"

        # Clear-text ``_auth`` is handled locally like legacy ReqServerChannel so
        # bootstrap sign-in does not rely on pool IPC (flaky on Windows with pooled routing).
        if (
            payload.get("enc") == "clear"
            and isinstance(payload.get("load"), dict)
            and payload["load"].get("cmd") == "_auth"
        ):
            return await self._handle_clear_auth_local(payload, version)

        try:
            # Simple command-based routing from our routing table
            load = payload.get("load", {})
            if isinstance(load, dict):
                cmd = load.get("cmd", "unknown")
            else:
                # This is likely an encrypted payload. We need to decrypt
                # to determine the command for routing.
                try:
                    # Determine which key to use based on the 'enc' field
                    enc = payload.get("enc", "aes")
                    if enc == "aes":
                        import salt.master

                        key = (
                            salt.master.SMaster.secrets.get("aes", {})
                            .get("secret", {})
                            .value
                        )
                        if key:
                            import salt.crypt

                            crypticle = salt.crypt.Crypticle(self.opts, key)
                            decrypted = crypticle.loads(load)
                            if isinstance(decrypted, dict) and "cmd" in decrypted:
                                cmd = decrypted.get("cmd", "unknown")
                            elif isinstance(decrypted, dict) and "load" in decrypted:
                                cmd = decrypted["load"].get("cmd", "unknown")
                            else:
                                cmd = "unknown"
                        else:
                            cmd = "unknown"
                    elif enc == "pub":
                        # RSA encryption
                        import salt.crypt

                        mkey = salt.crypt.MasterKeys(self.opts)
                        decrypted = mkey.priv_decrypt(load)
                        if isinstance(decrypted, bytes):
                            import salt.payload

                            decrypted = salt.payload.loads(decrypted)
                        if isinstance(decrypted, dict) and "cmd" in decrypted:
                            cmd = decrypted.get("cmd", "unknown")
                        elif isinstance(decrypted, dict) and "load" in decrypted:
                            cmd = decrypted["load"].get("cmd", "unknown")
                        else:
                            cmd = "unknown"
                    else:
                        cmd = "unknown"
                except Exception:  # pylint: disable=broad-except
                    cmd = "unknown"

            pool_name = self.command_to_pool.get(cmd, self.default_pool)

            log.debug(
                "Routing: cmd=%s -> pool='%s' (pools: %s)",
                cmd,
                pool_name,
                list(self.worker_pools.keys()),
            )

            # Block non-_auth requests until this node is a committed Raft voter.
            if cmd != "_auth" and not _cluster_is_ready(self.opts):
                log.debug("Cluster not ready yet — deferring %s request", cmd)
                return {"enc": "clear", "load": {"ret": False, "cluster_retry": True}}

            if pool_name not in self.pool_clients:
                log.error(
                    "No client available for pool '%s'. Available: %s",
                    pool_name,
                    list(self.pool_clients.keys()),
                )
                return {"error": f"No client for pool {pool_name}"}

            # Forward to the appropriate pool's RequestServer via IPC
            client = self.pool_clients[pool_name]
            reply = await client.send(payload)

            return reply

        except Exception as exc:  # pylint: disable=broad-except
            log.error(
                "Error in pool routing: %s",
                exc,
                exc_info=True,
            )
            return {"error": "Internal routing error", "success": False}

    # Alias for compatibility with older tests and code that expect handle_message
    handle_message = handle_and_route_message

    def close(self):
        """
        Close all resources: pool clients, pool servers, event manager, and external transport.
        """
        log.info("Closing PoolRoutingChannel")

        # Close all pool clients (RequestClients to pool RequestServers)
        for pool_name, client in self.pool_clients.items():
            try:
                if hasattr(client, "close"):
                    client.close()
                elif hasattr(client, "destroy"):
                    client.destroy()
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Error closing client for pool '%s': %s", pool_name, exc)
        self.pool_clients.clear()

        # Close all pool servers
        for pool_name, server in self.pool_servers.items():
            try:
                if hasattr(server, "close"):
                    server.close()
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Error closing server for pool '%s': %s", pool_name, exc)
        self.pool_servers.clear()

        # Close event manager
        if self.event is not None:
            try:
                self.event.destroy()
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Error closing event manager: %s", exc)
            self.event = None

        # Close external transport
        if hasattr(self.transport, "close"):
            try:
                self.transport.close()
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Error closing external transport: %s", exc)

        log.info("PoolRoutingChannel closed")


class PubServerChannel:
    """
    Factory class to create subscription channels to the master's Publisher
    """

    @classmethod
    def factory(cls, opts, **kwargs):
        if "master_uri" not in opts and "master_uri" in kwargs:
            opts["master_uri"] = kwargs["master_uri"]
        presence_events = False
        if opts.get("presence_events", False):
            tcp_only = True
            for transport, _ in salt.utils.channel.iter_transport_opts(opts):
                if transport != "tcp":
                    tcp_only = False
            if tcp_only:
                # Only when the transport is TCP only, the presence events will
                # be handled here. Otherwise, it will be handled in the
                # 'Maintenance' process.
                presence_events = True
        transport = salt.transport.publish_server(opts, **kwargs)
        return cls(opts, transport, presence_events=presence_events)

    def __init__(self, opts, transport, presence_events=False):
        self.opts = opts
        self.ckminions = salt.utils.minions.CkMinions(self.opts)
        self.transport = transport
        self.aes_funcs = salt.master.AESFuncs(self.opts)
        self.present = {}
        self.presence_events = presence_events
        self.event = salt.utils.event.get_event("master", opts=self.opts, listen=False)

    @property
    def aes_key(self):
        if self.opts.get("cluster_id", None):
            return salt.master.SMaster.secrets["cluster_aes"]["secret"].value
        return salt.master.SMaster.secrets["aes"]["secret"].value

    def __getstate__(self):
        return {
            "opts": self.opts,
            "transport": self.transport,
            "presence_events": self.presence_events,
        }

    def __setstate__(self, state):
        self.opts = state["opts"]
        self.state = state["presence_events"]
        self.transport = state["transport"]
        self.event = salt.utils.event.get_event("master", opts=self.opts, listen=False)
        self.ckminions = salt.utils.minions.CkMinions(self.opts)
        self.present = {}
        self.master_key = salt.crypt.MasterKeys(self.opts)

    def close(self):
        self.transport.close()
        if self.event is not None:
            self.event.destroy()
            self.event = None
        if self.aes_funcs is not None:
            self.aes_funcs.destroy()
            self.aes_funcs = None

    def pre_fork(self, process_manager, *args, **kwargs):
        """
        Do anything necessary pre-fork. Since this is on the master side this will
        primarily be used to create IPC channels and create our daemon process to
        do the actual publishing

        :param func process_manager: A ProcessManager, from salt.utils.process.ProcessManager
        """
        if hasattr(self.transport, "publish_daemon"):
            # Extract kwargs for the process.
            # We check for a named 'kwargs' key first (from salt/master.py),
            # then fallback to the entire kwargs dict.
            proc_kwargs = kwargs.pop("kwargs", kwargs).copy()
            if "secrets" not in proc_kwargs:
                import salt.master

                proc_kwargs["secrets"] = salt.master.SMaster.secrets
            if "started" not in proc_kwargs:
                proc_kwargs["started"] = self.transport.started
            process_manager.add_process(self._publish_daemon, kwargs=proc_kwargs)

    def _publish_daemon(self, **kwargs):
        import salt.master

        if self.opts["pub_server_niceness"] and not salt.utils.platform.is_windows():
            log.debug(
                "setting Publish daemon niceness to %i",
                self.opts["pub_server_niceness"],
            )
            os.nice(self.opts["pub_server_niceness"])
        secrets = kwargs.pop("secrets", None)
        started = kwargs.pop("started", None)
        if secrets is not None:
            salt.master.SMaster.secrets = secrets
        self.master_key = salt.crypt.MasterKeys(self.opts)
        self.transport.publish_daemon(
            self.publish_payload,
            self.presence_callback,
            self.remove_presence_callback,
            secrets=secrets,
            started=started,
        )

    def presence_callback(self, subscriber, msg):
        if msg["enc"] != "aes":
            # We only accept 'aes' encoded messages for 'id'
            return
        crypticle = _get_crypticle(self.opts, self.aes_key)
        load = crypticle.loads(msg["load"])
        load = salt.transport.frame.decode_embedded_strs(load)
        if not self.aes_funcs.verify_minion(load["id"], load["tok"]):
            return
        subscriber.id_ = load["id"]
        self._add_client_present(subscriber)

    def remove_presence_callback(self, subscriber):
        self._remove_client_present(subscriber)

    def _add_client_present(self, client):
        id_ = client.id_
        if id_ in self.present:
            clients = self.present[id_]
            clients.add(client)
        else:
            self.present[id_] = {client}
            if self.presence_events:
                data = {"new": [id_], "lost": []}
                self.event.fire_event(
                    data, salt.utils.event.tagify("change", "presence")
                )
                data = {"present": list(self.present.keys())}
                self.event.fire_event(
                    data, salt.utils.event.tagify("present", "presence")
                )

    def _remove_client_present(self, client):
        id_ = client.id_
        if id_ is None or id_ not in self.present:
            # This is possible if _remove_client_present() is invoked
            # before the minion's id is validated.
            return

        clients = self.present[id_]
        if client not in clients:
            # Since _remove_client_present() is potentially called from
            # _stream_read() and/or publish_payload(), it is possible for
            # it to be called twice, in which case we will get here.
            # This is not an abnormal case, so no logging is required.
            return

        clients.remove(client)
        if len(clients) == 0:
            del self.present[id_]
            if self.presence_events:
                data = {"new": [], "lost": [id_]}
                self.event.fire_event(
                    data, salt.utils.event.tagify("change", "presence")
                )
                data = {"present": list(self.present.keys())}
                self.event.fire_event(
                    data, salt.utils.event.tagify("present", "presence")
                )

    async def publish_payload(self, load, *args):
        load = salt.payload.loads(load)
        unpacked_package = self.wrap_payload(load)
        try:
            payload = salt.payload.loads(unpacked_package["payload"])
        except KeyError:
            log.error("Invalid package %r", unpacked_package)
            raise
        payload = salt.payload.dumps(payload)
        if "topic_lst" in unpacked_package:
            topic_list = unpacked_package["topic_lst"]
            ret = await self.transport.publish_payload(payload, topic_list)
        else:
            ret = await self.transport.publish_payload(payload)
        return ret

    def wrap_payload(self, load):
        payload = {"enc": "aes"}
        if not self.opts.get("cluster_id", None):
            load["serial"] = salt.master.SMaster.get_serial()
        crypticle = _get_crypticle(self.opts, self.aes_key)
        payload["load"] = crypticle.dumps(load)
        if self.opts["sign_pub_messages"]:
            log.debug("Signing data packet")
            payload["sig_algo"] = self.opts["publish_signing_algorithm"]
            payload["sig"] = self.master_key.sign(
                payload["load"], self.opts["publish_signing_algorithm"]
            )

        int_payload = {"payload": salt.payload.dumps(payload)}

        # If topics are upported, target matching has to happen master side
        match_targets = ["pcre", "glob", "list"]
        if self.transport.topic_support() and load["tgt_type"] in match_targets:
            # add some targeting stuff for lists only (for now)
            if load["tgt_type"] == "list":
                int_payload["topic_lst"] = load["tgt"]
            if isinstance(load["tgt"], str):
                # Fetch a list of minions that match
                _res = self.ckminions.check_minions(
                    load["tgt"], tgt_type=load["tgt_type"]
                )
                match_ids = _res["minions"]
                log.debug("Publish Side Match: %s", match_ids)
                # Send list of miions thru so zmq can target them
                int_payload["topic_lst"] = match_ids
            else:
                int_payload["topic_lst"] = load["tgt"]

        return int_payload

    async def publish(self, load):
        """
        Publish "load" to minions
        """
        log.debug(
            "Sending payload to publish daemon. jid=%s load=%s",
            load.get("jid", None),
            repr(load)[:40],
        )
        payload = salt.payload.dumps(load)
        await self.transport.publish(payload)


class MasterPubServerChannel:
    """ """

    @classmethod
    def factory(cls, opts, **kwargs):
        if opts.get("cluster_id"):
            # Cluster mode: Use TCP-based transport for peer communication while
            # preserving normal local IPC behavior for internal processes.
            port = opts.get("cluster_port", 55596)
            pull_path = os.path.join(opts["sock_dir"], "master_event_pull.ipc")
            pub_path = os.path.join(opts["sock_dir"], "master_event_pub.ipc")
            bind_host = opts.get("interface", "127.0.0.1")

            try:
                transport = salt.transport.tcp.PublishServer(
                    opts,
                    pub_host=bind_host,
                    pub_port=opts.get("publish_port", 4505),
                    pub_path=pub_path,
                    pull_host=bind_host,
                    pull_port=port,
                    pull_path=pull_path,
                )
            except OSError as exc:
                if exc.errno == errno.EADDRINUSE:
                    transport = salt.transport.tcp.PublishServer(
                        opts,
                        pub_host=bind_host,
                        pub_port=opts.get("publish_port", 4505),
                        pub_path=pub_path,
                        pull_host=bind_host,
                        pull_port=0,
                        pull_path=pull_path,
                    )
                else:
                    raise
        else:
            transport = salt.transport.ipc_publish_server("master", opts)

        return cls(opts, transport)

    def __init__(
        self,
        opts,
        transport,
        presence_events=False,
    ):
        self.opts = opts
        self.transport = transport
        self.io_loop = tornado.ioloop.IOLoop.current()
        self.master_key = salt.crypt.MasterKeys(self.opts)
        self.peer_keys = {}
        self.cluster_peers = self.opts["cluster_peers"]
        self._discover_event = None
        self._discover_token = None
        self._discover_candidates = {}
        # Set by service.py once the Raft node is started.
        self._raft_dispatcher = None

    def _start_raft_as_founding_voter(self):
        """
        Start Raft as a voting founding member.

        Called by a timer in ``_publish_daemon`` when no ``join-reply`` was
        received within ``cluster_join_timeout`` seconds.  This indicates that
        the node is part of a brand-new cluster where all peers are starting
        simultaneously and none have sent a join-reply yet.
        """
        if self._raft_service is not None:
            return  # already started by a join-reply race

        log.info(
            "No join-reply received — starting Raft as founding voter for cluster %r",
            self.opts["cluster_id"],
        )
        try:
            import salt.utils.asynchronous  # pylint: disable=import-outside-toplevel
            from salt.cluster.consensus.service import (  # pylint: disable=import-outside-toplevel
                RaftService,
                build_peer_pushers,
            )

            aio_loop = salt.utils.asynchronous.aioloop(self.io_loop)
            peer_pushers = build_peer_pushers(self.opts, self.pushers)
            self._raft_service = RaftService(
                self.opts,
                aio_loop,
                peer_pushers,
                on_ready=self._signal_cluster_ready,
            )
            self._raft_service.attach(self)
            self._raft_service.start()
            # Write the join sentinel so future restarts skip discover/join.
            self._mark_joined_cluster()
            log.info(
                "Raft consensus service started as founding voter for cluster %r",
                self.opts["cluster_id"],
            )
        except Exception:  # pylint: disable=broad-except
            log.exception("Failed to start Raft as founding voter")

    def _start_raft_as_learner(self, known_peers):
        """
        Start ``RaftService`` as a non-voting learner after a dynamic join.

        Called from ``handle_pool_publish`` when ``cluster/peer/join-reply``
        is received.  At this point ``_publish_daemon`` is inside
        ``io_loop.start()`` so the asyncio loop is already running.

        :param known_peers: dict ``{peer_id: pub_key_pem}`` from the
                            ``join-reply`` payload — the addresses of all
                            existing cluster members.
        """
        if self._raft_service is not None:
            return

        import salt.utils.asynchronous  # pylint: disable=import-outside-toplevel

        try:
            from salt.cluster.consensus.service import (  # pylint: disable=import-outside-toplevel
                RaftService,
            )

            aio_loop = salt.utils.asynchronous.aioloop(self.io_loop)
            port = self.opts.get("cluster_port", 55596)

            # One pusher per remote host.  Do not use ``build_peer_pushers`` here:
            # discover-reply appends duplicate hosts to ``opts["cluster_peers"]`` and
            # extra pushers, which would mis-align a plain zip with the static opts list.
            peer_pushers = {p.pull_host: p for p in self.pushers}
            for peer_id in known_peers:
                if peer_id not in peer_pushers:
                    pusher = self.pusher(peer_id, port)
                    self.pushers.append(pusher)
                    peer_pushers[peer_id] = pusher

            self._raft_service = RaftService(
                self.opts,
                aio_loop,
                peer_pushers,
                voting=False,
                on_ready=self._signal_cluster_ready,
            )
            self._raft_service.attach(self)
            aio_loop.call_soon(self._raft_service.start)
            log.info(
                "Raft consensus service started as learner for cluster %r after dynamic join",
                self.opts["cluster_id"],
            )
        except Exception:  # pylint: disable=broad-except
            log.exception("Failed to start Raft consensus service after join")

    def gen_token(self):
        return "".join(random.choices(string.ascii_letters + string.digits, k=32))

    async def _send_state_sync_chunks(self, session_id, peer_id):
        """
        Stream the four state-sync channels (keys, denied_keys,
        file_roots, pillar_roots) to a freshly joined peer.

        Each channel runs to completion independently and emits at least
        one chunk (an empty chunk with ``eof=True`` if the channel has
        no data).  All chunks are encrypted with the cluster session AES
        key — the joiner has it from the join-reply we just sent.
        """
        from salt.cluster.state_sync import (  # pylint: disable=import-outside-toplevel
            DENIED_CHANNEL,
            FILE_ROOTS_CHANNEL,
            KEYS_CHANNEL,
            PILLAR_ROOTS_CHANNEL,
            iter_keys_chunks,
            iter_root_chunks,
        )

        pusher = self.pusher(peer_id)
        crypticle = salt.crypt.Crypticle(
            self.opts,
            salt.master.SMaster.secrets["cluster_aes"]["secret"].value,
        )

        async def send_channel(channel, chunk_iter):
            chunks = list(chunk_iter)
            if not chunks:
                # Defensive: every iter_*_chunks must yield ≥ 1 (empty
                # for empty data).  Synthesize an eof-only chunk so the
                # receiver doesn't hang on a missing channel.
                chunks = [[]]
            total = len(chunks)
            for seq, items in enumerate(chunks):
                payload = {
                    "session": session_id,
                    "channel": channel,
                    "seq": seq,
                    "total": total,
                    "eof": seq == total - 1,
                    "items": items,
                }
                event_data = salt.utils.event.SaltEvent.pack(
                    salt.utils.event.tagify("state-sync-chunk", "peer", "cluster"),
                    crypticle.dumps(payload),
                )
                try:
                    await pusher.publish(event_data)
                except Exception:  # pylint: disable=broad-except
                    log.exception(
                        "state-sync %s/%s seq=%d publish failed to %s",
                        session_id,
                        channel,
                        seq,
                        peer_id,
                    )
                    return
            log.info(
                "state-sync %s/%s sent %d chunks (%d items total) to %s",
                session_id,
                channel,
                total,
                sum(len(c) for c in chunks),
                peer_id,
            )

        # Run the four channels concurrently — each finishes when it
        # finishes, and a slow file_roots stream does not block keys.
        try:
            await asyncio.gather(
                send_channel(KEYS_CHANNEL, iter_keys_chunks(self.opts, KEYS_CHANNEL)),
                send_channel(
                    DENIED_CHANNEL, iter_keys_chunks(self.opts, DENIED_CHANNEL)
                ),
                send_channel(
                    FILE_ROOTS_CHANNEL,
                    iter_root_chunks(self.opts.get("file_roots")),
                ),
                send_channel(
                    PILLAR_ROOTS_CHANNEL,
                    iter_root_chunks(self.opts.get("pillar_roots")),
                ),
            )
        except Exception:  # pylint: disable=broad-except
            log.exception("state-sync session %s aborted unexpectedly", session_id)

    def _apply_state_sync_chunk(self, chunk):
        """
        Install one ``cluster/peer/state-sync-chunk`` payload locally.

        The chunk has already been Crypticle-decrypted by the caller.
        We dispatch to the right install helper by ``chunk["channel"]``,
        then ping the matching :class:`StateSyncSession` so
        :meth:`_start_raft_as_learner` fires once all four channels eof.
        """
        from salt.cluster.state_sync import (  # pylint: disable=import-outside-toplevel
            DENIED_CHANNEL,
            FILE_ROOTS_CHANNEL,
            KEYS_CHANNEL,
            PILLAR_ROOTS_CHANNEL,
            install_keys_chunk,
            install_root_chunk,
        )

        if not isinstance(chunk, dict):
            log.warning("state-sync chunk is not a dict: %r", type(chunk).__name__)
            return
        session_id = chunk.get("session")
        channel = chunk.get("channel")
        seq = chunk.get("seq", -1)
        eof = bool(chunk.get("eof"))
        items = chunk.get("items") or []
        sessions = getattr(self, "_state_sync_sessions", None) or {}
        session = sessions.get(session_id)
        if session is None:
            log.warning(
                "state-sync chunk for unknown session %r (channel=%s seq=%s); dropping",
                session_id,
                channel,
                seq,
            )
            return

        installed = 0
        try:
            if channel in (KEYS_CHANNEL, DENIED_CHANNEL):
                installed = install_keys_chunk(self.opts, channel, items)
            elif channel == FILE_ROOTS_CHANNEL:
                installed = install_root_chunk(self.opts.get("file_roots"), items)
            elif channel == PILLAR_ROOTS_CHANNEL:
                installed = install_root_chunk(self.opts.get("pillar_roots"), items)
            else:
                log.warning(
                    "state-sync chunk for unknown channel %r (session=%s seq=%s)",
                    channel,
                    session_id,
                    seq,
                )
                return
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "state-sync %s/%s seq=%s install failed",
                session_id,
                channel,
                seq,
            )

        log.info(
            "state-sync %s/%s seq=%s installed %d items%s",
            session_id,
            channel,
            seq,
            installed,
            " (eof)" if eof else "",
        )
        session.record_chunk(channel, seq, eof, installed)

    def _begin_state_sync_session(self, session_id, known_peers, discover_event):
        """
        Register a state-sync session and arm its watchdog timer.

        Called from the join-reply handler once we know the responder is
        running with ``cluster_isolated_filesystem=True`` and intends to
        push the four chunked channels at us.  The session's
        ``on_complete`` callback fires
        :meth:`_start_raft_as_learner` exactly once, either when all four
        channels report eof or when the deadline expires.
        """
        from salt.cluster.state_sync import (  # pylint: disable=import-outside-toplevel
            DEFAULT_RECEIVE_TIMEOUT,
            StateSyncSession,
        )

        if not hasattr(self, "_state_sync_sessions"):
            self._state_sync_sessions = {}

        if session_id in self._state_sync_sessions:
            log.warning(
                "Duplicate state-sync session id %s; ignoring second join-reply",
                session_id,
            )
            return

        completed_holder = {"done": False}

        def _on_complete():
            if completed_holder["done"]:
                return
            completed_holder["done"] = True
            try:
                self._start_raft_as_learner(known_peers)
            except Exception:  # pylint: disable=broad-except
                log.exception(
                    "state-sync %s: _start_raft_as_learner failed", session_id
                )
            if discover_event is not None:
                discover_event.set()
            # Cancel the watchdog if it hasn't fired yet.
            handle = session.watchdog_handle
            if handle is not None:
                try:
                    handle.cancel()
                except Exception:  # pylint: disable=broad-except
                    pass
            # Drop the session from the registry — keep memory bounded.
            self._state_sync_sessions.pop(session_id, None)

        session = StateSyncSession(session_id, _on_complete)
        # Stash the watchdog handle on the session so on_complete can
        # cancel it; created below.
        session.watchdog_handle = None
        self._state_sync_sessions[session_id] = session

        try:
            loop = asyncio.get_event_loop()
            session.watchdog_handle = loop.call_later(
                DEFAULT_RECEIVE_TIMEOUT, session.force_complete
            )
        except RuntimeError:
            # No running event loop in this context (defensive — the
            # join-reply handler runs inside ``_publish_daemon``'s loop,
            # so this branch should not execute in production).
            log.warning(
                "state-sync %s: no event loop for watchdog; running without timeout",
                session_id,
            )

    def _join_sentinel_path(self):
        """
        Return the path to the per-master join sentinel file.

        The filename is namespaced by the master's interface address so that
        deployments which share ``cachedir`` between cluster members (and the
        cluster integration tests, which point every master at the same
        ``cluster_cache_path``) keep distinct sentinels — without that, the
        first master to join writes ``.cluster_joined`` and every later
        master sees it on startup, takes the "rejoining" path, and skips
        the deterministic founding-voter election.
        """
        interface = self.opts.get("interface") or "unknown"
        return pathlib.Path(self.opts["cachedir"]) / f".cluster_joined.{interface}"

    def _has_joined_cluster(self):
        """
        Return True if this master has previously completed the cluster join
        handshake.  The sentinel is per-master (see :meth:`_join_sentinel_path`).
        """
        return self._join_sentinel_path().exists()

    def _mark_joined_cluster(self):
        """Write the join sentinel to signal that this master has joined."""
        sentinel = self._join_sentinel_path()
        try:
            sentinel.touch()
        except OSError as exc:
            log.warning("Could not write cluster join sentinel %s: %s", sentinel, exc)

    def discover_peers(self):
        """
        Send a ``cluster/peer/discover`` event to each configured peer.

        Called during master startup when this node has no Raft history (term=0,
        empty log), meaning it is joining an existing cluster for the first time.
        Existing peers will reply with ``cluster/peer/discover-reply``, which
        triggers the full join handshake and eventually ``cluster/peer/join-reply``
        received by ``handle_pool_publish``.
        """
        path = self.master_key.master_pub_path
        with salt.utils.files.fopen(path, "r") as fp:
            pub = fp.read()

        self._discover_token = self.gen_token()

        for peer in self.cluster_peers:
            log.info("Sending cluster discover to peer %s", peer)
            tosign = salt.payload.package(
                {
                    "peer_id": self.opts["id"],
                    "pub": pub,
                    "token": self._discover_token,
                }
            )
            key = salt.crypt.PrivateKeyString(self.private_key())
            sig = key.sign(tosign, algorithm=self.opts["publish_signing_algorithm"])
            data = {
                "sig": sig,
                "payload": tosign,
            }
            with salt.utils.event.get_master_event(
                self.opts, self.opts["sock_dir"], listen=False
            ) as event:
                success = event.fire_event(
                    data,
                    salt.utils.event.tagify("discover", "peer", "cluster"),
                    timeout=30000,
                )
                if not success:
                    log.error("Unable to send cluster discover event to %s", peer)

    def send_aes_key_event(self):
        log.debug("Sending AES key event")
        data = {"peer_id": self.opts["id"], "peers": {}}
        for peer in self.cluster_peers:
            peer_pub = (
                pathlib.Path(self.opts["cluster_pki_dir"]) / "peers" / f"{peer}.pub"
            )
            if peer_pub.exists():
                pub = salt.crypt.PublicKey.from_file(peer_pub)
                aes = salt.master.SMaster.secrets["aes"]["secret"].value
                digest = salt.utils.stringutils.to_bytes(
                    hashlib.sha256(aes).hexdigest()
                )
                data["peers"][peer] = {
                    "aes": pub.encrypt(
                        aes, algorithm=self.opts["cluster_encryption_algorithm"]
                    ),
                    "sig": self.master_key.master_key.encrypt(digest),
                }
            else:
                log.warning("Peer key missing %r", peer_pub)
                # request peer key
                data["peers"][peer] = {}
        with salt.utils.event.get_master_event(
            self.opts, self.opts["sock_dir"], listen=False
        ) as event:
            success = event.fire_event(
                data,
                salt.utils.event.tagify(self.opts["id"], "peer", "cluster"),
                timeout=30000,  # 30 second timeout
            )
            if not success:
                log.error("Unable to send aes key event")

    def __getstate__(self):
        return {
            "opts": self.opts,
            "transport": self.transport,
        }

    def __setstate__(self, state):
        self.opts = state["opts"]
        self.transport = state["transport"]
        self._discover_event = None
        self._raft_dispatcher = None
        self._raft_service = None

    def close(self):
        self.transport.close()

    def pre_fork(self, process_manager, *args, **kwargs):
        """
        Do anything necessary pre-fork. Since this is on the master side this will
        primarily be used to create IPC channels and create our daemon process to
        do the actual publishing

        :param func process_manager: A ProcessManager, from salt.utils.process.ProcessManager
        """
        if hasattr(self.transport, "publish_daemon"):
            proc_kwargs = kwargs.pop("kwargs", kwargs)
            process_manager.add_process(
                self._publish_daemon, kwargs=proc_kwargs, name="EventPublisher"
            )

    def _publish_daemon(self, **kwargs):
        """Clean implementation: separate local IPC from cluster peer communication."""
        import salt.master  # pylint: disable=import-outside-toplevel

        if (
            self.opts.get("event_publisher_niceness")
            and not salt.utils.platform.is_windows()
        ):
            log.info(
                "setting EventPublisher niceness to %i",
                self.opts["event_publisher_niceness"],
            )
            os.nice(self.opts["event_publisher_niceness"])

        self.io_loop = tornado.ioloop.IOLoop.current()

        # Always set up the local IPC-based event publisher first
        # This ensures internal processes (like pytest_engine) can communicate reliably
        if hasattr(self.transport, "publisher"):
            aio_loop = salt.utils.asynchronous.aioloop(self.io_loop)
            aio_loop.create_task(
                self.transport.publisher(
                    self.publish_payload,
                    io_loop=self.io_loop,
                )
            )

        # Initialize cluster peer state unconditionally so that non-cluster
        # masters also have an empty ``pushers`` list -- publish_payload
        # iterates ``self.pushers`` on every event.
        self.pushers = []

        # Cluster-specific peer communication (separate from local IPC)
        if self.opts.get("cluster_id"):
            self.tcp_master_pool_port = self.opts.get("cluster_port", 55596)
            self.auth_errors = collections.defaultdict(collections.deque)
            self.peer_map = {}

            for peer in self.opts.get("cluster_peers", []):
                host, port = peer.rsplit(":", 1) if ":" in peer else (peer, 55596)
                pusher = self.pusher(host, int(port))
                self.pushers.append(pusher)

            # Set up the cluster pool puller for incoming peer events
            self.pool_puller = salt.transport.tcp.TCPPuller(
                host=self.opts.get("interface", "127.0.0.1"),
                port=self.tcp_master_pool_port,
                io_loop=self.io_loop,
                payload_handler=self.handle_pool_publish,
            )
            self.pool_puller.start()

        # Start the Raft node when this master is part of a cluster.
        # A node without a cluster private key hasn't completed the join
        # handshake yet — defer Raft startup to _start_raft_as_learner, which
        # is called from handle_pool_publish when join-reply arrives.
        self._raft_service = None
        if self.opts.get("cluster_id") and self.opts.get("cluster_peers"):
            _is_new_node = not self._has_joined_cluster()

            if not _is_new_node:
                aio_loop = salt.utils.asynchronous.aioloop(self.io_loop)
                try:
                    from salt.cluster.consensus.service import (
                        RaftService,
                        build_peer_pushers,
                    )

                    peer_pushers = build_peer_pushers(self.opts, self.pushers)
                    self._raft_service = RaftService(
                        self.opts,
                        aio_loop,
                        peer_pushers,
                        on_ready=self._signal_cluster_ready,
                    )
                    self._raft_service.attach(self)
                    aio_loop.call_soon(self._raft_service.start)
                    log.info(
                        "Raft consensus service started for cluster %r",
                        self.opts["cluster_id"],
                    )
                except Exception:  # pylint: disable=broad-except
                    log.exception("Failed to start Raft consensus service")
            else:
                # Deterministic bootstrap: only the lowest interface address
                # in the configured cluster bootstraps as the founding
                # voter.  Every other master comes up as a learner via the
                # join-reply path.  This eliminates the race where several
                # masters' timers expire before they can exchange
                # join-replies and each one bootstraps its own single-member
                # cluster, leaving the cluster with multiple disjoint
                # leaders or — when join-replies land first — zero voters.
                bootstrap_pool = sorted(
                    {self.opts["interface"], *self.opts.get("cluster_peers", [])}
                )
                aio_loop_deferred = salt.utils.asynchronous.aioloop(self.io_loop)
                if bootstrap_pool and bootstrap_pool[0] == self.opts["interface"]:
                    log.info(
                        "New node bootstrapping cluster %r as designated founder",
                        self.opts["cluster_id"],
                    )
                    # The founder is the lowest-IP master and never runs
                    # discover (see ``salt.master.Master.start``), so no
                    # inbound join-reply can race this start-up.  Still
                    # delay by ``cluster_join_timeout`` before starting
                    # Raft so peer masters have time to bring up their
                    # cluster pool pullers — the very first ``pre-vote``
                    # the founder fires must reach at least one peer to
                    # form quorum, otherwise the node never re-arms its
                    # election timer.
                    _join_timeout = self.opts.get("cluster_join_timeout", 5)
                    aio_loop_deferred.call_later(
                        _join_timeout, self._start_raft_as_founding_voter
                    )
                else:
                    log.info(
                        "New node joining cluster %r — waiting for join-reply to start Raft as learner",
                        self.opts["cluster_id"],
                    )
        # run forever
        try:
            self.io_loop.start()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            if self._raft_service is not None:
                self._raft_service.stop()
            self.close()

    def _signal_cluster_ready(self):
        """
        Set the ``cluster_ready`` event in ``SMaster.secrets`` so that request
        workers know this node is a committed Raft voter and may serve traffic.

        Called exactly once by ``RaftService._on_membership_change`` when the
        founding or promotion CONFIG entry commits with this node in the voter set.

        Also writes the Kubernetes readiness sentinel so an exec probe
        can route traffic to this master.
        """
        import salt.cluster.healthchecks  # pylint: disable=import-outside-toplevel
        import salt.master  # pylint: disable=import-outside-toplevel

        entry = salt.master.SMaster.secrets.get("cluster_ready")
        if entry is not None:
            log.info("MasterPubServerChannel: cluster ready — opening request gate")
            entry["event"].set()
        salt.cluster.healthchecks.mark_cluster_ready(self.opts)

    def private_key(self):
        """
        The public key string associated with this node.
        """
        # XXX Do not read every time
        path = self.master_key.master_rsa_path
        with salt.utils.files.fopen(path, "r") as fp:
            return fp.read()

    def public_key(self):
        """
        The public key string associated with this node.
        """
        # XXX Do not read every time
        path = self.master_key.master_pub_path
        with salt.utils.files.fopen(path, "r") as fp:
            return fp.read()

    def cluster_key(self):
        """
        The private key associated with this cluster.
        """
        # XXX Do not read every time
        path = pathlib.Path(self.master_key.cluster_rsa_path)
        if path.exists():
            return path.read_text(encoding="utf-8")

    def cluster_public_key(self):
        """
        The private key associated with this cluster.
        """
        # XXX Do not read every time
        path = pathlib.Path(self.master_key.cluster_pub_path)
        if path.exists():
            return path.read_text(encoding="utf-8")

    def pusher(self, peer, port=None):
        if port is None:
            port = self.tcp_master_pool_port
        return salt.transport.tcp.PublishServer(
            self.opts,
            pull_host=peer,
            pull_port=port,
        )

    async def handle_pool_publish(self, payload):
        """
        Handle incoming events from cluster peer.
        """
        try:
            tag, data = salt.utils.event.SaltEvent.unpack(payload)
            if salt.cluster.consensus.rpc.is_raft_tag(tag):
                if self._raft_dispatcher is not None:
                    try:
                        _, src, rpc_id, rpc_payload = salt.cluster.consensus.rpc.unpack(
                            payload
                        )
                        await self._raft_dispatcher.dispatch(
                            tag, src, rpc_id, rpc_payload
                        )
                    except Exception:  # pylint: disable=broad-except
                        log.exception("Error dispatching Raft RPC tag %s", tag)
                else:
                    log.debug(
                        "Raft RPC received but dispatcher not initialised: %s", tag
                    )
                return
            log.debug("Incomming from peer %s %r", tag, data)
            if tag.startswith("cluster/peer/state-sync-chunk"):
                # Encrypted with the shared cluster_aes the joiner just
                # installed in the matching join-reply.  Each chunk
                # belongs to one of four channels; install items
                # in-order, mark eof when announced, and let the
                # session's ``on_complete`` fire ``_start_raft_as_learner``.
                try:
                    crypticle = salt.crypt.Crypticle(
                        self.opts,
                        salt.master.SMaster.secrets["cluster_aes"]["secret"].value,
                    )
                    chunk = crypticle.loads(data)
                except Exception:  # pylint: disable=broad-except
                    log.exception("Failed to decrypt state-sync-chunk")
                    return
                self._apply_state_sync_chunk(chunk)
                return
            if tag.startswith("cluster/peer/join-notify"):
                # join-notify is encrypted with the shared cluster AES key.
                try:
                    crypticle = salt.crypt.Crypticle(
                        self.opts,
                        salt.master.SMaster.secrets["cluster_aes"]["secret"].value,
                    )
                    notify = crypticle.loads(data)
                except Exception:  # pylint: disable=broad-except
                    log.exception("Failed to decrypt join-notify")
                    return
                log.info(
                    "Cluster join notify from %s for %s",
                    notify["peer_id"],
                    notify["join_peer_id"],
                )
                peer_pub = (
                    pathlib.Path(self.opts["cluster_pki_dir"])
                    / "peers"
                    / f"{notify['join_peer_id']}.pub"
                )
                # Match ``cluster/peer/join``: only create the file when missing.
                # Peer pubs are often mode 0400; reopening for write raises
                # ``PermissionError`` on peers that already received the key.
                if not peer_pub.exists():
                    with salt.utils.files.fopen(peer_pub, "w") as fp:
                        fp.write(notify["pub"])
                elif (
                    peer_pub.read_text(encoding="utf-8").strip()
                    != notify["pub"].strip()
                ):
                    log.warning(
                        "Cluster join-notify: peer %s pub on disk does not "
                        "match wire copy; keeping disk file.",
                        notify["join_peer_id"],
                    )
                # Tell the Raft service about the new peer so it can be added
                # as a learner and eventually promoted to voter.
                if self._raft_service is not None:
                    self._raft_service.notify_peer_joined(notify["join_peer_id"])
            elif tag.startswith("cluster/peer/join-reply"):
                # The join-reply carries a signed, packed inner payload.
                inner = salt.payload.loads(data["payload"])
                log.info("Cluster join reply from %s", inner.get("peer_id", "unknown"))
                # ``cluster_aes`` (the cluster's shared session AES key) is
                # encrypted to our master pub here so a joiner without access
                # to a shared ``cluster_pki_dir/.aes`` can adopt the cluster
                # session.  ``cluster.pem`` (cluster RSA private) is still
                # expected to be present locally — wire delivery for it is
                # tracked separately.
                token = self._discover_token or ""
                if isinstance(token, str):
                    token = token.encode()
                if "cluster_aes" in inner:
                    try:
                        salted = salt.crypt.PrivateKey.from_file(
                            self.master_key.master_rsa_path
                        ).decrypt(
                            inner["cluster_aes"],
                            algorithm=self.opts["cluster_encryption_algorithm"],
                        )
                        new_cluster_aes = salted[len(token) :]
                        with salt.master.SMaster.secrets["cluster_aes"][
                            "secret"
                        ].get_lock():
                            salt.master.SMaster.secrets["cluster_aes"][
                                "secret"
                            ].value = new_cluster_aes
                        # Persist locally so the joiner survives restart
                        # without re-running the join handshake.
                        aes_path = pathlib.Path(self.opts["cluster_pki_dir"]) / ".aes"
                        aes_path.parent.mkdir(parents=True, exist_ok=True)
                        with salt.utils.files.set_umask(0o177):
                            with salt.utils.files.fopen(aes_path, "wb") as fp:
                                fp.write(new_cluster_aes)
                        log.info(
                            "Installed cluster_aes from join-reply (%d bytes)",
                            len(new_cluster_aes),
                        )
                    except Exception:  # pylint: disable=broad-except
                        log.exception("Failed to install cluster_aes from join-reply")
                # Install the cluster RSA key pair (private + public) from
                # the wire so a joiner without shared ``cluster_pki_dir``
                # can sign cluster events and serve discover-reply.
                if "cluster_key_session" in inner and "cluster_pem" in inner:
                    try:
                        salted_session = salt.crypt.PrivateKey.from_file(
                            self.master_key.master_rsa_path
                        ).decrypt(
                            inner["cluster_key_session"],
                            algorithm=self.opts["cluster_encryption_algorithm"],
                        )
                        session_key_str = salted_session[len(token) :].decode()
                        cluster_key_crypt = salt.crypt.Crypticle(
                            self.opts, session_key_str
                        )
                        pem_bytes = cluster_key_crypt.decrypt(inner["cluster_pem"])
                        pub_pem = inner.get("cluster_pub") or ""
                        if isinstance(pub_pem, bytes):
                            pub_pem = pub_pem.decode()
                        cluster_pki = pathlib.Path(self.opts["cluster_pki_dir"])
                        cluster_pki.mkdir(parents=True, exist_ok=True)
                        # ``find_or_create_keys`` may have already written a
                        # locally-generated cluster.pem at mode 0400; unlink
                        # before writing so the wire-delivered version wins.
                        pem_path = cluster_pki / "cluster.pem"
                        pub_path = cluster_pki / "cluster.pub"
                        for p in (pem_path, pub_path):
                            try:
                                p.unlink()
                            except FileNotFoundError:
                                pass
                        with salt.utils.files.set_umask(0o277):
                            with salt.utils.files.fopen(pem_path, "wb") as fp:
                                fp.write(pem_bytes)
                        if pub_pem:
                            with salt.utils.files.fopen(pub_path, "w") as fp:
                                fp.write(pub_pem)
                        log.info(
                            "Installed cluster.pem (%d bytes) and cluster.pub from join-reply",
                            len(pem_bytes),
                        )
                    except Exception:  # pylint: disable=broad-except
                        log.exception(
                            "Failed to install cluster RSA key pair from join-reply"
                        )
                event = self._discover_event
                self._discover_event = None
                # Write the join sentinel so future restarts skip discover/join.
                self._mark_joined_cluster()
                # Paged bulk state-sync: the join-reply names a session id
                # and the responder follows up with chunked
                # ``cluster/peer/state-sync-chunk`` events, four channels
                # in parallel (keys, denied_keys, file_roots, pillar_roots).
                # Defer the Raft-learner start until all four channels eof
                # (or the per-session deadline elapses).
                known_peers = {p: inner["peers"][p] for p in inner.get("peers", {})}
                state_sync_session = inner.get("state_sync_session")
                if state_sync_session and self.opts.get("cluster_isolated_filesystem"):
                    self._begin_state_sync_session(
                        state_sync_session, known_peers, event
                    )
                else:
                    # Either the responder isn't running with isolated-FS
                    # mode or the session announcement is missing.  Fall
                    # back to immediate learner start; event-driven
                    # replication will fill any gaps.
                    self._start_raft_as_learner(known_peers)
                    if event is not None:
                        event.set()
            elif tag.startswith("cluster/peer/join"):

                payload = salt.payload.loads(data["payload"])

                pub, token = self._discover_candidates[payload["peer_id"]]

                if payload["pub"] != pub:
                    log.warning("Cluster join, peer public keys do not match")
                    return
                if payload["return_token"] != token:
                    log.warning("Cluster join, token does not not match")
                    return
                pubk = salt.crypt.PublicKeyString(payload["pub"])
                if not pubk.verify(
                    data["payload"],
                    data["sig"],
                    algorithm=self.opts["publish_signing_algorithm"],
                ):
                    log.warning("Cluster join signature invalid.")
                    return

                log.info("Cluster join from %s", payload["peer_id"])
                salted_secret = (
                    salt.crypt.PrivateKey.from_file(self.master_key.master_rsa_path)
                    .decrypt(
                        payload["secret"],
                        algorithm=self.opts["cluster_encryption_algorithm"],
                    )
                    .decode()
                )

                secret = salted_secret[len(token) :]

                if secret != (self.opts.get("cluster_secret") or ""):
                    log.warning("Cluster secret invalid.")
                    return

                log.info("Peer %s joined cluster", payload["peer_id"])
                salted_aes = (
                    salt.crypt.PrivateKey.from_file(self.master_key.master_rsa_path)
                    .decrypt(
                        payload["key"],
                        algorithm=self.opts["cluster_encryption_algorithm"],
                    )
                    .decode()
                )

                aes_key = salted_aes[len(token) :]

                # XXX needs safe join
                peer_pub = (
                    pathlib.Path(self.opts["cluster_pki_dir"])
                    / "peers"
                    / f"{payload['peer_id']}.pub"
                )
                # For statically-configured peers the pub key is already on
                # disk with restrictive perms. Only write when missing.
                if not peer_pub.exists():
                    with salt.utils.files.fopen(peer_pub, "w") as fp:
                        fp.write(payload["pub"])
                elif (
                    peer_pub.read_text(encoding="utf-8").strip()
                    != payload["pub"].strip()
                ):
                    log.warning(
                        "Cluster peer %s pub key on disk does not match the "
                        "key received during join; keeping disk copy.",
                        payload["peer_id"],
                    )

                self.cluster_peers.append(payload["peer_id"])
                self.pushers.append(self.pusher(payload["peer_id"]))

                # Add the joining peer to our own Raft state as a learner.
                # The join-notify broadcast below tells *other* peers about
                # the new node, but the receiver of the join request never
                # sees its own broadcast — without this call the leader
                # learned about its peers via cluster_peers but never began
                # replicating to a freshly joined master, so promotion to
                # voter (and the joiner's gate opening) stalled.
                if self._raft_service is not None:
                    try:
                        self._raft_service.notify_peer_joined(payload["peer_id"])
                    except Exception:  # pylint: disable=broad-except
                        log.exception(
                            "RaftService.notify_peer_joined failed for %s",
                            payload["peer_id"],
                        )

                for pusher in self.pushers:
                    # XXX Send new peer id and public key to other nodes
                    # XXX This needs to be able to be validated by receiveing peers
                    # XXX Send other nodes pub (and aes?) keys to new node
                    # Use the cluster-wide AES key so all members can decrypt.
                    crypticle = salt.crypt.Crypticle(
                        self.opts,
                        salt.master.SMaster.secrets["cluster_aes"]["secret"].value,
                    )
                    event_data = salt.utils.event.SaltEvent.pack(
                        salt.utils.event.tagify("join-notify", "peer", "cluster"),
                        crypticle.dumps(
                            {
                                "peer_id": self.opts["id"],
                                "join_peer_id": payload["peer_id"],
                                "pub": payload["pub"],
                                "aes": aes_key,
                            }
                        ),
                    )

                    # XXX gather tasks instead of looping
                    try:
                        await pusher.publish(event_data)
                    except Exception as exc:  # pylint: disable=broad-except
                        log.warning(
                            "Unable to publish join-notify to peer %s:%s: %s",
                            pusher.pull_host,
                            pusher.pull_port,
                            exc,
                        )

                # XXX Kick off minoins key repair

                self.send_aes_key_event()

                joiner_pub = salt.crypt.PublicKeyString(payload["pub"])
                token_bytes = (
                    payload["token"].encode()
                    if isinstance(payload["token"], str)
                    else payload["token"]
                )
                aes_secret = salt.master.SMaster.secrets["aes"]["secret"].value
                if isinstance(aes_secret, str):
                    aes_secret = aes_secret.encode()
                cluster_aes_secret = salt.master.SMaster.secrets["cluster_aes"][
                    "secret"
                ].value
                if isinstance(cluster_aes_secret, str):
                    cluster_aes_secret = cluster_aes_secret.encode()
                # No-shared-filesystem support: the join-reply carries
                # ``cluster_aes`` and the cluster RSA key pair so a joiner
                # without access to a shared ``cluster_pki_dir`` can adopt
                # the cluster identity from the wire alone.
                #
                # ``cluster.pem`` is too large for direct RSA encryption, so
                # it travels under a fresh Crypticle session key wrapped to
                # the joiner's RSA pub.  ``cluster.pub`` is not secret so it
                # rides in the inner payload unencrypted (and the inner
                # payload is signed with this master's private key).
                cluster_pem_pem = self.cluster_key() or ""
                cluster_pub_pem = self.cluster_public_key() or ""
                cluster_key_session = salt.crypt.Crypticle.generate_key_string()
                cluster_key_crypt = salt.crypt.Crypticle(self.opts, cluster_key_session)
                cluster_pem_ciphertext = cluster_key_crypt.encrypt(
                    cluster_pem_pem.encode()
                )
                wrapped_session = joiner_pub.encrypt(
                    token_bytes + cluster_key_session.encode(),
                    algorithm=self.opts["cluster_encryption_algorithm"],
                )
                inner_payload = {
                    "return_token": payload["token"],
                    "peer_id": self.opts["id"],
                    "aes": joiner_pub.encrypt(
                        token_bytes + aes_secret,
                        algorithm=self.opts["cluster_encryption_algorithm"],
                    ),
                    "cluster_aes": joiner_pub.encrypt(
                        token_bytes + cluster_aes_secret,
                        algorithm=self.opts["cluster_encryption_algorithm"],
                    ),
                    "cluster_key_session": wrapped_session,
                    "cluster_pem": cluster_pem_ciphertext,
                    "cluster_pub": cluster_pub_pem,
                    "peers": {},
                }
                # Isolated-FS bulk state sync: announce a session id in the
                # join-reply, then push the per-channel chunks separately.
                # The joiner waits on all four channel eofs before becoming
                # a Raft learner; per-channel chunking lets each stream
                # progress independently and isolates failures.
                state_sync_session_id = None
                if self.opts.get("cluster_isolated_filesystem"):
                    from salt.cluster.state_sync import (  # pylint: disable=import-outside-toplevel
                        new_session_id,
                    )

                    state_sync_session_id = new_session_id()
                    inner_payload["state_sync_session"] = state_sync_session_id
                tosign = salt.payload.package(inner_payload)
                sig = salt.crypt.PrivateKeyString(self.private_key()).sign(
                    tosign, algorithm=self.opts["publish_signing_algorithm"]
                )
                event_data = salt.utils.event.SaltEvent.pack(
                    salt.utils.event.tagify("join-reply", "peer", "cluster"),
                    {
                        "sig": sig,
                        "payload": tosign,
                    },
                )
                await self.pusher(payload["peer_id"]).publish(event_data)
                if state_sync_session_id is not None:
                    asyncio.get_event_loop().create_task(
                        self._send_state_sync_chunks(
                            state_sync_session_id, payload["peer_id"]
                        )
                    )
            elif tag.startswith("cluster/peer/discover-reply"):
                payload = salt.payload.loads(data["payload"])

                if not cluster_pub_matches_fingerprint(
                    self.opts, payload["cluster_pub"]
                ):
                    log.warning(
                        "cluster_pub fingerprint mismatch in discover-reply "
                        "from %s; rejecting",
                        payload.get("peer_id"),
                    )
                    return

                cluster_pub = salt.crypt.PublicKeyString(payload["cluster_pub"])
                if not cluster_pub.verify(
                    data["payload"],
                    data["sig"],
                    algorithm=self.opts["publish_signing_algorithm"],
                ):
                    log.warning("Invalid signature of cluster discover payload")
                    return

                # XXX First token created in different process
                # if payload.get("return_token", None) != self._discover_token:
                #    log.warning("Invalid token in discover reply %s != %s",
                #        payload.get("return_token", None), self._discover_token
                #    )
                #    return

                log.info("Cluster discover reply from %s", payload["peer_id"])
                key = salt.crypt.PublicKeyString(payload["pub"])
                self._discover_token = self.gen_token()
                tosign = salt.payload.package(
                    {
                        "return_token": payload["token"],
                        "token": self._discover_token,
                        "peer_id": self.opts["id"],
                        "secret": key.encrypt(
                            payload["token"].encode()
                            + (self.opts.get("cluster_secret") or "").encode(),
                            algorithm=self.opts["cluster_encryption_algorithm"],
                        ),
                        "key": key.encrypt(
                            payload["token"].encode()
                            + salt.master.SMaster.secrets["aes"]["secret"].value,
                            algorithm=self.opts["cluster_encryption_algorithm"],
                        ),
                        "pub": self.public_key(),
                    }
                )
                sig = salt.crypt.PrivateKeyString(self.private_key()).sign(
                    tosign, algorithm=self.opts["publish_signing_algorithm"]
                )
                self.cluster_peers.append(payload["peer_id"])
                event_data = salt.utils.event.SaltEvent.pack(
                    salt.utils.event.tagify("join", "peer", "cluster"),
                    {"sig": sig, "payload": tosign},
                )
                peer_pub = (
                    pathlib.Path(self.opts["cluster_pki_dir"])
                    / "peers"
                    / f"{payload['peer_id']}.pub"
                )
                # For statically-configured peers the pub key is already on
                # disk with restrictive perms (0400). Only write when it is
                # missing, otherwise verify the key on disk matches.
                if not peer_pub.exists():
                    with salt.utils.files.fopen(peer_pub, "w") as fp:
                        fp.write(payload["pub"])
                else:
                    existing = peer_pub.read_text(encoding="utf-8")
                    if existing.strip() != payload["pub"].strip():
                        log.warning(
                            "Cluster peer %s pub key on disk does not match "
                            "the key received during discovery; keeping disk "
                            "copy.",
                            payload["peer_id"],
                        )
                pusher = self.pusher(payload["peer_id"])
                self.pushers.append(pusher)
                try:
                    await pusher.publish(event_data)
                except Exception as exc:  # pylint: disable=broad-except
                    log.warning(
                        "Unable to publish join to peer %s:%s: %s",
                        pusher.pull_host,
                        pusher.pull_port,
                        exc,
                    )
            elif tag.startswith("cluster/peer/discover"):
                payload = salt.payload.loads(data["payload"])
                peer_key = salt.crypt.PublicKeyString(payload["pub"])
                if not peer_key.verify(
                    data["payload"],
                    data["sig"],
                    algorithm=self.opts["publish_signing_algorithm"],
                ):
                    log.warning("Invalid signature of cluster discover payload")
                    return
                log.info("Cluster discovery from %s", payload["peer_id"])
                token = self.gen_token()
                # Store this peer as a candidate.
                # XXX Add timestamp so we can clean up old candidates
                self._discover_candidates[payload["peer_id"]] = (payload["pub"], token)
                tosign = salt.payload.package(
                    {
                        "return_token": payload["token"],
                        "token": token,
                        "peer_id": self.opts["id"],
                        "pub": self.public_key(),
                        "cluster_pub": self.cluster_public_key(),
                    }
                )
                key = salt.crypt.PrivateKeyString(self.cluster_key())
                sig = key.sign(tosign, algorithm=self.opts["publish_signing_algorithm"])
                _ = salt.payload.package(
                    {
                        "sig": sig,
                        "payload": tosign,
                    }
                )
                event_data = salt.utils.event.SaltEvent.pack(
                    salt.utils.event.tagify("discover-reply", "peer", "cluster"),
                    {"sig": sig, "payload": tosign},
                )
                await self.pusher(payload["peer_id"]).publish(event_data)
            elif tag.startswith("cluster/peer"):
                peer = data["peer_id"]
                if peer == self.opts["id"]:
                    log.debug("Skip our own cluster peer event %s", tag)
                    return
                aes = data["peers"][self.opts["id"]]["aes"]
                sig = data["peers"][self.opts["id"]]["sig"]
                key_str = self.master_key.master_key.decrypt(
                    aes, algorithm=self.opts["cluster_encryption_algorithm"]
                )
                digest = salt.utils.stringutils.to_bytes(
                    hashlib.sha256(key_str).hexdigest()
                )
                key = self.master_key.fetch(f"peers/{peer}.pub")
                m_digest = key.decrypt(sig)
                if m_digest != digest:
                    log.error("Invalid aes signature from peer: %s", peer)
                    return
                log.info("Received new AES key from peer %s", peer)
                if peer in self.peer_keys:
                    if self.peer_keys[peer] != key_str:
                        self.peer_keys[peer] = key_str
                        self.send_aes_key_event()
                        while self.auth_errors[peer]:
                            key, data = self.auth_errors[peer].popleft()
                            peer_id, parsed_tag = self.parse_cluster_tag(tag)
                            try:
                                event_data = self.extract_cluster_event(peer_id, data)
                            except salt.exceptions.AuthenticationError:
                                log.error(
                                    "Event from peer failed authentication: %s", peer_id
                                )
                            else:
                                await self.transport.publish_payload(
                                    salt.utils.event.SaltEvent.pack(
                                        parsed_tag, event_data
                                    )
                                )
                else:
                    self.peer_keys[peer] = key_str
                    self.send_aes_key_event()
                    while self.auth_errors[peer]:
                        key, data = self.auth_errors[peer].popleft()
                        peer_id, parsed_tag = self.parse_cluster_tag(tag)
                        try:
                            event_data = self.extract_cluster_event(peer_id, data)
                        except salt.exceptions.AuthenticationError:
                            log.error(
                                "Event from peer failed authentication: %s", peer_id
                            )
                        else:
                            await self.transport.publish_payload(
                                salt.utils.event.SaltEvent.pack(parsed_tag, event_data)
                            )
            elif tag.startswith("cluster/event"):
                peer_id, parsed_tag = self.parse_cluster_tag(tag)
                try:
                    event_data = self.extract_cluster_event(peer_id, data)
                except salt.exceptions.AuthenticationError:
                    self.auth_errors[peer_id].append((tag, data))
                else:
                    await self.transport.publish_payload(
                        salt.utils.event.SaltEvent.pack(parsed_tag, event_data)
                    )
            else:
                log.error("This cluster tag not valid %s", tag)
        except Exception:  # pylint: disable=broad-except
            log.critical("Unhandled error while polling master events", exc_info=True)
            return None

    def parse_cluster_tag(self, tag):
        peer_id = tag.replace("cluster/event/", "").split("/")[0]
        stripped_tag = tag.replace(f"cluster/event/{peer_id}/", "")
        return peer_id, stripped_tag

    def extract_cluster_event(self, peer_id, data):
        if peer_id in self.peer_keys:
            crypticle = _get_crypticle(self.opts, self.peer_keys[peer_id])
            event_data = crypticle.loads(data)["event_payload"]
            # __peer_id can be used to know if this event came from a
            # different master.
            event_data["__peer_id"] = peer_id
            return event_data
        raise salt.exceptions.AuthenticationError("Peer aes key not available")

    async def publish_payload(self, load, *args):
        tag, data = salt.utils.event.SaltEvent.unpack(load)
        # log.warning("Event %s %s %r", len(self.pushers), tag, data)
        tasks = []
        if not tag.startswith("cluster/peer"):
            tasks = [
                asyncio.create_task(
                    self.transport.publish_payload(load), name=self.opts["id"]
                )
            ]
        for pusher in self.pushers:
            log.info("Publish event to peer %s:%s", pusher.pull_host, pusher.pull_port)
            if tag.startswith("cluster/peer"):
                # log.info("Send %s %r", tag, load)
                tasks.append(
                    asyncio.create_task(pusher.publish(load), name=pusher.pull_host)
                )
                continue
            crypticle = _get_crypticle(
                self.opts, salt.master.SMaster.secrets["aes"]["secret"].value
            )
            load = {"event_payload": data}
            event_data = salt.utils.event.SaltEvent.pack(
                salt.utils.event.tagify(tag, self.opts["id"], "cluster/event"),
                crypticle.dumps(load),
            )
            tasks.append(asyncio.create_task(pusher.publish(event_data)))
        await asyncio.gather(*tasks, return_exceptions=True)
        for task in tasks:
            try:
                task.result()
            # XXX This error is transport specific and should be something else
            except tornado.iostream.StreamClosedError:
                if task.get_name() == self.opts["id"]:
                    log.error("Unable to forward event to local ipc bus")
                else:
                    peer = task.get_name()
                    log.warning(
                        "Unable to forward event to cluster peer %s; "
                        "resetting pusher for reconnect",
                        peer,
                    )
                    # Reset the broken pub_sock so the next publish attempt
                    # triggers a fresh TCP connection rather than reusing a
                    # dead stream.
                    for pusher in self.pushers:
                        if pusher.pull_host == peer and pusher.pub_sock is not None:
                            try:
                                pusher.pub_sock.close()
                            except Exception:  # pylint: disable=broad-except
                                pass
                            pusher.pub_sock = None
                    # Schedule an AES-key re-announcement so the peer
                    # learns our key after it reconnects.
                    self.io_loop.call_later(2.0, self.send_aes_key_event)
            except Exception as exc:  # pylint: disable=broad-except
                log.error(
                    "Unhandled error sending task %s", task.get_name(), exc_info=True
                )
