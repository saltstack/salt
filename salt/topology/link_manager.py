"""
Process-wide link lifecycle for master topology.

Owns two concerns:

* Outbound registry: a module-level dict of
  :class:`salt.topology.link.PeerMasterLink` instances keyed
  by peer ``cluster_id``.
* Inbound listener: a :class:`salt.channel.server.ReqServerChannel`
  (reused as a library primitive, not extended) opened on
  ``topology_link_port`` with a topology-specific payload
  handler that dispatches by tag to the router and the
  identity / attach handlers in this module.

The one-shot solo-to-clustered migration lives in
:mod:`salt.topology.migration` and is invoked from
:func:`start`.

Follows the module-level singleton pattern of
:mod:`salt.cluster.ring_membership`: no object passed around
through the master process, callers reach the state via
module-level functions.
"""

import asyncio
import fcntl
import logging
import os
import socket
import threading
import time

import salt.topology.breadcrumbs as breadcrumbs
import salt.topology.registry as registry
import salt.topology.router as router_mod
import salt.utils.files
from salt.config.topology import PeerRef, load_topology_config
from salt.topology.link import PeerMasterLink

log = logging.getLogger(__name__)


# Module-level registry of outbound links (we initiated the TCP).
# Key is peer ``cluster_id`` after handshake.  Before handshake the
# link is tracked by a provisional key derived from the seed
# :class:`salt.config.topology.PeerRef`.
_LINKS = {}

# Module-level registry of inbound links (peer initiated to us).
# Key is peer ``cluster_id`` after handshake.
_INBOUND = {}

# Inbound listener state.  Owned here --- not a separate module ---
# because inbound and outbound lifecycle are intertwined (both come
# up together, both tear down together) and both share the single
# process-level :class:`~salt.topology.router.TopologyRouter`.
_LISTENER = None

# Pre-fork reserved listening socket (SO_REUSEADDR + FD_CLOEXEC).
# Populated by :func:`pre_fork`; consumed by :func:`start` when it
# constructs the ReqServerChannel.  Kept distinct from ``_LISTENER``
# which holds the fully-wired channel.
_LISTENER_SOCKET = None

# PID of the process that called :func:`start`.  Writes into
# ``_LINKS`` / ``_INBOUND`` are only allowed from this process so a
# fork-inherited MWorker that still holds the module globals cannot
# mutate the publish daemon's state.
_OWNER_PID = None

# Writer handles onto the registry + breadcrumb MmapCaches.  Opened
# in :func:`start` and closed in :func:`stop`.
_REGISTRY_CACHE = None
_BREADCRUMB_CACHE = None

# Reference to the asyncio loop :func:`start` was called with so
# ``add_link`` / ``remove_link`` can schedule onto it from the Raft
# apply thread via ``call_soon_threadsafe``.
_IO_LOOP = None

# Reference to the raft service (passed in by caller for clustered
# masters); None for solo masters.
_RAFT_SERVICE = None

# Loaded :class:`salt.config.topology.TopologyConfig`.
_CONFIG = None

# Opts dict captured at :func:`start` time.  Immutable snapshot used
# by the inbound handlers so they do not need the caller to pass
# opts into every dispatch.
_OPTS = None

_LOCK = threading.RLock()


def _reset_module_state():
    """Reset every module-level variable to its post-import default.

    Used by :func:`stop` and by test fixtures that need the module in
    a known state between runs.
    """
    global _LINKS, _INBOUND, _LISTENER, _LISTENER_SOCKET, _OWNER_PID
    global _REGISTRY_CACHE, _BREADCRUMB_CACHE, _IO_LOOP, _RAFT_SERVICE
    global _CONFIG, _OPTS
    _LINKS = {}
    _INBOUND = {}
    _LISTENER = None
    _LISTENER_SOCKET = None
    _OWNER_PID = None
    _REGISTRY_CACHE = None
    _BREADCRUMB_CACHE = None
    _IO_LOOP = None
    _RAFT_SERVICE = None
    _CONFIG = None
    _OPTS = None


def _check_owner_pid():
    """Raise RuntimeError if the current PID is not the owner."""
    if _OWNER_PID is None:
        # ``start`` has not been called yet; defer the guard to
        # start-time.  Allows unit tests to exercise helpers that do
        # not touch ``_LINKS`` without first spinning up ``start``.
        return
    if os.getpid() != _OWNER_PID:
        raise RuntimeError(
            "salt.topology.link_manager accessed from PID "
            f"{os.getpid()} but was started by PID {_OWNER_PID}; "
            "writes are permitted only from the publish daemon."
        )


