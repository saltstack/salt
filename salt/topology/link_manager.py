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
import logging
import os
import threading
import time

import salt.topology.breadcrumbs as breadcrumbs
import salt.topology.registry as registry
import salt.topology.router as router_mod
import salt.utils.asynchronous
import salt.utils.event
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


def is_owner():
    """
    Return ``True`` when this process owns the link_manager state.

    The link_manager module globals are populated in-process by
    :func:`start` from the publish daemon.  Followers (non-leaders)
    and MWorker children never call :func:`start`, so their copy of
    this module has ``_OWNER_PID is None`` and no live link entries.

    :class:`salt.cluster.consensus.raft.topology.TopologyStateMachine`
    uses this to decide whether a routing query (``next_hop``) can be
    answered from live state or must be refused with
    :class:`salt.cluster.consensus.raft.topology.NotLeaderError`.
    """
    return _OWNER_PID is not None and os.getpid() == _OWNER_PID


def pre_fork(opts, process_manager):
    """
    Called from
    :meth:`salt.channel.server.MasterPubServerChannel.pre_fork`
    when ``opts["topology_enabled"]`` is True.

    Pre-create the breadcrumb and registry MmapCache files via
    :func:`salt.topology.breadcrumbs.pre_create` and
    :func:`salt.topology.registry.pre_create`.  Prevents the
    startup race where MWorkers fork and call :func:`open_reader`
    on a file the publish daemon has not yet opened.

    This function must NOT touch ``_LINKS``, ``_INBOUND``, or
    ``_LISTENER``.  Those are populated by :func:`start` on the
    publish daemon side, after fork.  Populating them pre-fork
    would leak into every forked child.

    ``topology_link_port`` is bound by
    :class:`salt.transport.zeromq.RequestServer`'s ``direct_bind``
    path inside the publish daemon after fork.  No pre-fork
    reservation is needed; a reservation here would hold a bound
    fd in the parent process and cause the publish daemon's zmq
    bind to fail with EADDRINUSE.
    """
    if not opts.get("topology_enabled"):
        return
    registry.pre_create(opts)
    breadcrumbs.pre_create(opts)


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

    # Step 2: own this process's state.  The io_loop passed in from
    # :meth:`salt.channel.server.MasterPubServerChannel._publish_daemon`
    # is a tornado ``AsyncIOMainLoop``; the unit/scenario harnesses
    # pass a bare ``asyncio.AbstractEventLoop``.  Every subsequent
    # ``call_soon_threadsafe`` dispatch (``_schedule_connect`` /
    # ``_schedule_quiesce`` from state-machine callback apply
    # threads) requires an asyncio loop, so normalize here once
    # instead of guarding each call site.
    _OWNER_PID = os.getpid()
    io_loop = salt.utils.asynchronous.aioloop(io_loop)
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
    #
    # Solo (non-3008.x) masters do not set ``opts["cluster_id"]`` --
    # that key is the 3008.x master-cluster primitive.  Project the
    # topology-config ``cluster_id`` into the opts handed to the
    # router (and later to each :class:`PeerMasterLink`) so
    # ``TopologyRouter.cluster_id`` and
    # :attr:`salt.topology.link.PeerMasterLink.opts["cluster_id"]`
    # both resolve to the configured identity.  Without this
    # projection, every outbound envelope goes on the wire with
    # ``origin=None, path=[None]`` and the peer rejects it as a
    # tampered path.
    projected_opts = dict(opts)
    if not projected_opts.get("cluster_id") and cfg.cluster_id:
        projected_opts["cluster_id"] = cfg.cluster_id
    _topology_router = router_mod.TopologyRouter(
        projected_opts, _REGISTRY_CACHE, _BREADCRUMB_CACHE
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

    # Step 8: outbound links from topology.conf.  Reuse the
    # ``cluster_id``-projected opts the router already uses; without
    # it the outbound ``topology/_master_auth`` handshake would send
    # ``cluster_id=None`` and the receiving peer's
    # :func:`_handle_master_auth` would reject it via
    # :func:`_reserved_cluster_id` (``None`` fails the "non-empty
    # str" guard), leaving every solo-to-solo link stuck in retry.
    for peer_ref in cfg.peers:
        try:
            link = PeerMasterLink(projected_opts, peer_ref, io_loop)
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

    # Replay pre-existing committed peers from the registry MmapCache.
    # Raft apply() does not re-fire already-applied entries, so without
    # this a clustered-master restart would come up with zero outbound
    # links.  Mirror of the solo-path peer replay in _replay_registry.
    if _REGISTRY_CACHE is None:
        return
    try:
        peer_ids = registry.list_peer_ids(_REGISTRY_CACHE)
    except Exception:  # pylint: disable=broad-except
        log.debug("topology: clustered registry replay failed", exc_info=True)
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
        add_link(link)


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


def _register_connected_link(link):
    """Re-key ``_LINKS`` under ``peer_cluster_id`` and wire the link
    into the process-wide :class:`salt.topology.router.TopologyRouter`.

    Call sites: scheduled on the io_loop after
    :meth:`salt.topology.link.PeerMasterLink.connect` completes
    successfully.  Before this runs the link is registered in
    ``_LINKS`` under a ``__pending__:host:port`` key with no
    ``peer_cluster_id`` yet — nothing can route to it because the
    router keys outbound dispatch by peer ``cluster_id``.  After this
    runs the router sees the link under its real id and
    ``route_publish`` / ``forward_publish`` can pick it up.

    Idempotent: a second call for the same link is a no-op.  Safe to
    call when the connect attempt failed and left no
    ``peer_cluster_id`` behind — nothing happens.
    """
    peer_id = getattr(link, "peer_cluster_id", None)
    if not peer_id:
        return
    with _LOCK:
        # Drop any provisional (pre-handshake) key pointing at this link.
        stale_keys = [
            k
            for k, v in _LINKS.items()
            if v is link and isinstance(k, str) and k.startswith("__pending__:")
        ]
        for k in stale_keys:
            _LINKS.pop(k, None)
        _LINKS[peer_id] = link
    router = router_mod.get_router()
    if router is not None:
        router._links[peer_id] = link  # pylint: disable=protected-access


async def _connect_and_register(link):
    """Await ``link.connect()`` then publish the result into
    ``_LINKS`` + ``router._links`` via :func:`_register_connected_link`.

    Split out so :func:`_schedule_connect` keeps its "fire and forget"
    shape while the post-handshake wiring stays single-sourced.
    """
    try:
        await link.connect()
    except Exception:  # pylint: disable=broad-except
        # ``asyncio.CancelledError`` is a ``BaseException`` subclass on
        # modern Python and does not match this ``Exception`` branch;
        # the task cancellation propagates naturally.
        log.exception("topology: link.connect() failed")
        return
    try:
        _register_connected_link(link)
    except Exception:  # pylint: disable=broad-except
        log.exception("topology: _register_connected_link failed")


def _schedule_connect(link):
    """Create the connect task on the io_loop.

    Must run on the io_loop thread.  Scheduled via
    ``call_soon_threadsafe`` from any thread.  Wraps the raw
    ``link.connect()`` with :func:`_connect_and_register` so a
    successful handshake re-keys ``_LINKS`` and populates
    ``router._links``.
    """
    try:
        asyncio.ensure_future(_connect_and_register(link), loop=_IO_LOOP)
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
        # Disable the minion-auth downgrade check for the topology REP
        # channel.  ``ReqServerChannel.handle_message`` rejects any
        # payload with ``version < minimum_auth_version`` (default 3),
        # which is correct for minion ``_auth`` traffic but wrong for
        # the topology ``_master_auth`` handshake, which is clear-text,
        # version-less, and authenticated at the
        # ``masters/<cluster_id>.pub`` boundary.  Without this override
        # every inbound topology REQ gets "bad load" back and the
        # east<->west handshake deadlocks.
        channel_opts["minimum_auth_version"] = 0
        # Force the plain (non-pooled) :class:`ReqServerChannel`
        # irrespective of ``worker_pools_enabled``.  The pooled
        # :class:`PoolRoutingChannel` routes every request through
        # per-pool IPC into an MWorker and the ``payload_handler``
        # registered here is only honoured in the main routing path
        # — never on a pool worker.  Our dispatch table lives in
        # this process (:func:`_handle_inbound` + ``_DISPATCH_TABLE``)
        # so we need the request to come back here, not into a
        # worker's :meth:`salt.master.MWorker._handle_payload`.
        channel_opts["worker_pools_enabled"] = False
        channel = ReqServerChannel.factory(channel_opts)
        if hasattr(channel, "post_fork"):
            # Pass the channel adapter, not the bare dispatcher: the
            # channel unpacks ``payload_handler``'s return as
            # ``(ret, req_opts)`` and dispatches on
            # ``req_opts["fun"]``.  Direct in-process callers continue
            # to invoke :func:`_handle_inbound` (which returns a single
            # value) via the same module API.
            #
            # ``direct_bind=True`` tells the underlying transport
            # :class:`salt.transport.zeromq.RequestServer` to bind the REP
            # socket directly to ``tcp://interface:topology_link_port``
            # instead of connecting to the master's ``MWorkerQueue`` on
            # ``workers.ipc``.  Topology does not front its port with an
            # MWorkerQueue -- we dispatch inbound requests here in the
            # publish daemon via ``_handle_inbound_channel`` -- so there is
            # no DEALER waiting for us on the other end of ``workers.ipc``.
            channel.post_fork(_handle_inbound_channel, io_loop, direct_bind=True)
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
    """Create the quiesce task on the io_loop.

    Passes the module's breadcrumb cache so the drain exits early when
    no return still routes through the link; without the cache the
    drain always runs the full ``topology_detach_quiesce`` timer.
    """
    try:
        asyncio.ensure_future(
            link.quiesce(breadcrumb_cache=_BREADCRUMB_CACHE),
            loop=_IO_LOOP,
        )
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


async def _dispatch_pub(payload):
    """
    Handle an inbound ``topology/pub`` payload.

    Calls :meth:`salt.topology.router.TopologyRouter.forward_publish`
    to decide the next-hop link set + whether this cluster should
    also publish to its own minions.  When ``local_match`` is True,
    strips the ``C@`` scope from the target (so the minion-side
    compound matcher stays oblivious to topology) and dispatches
    the stripped load via the master publish channel so the local
    accepted minions receive it.

    Returns ``(links, local_match)`` from the router call.  The
    inbound ReqServerChannel does not consume the return value;
    the tuple is kept for test observability.
    """
    router = router_mod.get_router()
    if router is None:
        return None
    load = payload.get("load") if isinstance(payload, dict) else payload
    inbound_cluster = (
        payload.get("origin_cluster_id") if isinstance(payload, dict) else None
    )
    inbound_link = _INBOUND.get(inbound_cluster) if inbound_cluster else None
    try:
        result = router.forward_publish(load, inbound_link)
    except Exception:  # pylint: disable=broad-except
        log.exception("topology: forward_publish raised")
        return None
    if not isinstance(result, tuple) or len(result) != 2:
        # Legacy / fake router: nothing to do with local_match.
        return result
    links, local_match = result
    if local_match and isinstance(load, dict):
        # Minion-return event forwarded from a transit cluster: west
        # fires ``salt/job/<jid>/ret/<minion_id>`` on its event bus when
        # its locally-attached minion returns.  The publish daemon's
        # topology hook packages that as a ``topology/pub``, so the
        # return arrives on the origin cluster through this very
        # ``_dispatch_pub`` -- not through the ``topology/ret`` path,
        # which currently depends on an event-bus subscriber the
        # publish daemon does not yet own.  Short-circuit here: when
        # the load looks like a native minion return (``cmd='_return'``
        # with ``jid`` + ``id`` + ``return``), write it to this
        # master's local returner via
        # :func:`salt.utils.job.store_job` so the ``salt`` CLI's
        # ``local_cache`` poll finds it.  Native publishes (which
        # carry ``tgt``/``tgt_type``/``fun``/``arg`` but no
        # ``return``) continue to flow to local minions via
        # :func:`_publish_to_local_minions`.
        if _looks_like_minion_return(load):
            try:
                _store_forwarded_return(load)
            except Exception:  # pylint: disable=broad-except
                log.exception(
                    "topology: store_job for forwarded return failed for jid=%r",
                    load.get("jid"),
                )
        else:
            try:
                await _publish_to_local_minions(load)
            except Exception:  # pylint: disable=broad-except
                log.exception(
                    "topology: local-minion publish failed for forwarded jid=%r",
                    load.get("jid"),
                )
    return links, local_match


def _looks_like_minion_return(load):
    """Return True when ``load`` is a minion-return event payload rather
    than a target publish.  See the discriminator comment in
    :func:`_dispatch_pub`.
    """
    if not isinstance(load, dict):
        return False
    return (
        load.get("cmd") == "_return"
        and "jid" in load
        and "id" in load
        and "return" in load
    )


_MMINION_CACHE = None


def _store_forwarded_return(load):
    """Write a return received via topology forwarding into this
    master's local returner.

    Lazy-loaded :class:`salt.minion.MasterMinion` is cached at module
    level so repeated calls don't re-walk the returner loader for
    every forwarded return in a hot publish.
    """
    global _MMINION_CACHE
    if _OPTS is None:
        return
    import salt.utils.job  # pylint: disable=import-outside-toplevel

    if _MMINION_CACHE is None:
        import salt.minion  # pylint: disable=import-outside-toplevel

        _MMINION_CACHE = salt.minion.MasterMinion(_OPTS, states=False, rend=False)
    event = salt.utils.event.get_master_event(
        _OPTS, _OPTS.get("sock_dir"), listen=False
    )
    salt.utils.job.store_job(_OPTS, load, event=event, mminion=_MMINION_CACHE)

    # ``store_job`` writes the return under ``<jid>/<minion_id>/return.p``
    # but does not touch ``<jid>/.minions.p`` -- that list was pre-written
    # by the local master when the publish was first issued and names
    # only the LOCAL minions matched by the target.  For a C@-scoped
    # publish on a master whose own minion set has no overlap with the
    # scope, that list is empty, so the ``salt`` CLI polling
    # :func:`salt.returners.local_cache.get_minions` concludes "no
    # minions matched" and exits before our forwarded return arrives.
    # Append the returning minion so the CLI's next poll finds a match.
    minion_id = load.get("id")
    jid = load.get("jid")
    if minion_id and jid:
        try:
            job_cache = _OPTS.get("master_job_cache", "local_cache")
            save_minions_fn = _MMINION_CACHE.returners.get(f"{job_cache}.save_minions")
            if save_minions_fn is not None:
                save_minions_fn(jid, [minion_id])
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "topology: save_minions for forwarded return failed jid=%r id=%r",
                jid,
                minion_id,
            )