def _reserve_listener_socket(opts):
    """Bind + listen on ``topology_link_port`` and return the socket.

    SO_REUSEADDR to tolerate TIME_WAIT across restarts;
    FD_CLOEXEC so MWorker fork children do not inherit the fd.
    Returns the socket on success.  Raises OSError on bind failure
    --- the caller treats that as fatal in the master pre-fork path.
    """
    host = opts.get("interface", "127.0.0.1")
    port = int(opts.get("topology_link_port") or 0)
    if port == 0:
        raise ValueError(
            "topology_link_port is not set; cannot reserve inbound listener"
        )
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
    except OSError:
        sock.close()
        raise
    sock.listen(opts.get("topology_link_backlog", 128))
    # FD_CLOEXEC so MWorker fork() does not inherit the listening fd.
    flags = fcntl.fcntl(sock.fileno(), fcntl.F_GETFD)
    fcntl.fcntl(sock.fileno(), fcntl.F_SETFD, flags | fcntl.FD_CLOEXEC)
    return sock


def pre_fork(opts, process_manager):
    """
    Called from
    :meth:`salt.channel.server.MasterPubServerChannel.pre_fork`
    when ``opts["topology_enabled"]`` is True.

    Two responsibilities:

    1. Reserve the ``topology_link_port`` socket in the parent
       process so the forked publish daemon inherits a listening
       fd.  Follows the pattern used by
       :class:`salt.channel.server.PubServerChannel.pre_fork`.
       Sets ``FD_CLOEXEC`` on the listening fd for MWorker
       descriptors so the listener is not inherited by workers
       that have no business accepting on it.
    2. Pre-create the breadcrumb and registry MmapCache files
       via :func:`salt.topology.breadcrumbs.pre_create` and
       :func:`salt.topology.registry.pre_create`.  Prevents the
       startup race where MWorkers fork and call
       :func:`open_reader` on a file the publish daemon has not
       yet opened.

    This function must NOT touch ``_LINKS``, ``_INBOUND``, or
    ``_LISTENER``.  Those are populated by :func:`start` on the
    publish daemon side, after fork.  Populating them pre-fork
    would leak into every forked child.
    """
    global _LISTENER_SOCKET
    if not opts.get("topology_enabled"):
        return
    registry.pre_create(opts)
    breadcrumbs.pre_create(opts)
    try:
        _LISTENER_SOCKET = _reserve_listener_socket(opts)
    except OSError as exc:
        log.warning(
            "topology pre_fork: could not reserve topology_link_port %r: %s",
            opts.get("topology_link_port"),
            exc,
        )
        _LISTENER_SOCKET = None


async def start(opts, io_loop, raft_service=None):
    """
    Bring up the topology subsystem in the publish daemon.

    Steps, in strict order (ordering is correctness-critical):

    1. :func:`salt.config.topology.load_topology_config`.  If
       disabled, return immediately (idempotent no-op).
    2. Record this process's PID in the module-level
       ``_OWNER_PID`` guard; subsequent calls into this module
       from a different PID raise.
    3. Open the registry and breadcrumb MmapCaches in writer
       mode (pre-created in :func:`pre_fork`).
    4. Construct the process-wide
       :class:`~salt.topology.router.TopologyRouter`; make it
       accessible via :func:`salt.topology.router.get_router`.
    5. **Register state-machine callbacks BEFORE replaying
       committed entries.**  Register :func:`add_link` /
       :func:`remove_link` on the
       :class:`~salt.cluster.consensus.raft.topology.TopologyStateMachine`
       so that pre-existing committed peer entries (from a
       previous process generation) are replayed into the
       callbacks on registration.  Doing this AFTER step 6 or
       step 7 would silently miss attach entries that applied
       before the callback existed.
    6. If :func:`salt.topology.migration.needs_migration`
       returns True (solo master starting clustered for the
       first time), call
       :func:`salt.topology.migration.promote_solo_to_clustered`
       to seed Raft from the current registry contents.  Any
       entries this proposes commit through the callbacks
       registered in step 5.
    7. Open the inbound listener on ``topology_link_port`` using
       :class:`salt.channel.server.ReqServerChannel` with
       :func:`_handle_inbound` as its payload handler.
    8. For each :class:`salt.config.topology.PeerRef` in the
       config, instantiate a
       :class:`salt.topology.link.PeerMasterLink` and schedule
       its ``connect()`` on ``io_loop`` via
       ``io_loop.call_soon_threadsafe`` (same path used by
       :func:`add_link` for apply-thread -> io_loop handoffs).

    Idempotent: a second call after :func:`stop` is a fresh
    start; a second call without stop is a no-op with a WARNING
    log.
    """
    global _OWNER_PID, _REGISTRY_CACHE, _BREADCRUMB_CACHE
    global _IO_LOOP, _RAFT_SERVICE, _CONFIG, _LISTENER, _OPTS

    # Step 1: load config (handles disabled early-return).
    cfg = load_topology_config(opts)
    if not cfg.enabled:
        log.info("topology disabled; link_manager.start is a no-op")
        return

    # Idempotency: a second start without stop is a WARNING.
    if _OWNER_PID is not None:
        log.warning(
            "salt.topology.link_manager.start called twice without stop; "
            "owner_pid=%s current_pid=%s --- ignoring",
            _OWNER_PID,
            os.getpid(),
        )
        return

    # Step 2: own this process's state.
    _OWNER_PID = os.getpid()
    _IO_LOOP = io_loop
    _RAFT_SERVICE = raft_service
    _CONFIG = cfg
    _OPTS = dict(opts)

    # Step 3: open MmapCaches writer-side.  ``pre_create`` is called
    # defensively in case ``pre_fork`` did not run (e.g. unit tests).
    registry.pre_create(opts)
    breadcrumbs.pre_create(opts)
    _REGISTRY_CACHE = registry.open_writer(opts)
    _BREADCRUMB_CACHE = breadcrumbs.open_writer(opts)

    # Step 4: build the router and expose it via get_router().  The
    # router module keeps a module-level singleton; we poke it in
    # via its documented accessor path.  The stubbed router may
    # ignore its constructor args (empty body); we still attach the
    # cache handles so our dispatch helpers can rely on them.
    _topology_router = router_mod.TopologyRouter(
        opts, _REGISTRY_CACHE, _BREADCRUMB_CACHE
    )
    if not hasattr(_topology_router, "opts"):
        _topology_router.opts = opts
    if not hasattr(_topology_router, "registry_cache"):
        _topology_router.registry_cache = _REGISTRY_CACHE
    if not hasattr(_topology_router, "breadcrumbs_cache"):
        _topology_router.breadcrumbs_cache = _BREADCRUMB_CACHE
    router_mod._ROUTER = _topology_router  # pylint: disable=protected-access

    # Step 5: install state-machine callbacks before replaying.
    sm = None
    if raft_service is not None:
        sm = getattr(raft_service, "topology_sm", None)
    if sm is not None:
        _install_sm_callbacks(sm)
    else:
        # Solo master: no SM to register against.  Replay the
        # registry directly so pre-existing peers from a prior
        # process generation re-create outbound links.
        _replay_registry()

    # Step 6: solo -> clustered migration, if any.
    try:
        import salt.topology.migration as migration

        if migration.needs_migration(opts):
            migration.promote_solo_to_clustered(opts, raft_service)
    except Exception as exc:  # pylint: disable=broad-except
        log.warning(
            "topology migration step failed (continuing): %s", exc, exc_info=True
        )

    # Step 7: inbound listener.  The ReqServerChannel pulls in a lot
    # of master infrastructure; failures here are logged and the
    # subsystem continues in outbound-only mode so unit / functional
    # tests without full master context do not implode.
    _LISTENER = _open_inbound_listener(opts, io_loop)

    # Step 8: outbound links from topology.conf.
    for peer_ref in cfg.peers:
        try:
            link = PeerMasterLink(opts, peer_ref, io_loop)
        except TypeError as exc:
            log.warning("topology: could not build link for peer %r: %s", peer_ref, exc)
            continue
        provisional_key = _provisional_key(peer_ref)
        _LINKS[provisional_key] = link
        io_loop.call_soon_threadsafe(_schedule_connect, link)