async def _publish_to_local_minions(load):
    """
    Fan a forwarded publish out to this master's own minions.

    Strips every ``C@`` scope from ``load["tgt"]`` via
    :func:`salt.topology.router.strip_cluster_scope` so a
    (non-topology-aware) minion still sees a well-formed compound
    expression.  Then opens a transient
    :class:`salt.channel.server.PubServerChannel` and sends the
    stripped load through the same IPC path the local
    :meth:`salt.master.ClearFuncs._send_pub` uses for new publishes.

    Idempotent at the channel layer: ``publish`` is a pure
    IPC-pull-socket write, no bind.
    """
    import salt.channel.server
    import salt.utils.channel

    stripped = dict(load)
    tgt = stripped.get("tgt")
    try:
        stripped["tgt"] = router_mod.strip_cluster_scope(tgt)
    except Exception:  # pylint: disable=broad-except
        log.debug(
            "topology: strip_cluster_scope failed; publishing raw tgt", exc_info=True
        )
    for transport, opts in salt.utils.channel.iter_transport_opts(_OPTS or {}):
        chan = salt.channel.server.PubServerChannel.factory(opts)
        try:
            await chan.publish(stripped)
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "topology: PubServerChannel.publish failed on transport %r",
                transport,
            )


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


def _maybe_lazy_register_inbound(payload):
    """Register ``_INBOUND[origin]`` when the peer key is accepted but
    the in-process inbound record is missing.

    Called from :func:`_handle_inbound` before :func:`_verify_session`
    on every non-handshake frame.  Idempotent: a frame that arrives
    with an existing matching session leaves the record untouched; a
    frame carrying a strictly higher ``session_generation`` bumps the
    record forward (handles the "peer re-handshaked out-of-band"
    case).  Older-generation frames fail :func:`_verify_session`
    naturally.

    No-op when:

    * the payload is not a dict
    * ``origin_cluster_id`` is missing / reserved
    * the peer key is not in ``masters/<cluster_id>.pub``
      (``_handle_master_auth`` is still the only way to accept keys)
    """
    if not isinstance(payload, dict):
        return
    origin = payload.get("origin_cluster_id")
    gen = payload.get("session_generation")
    if _reserved_cluster_id(origin) or gen is None:
        return
    if _OPTS is None:
        return
    try:
        gen_i = int(gen)
    except (TypeError, ValueError):
        return
    accepted = os.path.join(_masters_subdir(_OPTS, "masters"), f"{origin}.pub")
    if not os.path.exists(accepted):
        return
    # Mutating ``_INBOUND`` concurrently with the Raft-SM apply thread's
    # :func:`remove_link` (``_INBOUND.pop`` under ``_LOCK``) is a data
    # race; hold the module lock around both the staleness check and the
    # write so a detach landing mid-registration cannot leave a stale
    # record resurrected.
    with _LOCK:
        existing = _INBOUND.get(origin)
        if existing is not None and existing.session_generation >= gen_i:
            return
        _INBOUND[origin] = _InboundLink(
            peer_cluster_id=origin,
            session_generation=gen_i,
            session_aes=None,
        )


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