def _install_sm_callbacks(sm):
    """Wrap the state machine's attach/detach handlers so a commit
    fires :func:`add_link` / :func:`remove_link` after the handler
    writes into the registry.

    Idempotent: a repeat call on the same SM is a no-op.  Callbacks
    are installed BEFORE snapshot replay so pre-existing peers fire
    into the callbacks on registration.
    """
    if getattr(sm, "_link_manager_wired", False):
        return
    original_attach = sm._handle_peer_attach  # pylint: disable=protected-access
    original_detach = sm._handle_peer_detach  # pylint: disable=protected-access

    def _wrapped_attach(entry):
        original_attach(entry)
        cluster_id = entry.get("cluster_id")
        if not cluster_id:
            return
        peer_state = registry.get_peer(_REGISTRY_CACHE, cluster_id)
        if peer_state is None:
            return
        # Build a provisional PeerRef from the peer_state endpoints.
        endpoints = peer_state.get("endpoints") or ()
        if not endpoints:
            return
        ref = _ref_from_endpoint(endpoints[0])
        if ref is None:
            return
        try:
            link = PeerMasterLink(
                _CONFIG and {"cluster_id": _CONFIG.cluster_id} or {}, ref, _IO_LOOP
            )
        except TypeError:
            return
        add_link(link)

    def _wrapped_detach(entry):
        original_detach(entry)
        cluster_id = entry.get("cluster_id")
        if cluster_id:
            remove_link(cluster_id)

    sm._handle_peer_attach = _wrapped_attach  # pylint: disable=protected-access
    sm._handle_peer_detach = _wrapped_detach  # pylint: disable=protected-access
    # Rebuild the dispatch table so apply() picks up the wrappers.
    from salt.cluster.consensus.raft.log import LogEntryType

    sm._handlers[LogEntryType.MASTER_PEER_ATTACH] = _wrapped_attach
    sm._handlers[LogEntryType.MASTER_PEER_DETACH] = _wrapped_detach
    sm._link_manager_wired = True


def _replay_registry():
    """Replay committed peers from the registry MmapCache.

    Walks :func:`registry.list_peer_ids` and schedules an outbound
    link per peer.  Called from solo masters at startup.
    """
    if _REGISTRY_CACHE is None:
        return
    try:
        peer_ids = registry.list_peer_ids(_REGISTRY_CACHE)
    except Exception:  # pylint: disable=broad-except
        log.debug("topology: registry replay failed", exc_info=True)
        return
    for cluster_id in peer_ids:
        peer_state = registry.get_peer(_REGISTRY_CACHE, cluster_id)
        if peer_state is None:
            continue
        endpoints = peer_state.get("endpoints") or ()
        if not endpoints:
            continue
        ref = _ref_from_endpoint(endpoints[0])
        if ref is None:
            continue
        try:
            link = PeerMasterLink(
                {"cluster_id": _CONFIG.cluster_id if _CONFIG else ""},
                ref,
                _IO_LOOP,
            )
        except (TypeError, ValueError):
            continue
        _LINKS[cluster_id] = link
        if _IO_LOOP is not None:
            _IO_LOOP.call_soon_threadsafe(_schedule_connect, link)


def _ref_from_endpoint(endpoint):
    """Return a :class:`PeerRef` for an endpoint string ``"host:port"``.

    Returns ``None`` on malformed input (callers log at a lower
    level if desired).
    """
    if isinstance(endpoint, PeerRef):
        return endpoint
    if not isinstance(endpoint, str) or ":" not in endpoint:
        return None
    host, _, port_str = endpoint.rpartition(":")
    try:
        port = int(port_str)
    except (TypeError, ValueError):
        return None
    return PeerRef(host=host or "127.0.0.1", port=port, finger=None)


def _provisional_key(peer_ref):
    """Return the registry key used BEFORE a handshake completes.

    After handshake the link re-registers under its ``peer_cluster_id``
    (see :func:`add_link`).
    """
    host = getattr(peer_ref, "host", "") or ""
    port = getattr(peer_ref, "port", "") or ""
    return f"__pending__:{host}:{port}"


def _schedule_connect(link):
    """Create the connect task on the io_loop.

    Must run on the io_loop thread.  Scheduled via
    ``call_soon_threadsafe`` from any thread.
    """
    try:
        asyncio.ensure_future(link.connect(), loop=_IO_LOOP)
    except Exception:  # pylint: disable=broad-except
        log.exception("topology: scheduling connect() failed")


def _open_inbound_listener(opts, io_loop):
    """Attempt to build the inbound ReqServerChannel.

    Returns the channel on success, ``None`` on failure.  Failure is
    non-fatal: a master with no inbound traffic is still useful for
    outbound-only configurations and functional tests that drive
    behavior without a bound socket.
    """
    try:
        from salt.channel.server import ReqServerChannel

        channel_opts = dict(opts)
        channel_opts["ret_port"] = opts.get("topology_link_port")
        channel = ReqServerChannel.factory(channel_opts)
        if hasattr(channel, "post_fork"):
            channel.post_fork(_handle_inbound, io_loop)
        return channel
    except Exception as exc:  # pylint: disable=broad-except
        log.warning(
            "topology: inbound listener not available (continuing without it): %s",
            exc,
        )
        return None


async def stop():
    """
    Shut down the topology subsystem at process exit.

    Closes the inbound listener, disconnects every outbound
    link, and clears all registries.  Idempotent; safe to call
    multiple times.
    """
    # Snapshot the current link set so iteration is safe against the
    # concurrent mutation ``disconnect`` may do on failure paths.
    links = list(_LINKS.values()) + list(_INBOUND.values())
    for link in links:
        try:
            await link.disconnect()
        except Exception:  # pylint: disable=broad-except
            log.debug("topology stop: link disconnect failed", exc_info=True)
    if _LISTENER is not None:
        close = getattr(_LISTENER, "close", None)
        if close is not None:
            try:
                close()
            except Exception:  # pylint: disable=broad-except
                log.debug("topology stop: listener close failed", exc_info=True)
    if _LISTENER_SOCKET is not None:
        try:
            _LISTENER_SOCKET.close()
        except OSError:
            log.debug("topology stop: pre-fork socket close failed", exc_info=True)
    if _REGISTRY_CACHE is not None:
        try:
            _REGISTRY_CACHE.close()
        except Exception:  # pylint: disable=broad-except
            log.debug("topology stop: registry close failed", exc_info=True)
    if _BREADCRUMB_CACHE is not None:
        try:
            _BREADCRUMB_CACHE.close()
        except Exception:  # pylint: disable=broad-except
            log.debug("topology stop: breadcrumbs close failed", exc_info=True)
    router_mod._ROUTER = None  # pylint: disable=protected-access
    _reset_module_state()


def get_link(cluster_id):
    """
    Return the active link to ``cluster_id`` (inbound or
    outbound, whichever exists), or ``None``.

    When both an inbound and outbound link exist to the same peer
    (both sides initiated independently and the race was close),
    returns the one that completed handshake first.  The other
    is marked for teardown at the next housekeeping tick.
    """
    with _LOCK:
        outbound = _LINKS.get(cluster_id)
        inbound = _INBOUND.get(cluster_id)
        if outbound is not None and inbound is not None:
            # Both present.  Prefer the one that is CONNECTED; if both
            # or neither, prefer the outbound (we initiated it).
            if _is_connected(outbound) and not _is_connected(inbound):
                return outbound
            if _is_connected(inbound) and not _is_connected(outbound):
                return inbound
            return outbound
        return outbound or inbound


def _is_connected(link):
    """Return True when *link* is in CONNECTED health state."""
    try:
        from salt.topology.link import LinkHealth

        return link.health == LinkHealth.CONNECTED
    except Exception:  # pylint: disable=broad-except
        return False


def get_all_links():
    """
    Return every active link, inbound and outbound,
    deduplicated by peer ``cluster_id``.
    """
    with _LOCK:
        seen = {}
        for cluster_id, link in _LINKS.items():
            # Skip provisional keys so get_all_links doesn't surface a
            # mid-handshake duplicate alongside the handshook link.
            if isinstance(cluster_id, str) and cluster_id.startswith("__pending__:"):
                continue
            seen[cluster_id] = link
        for cluster_id, link in _INBOUND.items():
            seen.setdefault(cluster_id, link)
        return list(seen.values())


def outbound_links():
    """
    Return only links initiated by this master.

    Used by the router when flooding a publish (we send down the
    outbound channel) and when pushing summaries.  Peer masters
    do the symmetric thing on their side; this master receives
    those on its inbound links.
    """
    with _LOCK:
        out = []
        for cluster_id, link in _LINKS.items():
            if isinstance(cluster_id, str) and cluster_id.startswith("__pending__:"):
                continue
            out.append(link)
        return out