def _unwrap_inbound_envelope(payload):
    """Return the topology-level payload, peeling the ReqServerChannel
    wire envelope (``{"enc": ..., "load": {...}, "version": N}``) if it
    is wrapped around a dict.

    Direct in-process callers (functional tests driving dispatch
    without a channel) pass the topology envelope untouched; the
    on-wire inbound path lands here with the outer envelope.  A
    single unwrap handles both.
    """
    if not isinstance(payload, dict):
        return None
    if "enc" in payload and isinstance(payload.get("load"), dict):
        inner = payload["load"]
        # Only unwrap when the outer envelope is clearly transport-level
        # (``enc`` present).  Topology-native payloads with an inner
        # ``load`` key (e.g. a dispatch to :func:`_dispatch_pub` whose
        # inner dict holds the publish body) are NOT touched here --
        # the dispatchers themselves pull ``payload["load"]`` as the
        # application-level body.
        return inner
    return payload


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
    inner = _unwrap_inbound_envelope(payload)
    if inner is None:
        log.debug("topology inbound: non-dict payload dropped")
        return None
    tag = inner.get("tag") or inner.get("cmd")
    handler = _DISPATCH_TABLE.get(tag)
    if handler is None:
        log.debug("topology inbound: unknown tag %r dropped", tag)
        return None
    # Lazy inbound registration: when a frame arrives from a peer whose
    # key is accepted on disk but ``_INBOUND[origin]`` is empty in this
    # process, auto-register.  Covers the common zmq REQ-REP survival
    # pattern where the client's socket silently reconnects after the
    # server restarts -- the client never learns the session is dead
    # (zmq delivers the queued send to the fresh server), so the server
    # must bootstrap state from the authenticated key on disk rather
    # than wait for a re-handshake that will not come.
    #
    # The accepted-key check is the authentication boundary.  The
    # frame's self-reported ``origin_cluster_id`` is only trusted
    # because the peer could not have reached us on
    # ``topology_link_port`` without previously completing a
    # ``_master_auth`` whose cluster_id key is now in
    # ``masters/<cluster_id>.pub`` -- a stranger with no accepted key
    # cannot forge an entry here.
    if tag not in ("_master_auth", "topology/_master_auth"):
        _maybe_lazy_register_inbound(inner)
    if not _verify_session(inner):
        log.warning(
            "topology inbound: dropping %r with bad/missing session (origin=%r, gen=%r)",
            tag,
            inner.get("origin_cluster_id"),
            inner.get("session_generation"),
        )
        return None
    result = handler(inner)
    if asyncio.iscoroutine(result):
        result = await result
    return result