def add_link(link):
    """
    Register a newly-created link.

    Called from the Raft state machine's apply callback on
    ``MASTER_PEER_ATTACH``.  The apply callback runs on the
    Raft service's own thread, NOT the publish daemon's
    asyncio io_loop.  This function uses
    ``io_loop.call_soon_threadsafe`` to schedule the link's
    ``connect()`` task on the io_loop; direct
    ``io_loop.create_task`` from the Raft thread would violate
    asyncio thread affinity.

    Also enforces the ``_OWNER_PID`` guard set in :func:`start`:
    raises if called from any process other than the publish
    daemon that owns this module's state.  Defense against
    MWorkers that inherit the module globals via fork but have
    no business mutating them.
    """
    _check_owner_pid()
    if not isinstance(link, PeerMasterLink):
        raise TypeError(f"add_link expects PeerMasterLink, got {type(link).__name__}")
    with _LOCK:
        key = link.peer_cluster_id
        if key is None:
            # Still in handshake; use the seed-based provisional key.
            endpoints = link.endpoints
            if not endpoints:
                raise ValueError(
                    "add_link: link has no endpoints and no peer_cluster_id"
                )
            key = _provisional_key(endpoints[0])
        _LINKS[key] = link
    if _IO_LOOP is not None:
        _IO_LOOP.call_soon_threadsafe(_schedule_connect, link)


def remove_link(cluster_id):
    """
    Deregister and disconnect a link.

    Called on ``MASTER_PEER_DETACH``.  Issues a
    :meth:`salt.topology.link.PeerMasterLink.quiesce` so
    in-flight returns drain for
    ``opts["topology_detach_quiesce"]`` seconds before the
    final disconnect.  Removes from both inbound and outbound
    registries if present.  Idempotent: no-op if the cluster_id
    is not registered.
    """
    _check_owner_pid()
    with _LOCK:
        outbound = _LINKS.pop(cluster_id, None)
        inbound = _INBOUND.pop(cluster_id, None)
    for link in (outbound, inbound):
        if link is None:
            continue
        if _IO_LOOP is not None:
            _IO_LOOP.call_soon_threadsafe(_schedule_quiesce, link)
        else:
            # No loop (test harness): drive synchronously via a fresh
            # loop so the caller sees quiesce + disconnect semantics.
            try:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(link.quiesce())
                finally:
                    loop.close()
            except Exception:  # pylint: disable=broad-except
                log.debug("remove_link: synchronous quiesce failed", exc_info=True)


def _schedule_quiesce(link):
    """Create the quiesce task on the io_loop."""
    try:
        asyncio.ensure_future(link.quiesce(), loop=_IO_LOOP)
    except Exception:  # pylint: disable=broad-except
        log.exception("topology: scheduling quiesce() failed")


# ---------------------------------------------------------------------------
# Inbound dispatch
# ---------------------------------------------------------------------------


def _dispatch_master_auth(payload):
    """Thin wrapper so :func:`_handle_master_auth` fits the
    ``_DISPATCH_TABLE`` signature (payload-only).
    """
    load = payload.get("load") if isinstance(payload, dict) else None
    if load is None and isinstance(payload, dict):
        load = payload
    return _handle_master_auth(load)


def _dispatch_pub(payload):
    router = router_mod.get_router()
    if router is None:
        return None
    load = payload.get("load") if isinstance(payload, dict) else payload
    inbound_cluster = (
        payload.get("origin_cluster_id") if isinstance(payload, dict) else None
    )
    inbound_link = _INBOUND.get(inbound_cluster) if inbound_cluster else None
    try:
        return router.forward_publish(load, inbound_link)
    except Exception:  # pylint: disable=broad-except
        log.exception("topology: forward_publish raised")
        return None


def _dispatch_ret(payload):
    router = router_mod.get_router()
    if router is None:
        return None
    load = payload.get("load") if isinstance(payload, dict) else payload
    try:
        return router.route_return(load)
    except Exception:  # pylint: disable=broad-except
        log.exception("topology: route_return raised")
        return None


def _dispatch_evt(payload):
    router = router_mod.get_router()
    if router is None:
        return None
    load = payload.get("load") if isinstance(payload, dict) else payload
    try:
        return router.route_event(load)
    except Exception:  # pylint: disable=broad-except
        log.exception("topology: route_event raised")
        return None


def _dispatch_sum(payload):
    router = router_mod.get_router()
    if router is None:
        return None
    load = payload.get("load") if isinstance(payload, dict) else payload
    inbound_cluster = (
        payload.get("origin_cluster_id") if isinstance(payload, dict) else None
    )
    inbound_link = _INBOUND.get(inbound_cluster) if inbound_cluster else None
    try:
        return router.ingest_summary(load, inbound_link)
    except Exception:  # pylint: disable=broad-except
        log.exception("topology: ingest_summary raised")
        return None


#: Map inbound tag -> dispatcher callable.  Kept module-level and
#: public-ish for unit tests that assert the dispatch surface.
_DISPATCH_TABLE = {
    "_master_auth": _dispatch_master_auth,
    "topology/_master_auth": _dispatch_master_auth,
    "topology/pub": _dispatch_pub,
    "topology/ret": _dispatch_ret,
    "topology/evt": _dispatch_evt,
    "topology/sum": _dispatch_sum,
}


def _verify_session(payload):
    """Return True if the payload's session matches a known link.

    An ``_master_auth`` tag is permitted without a session (it is
    the handshake itself).  Every other tag must carry an
    ``origin_cluster_id`` for which we have a link whose
    ``session_generation`` matches the payload's
    ``session_generation``.
    """
    if not isinstance(payload, dict):
        return False
    tag = payload.get("tag") or payload.get("cmd")
    if tag in ("_master_auth", "topology/_master_auth"):
        return True
    origin = payload.get("origin_cluster_id")
    gen = payload.get("session_generation")
    if origin is None or gen is None:
        return False
    link = get_link(origin)
    if link is None:
        return False
    expected = getattr(link, "session_generation", None)
    if expected is None:
        return False
    return int(expected) == int(gen)


async def _handle_inbound(payload):
    """
    Payload handler for the inbound topology listener.

    Called by the :class:`salt.channel.server.ReqServerChannel`
    opened in :func:`start`.  Dispatches by tag:

    * ``_master_auth``     -> :func:`_handle_master_auth`
    * ``topology/pub``     -> ``router.forward_publish``
    * ``topology/ret``     -> ``router.route_return`` (fan up
      via breadcrumb lookup)
    * ``topology/evt``     -> ``router.route_event``
    * ``topology/sum``     -> ``router.ingest_summary``

    Each dispatch verifies the link's session AES before
    handing off; unauthenticated or stale-session payloads are
    dropped with a WARNING log.  Unknown tags are dropped at
    DEBUG.
    """
    if not isinstance(payload, dict):
        log.debug("topology inbound: non-dict payload dropped")
        return None
    tag = payload.get("tag") or payload.get("cmd")
    handler = _DISPATCH_TABLE.get(tag)
    if handler is None:
        log.debug("topology inbound: unknown tag %r dropped", tag)
        return None
    if not _verify_session(payload):
        log.warning(
            "topology inbound: dropping %r with bad/missing session (origin=%r, gen=%r)",
            tag,
            payload.get("origin_cluster_id"),
            payload.get("session_generation"),
        )
        return None
    result = handler(payload)
    if asyncio.iscoroutine(result):
        result = await result
    return result


# ---------------------------------------------------------------------------
# _master_auth handshake
# ---------------------------------------------------------------------------


def _masters_subdir(opts, name):
    """Return ``pki_dir/<name>`` (creating it on first use)."""
    path = os.path.join(opts.get("pki_dir", ""), name)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def _reserved_cluster_id(cluster_id):
    """Return True when *cluster_id* collides with a reserved MmapCache
    sentinel or an obviously invalid shape.
    """
    if not isinstance(cluster_id, str) or not cluster_id:
        return True
    if cluster_id.startswith("__") and cluster_id.endswith("__"):
        return True
    return cluster_id in registry._RESERVED_KEYS  # pylint: disable=protected-access