async def _handle_inbound_channel(payload):
    """
    Wire-adapter for :meth:`salt.channel.server.ReqServerChannel.handle_message`.

    ``handle_message`` unpacks ``payload_handler``'s return as
    ``(ret, req_opts)`` and dispatches by ``req_opts["fun"]``.  The
    core :func:`_handle_inbound` returns a single value (the inner
    dispatch result, or ``None`` on drop) so in-process callers do not
    have to carry the channel's return-shape contract.  This wrapper
    adapts between the two: it awaits the inner dispatch and always
    returns a ``(ret, {"fun": "send_clear"})`` tuple so a dropped
    message yields a well-formed empty cleartext reply instead of a
    transport-level failure.
    """
    result = await _handle_inbound(payload)
    if result is None:
        result = {}
    return result, {"fun": "send_clear"}


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


class _InboundLink:
    """Server-side record of a peer master link.

    Carries the minimum attributes the inbound dispatch path needs:

    * ``peer_cluster_id`` --- for
      :meth:`salt.topology.router.TopologyRouter.forward_publish`'s
      path-authentication check (the first-hop in the authenticated
      path must equal this).
    * ``session_generation`` --- for :func:`_verify_session` to accept
      follow-on ``topology/pub|ret|evt|sum`` frames.  Mirrors the
      sender's :attr:`salt.topology.link.PeerMasterLink.session_generation`
      which increments from 0 to 1 on first successful handshake and
      bumps on each re-handshake.
    * ``session_aes`` --- the AES handed back in the handshake reply;
      retained so a future crypt-aware inbound dispatch can decrypt.

    Separate from :class:`salt.topology.link.PeerMasterLink` because the
    server-side record never initiates outbound traffic through this
    object --- the symmetric outbound link lives in ``_LINKS`` and runs
    its own ``connect()``.  Keeping the two record-sides separate avoids
    coupling the inbound side to a :class:`salt.config.topology.PeerRef`
    (host/port) that the handshake load never carries.
    """

    __slots__ = ("peer_cluster_id", "session_generation", "session_aes")

    def __init__(self, peer_cluster_id, session_generation, session_aes):
        self.peer_cluster_id = peer_cluster_id
        self.session_generation = session_generation
        self.session_aes = session_aes

    def __repr__(self):
        return (
            f"<_InboundLink peer={self.peer_cluster_id!r} "
            f"gen={self.session_generation}>"
        )


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

    # Register the server-side inbound link so follow-on
    # ``topology/pub|ret|evt|sum`` frames from this peer pass
    # :func:`_verify_session`.  The sender's
    # :class:`salt.topology.link.PeerMasterLink` increments its own
    # :attr:`session_generation` from 0 -> 1 on receipt of this ``ok``
    # reply (and bumps on each re-handshake), so mirror by incrementing
    # the server-side counter here.  Prior ``_INBOUND[cluster_id]`` is
    # a re-handshake; absence is a first-handshake.
    #
    # Hold ``_LOCK`` around the read-modify-write: the Raft-SM apply
    # thread's :func:`remove_link` also touches ``_INBOUND`` under the
    # same lock, so an un-serialized sequence here could resurrect an
    # inbound record for a cluster_id the SM has just detached.
    with _LOCK:
        existing = _INBOUND.get(cluster_id)
        next_gen = existing.session_generation + 1 if existing is not None else 1
        _INBOUND[cluster_id] = _InboundLink(
            peer_cluster_id=cluster_id,
            session_generation=next_gen,
            session_aes=aes,
        )
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
    """When a Raft service is wired, propose MASTER_PEER_ATTACH.

    Pre-check: if the Raft service exposes the rolling-upgrade gate
    (:meth:`RaftService._min_cluster_protocol_version`) and any
    cluster voter still advertises the pre-topology version, log a
    WARNING naming the laggard(s) and skip the propose.  Catching
    the eventual propose exception is not sufficient here because
    the attach path reaches us from the inbound ``_master_auth``
    coroutine --- naming the laggard in the daemon log keeps the
    diagnostic signal operator-visible without requiring an
    exception to escape the handler.
    """
    if _RAFT_SERVICE is None:
        return
    propose = getattr(_RAFT_SERVICE, "propose_peer_attach", None)
    if propose is None:
        # No Raft propose API (service is a stub); nothing to do.
        return

    # Pre-check the gate so we can log a clean, operator-visible
    # WARNING before the propose raises.  The service's propose
    # method itself enforces the gate too --- this is defence in
    # depth, not a replacement.
    try:
        from salt.cluster.consensus.service import (  # pylint: disable=import-outside-toplevel
            TOPOLOGY_PROTOCOL_VERSION,
            MixedVersionClusterError,
        )
    except ImportError:
        TOPOLOGY_PROTOCOL_VERSION = None
        MixedVersionClusterError = None
    gate_check = getattr(_RAFT_SERVICE, "_min_cluster_protocol_version", None)
    if (
        gate_check is not None
        and TOPOLOGY_PROTOCOL_VERSION is not None
        and MixedVersionClusterError is not None
    ):
        try:
            min_version = gate_check()  # pylint: disable=not-callable
        except Exception:  # pylint: disable=broad-except
            min_version = None
        if min_version is not None and min_version < TOPOLOGY_PROTOCOL_VERSION:
            laggards_fn = getattr(_RAFT_SERVICE, "_laggard_voters", None)
            laggards = (
                laggards_fn()  # pylint: disable=not-callable
                if callable(laggards_fn)
                else []
            )
            log.warning(
                "topology _master_auth: refusing MASTER_PEER_ATTACH for "
                "%r --- cluster peer(s) still advertise pre-topology "
                "protocol version (min=%s, required=%s); finish rolling "
                "upgrade first (laggards: %s)",
                cluster_id,
                min_version,
                TOPOLOGY_PROTOCOL_VERSION,
                laggards,
            )
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
    except Exception as exc:  # pylint: disable=broad-except
        if MixedVersionClusterError is not None and isinstance(
            exc, MixedVersionClusterError
        ):
            # Already surfaced via the pre-check above in nearly every
            # case; this branch covers a race where the gate state
            # changed between pre-check and propose.
            log.warning(
                "topology _master_auth: MASTER_PEER_ATTACH blocked by "
                "rolling-upgrade gate for %r: %s",
                cluster_id,
                exc,
            )
            return
        log.exception(
            "topology _master_auth: propose_peer_attach failed for %r", cluster_id
        )