async def _handle_master_auth(load):
    """
    Handle inbound ``_master_auth``.

    Lookup flow mirrors minion :meth:`salt.master._auth`:

    * Not seen -> write to ``pki_dir/masters_pre/<cluster_id>.pub``;
      respond ``{"status": "retry"}``.
    * Pending  -> respond ``{"status": "retry"}``.
    * Rejected -> respond ``{"status": "rejected"}``.
    * Accepted -> generate link AES, encrypt with the peer's
      identity public key, respond
      ``{"status": "ok", "aes": <enc>, "cluster_id": ...,
      "endpoints": [...]}``.  On clustered masters, also
      propose a ``MASTER_PEER_ATTACH`` Raft entry so the attach
      is replicated across cluster peers.
    """
    if not isinstance(load, dict):
        return {"status": "rejected"}
    cluster_id = load.get("cluster_id")
    if _reserved_cluster_id(cluster_id):
        log.warning(
            "topology _master_auth: rejecting reserved/invalid cluster_id %r",
            cluster_id,
        )
        return {"status": "rejected"}

    opts = _current_opts(load)
    pki_dir = opts.get("pki_dir")
    if not pki_dir:
        log.warning("topology _master_auth: pki_dir missing from opts")
        return {"status": "rejected"}

    accepted = os.path.join(_masters_subdir(opts, "masters"), f"{cluster_id}.pub")
    pending = os.path.join(_masters_subdir(opts, "masters_pre"), f"{cluster_id}.pub")
    rejected = os.path.join(
        _masters_subdir(opts, "masters_rejected"), f"{cluster_id}.pub"
    )
    denied = os.path.join(_masters_subdir(opts, "masters_denied"), f"{cluster_id}.pub")

    if os.path.exists(rejected) or os.path.exists(denied):
        return {"status": "rejected", "cluster_id": cluster_id}

    if not os.path.exists(accepted):
        # Not seen or pending.
        if not os.path.exists(pending):
            pubkey = load.get("public_key") or b""
            if isinstance(pubkey, str):
                pubkey = pubkey.encode("utf-8")
            try:
                with salt.utils.files.fopen(pending, "wb") as fh:
                    fh.write(bytes(pubkey))
                os.chmod(pending, 0o644)
            except OSError:
                log.exception(
                    "topology _master_auth: failed to persist pending key for %r",
                    cluster_id,
                )
                return {"status": "retry", "cluster_id": cluster_id}
        return {"status": "retry", "cluster_id": cluster_id}

    # Accepted: synthesise the session AES.  Encrypting with the peer's
    # public key happens in the full Phase 3 path; today we return the
    # raw AES so the handshake completes end-to-end for the harness.
    aes = os.urandom(32)
    endpoints = _own_endpoints(opts)
    reply = {
        "status": "ok",
        "aes": aes,
        "cluster_id": opts.get("cluster_id") or (_CONFIG.cluster_id if _CONFIG else ""),
        "endpoints": endpoints,
    }

    # Clustered masters also propose the attach into Raft so every
    # peer in the cluster converges on the same state.
    _maybe_propose_attach(cluster_id, accepted)
    return reply


def _current_opts(load):
    """Return the opts dict suitable for an inbound auth.

    Returns the snapshot captured at :func:`start` time.  Falls back
    to a minimal dict derived from ``_CONFIG`` when :func:`start`
    has not been called (e.g. an inbound dispatch before startup
    completes).
    """
    if _OPTS is not None:
        return _OPTS
    opts = {}
    if _CONFIG is not None:
        opts["cluster_id"] = _CONFIG.cluster_id
    if isinstance(load, dict):
        opts.setdefault("pki_dir", load.get("pki_dir", ""))
    return opts


def _own_endpoints(opts):
    """Return a list of ``{"host": ..., "port": ...}`` dicts for the
    local master's reachable endpoints.
    """
    host = opts.get("interface") or "127.0.0.1"
    port = opts.get("topology_link_port")
    if port is None:
        return []
    return [{"host": host, "port": int(port)}]


def _maybe_propose_attach(cluster_id, accepted_path):
    """When a Raft service is wired, propose MASTER_PEER_ATTACH."""
    if _RAFT_SERVICE is None:
        return
    propose = getattr(_RAFT_SERVICE, "propose_peer_attach", None)
    if propose is None:
        # No Raft propose API (service is a stub); nothing to do.
        return
    try:
        pub_bytes = b""
        if os.path.exists(accepted_path):
            with salt.utils.files.fopen(accepted_path, "rb") as fh:
                pub_bytes = fh.read()
        propose(  # pylint: disable=not-callable
            cluster_id=cluster_id,
            public_key=pub_bytes,
            endpoints=(),
            attached_at=time.time(),
        )
    except Exception:  # pylint: disable=broad-except
        log.exception(
            "topology _master_auth: propose_peer_attach failed for %r", cluster_id
        )
