"""
Process-wide link lifecycle for master topology.

Owns two concerns:

* Outbound registry: a module-level dict of
  :class:`salt.topology.link.PeerMasterLink` instances keyed
  by peer ``cluster_id`` (the peer master's external identity;
  solo and clustered peers key the same way).
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
import salt.topology.summary as summary_mod
import salt.utils.asynchronous
import salt.utils.event
import salt.utils.files
from salt.config.topology import PeerRef, load_topology_config
from salt.topology.link import PeerMasterLink

log = logging.getLogger(__name__)


# Module-level registry of outbound links (we initiated the TCP).
# Key is peer ``cluster_id`` after handshake --- i.e. the peer
# master's external identity; the same key shape is used whether
# the peer is a solo master or a clustered one.  Before handshake
# the link is tracked by a provisional key derived from the seed
# :class:`salt.config.topology.PeerRef`.
_LINKS = {}

# Module-level registry of inbound links (peer initiated to us).
# Key is peer ``cluster_id`` after handshake --- the peer master's
# external identity (same shape for solo and clustered peers).
_INBOUND = {}

# Timeout for outbound ``topology/pub`` / ``topology/ret`` sends.
# The publish daemon's io_loop also drives the IPC pull-socket read
# and every topology dispatcher coroutine.  A single unbounded
# ``await`` on a slow / wedged peer (whose link's REQ.send never
# resolves) stalls everything co-scheduled -- in the worst case
# the pub-pull reader stops picking up new publishes for minutes
# at a time, which surfaces as "one leaf cluster's minions
# silently miss a publish".  Bound every outbound topology send
# so a wedged peer only costs us this many seconds.
_TOPOLOGY_AWAIT_TIMEOUT = 10.0

# Inbound listener state.  Owned here --- not a separate module ---
# because inbound and outbound lifecycle are intertwined (both come
# up together, both tear down together) and both share the single
# process-level :class:`~salt.topology.router.TopologyRouter`.
_LISTENER = None

#: Master-event subscriber that watches ``salt/topology/return/*``.
#: Populated by :func:`_start_return_subscriber`; torn down in
#: :func:`stop`.
_RETURN_SUBSCRIBER = None

#: Periodic ``topology/sum`` emission task.  Populated by
#: :func:`start`; cancelled in :func:`stop`.  Builds a fresh
#: :class:`salt.topology.summary.ClusterSummary` every
#: ``topology_summary_interval`` seconds and pushes it to every
#: attached peer link so each peer learns a route to this cluster.
_SUMMARY_TASK = None

#: Periodic re-handshake task for outbound links whose channels have
#: been torn down after a send fault
#: (:meth:`salt.topology.link.PeerMasterLink._handle_send_fault`).
#: Without this, a wedged REQ channel stays wedged until the master
#: restarts: ``topology.peers`` still shows ``attached`` but every
#: outbound forward times out silently.  Populated by :func:`start`;
#: cancelled in :func:`stop`.
_RECONNECT_TASK = None

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

#: Process-wide hook that fires an event on the local master event bus
#: without blocking the publish daemon's io_loop.  Set by
#: :func:`_wire_router_fire_event` once at :func:`start` time; also used
#: by :func:`_publish_to_local_minions` to announce forwarded publishes
#: via ``salt/job/<jid>/new`` and ``salt/job/<jid>/publish``.  Signature:
#: ``_FIRE_EVENT(tag, data)``.
_FIRE_EVENT = None

#: Cached :class:`salt.utils.event.MasterEvent` client used by
#: :func:`_publish_to_local_minions` to fire the forwarded-publish
#: new-job + publish-job events sequentially via
#: :meth:`fire_event_async`.  Set alongside :data:`_FIRE_EVENT` by
#: :func:`_wire_router_fire_event`.  Sharing a single client across
#: fires preserves the single-pusher-socket connection so paired
#: ``/new`` + ``/publish`` writes land in order on
#: ``master_event_pull.ipc``.
_EVENT_BUS = None

_LOCK = threading.RLock()

#: Registry of in-flight ``topology/pub-complete`` collectors keyed by
#: jid.  Populated by :func:`_spawn_pub_complete_collector`, cleared
#: by the collector coroutine's ``finally`` block.  Bounded by
#: ``opts["topology_pub_complete_max_inflight"]`` so a publish flood
#: cannot leak unbounded asyncio.Task objects.  See RFC
#: ``doc/topics/master-topology/rfc-pub-ack-complete.md`` Phase 1.5.
_PUB_COMPLETE_COLLECTORS = {}


def _reset_module_state():
    """Reset every module-level variable to its post-import default.

    Used by :func:`stop` and by test fixtures that need the module in
    a known state between runs.
    """
    global _LINKS, _INBOUND, _LISTENER, _LISTENER_SOCKET, _OWNER_PID
    global _REGISTRY_CACHE, _BREADCRUMB_CACHE, _IO_LOOP, _RAFT_SERVICE
    global _CONFIG, _OPTS, _RETURN_SUBSCRIBER, _SUMMARY_TASK, _RECONNECT_TASK
    global _FIRE_EVENT, _EVENT_BUS
    for chan in _PUB_CHANNEL_CACHE.values():
        try:
            chan.close()
        except Exception:  # pylint: disable=broad-except
            log.debug("topology: cached PubServerChannel close failed", exc_info=True)
    _PUB_CHANNEL_CACHE.clear()
    # Cancel any outstanding pub-complete collectors so a re-start does
    # not inherit stale per-jid tasks from the prior process generation.
    for task in list(_PUB_COMPLETE_COLLECTORS.values()):
        try:
            task.cancel()
        except Exception:  # pylint: disable=broad-except
            log.debug(
                "topology: pub-complete collector cancel on reset failed",
                exc_info=True,
            )
    _PUB_COMPLETE_COLLECTORS.clear()
    _FIRE_EVENT = None
    _EVENT_BUS = None
    _LINKS = {}
    _INBOUND = {}
    _LISTENER = None
    _LISTENER_SOCKET = None
    _RETURN_SUBSCRIBER = None
    _SUMMARY_TASK = None
    _RECONNECT_TASK = None
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


def _wire_router_fire_event(router, opts, io_loop):
    """Install a real-bus ``_fire_event`` hook on *router*.

    Also publishes the hook as module-level :data:`_FIRE_EVENT` so
    other link_manager helpers (e.g. :func:`_publish_to_local_minions`
    which fires ``salt/job/<jid>/new`` and ``salt/job/<jid>/publish``
    for forwarded publishes) share the single cached event-bus client.

    Returns silently if the required pieces (sock_dir / running loop)
    aren't available; the router's default WARNING-log fallback then
    remains in effect, matching pre-fix behavior for test harnesses.
    """
    global _FIRE_EVENT, _EVENT_BUS
    sock_dir = opts.get("sock_dir")
    if not sock_dir:
        return
    try:
        event = salt.utils.event.get_master_event(
            opts, sock_dir, listen=False, io_loop=io_loop
        )
    except Exception:  # pylint: disable=broad-except
        log.debug(
            "topology: get_master_event failed; _fire_event not wired", exc_info=True
        )
        return

    def _fire(tag, data):
        try:
            fire_async = getattr(event, "fire_event_async", None)
            if fire_async is not None:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop is not None:
                    loop.create_task(fire_async(data, tag))
                    return
            event.fire_event(data, tag)
        except Exception:  # pylint: disable=broad-except
            log.debug("topology: _fire_event failed for %s", tag, exc_info=True)

    router._fire_event = _fire  # pylint: disable=protected-access
    _FIRE_EVENT = _fire
    _EVENT_BUS = event


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
    # Wire the router's ``_fire_event`` hook onto the publish daemon's
    # master event bus.  The default implementation in
    # :meth:`TopologyRouter._fire_event` logs a WARNING ("no event bus
    # wired") because the router module is import-safe for test
    # harnesses that run without a loop.  Here in the real daemon we
    # DO have a loop and a ``master_event_pull.ipc`` reachable, so
    # install a fire function that pushes ``salt/topology/pub/failed/*``
    # (and future router-side events) onto the real bus where the viz
    # backend and :mod:`salt.engines.topology_events` subscribers can
    # consume them.  Falls back to the sync fire path when no running
    # loop is detected, mirroring ``_fire_event_on_running_loop`` in
    # :class:`salt.master.ClearFuncs`.
    _wire_router_fire_event(_topology_router, opts, io_loop)
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

    # Step 9: topology-return subscriber.  Bridges the MWorker's
    # ``salt/topology/return/<origin>/<jid>`` event (fired by
    # :meth:`salt.master.AESFuncs._maybe_fire_topology_return` when a
    # local minion returns for a jid that we forwarded from an
    # inbound peer) to the outbound ``topology/ret`` RPC via the
    # :class:`PeerMasterLink.send_return` method of the breadcrumbed
    # upstream link.  Without this subscriber the forwarded publish
    # loop never closes: edges store returns locally but no hop
    # propagates them back toward origin.
    try:
        _start_return_subscriber(opts, io_loop)
    except Exception:  # pylint: disable=broad-except
        log.exception("topology: return-subscriber bootstrap failed")

    # Step 10: periodic ``topology/sum`` emission.  Routes in each
    # peer's :class:`salt.topology.router.TopologyRouter` are built
    # from inbound summaries; without a local emission loop the
    # routing table stays empty and non-adjacent ``C@`` publishes
    # fall back to ``route_publish flooding --- no known route``.
    # Peers tolerate send failures (link not yet healthy, transient
    # transport flap) so the loop keeps going.
    global _SUMMARY_TASK, _RECONNECT_TASK
    _SUMMARY_TASK = asyncio.ensure_future(_summary_emit_loop(opts), loop=io_loop)

    # Step 11: periodic reconnect sweep.  Walks ``_LINKS`` on a short
    # cadence and re-handshakes any outbound link that
    # :meth:`PeerMasterLink._handle_send_fault` has transitioned to
    # DEGRADED (or any that remained DISCONNECTED after a bounded
    # connect retry).  Without this, a REQ-channel wedge after one
    # send timeout pins the link until the master restarts.
    _RECONNECT_TASK = asyncio.ensure_future(_reconnect_loop(opts), loop=io_loop)


async def _summary_emit_loop(opts):
    """
    Build a local :class:`salt.topology.summary.ClusterSummary` on
    every ``topology_summary_interval`` tick and push it to every
    attached peer link.

    First iteration runs with a short bootstrap delay so routes
    populate well before any ``C@<peer>`` publish fires -- without
    this, the first full interval (30s default) wait would make
    every topology-forward CLI call see
    ``route_publish flooding --- no known route`` and fail to
    route to any transit destination.

    Resilient:

    * Catches exceptions from :func:`summary_mod.collect` so a
      transient opts/pki hiccup doesn't kill the loop.
    * Catches per-link send errors so one unhealthy peer doesn't
      block emission to the others.
    """
    interval = float(opts.get("topology_summary_interval", 30) or 30)
    # Bootstrap delay: short enough that routes populate before the
    # first forward publish, long enough that outbound links have had
    # a chance to complete their handshake and transition to
    # CONNECTED (send_summary on a not-yet-CONNECTED link raises).
    bootstrap_delay = min(2.0, interval)
    cluster_id = opts.get("cluster_id") or ""
    first = True
    while True:
        await asyncio.sleep(bootstrap_delay if first else interval)
        first = False
        try:
            summary = summary_mod.collect(opts)
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "topology: summary collect failed for cluster_id=%r", cluster_id
            )
            continue
        # Snapshot the link set so a concurrent attach/detach does
        # not perturb iteration.
        links = list(_LINKS.items())
        for peer_id, link in links:
            try:
                await asyncio.wait_for(
                    link.send_summary(summary),
                    timeout=_TOPOLOGY_AWAIT_TIMEOUT,
                )
            except Exception:  # pylint: disable=broad-except
                log.debug(
                    "topology: summary emit to peer=%r failed",
                    peer_id,
                    exc_info=True,
                )


#: Interval between reconnect sweeps.  Short enough that a wedged
#: link recovers inside the operator-visible lifecycle of a single
#: ``salt`` CLI publish (default 60s overall master publish timeout),
#: long enough that the sweeper is cheap when every link is healthy.
_RECONNECT_INTERVAL = 5.0


async def _reconnect_loop(opts):
    """Re-handshake outbound links whose channels have been torn down.

    A :meth:`salt.topology.link.PeerMasterLink._handle_send_fault`
    transitions the link to :data:`LinkHealth.DEGRADED` and nulls the
    REQ channel after a send failure.  Without this loop, the link
    stays DEGRADED until the master restarts: no code path drives
    ``link.connect()`` after startup except ``add_link`` (fires on
    attach, not on fault) and the handshake retry inside
    :meth:`connect` itself.

    Walks ``_LINKS`` every :data:`_RECONNECT_INTERVAL` seconds; for
    any link whose health is DEGRADED or DISCONNECTED (and which is
    not currently in CONNECTING), schedules a fresh
    ``_connect_and_register`` task.  The connect task is fire-and-
    forget: a wedged peer will still time out, but on its own
    coroutine so it does not stall the sweeper.
    """
    while True:
        await asyncio.sleep(_RECONNECT_INTERVAL)
        try:
            from salt.topology.link import (
                LinkHealth,  # pylint: disable=import-outside-toplevel
            )

            # Snapshot before iteration so a concurrent attach/detach
            # does not perturb the walk.
            with _LOCK:
                snapshot = list(_LINKS.items())
            for key, link in snapshot:
                health = getattr(link, "health", None)
                if isinstance(key, str) and key.startswith("__pending__:"):
                    # Provisional key: the first-connect task may have
                    # finished and left the link in DISCONNECTED or
                    # PENDING_ACCEPT without ever learning the peer's
                    # cluster_id (so no re-key under _register_connected_link
                    # ran).  Skip only while the connect is actively mid-
                    # flight (CONNECTING); otherwise the link stays wedged
                    # under its provisional key forever.
                    if health == LinkHealth.CONNECTING:
                        continue
                if health in (
                    LinkHealth.DEGRADED,
                    LinkHealth.DISCONNECTED,
                    LinkHealth.PENDING_ACCEPT,
                ):
                    log.info(
                        "topology: scheduling re-handshake for peer=%r "
                        "(health=%r, send_fault_count=%d)",
                        getattr(link, "peer_cluster_id", None),
                        health,
                        getattr(link, "send_fault_count", 0),
                    )
                    try:
                        asyncio.ensure_future(_connect_and_register(link))
                    except Exception:  # pylint: disable=broad-except
                        log.exception(
                            "topology: scheduling reconnect for peer=%r failed",
                            getattr(link, "peer_cluster_id", None),
                        )
        except Exception:  # pylint: disable=broad-except
            # Never let the sweeper die; a single bad link should not
            # take out recovery for every other peer.
            log.exception("topology: reconnect sweep raised; continuing")


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

    Also pushes an initial ``topology/sum`` to the peer so its
    routing table learns the way back to this cluster without
    waiting for the next periodic emission.  Without this immediate
    push, a ``C@<peer>`` CLI publish that fires within the first
    ``topology_summary_interval`` after handshake arrives at the
    other side's router with an empty route table and falls back to
    ``route_publish flooding --- no known route``.

    Split out so :func:`_schedule_connect` keeps its "fire and
    forget" shape while the post-handshake wiring stays
    single-sourced.
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
    # First summary push: immediately so routes populate before any
    # user-driven ``C@<peer>`` publish.  Guard with a short timeout
    # so a transient slow peer doesn't block the connect task.
    try:
        summary = summary_mod.collect(_OPTS or {})
        await asyncio.wait_for(
            link.send_summary(summary),
            timeout=_TOPOLOGY_AWAIT_TIMEOUT,
        )
    except Exception:  # pylint: disable=broad-except
        log.debug(
            "topology: initial summary emit to %r failed",
            getattr(link, "peer_cluster_id", None),
            exc_info=True,
        )


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
        # Bypass the ``_cluster_is_ready`` gate at
        # :func:`salt.channel.server.ReqServerChannel.handle_message`.
        # That gate exists for minion/CLI traffic that depends on Raft
        # state --- a publish, a key accept, a jid lookup.  Topology peer
        # handshake has NO such dependency: it is a key-on-disk identity
        # exchange that runs before Raft committed state is relevant and
        # that must work on a brand-new cluster whose Raft is still
        # forming consensus.  Zeroing ``cluster_peers`` in the listener's
        # channel-opts dict makes the gate short-circuit to True via its
        # "no cluster_peers -> non-cluster master" branch, so inbound
        # ``topology/_master_auth`` reaches our dispatch table instead
        # of being replied-to with ``cluster_retry`` and never
        # progressing past PENDING_ACCEPT.
        channel_opts["cluster_peers"] = []
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


def _start_return_subscriber(opts, io_loop):
    """Open a master-event subscriber for ``salt/topology/return/*``.

    The MWorker that processes a ``_return`` from a locally-attached
    minion fires ``salt/topology/return/<origin>/<jid>`` on the
    master event bus when the jid belongs to a publish forwarded
    from an inbound peer (see
    :meth:`salt.master.AESFuncs._maybe_fire_topology_return`).  This
    subscriber owns the next hop: it looks up the breadcrumb for
    ``jid`` to find the upstream peer and calls
    :meth:`PeerMasterLink.send_return` on that link.  On the receiving
    master the inbound ``topology/ret`` dispatch
    (:func:`_dispatch_ret`) stores or forwards the return based on
    its own origin-check -- so the hop chain continues until the
    origin terminates it.
    """
    global _RETURN_SUBSCRIBER
    event_bus = salt.utils.event.get_master_event(
        opts, opts.get("sock_dir"), io_loop=io_loop, listen=True
    )
    event_bus.subscribe("salt/topology/return", match_type="startswith")
    # ``set_event_handler`` wraps the callback with
    # :func:`asyncio.ensure_future` which expects a coroutine, so pass
    # the async def directly rather than a lambda that pre-schedules
    # a Task.
    event_bus.set_event_handler(_handle_topology_return_event)
    _RETURN_SUBSCRIBER = event_bus


async def _handle_topology_return_event(package):
    """Forward a ``salt/topology/return/<origin>/<jid>`` event upstream.

    Called from the subscriber installed in
    :func:`_start_return_subscriber`.  Looks up the breadcrumb for
    the jid and sends the return load via that link's
    :meth:`PeerMasterLink.send_return`.
    """
    try:
        tag, data = salt.utils.event.SaltEvent.unpack(package)
    except Exception:  # pylint: disable=broad-except
        log.exception("topology: unpack failed for topology-return event")
        return
    if not tag.startswith("salt/topology/return/"):
        return
    load = (data or {}).get("load")
    if not isinstance(load, dict):
        return
    jid = load.get("jid")
    if not jid:
        return
    router = router_mod.get_router()
    if router is None:
        return
    try:
        upstream = router.route_return(load)
    except Exception:  # pylint: disable=broad-except
        log.exception("topology: route_return raised for jid=%r", jid)
        return
    if upstream is None:
        log.debug(
            "topology: no breadcrumb for jid=%r at return-subscriber -- "
            "either origin or breadcrumb expired",
            jid,
        )
        return
    try:
        if not router.forward_return_once(load):
            return
    except Exception:  # pylint: disable=broad-except
        log.exception("topology: forward_return_once raised for jid=%r", jid)
    try:
        await asyncio.wait_for(
            upstream.send_return([load], [router.cluster_id]),
            timeout=_TOPOLOGY_AWAIT_TIMEOUT,
        )
    except asyncio.TimeoutError:
        log.warning(
            "topology: send_return to upstream=%r timed out for jid=%r "
            "after %ss; recovering loop",
            getattr(upstream, "peer_cluster_id", None),
            jid,
            _TOPOLOGY_AWAIT_TIMEOUT,
        )
    except Exception:  # pylint: disable=broad-except
        log.exception(
            "topology: send_return to upstream=%r failed for jid=%r",
            getattr(upstream, "peer_cluster_id", None),
            jid,
        )


async def stop():
    """
    Shut down the topology subsystem at process exit.

    Closes the inbound listener, disconnects every outbound
    link, and clears all registries.  Idempotent; safe to call
    multiple times.
    """
    # Cancel the periodic summary emitter before tearing down links
    # so an in-flight ``send_summary`` doesn't race the disconnect.
    global _SUMMARY_TASK, _RECONNECT_TASK
    if _SUMMARY_TASK is not None:
        _SUMMARY_TASK.cancel()
        try:
            await _SUMMARY_TASK
        except (asyncio.CancelledError, Exception):  # pylint: disable=broad-except
            pass
        _SUMMARY_TASK = None
    if _RECONNECT_TASK is not None:
        _RECONNECT_TASK.cancel()
        try:
            await _RECONNECT_TASK
        except (asyncio.CancelledError, Exception):  # pylint: disable=broad-except
            pass
        _RECONNECT_TASK = None

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
    if _RETURN_SUBSCRIBER is not None:
        close = getattr(_RETURN_SUBSCRIBER, "close", None)
        if close is not None:
            try:
                close()
            except Exception:  # pylint: disable=broad-except
                log.debug(
                    "topology stop: return subscriber close failed",
                    exc_info=True,
                )
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

    # Return-shaped inbound: decide origin vs transit.  Origin is
    # the master that originally issued the publish; it is the only
    # cluster that has the jid materialized in its local job cache
    # (``.load.p`` / ``.minions.p`` under
    # ``<cachedir>/jobs/<hash>/``).  Transit clusters never see the
    # publish go through their own ``publish`` runner so no files
    # exist for them.
    #
    # Why not use :meth:`route_return` alone: a breadcrumb-based test
    # is unreliable at the origin because the FIRST return that
    # arrives falls through to :meth:`forward_publish`, which writes
    # a breadcrumb (jid -> inbound) as part of its normal
    # bookkeeping.  Subsequent returns for the same jid would then
    # look up as "transit" and get forwarded back to the sender --
    # breaking fan-in.  The on-disk origin test is monotonic and
    # cannot be perturbed by inbound traffic.
    if isinstance(load, dict) and _looks_like_minion_return(load):
        if _jid_is_local_origin(load.get("jid")):
            # Origin: store locally, skip forward_publish so we
            # don't fan the return to our other peers (who have no
            # interest in it).  Offload to a thread -- the inner
            # ``store_job`` does synchronous disk I/O.
            try:
                await _store_forwarded_return_offload(load)
            except Exception:  # pylint: disable=broad-except
                log.exception(
                    "topology: store_job for forwarded return failed for jid=%r",
                    load.get("jid"),
                )
            return [], True
        # Transit: use the breadcrumb to find the upstream peer and
        # forward the return one hop closer to origin.
        upstream = None
        try:
            upstream = router.route_return(load)
        except Exception:  # pylint: disable=broad-except
            log.exception("topology: route_return raised for jid=%r", load.get("jid"))
        if upstream is not None:
            try:
                first_time = router.forward_return_once(load)
            except Exception:  # pylint: disable=broad-except
                log.exception(
                    "topology: forward_return_once raised for jid=%r",
                    load.get("jid"),
                )
                first_time = True
            if first_time:
                try:
                    await asyncio.wait_for(
                        upstream.send_publish(load, [router.cluster_id]),
                        timeout=_TOPOLOGY_AWAIT_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    log.warning(
                        "topology: upstream return forward to %r timed out "
                        "for jid=%r after %ss; recovering loop",
                        getattr(upstream, "peer_cluster_id", None),
                        load.get("jid"),
                        _TOPOLOGY_AWAIT_TIMEOUT,
                    )
                except Exception:  # pylint: disable=broad-except
                    log.exception(
                        "topology: upstream return forward failed for jid=%r",
                        load.get("jid"),
                    )
            # Transit path: do NOT also run forward_publish (which
            # would write a breadcrumb into this inbound link and
            # replay the return on the local returner).
            return [upstream], False

    try:
        result = router.forward_publish(load, inbound_link)
    except Exception:  # pylint: disable=broad-except
        log.exception("topology: forward_publish raised")
        return None
    if not isinstance(result, tuple) or len(result) != 2:
        # Legacy / fake router: nothing to do with local_match.
        return result
    links, local_match = result
    # Resolve the local-match set BEFORE dispatching to local minions so
    # the topology/pub-ack frame (see
    # doc/topics/master-topology/rfc-pub-ack-complete.md) carries the
    # exact minion-id list the peer will publish to.  The RFC requires
    # the ack to precede any return the acked peer could emit; firing
    # before ``_publish_to_local_minions`` satisfies that invariant.
    # Gated on ``topology_pub_ack`` opt (default True); peers running
    # without the feature simply don't send the ack and the originator
    # falls back to pre-RFC silent-inference behavior.
    matched_for_ack = None
    if (
        local_match
        and isinstance(load, dict)
        and load.get("jid")
        and not _looks_like_minion_return(load)
        and (_OPTS or {}).get("topology_pub_ack", True)
        and inbound_link is not None
    ):
        try:
            loop = asyncio.get_event_loop()
            matched_for_ack = await loop.run_in_executor(
                None, _resolve_local_match, load
            )
        except Exception:  # pylint: disable=broad-except
            log.debug(
                "topology: pub-ack local-match resolution failed for jid=%r",
                load.get("jid"),
                exc_info=True,
            )
            matched_for_ack = []
        envelope = load.get("topology") or {}
        path_list = envelope.get("path") or []
        # ``forward_publish`` appends self to the authenticated path, so
        # path[0] is the originator.  Fall back to envelope.origin for
        # legacy senders that pre-date the authenticated-path append.
        target_cluster_id = path_list[0] if path_list else envelope.get("origin")
        if target_cluster_id:
            try:
                # Schedule + yield once so the pub-ack coroutine takes its
                # first synchronous step (health-gate + envelope build +
                # ``AsyncReqChannel.send`` kickoff) BEFORE the awaited
                # :func:`_publish_to_local_minions` begins its IPC fan-out.
                # The RFC requires the ack to precede any return from this
                # peer; yielding here guarantees the ack has at least begun
                # its wire send before local minions can execute, without
                # blocking the dispatcher on the remote ack delivery.
                asyncio.ensure_future(
                    _send_pub_ack_fire_and_forget(
                        inbound_link,
                        load.get("jid"),
                        target_cluster_id,
                        matched_for_ack,
                        router.cluster_id,
                    )
                )
                await asyncio.sleep(0)
            except Exception:  # pylint: disable=broad-except
                log.debug(
                    "topology: pub-ack schedule failed for jid=%r",
                    load.get("jid"),
                    exc_info=True,
                )
            # Phase 1.5: spawn the per-jid return collector that will emit
            # ``topology/pub-complete`` once every ack'd minion returns
            # (or on local timeout, whichever comes first).  The spawn
            # happens AFTER the pub-ack is scheduled so the originator
            # sees the ack before the complete.  See RFC pub-ack-complete
            # "topology/pub-complete" wire section.
            try:
                _spawn_pub_complete_collector(
                    load.get("jid"),
                    matched_for_ack,
                    inbound_link,
                    [router.cluster_id] if router.cluster_id else None,
                )
            except Exception:  # pylint: disable=broad-except
                log.debug(
                    "topology: pub-complete collector spawn failed for jid=%r",
                    load.get("jid"),
                    exc_info=True,
                )

    if local_match and isinstance(load, dict):
        # Origin side of the return path (``route_return`` returned
        # ``None`` above -- no breadcrumb points upstream because this
        # master issued the publish).  Writing to the local returner
        # here is what makes the ``salt`` CLI's ``local_cache`` poll
        # see the forwarded minion return.  Native publishes (no
        # ``return`` key) continue to flow to local minions via
        # :func:`_publish_to_local_minions`.
        if _looks_like_minion_return(load):
            try:
                await _store_forwarded_return_offload(load)
            except Exception:  # pylint: disable=broad-except
                log.exception(
                    "topology: store_job for forwarded return failed for jid=%r",
                    load.get("jid"),
                )
        else:
            try:
                await _publish_to_local_minions(load, matched=matched_for_ack)
            except Exception:  # pylint: disable=broad-except
                log.exception(
                    "topology: local-minion publish failed for forwarded jid=%r",
                    load.get("jid"),
                )
    # Transit fan-out: ``forward_publish`` returned a list of further
    # peer links (destinations minus inbound, flood-mode minus self);
    # we are the only code path that can propagate the publish beyond
    # this hop.  Without this, a 3-hop topology (east -> west ->
    # west-sub) stalls at west: west publishes to its local minions
    # and acks the REQ, but west-sub never sees the publish because
    # :func:`salt.topology.router.on_publish` only runs on the ORIGIN
    # master's :meth:`publish_payload`.  Native publishes only (not
    # minion-return frames -- those are handled by the return-shaped
    # short-circuit above) and only when ``jid`` is present (filters
    # out non-publish event forwards like key events).
    #
    # Scheduling: fire-and-forget via ``create_task`` so the REP
    # handler acks the inbound REQ without waiting for each outbound
    # ``send_publish`` to complete.  A slow or disconnected further
    # peer would otherwise serialize behind this handler and wedge
    # the receiver side of the publish fan for all other inbound
    # traffic.
    if (
        links
        and isinstance(load, dict)
        and load.get("jid")
        and not _looks_like_minion_return(load)
    ):
        cluster_id = router.cluster_id

        async def _transit_send(_link, _load):
            try:
                await asyncio.wait_for(
                    _link.send_publish(_load, [cluster_id]),
                    timeout=_TOPOLOGY_AWAIT_TIMEOUT,
                )
            except asyncio.TimeoutError:
                log.warning(
                    "topology: transit send_publish to peer=%r timed out "
                    "for jid=%r after %ss; dropping forward",
                    getattr(_link, "peer_cluster_id", None),
                    _load.get("jid") if isinstance(_load, dict) else None,
                    _TOPOLOGY_AWAIT_TIMEOUT,
                )
            except Exception:  # pylint: disable=broad-except
                log.exception(
                    "topology: transit forward to peer=%r failed for jid=%r",
                    getattr(_link, "peer_cluster_id", None),
                    _load.get("jid"),
                )

        for link in links:
            try:
                asyncio.ensure_future(_transit_send(link, load))
            except Exception:  # pylint: disable=broad-except
                log.exception(
                    "topology: transit scheduling to peer=%r failed",
                    getattr(link, "peer_cluster_id", None),
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


def _jid_is_local_origin(jid):
    """Return True when this master originated ``jid``.

    Checked by *absence* of a breadcrumb for the jid.
    :meth:`TopologyRouter.forward_publish` records a breadcrumb for
    every publish received from a peer, pointing at the inbound
    link.  The ORIGIN never calls ``forward_publish`` for its own
    jid (its publish goes out via :func:`route_publish` which does
    not write breadcrumbs), so lookup returns ``None`` there.

    Correctness depends on return-shaped frames NOT falling through
    to :meth:`forward_publish` (which would spuriously write a
    breadcrumb into the inbound link on origin and flip subsequent
    returns onto the transit path).  The caller in
    :func:`_dispatch_pub` short-circuits before that happens; see
    the comment there.
    """
    if not jid:
        return False
    router = router_mod.get_router()
    if router is None:
        return False
    try:
        return router.lookup_breadcrumb(jid) is None
    except Exception:  # pylint: disable=broad-except
        return False


_MMINION_CACHE = None


async def _store_forwarded_return_offload(load):
    """Run :func:`_store_forwarded_return` on the default executor.

    ``store_job`` + ``save_minions`` both perform synchronous disk I/O
    (atomic write with ``os.fsync`` + ``os.rename``) that, when called
    directly from the publish daemon's single-threaded ``asyncio``
    event loop, blocks the IPC pull-socket reader from picking up
    further publishes.  Under rapid-fire load those blocking windows
    accumulate into multi-minute stalls where new publishes queue
    on ``publish_pull.ipc`` but the daemon never wakes up to
    service them.  Offloading to a thread lets the loop stay
    responsive while the disk write completes in the background.
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _store_forwarded_return, load)


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


async def _publish_to_local_minions(load, matched=None):
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

    Also pre-seeds the local ``local_cache`` job dir with
    ``.load.p`` + ``.minions.p``.  Rationale:
    :meth:`salt.channel.server.PubServerChannel.publish` is a pure
    transport write; it does not run
    :meth:`salt.master.ClearFuncs.publish`'s ``save_load`` path, so
    on a transit master the forwarded publish lands with NO cache
    files.  The first local minion's ``_return`` then triggers
    :func:`salt.utils.job.store_job`, which calls
    :func:`salt.returners.local_cache.save_load` -- but ``save_load``
    only calls :func:`save_minions` when ``load["tgt"]`` is set,
    which is NOT the case for a minion-return load.  Result: a
    narrow race where the first return writes ``.load.p`` without
    ``.minions.p``, and the second concurrent return's ``get_load``
    sees ``.load.p`` present, tries to read ``.minions.p``, and
    crashes with ``CommandExecutionError`` which bubbles out of
    MWorker's ``_return`` handler, skipping the subsequent
    ``_maybe_fire_topology_return`` call.  Pre-seeding here ensures
    ``.minions.p`` exists before any return arrives.

    :param matched: Optional pre-resolved local matched-minion list.
        When the caller has already run :func:`_resolve_local_match`
        (e.g. :func:`_dispatch_pub` resolving ahead of a pub-ack
        emission), it passes the result in so the seed path reuses
        the same list instead of re-running ``check_minions``.
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
    # Offload the seed to a thread.  ``CkMinions.check_minions`` scans
    # the PKI directory and ``save_load`` does fsync + atomic rename;
    # both are synchronous disk I/O that blocks the publish daemon's
    # io_loop and starves the IPC pull-socket reader under load.
    try:
        loop = asyncio.get_event_loop()
        seeded = await loop.run_in_executor(
            None, _seed_local_cache_for_forwarded_publish, stripped, matched
        )
    except Exception:  # pylint: disable=broad-except
        log.debug("topology: seed_local_cache offload failed", exc_info=True)
        seeded = None
    # Prefer the caller-supplied list so the event payload reflects the
    # same set that was reported in pub-ack; fall back to the on-disk
    # seed result when the caller did not pre-resolve.
    if matched is None:
        matched = seeded
    # Announce the forwarded publish on the LOCAL master event bus so
    # reactors, returners, and metrics exporters that key off new-job
    # or publish-job events see it on THIS receiving master too.
    # ``_prep_pub`` fires ``salt/job/<jid>/new`` and ``ClearFuncs.publish``
    # fires ``salt/job/<jid>/publish`` on the origin master; the forward
    # path otherwise bypasses both (``chan.publish`` is a raw IPC write).
    # Mirror origin ordering: ``new`` first, then ``publish``, both
    # before the wire write.  Fire unconditionally (even on empty
    # ``matched``) to match ``_prep_pub``'s behavior.
    #
    # NOTE: ``ext_job_cache.save_load`` is also invoked on the origin
    # path (``salt/master.py:5987-6022``) but is NOT yet mirrored here;
    # tracked as a follow-up (returner-loader + argspec probe).
    jid = stripped.get("jid")
    if jid:
        new_job_load = {
            "jid": jid,
            "tgt": stripped.get("tgt"),
            "tgt_type": stripped.get("tgt_type"),
            "fun": stripped.get("fun"),
            "arg": stripped.get("arg"),
            "user": stripped.get("user", "topology-forward"),
            "minions": matched if isinstance(matched, list) else [],
            "missing": [],
        }
        new_tag = salt.utils.event.tagify([jid, "new"], "job")
        pub_tag = salt.utils.event.tagify([jid, "publish"], "job")
        # Prefer awaiting ``fire_event_async`` sequentially on the cached
        # bus: two independent ``create_task`` calls on the same pusher
        # race on ``connect_pull`` and can silently drop one of the
        # writes on ``master_event_pull.ipc``.  Sequential await also
        # guarantees that any subscriber ordering ``new`` -> ``publish``
        # matches the origin master.  Fall back to the sync
        # ``_FIRE_EVENT`` hook when the cached bus isn't wired (test
        # harness without a ``sock_dir``).
        if _EVENT_BUS is not None:
            try:
                await _EVENT_BUS.fire_event_async(new_job_load, new_tag)
                await _EVENT_BUS.fire_event_async(new_job_load, pub_tag)
            except Exception:  # pylint: disable=broad-except
                log.debug(
                    "topology: fire salt/job/<jid>/{new,publish} async for "
                    "forwarded publish failed",
                    exc_info=True,
                )
        elif _FIRE_EVENT is not None:
            try:
                _FIRE_EVENT(new_tag, new_job_load)
                _FIRE_EVENT(pub_tag, new_job_load)
            except Exception:  # pylint: disable=broad-except
                log.debug(
                    "topology: fire salt/job/<jid>/{new,publish} for forwarded "
                    "publish failed",
                    exc_info=True,
                )
    # Reuse a cached per-transport :class:`PubServerChannel` -- do NOT
    # construct a fresh one per publish.  The transport's PUSH socket
    # that writes to ``publish_pull.ipc`` sets ``zmq.LINGER=1`` (one
    # millisecond, see ``salt/transport/zeromq.py`` PublishServer.connect).
    # A transient channel garbage-collected between publishes closes its
    # PUSH socket with that 1 ms grace window, and under rapid-fire load
    # any un-flushed queued message is **silently discarded** when the
    # pub-daemon's PULL reader doesn't drain within the window.  This
    # manifests as a per-master "chan.publish returned OK but minions
    # never executed" flake, where the entire local minion set misses the
    # publish.  Caching keeps the PUSH socket open for the lifetime of
    # the pub-daemon, so LINGER=1 never applies.
    for transport, opts in salt.utils.channel.iter_transport_opts(_OPTS or {}):
        chan = _get_cached_pub_channel(transport, opts)
        try:
            await chan.publish(stripped)
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "topology: PubServerChannel.publish failed on transport %r",
                transport,
            )


#: Cache of per-transport long-lived :class:`PubServerChannel` instances
#: used by :func:`_publish_to_local_minions`.  See the comment there for
#: why reusing matters.
_PUB_CHANNEL_CACHE = {}


def _get_cached_pub_channel(transport, opts):
    """Return a cached :class:`PubServerChannel` for *transport*.

    First call per transport constructs via ``factory(opts)``; subsequent
    calls return the cached instance.  The channel's underlying PUSH
    socket to ``publish_pull.ipc`` therefore stays open across publishes,
    bypassing the ``LINGER=1`` close-time discard window.
    """
    chan = _PUB_CHANNEL_CACHE.get(transport)
    if chan is None:
        import salt.channel.server  # pylint: disable=import-outside-toplevel

        chan = salt.channel.server.PubServerChannel.factory(opts)
        _PUB_CHANNEL_CACHE[transport] = chan
    return chan


def _seed_local_cache_for_forwarded_publish(load, matched=None):
    """Write ``.load.p`` + ``.minions.p`` for a forwarded publish jid.

    Returns the resolved local matched-minion list (possibly empty) so
    the caller can fire ``salt/job/<jid>/new`` with the same set of
    minions that was persisted to ``.minions.p``.  Returns ``None`` if
    the seed was skipped (no ``_OPTS``, no jid, bad shape).

    See the extended comment in :func:`_publish_to_local_minions` for
    the exact race this closes.  Writes the local-cache artifacts the
    same way :func:`salt.returners.local_cache.save_load` would, so
    the subsequent MWorker ``_return`` path treats this jid as an
    already-recorded publish and skips the ``save_load`` branch that
    races on ``.minions.p``.

    :param matched: Optional pre-resolved local matched-minion list.
        When the caller has already computed the match (e.g. the
        topology/pub-ack emission path in :func:`_dispatch_pub` resolves
        the match before dispatching so the ack carries the exact list),
        pass the same list in here so we persist the same set to
        ``.minions.p`` instead of re-running ``check_minions``.
    """
    global _MMINION_CACHE
    if _OPTS is None or not isinstance(load, dict):
        return None
    jid = load.get("jid")
    if not jid:
        return None
    try:
        if _MMINION_CACHE is None:
            import salt.minion  # pylint: disable=import-outside-toplevel

            _MMINION_CACHE = salt.minion.MasterMinion(_OPTS, states=False, rend=False)
        job_cache = _OPTS.get("master_job_cache", "local_cache")
        save_load_fn = _MMINION_CACHE.returners.get(f"{job_cache}.save_load")
        if save_load_fn is None:
            return None
        if matched is None:
            import salt.utils.minions  # pylint: disable=import-outside-toplevel

            # Resolve the local matched minions for this master so the
            # on-disk ``.minions.p`` reflects just the minions that THIS
            # master actually published to (the ones that will later
            # issue ``_return``).  Peer-master minions are routed via
            # their own masters' cache files.
            ckminions = salt.utils.minions.CkMinions.factory(_OPTS)
            resolved = ckminions.check_minions(
                load.get("tgt"), load.get("tgt_type", "glob")
            )
            matched = resolved.get("minions") if isinstance(resolved, dict) else None
        try:
            save_load_fn(jid, load, minions=matched)
        except TypeError:
            save_load_fn(jid, load)
        return matched if isinstance(matched, list) else []
    except Exception:  # pylint: disable=broad-except
        log.debug(
            "topology: seed_local_cache_for_forwarded_publish failed for jid=%r",
            jid,
            exc_info=True,
        )
        return None


async def _send_pub_ack_fire_and_forget(
    inbound_link, jid, target_cluster_id, matched, own_cluster_id
):
    """Send a ``topology/pub-ack`` upstream with fault isolation.

    Wraps :meth:`salt.topology.link.PeerMasterLink.send_pub_ack` with a
    bounded :func:`asyncio.wait_for` and broad exception handling so a
    wedged peer does not stall the dispatch coroutine.  Fire-and-forget
    per RFC: if the ack never reaches the originator, the originator's
    loop simply falls back to the pre-RFC timeout-based completion
    path.

    :param inbound_link: The link we received the publish on; the ack
        travels back up this hop.
    :param jid: The publish's jid.
    :param target_cluster_id: The originator cluster (path[0]).
    :param matched: The exact minion-id list the peer will publish to.
    :param own_cluster_id: This cluster's cluster_id, used as the ack
        frame's single-entry path (this master is the first hop).
    """
    try:
        await asyncio.wait_for(
            inbound_link.send_pub_ack(
                jid,
                target_cluster_id,
                matched,
                path=[own_cluster_id] if own_cluster_id else None,
            ),
            timeout=_TOPOLOGY_AWAIT_TIMEOUT,
        )
    except asyncio.TimeoutError:
        log.warning(
            "topology: send_pub_ack to upstream=%r timed out for jid=%r "
            "after %ss; originator falls back to silent-inference",
            getattr(inbound_link, "peer_cluster_id", None),
            jid,
            _TOPOLOGY_AWAIT_TIMEOUT,
        )
    except Exception:  # pylint: disable=broad-except
        log.debug(
            "topology: send_pub_ack to upstream=%r failed for jid=%r",
            getattr(inbound_link, "peer_cluster_id", None),
            jid,
            exc_info=True,
        )


def _spawn_pub_complete_collector(jid, expected_minions, inbound_link, path):
    """Spawn a per-jid return collector that emits ``topology/pub-complete``.

    Called from :func:`_dispatch_pub` immediately after the pub-ack is
    scheduled, so the collector exists before local returns can start
    arriving.  Design points (Phase 1.5 of RFC pub-ack-complete):

    * **Empty match path**: when ``expected_minions`` is empty the peer
      had zero local matches.  Emit pub-complete immediately on the
      current event loop (no collector task).  The originator needs this
      to distinguish "zero match" from "peer unreachable" the same way
      pub-ack does.
    * **Enabled opt**: honours ``opts["topology_pub_complete_enabled"]``
      (default True).  When False the spawn is a silent no-op; the
      originator falls back to pre-RFC silence-mode on ``--timeout``.
    * **Bounded in-flight**: caps concurrent collectors at
      ``opts["topology_pub_complete_max_inflight"]`` (default 1024).
      Over-cap jids are logged at WARNING and skipped -- they get the
      same silence-mode fallback as a disabled peer.  Prevents a publish
      flood from leaking Task objects when returns are slow.
    * **Idempotent per jid**: a second call for the same jid is a no-op
      (the first collector owns that jid's completion).

    :param jid: The publish's jid.
    :param expected_minions: List (or set) of minion ids the pub-ack
        promised.  ``returned ^ missed == set(expected_minions)``
        invariant at emit time.
    :param inbound_link: The link we received the publish on; the
        complete frame travels back up this hop, same as the ack did.
    :param path: Optional path list to carry on the complete envelope;
        defaults to this cluster's single-entry id list.
    """
    if _OPTS is None:
        return
    if not _OPTS.get("topology_pub_ack", True):
        # Phase 1 gate also turns off the collector: the originator
        # cannot consume complete without ack, so suppressing both
        # keeps the mixed-deployment story clean.
        return
    if not _OPTS.get("topology_pub_complete_enabled", True):
        return
    if not jid or inbound_link is None:
        return
    expected = set(expected_minions or [])
    # Empty-match fast path.  The RFC explicitly requires an empty ack +
    # complete pair so the originator can distinguish "peer had no local
    # match" from "peer unreachable".  Emit synchronously on the current
    # loop; no task bookkeeping needed.
    if not expected:
        try:
            asyncio.ensure_future(
                _emit_pub_complete_once(
                    inbound_link,
                    jid,
                    returned=[],
                    missed=[],
                    path=path,
                )
            )
        except Exception:  # pylint: disable=broad-except
            log.debug(
                "topology: empty-match pub-complete emit failed for jid=%r",
                jid,
                exc_info=True,
            )
        return
    # Enforce max-inflight.  Check against the current task count, not
    # the size of the dict post-insert, so the cap is a hard ceiling
    # rather than a "cap+1" soft limit.
    max_inflight = int(_OPTS.get("topology_pub_complete_max_inflight", 1024) or 1024)
    if len(_PUB_COMPLETE_COLLECTORS) >= max_inflight:
        log.warning(
            "topology: pub-complete collector in-flight cap reached "
            "(max=%d); skipping spawn for jid=%r -- originator will "
            "fall back to --timeout",
            max_inflight,
            jid,
        )
        return
    # Idempotency: a second spawn for the same jid is a no-op.  Could
    # happen if a peer re-dispatches a publish mid-collection (shouldn't,
    # but defense in depth).
    if jid in _PUB_COMPLETE_COLLECTORS:
        return
    timeout_s = float(_OPTS.get("topology_pub_complete_timeout", 60.0) or 60.0)
    try:
        task = asyncio.ensure_future(
            _collect_and_emit_pub_complete(jid, expected, inbound_link, path, timeout_s)
        )
    except Exception:  # pylint: disable=broad-except
        log.debug(
            "topology: pub-complete collector task ensure_future failed jid=%r",
            jid,
            exc_info=True,
        )
        return
    _PUB_COMPLETE_COLLECTORS[jid] = task


async def _emit_pub_complete_once(inbound_link, jid, returned, missed, path):
    """Send a single ``topology/pub-complete`` frame with fault isolation.

    Thin wrapper around :meth:`PeerMasterLink.send_pub_complete` that
    swallows DISCONNECTED (``LinkUnavailable``) and bounded timeouts so
    a collector never raises into the io_loop.  The frame is fire-and-
    forget per the RFC: if delivery fails the originator falls back to
    its own ``--timeout`` and reconstructs completion from
    ``topology/ret`` arrivals.

    Always emits ``cancelled=False, cancel_reason=None`` -- operator-
    cancel semantics are out of scope for Phase 1.5 (tracked under the
    Tier-2 ``topology/jid-cancel`` RFC).
    """
    try:
        await asyncio.wait_for(
            inbound_link.send_pub_complete(
                jid,
                returned=list(returned),
                missed=list(missed),
                cancelled=False,
                cancel_reason=None,
                path=list(path) if path else None,
            ),
            timeout=_TOPOLOGY_AWAIT_TIMEOUT,
        )
    except asyncio.TimeoutError:
        log.warning(
            "topology: send_pub_complete to upstream=%r timed out for "
            "jid=%r after %ss; originator falls back to --timeout",
            getattr(inbound_link, "peer_cluster_id", None),
            jid,
            _TOPOLOGY_AWAIT_TIMEOUT,
        )
    except Exception:  # pylint: disable=broad-except
        # Includes LinkUnavailable (DISCONNECTED health gate).  The RFC
        # calls this out explicitly: a down link stops the emission, the
        # originator falls back to --timeout.  Do NOT retry.
        log.debug(
            "topology: send_pub_complete to upstream=%r failed for jid=%r",
            getattr(inbound_link, "peer_cluster_id", None),
            jid,
            exc_info=True,
        )


async def _collect_and_emit_pub_complete(jid, expected, inbound_link, path, timeout_s):
    """Watch ``salt/job/<jid>/ret/*`` and emit ``topology/pub-complete``.

    Runs as an asyncio.Task spawned by
    :func:`_spawn_pub_complete_collector`.  Exits (and emits) when:

    * every minion id in ``expected`` has appeared in a
      ``salt/job/<jid>/ret/<id>`` event, OR
    * ``timeout_s`` seconds elapse (peer's local-return deadline).

    Whichever path terminates, this coroutine calls
    :meth:`PeerMasterLink.send_pub_complete` exactly once with the
    current ``returned`` / ``missed`` split and then cleans up its
    event-bus subscription in a ``finally`` block.

    :param jid: The publish's jid.
    :param expected: Set of minion ids that the pub-ack named.  May be
        passed as a set; a defensive copy is NOT made -- callers must
        not mutate after handoff.
    :param inbound_link: The link we received the publish on.
    :param path: Optional path list to carry on the complete envelope.
    :param timeout_s: Upper bound on collection (default 60.0 from
        ``topology_pub_complete_timeout``).
    """
    returned = set()
    tag = f"salt/job/{jid}/ret/"
    event_bus = None
    try:
        # Open a dedicated listen-mode bus for this jid.  Using
        # ``get_master_event`` with ``listen=True`` establishes the
        # subscriber socket to ``master_event_pub.ipc``; the separate
        # module-level ``_EVENT_BUS`` is listen=False (publish-only) so
        # we cannot reuse it for receive.  The dedicated bus is closed
        # in ``finally`` so a leak-check of fds under load stays clean.
        try:
            event_bus = salt.utils.event.get_master_event(
                _OPTS,
                (_OPTS or {}).get("sock_dir"),
                io_loop=asyncio.get_event_loop(),
                listen=True,
            )
        except Exception:  # pylint: disable=broad-except
            log.debug(
                "topology: pub-complete collector get_master_event failed jid=%r",
                jid,
                exc_info=True,
            )
            event_bus = None
        if event_bus is not None:
            try:
                event_bus.subscribe(tag, match_type="startswith")
            except Exception:  # pylint: disable=broad-except
                log.debug(
                    "topology: pub-complete subscribe failed jid=%r",
                    jid,
                    exc_info=True,
                )

        deadline = asyncio.get_event_loop().time() + timeout_s
        poll_interval = 0.05
        # Poll loop: short sleep + non-blocking ``get_event`` drain.  We
        # avoid ``set_event_handler`` here because it installs a
        # single-handler callback on the subscriber's on_recv -- fine for
        # one bus-wide subscriber (as :func:`_start_return_subscriber`
        # does) but per-jid collectors would fight for that single slot.
        # Polling keeps each collector self-contained.
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            if event_bus is not None:
                try:
                    # ``get_event`` with wait=0 is non-blocking; it pulls
                    # any already-queued matching event out of the pending
                    # buffer and returns None when the queue is empty.
                    pkg = event_bus.get_event(
                        wait=0,
                        tag=tag,
                        match_type="startswith",
                        full=True,
                    )
                except Exception:  # pylint: disable=broad-except
                    pkg = None
                    log.debug(
                        "topology: pub-complete get_event raised jid=%r",
                        jid,
                        exc_info=True,
                    )
                drained_any = False
                while pkg is not None:
                    drained_any = True
                    raw_tag = pkg.get("tag", "")
                    data = pkg.get("data") or {}
                    # Tag shape: ``salt/job/<jid>/ret/<minion_id>``.
                    minion_id = None
                    if isinstance(raw_tag, str) and raw_tag.startswith(tag):
                        minion_id = raw_tag[len(tag) :]
                    if not minion_id and isinstance(data, dict):
                        minion_id = data.get("id")
                    if minion_id and minion_id in expected:
                        returned.add(minion_id)
                    if returned >= expected:
                        break
                    try:
                        pkg = event_bus.get_event(
                            wait=0,
                            tag=tag,
                            match_type="startswith",
                            full=True,
                        )
                    except Exception:  # pylint: disable=broad-except
                        pkg = None
                        break
                if returned >= expected:
                    break
                # If we drained nothing this tick, sleep briefly.
                if not drained_any:
                    await asyncio.sleep(poll_interval)
                else:
                    # Yield once so other coroutines (and new events
                    # arriving on the bus) get a chance before we loop.
                    await asyncio.sleep(0)
            else:
                # No bus wired (test harness / misconfigured sock_dir).
                # Sleep until the timeout so we still emit with an
                # empty-returned set rather than spinning the loop.
                await asyncio.sleep(min(poll_interval, max(remaining, 0)))

        missed = expected - returned
        await _emit_pub_complete_once(
            inbound_link,
            jid,
            returned=sorted(returned),
            missed=sorted(missed),
            path=path,
        )
    except asyncio.CancelledError:  # pylint: disable=try-except-raise
        # Clean shutdown path (e.g. ``_reset_module_state``).  Do not
        # emit on cancel -- the receiving-side daemon is going away and
        # the frame would race the socket teardown.  The explicit catch-
        # then-re-raise exists so the ``finally`` cleanup runs without
        # the broader ``except Exception`` branch swallowing the cancel.
        raise
    except Exception:  # pylint: disable=broad-except
        log.exception("topology: pub-complete collector raised for jid=%r", jid)
    finally:
        if event_bus is not None:
            try:
                event_bus.unsubscribe(tag, match_type="startswith")
            except Exception:  # pylint: disable=broad-except
                log.debug(
                    "topology: pub-complete unsubscribe failed jid=%r",
                    jid,
                    exc_info=True,
                )
            try:
                close = getattr(event_bus, "destroy", None) or getattr(
                    event_bus, "close", None
                )
                if close is not None:
                    close()
            except Exception:  # pylint: disable=broad-except
                log.debug(
                    "topology: pub-complete event_bus close failed jid=%r",
                    jid,
                    exc_info=True,
                )
        _PUB_COMPLETE_COLLECTORS.pop(jid, None)


def _resolve_local_match(load):
    """Return this master's locally-matched minion-id list for *load*.

    Runs :meth:`salt.utils.minions.CkMinions.check_minions` against
    the publish's topology-stripped target.  Returns an empty list on
    any failure (missing opts, lookup error, bad shape) --- the caller
    (:func:`_dispatch_pub`) uses the result for the topology/pub-ack
    ``matched_minion_ids`` field and the empty list is the RFC's
    "zero-match peer still emits an ack" case.

    Synchronous and disk-bound (PKI scan); callers should offload via
    :meth:`loop.run_in_executor` the same way
    :func:`_seed_local_cache_for_forwarded_publish` does.
    """
    if _OPTS is None or not isinstance(load, dict):
        return []
    tgt = load.get("tgt")
    try:
        stripped_tgt = router_mod.strip_cluster_scope(tgt)
    except Exception:  # pylint: disable=broad-except
        stripped_tgt = tgt
    try:
        import salt.utils.minions  # pylint: disable=import-outside-toplevel

        ckminions = salt.utils.minions.CkMinions.factory(_OPTS)
        resolved = ckminions.check_minions(stripped_tgt, load.get("tgt_type", "glob"))
    except Exception:  # pylint: disable=broad-except
        log.debug(
            "topology: _resolve_local_match raised for jid=%r",
            load.get("jid"),
            exc_info=True,
        )
        return []
    matched = resolved.get("minions") if isinstance(resolved, dict) else None
    return list(matched) if isinstance(matched, list) else []


async def _dispatch_ret(payload):
    """Handle an inbound ``topology/ret`` RPC.

    The payload carries one or more minion-return loads that an edge
    or transit peer forwarded upstream.  Behaviour per load:

    * If this master is the publish's origin
      (:func:`_jid_is_local_origin`), write the return into the local
      returner so the ``salt`` CLI's ``local_cache`` poll finds it.
    * Otherwise, look up the breadcrumb's upstream peer and fan the
      return one more hop closer to origin via
      :meth:`PeerMasterLink.send_return`.

    The sender ships either a single load dict or a batch (list of
    loads) depending on which code path called
    :meth:`PeerMasterLink.send_return`; both shapes are accepted.
    """
    router = router_mod.get_router()
    if router is None:
        return None
    # ``send_return`` wraps a list of per-minion return dicts in a
    # ``{"batch": [...], "topology": {...}}`` body, which the inbound
    # envelope then puts under the ``load`` key.  Legacy call sites
    # (and some tests) pass a single return dict or a bare list; be
    # permissive about shape so new senders don't have to be careful.
    body = payload.get("load") if isinstance(payload, dict) else payload
    if isinstance(body, dict) and isinstance(body.get("batch"), list):
        batch = body["batch"]
    elif isinstance(body, list):
        batch = body
    elif isinstance(body, dict):
        batch = [body]
    else:
        batch = []
    for item in batch:
        if not isinstance(item, dict):
            continue
        jid = item.get("jid")
        if not jid:
            continue
        if _jid_is_local_origin(jid):
            try:
                await _store_forwarded_return_offload(item)
            except Exception:  # pylint: disable=broad-except
                log.exception(
                    "topology: store_job for inbound topology/ret failed for jid=%r",
                    jid,
                )
            continue
        try:
            upstream = router.route_return(item)
        except Exception:  # pylint: disable=broad-except
            log.exception("topology: route_return raised for jid=%r", jid)
            continue
        if upstream is None:
            log.debug(
                "topology: no breadcrumb for jid=%r on inbound topology/ret "
                "-- dropping",
                jid,
            )
            continue
        try:
            if not router.forward_return_once(item):
                continue
        except Exception:  # pylint: disable=broad-except
            log.exception("topology: forward_return_once raised for jid=%r", jid)
        try:
            await asyncio.wait_for(
                upstream.send_return([item], [router.cluster_id]),
                timeout=_TOPOLOGY_AWAIT_TIMEOUT,
            )
        except asyncio.TimeoutError:
            log.warning(
                "topology: send_return (transit) to upstream=%r timed out "
                "for jid=%r after %ss; recovering loop",
                getattr(upstream, "peer_cluster_id", None),
                jid,
                _TOPOLOGY_AWAIT_TIMEOUT,
            )
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "topology: send_return to upstream=%r failed for jid=%r",
                getattr(upstream, "peer_cluster_id", None),
                jid,
            )
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
    # Reconstitute the ClusterSummary from its wire form before handing to
    # :meth:`TopologyRouter.ingest_summary`, which reads attributes like
    # ``summary.path`` / ``summary.cluster_id`` and raises AttributeError
    # on a bare dict.  Without this, every inbound ``topology/sum`` fails
    # the ``'dict' has no attribute 'path'`` assertion and the registry
    # never acquires peer-cluster membership -- flooding stays as the
    # fallback and ``topology.links()`` reports every peer as
    # ``disconnected``.
    wire_summary = load.get("summary") if isinstance(load, dict) else None
    if wire_summary is None:
        log.debug("topology: dropping topology/sum with no summary body")
        return None
    try:
        summary = summary_mod.deserialize(wire_summary)
    except Exception:  # pylint: disable=broad-except
        log.exception("topology: topology/sum deserialize failed")
        return None
    # Schedule the ingest + fan-out via ``ensure_future`` so the inbound
    # REP handler is NOT blocked for the duration of the recursive summary
    # re-emit.  :meth:`TopologyRouter.ingest_summary` awaits
    # ``send_summary`` on every forward peer; running that inline inside
    # ``_handle_inbound_channel`` holds the REP socket for up to
    # ``_TOPOLOGY_AWAIT_TIMEOUT`` per hop, which cascades into pairwise
    # summary-emit deadlocks when both peers emit simultaneously (the
    # publish-shaped transit forwards at line ~1260 use the same
    # fire-and-forget pattern).
    try:
        asyncio.ensure_future(router.ingest_summary(summary, inbound_link))
    except Exception:  # pylint: disable=broad-except
        log.exception("topology: ingest_summary scheduling raised")
    return None


def _fire_local_event(tag, data):
    """Fire *data* under *tag* on the local master event bus.

    Prefers the cached :data:`_EVENT_BUS` client (reused across fires so
    paired writes land in order on ``master_event_pull.ipc``), falls
    back to :data:`_FIRE_EVENT` for test harnesses that did not wire the
    async bus.  Silent no-op when neither is available: the dispatcher
    is strictly a passthrough from wire to local bus, so a harness
    without an event bus should still accept the frame without raising.
    """
    if _EVENT_BUS is not None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        fire_async = getattr(_EVENT_BUS, "fire_event_async", None)
        if fire_async is not None and loop is not None:
            try:
                loop.create_task(fire_async(data, tag))
                return
            except Exception:  # pylint: disable=broad-except
                log.debug(
                    "topology: fire_event_async failed for %s", tag, exc_info=True
                )
        try:
            _EVENT_BUS.fire_event(data, tag)
            return
        except Exception:  # pylint: disable=broad-except
            log.debug("topology: fire_event failed for %s", tag, exc_info=True)
    if _FIRE_EVENT is not None:
        try:
            _FIRE_EVENT(tag, data)
        except Exception:  # pylint: disable=broad-except
            log.debug("topology: _FIRE_EVENT hook failed for %s", tag, exc_info=True)


def _validate_pub_ack_payload(inner):
    """Return True when *inner* carries a well-formed pub-ack load.

    Enforced fields (per RFC "Wire format" / pub-ack):

    * ``load.jid`` is a non-empty str.
    * ``load.matched_minion_ids`` is a list (may be empty).
    * ``session_generation`` is present on the outer frame.
    * ``origin_cluster_id`` is present on the outer frame.

    Rejection path is WARNING log + return False; the caller drops
    the frame without raising (lossy by design per the RFC).
    """
    if not isinstance(inner, dict):
        return False
    load = inner.get("load")
    if not isinstance(load, dict):
        log.warning(
            "topology: dropping topology/pub-ack with non-dict load: %r",
            type(load).__name__,
        )
        return False
    jid = load.get("jid")
    if not isinstance(jid, str) or not jid:
        log.warning("topology: dropping topology/pub-ack with invalid jid=%r", jid)
        return False
    matched = load.get("matched_minion_ids")
    if not isinstance(matched, list):
        log.warning(
            "topology: dropping topology/pub-ack jid=%r with non-list "
            "matched_minion_ids=%r",
            jid,
            type(matched).__name__,
        )
        return False
    if inner.get("session_generation") is None:
        log.warning(
            "topology: dropping topology/pub-ack jid=%r without session_generation",
            jid,
        )
        return False
    if not inner.get("origin_cluster_id"):
        log.warning(
            "topology: dropping topology/pub-ack jid=%r without origin_cluster_id",
            jid,
        )
        return False
    return True


def _validate_pub_complete_payload(inner):
    """Return True when *inner* carries a well-formed pub-complete load.

    Enforced fields (per RFC "Wire format" / pub-complete):

    * ``load.jid`` is a non-empty str.
    * ``load.returned`` and ``load.missed`` are both lists.
    * ``session_generation`` is present on the outer frame.
    * ``origin_cluster_id`` is present on the outer frame.
    """
    if not isinstance(inner, dict):
        return False
    load = inner.get("load")
    if not isinstance(load, dict):
        log.warning(
            "topology: dropping topology/pub-complete with non-dict load: %r",
            type(load).__name__,
        )
        return False
    jid = load.get("jid")
    if not isinstance(jid, str) or not jid:
        log.warning("topology: dropping topology/pub-complete with invalid jid=%r", jid)
        return False
    returned = load.get("returned")
    missed = load.get("missed")
    if not isinstance(returned, list) or not isinstance(missed, list):
        log.warning(
            "topology: dropping topology/pub-complete jid=%r with non-list "
            "returned=%r / missed=%r",
            jid,
            type(returned).__name__,
            type(missed).__name__,
        )
        return False
    if inner.get("session_generation") is None:
        log.warning(
            "topology: dropping topology/pub-complete jid=%r without "
            "session_generation",
            jid,
        )
        return False
    if not inner.get("origin_cluster_id"):
        log.warning(
            "topology: dropping topology/pub-complete jid=%r without "
            "origin_cluster_id",
            jid,
        )
        return False
    return True


def _dispatch_pub_ack(payload):
    """Handle an inbound ``topology/pub-ack`` frame.

    Validates the shape via :func:`_validate_pub_ack_payload` and
    (on accept) re-fires the inner payload on this master's local
    event bus under ``salt/topology/pub-ack/<jid>``.  Phase 1 does
    NOT consume the ack; the re-fire exists so Phase 2's CLI loop
    can subscribe to it with existing event-bus plumbing.

    Rejection path is WARNING log + silent drop; the frame is
    optional telemetry per the RFC.
    """
    if not _validate_pub_ack_payload(payload):
        return None
    load = payload["load"]
    jid = load["jid"]
    tag = f"salt/topology/pub-ack/{jid}"
    _fire_local_event(tag, load)
    return None


def _dispatch_pub_complete(payload):
    """Handle an inbound ``topology/pub-complete`` frame.

    Validates the shape via :func:`_validate_pub_complete_payload`
    and (on accept) re-fires the inner payload on this master's
    local event bus under ``salt/topology/pub-complete/<jid>``.
    Phase 1 does NOT consume it; the re-fire exists so Phase 2's
    CLI loop can subscribe with existing event-bus plumbing.

    Rejection path is WARNING log + silent drop.
    """
    if not _validate_pub_complete_payload(payload):
        return None
    load = payload["load"]
    jid = load["jid"]
    tag = f"salt/topology/pub-complete/{jid}"
    _fire_local_event(tag, load)
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
    "topology/pub-ack": _dispatch_pub_ack,
    "topology/pub-complete": _dispatch_pub_complete,
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
    ``origin_cluster_id`` whose server-side inbound record's
    ``session_generation`` matches the payload's.

    Match against :data:`_INBOUND[origin]` (the server-side record
    established at ``_master_auth`` handshake time and kept current
    by :func:`_maybe_lazy_register_inbound`), NEVER
    :data:`_LINKS[origin]`.  The two counters are independent:

    * ``_INBOUND[origin].session_generation`` -- *origin's* own
      session gen, received in origin's handshake load.  This is
      the correct counter to compare against the payload's
      self-reported gen because the payload also comes from origin.
    * ``_LINKS[origin].session_generation`` -- *self's* outbound
      session gen for the link where self initiated the handshake
      with origin.  Unrelated to anything origin sends us.

    :func:`get_link` was consulted here historically; it prefers
    the outbound ``_LINKS[origin]`` entry when both exist, which
    silently rejected every frame from an authenticated peer whose
    server-side gen differed from self's outbound-side gen.  In the
    8-master topology sandbox this surfaced as 21k+ ``bad/missing
    session`` drops per master over a 12-hour window, with the
    user-visible symptom being forwarded ``state.apply`` returning
    ``{"failed": True}`` for every minion more than one hop out --
    LocalClient's "no return within timeout" marker, because the
    transit's forwarded publishes never ran.
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
    try:
        gen_i = int(gen)
    except (TypeError, ValueError):
        return False
    inbound = _INBOUND.get(origin)
    if inbound is None:
        return False
    expected = getattr(inbound, "session_generation", None)
    if expected is None:
        return False
    return int(expected) == gen_i


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
    adapts between the two: it awaits the inner dispatch, extracts a
    msgpack-serializable ack, and returns a
    ``(ret, {"fun": "send_clear"})`` tuple so a dropped message yields
    a well-formed empty cleartext reply instead of a transport-level
    failure.

    The internal dispatchers return domain objects for the convenience
    of in-process callers and tests (``_dispatch_pub`` returns
    ``(links, local_match)`` with :class:`PeerMasterLink` instances,
    ``_dispatch_ret`` returns the breadcrumb-resolved link, etc.).
    Those objects do NOT serialize through msgpack and used to crash
    the REP ``send`` after a successful ``recv`` -- deadlocking the
    socket.  Collapse the dispatcher return to a serializable ack
    dict here so only the handshake path keeps its structured reply
    (``_master_auth`` already returns a plain dict).
    """
    result = await _handle_inbound(payload)
    if isinstance(result, dict):
        # Handshake reply (``_master_auth``) is already plain-dict and
        # msgpack-safe; pass through unchanged.
        reply = result
    elif result is None:
        reply = {}
    else:
        # Dispatcher return is internal state (e.g. list of
        # PeerMasterLink objects); the sender only needs to know the
        # message was accepted.
        reply = {"ok": True}
    return reply, {"fun": "send_clear"}


# ---------------------------------------------------------------------------
# _master_auth handshake
# ---------------------------------------------------------------------------


def _masters_subdir(opts, name):
    """Return ``<cluster_pki_dir or pki_dir>/<name>`` (creating it on first use).

    Clustered 3008.x masters share pre-accepted topology peer keys under
    ``cluster_pki_dir`` so all N replicas in a cluster see the same
    accept state (keyed by peer ``cluster_id``, not by replica node id).
    When ``cluster_pki_dir`` is set in opts, resolve the ``masters``
    tree against it; otherwise fall back to the non-clustered
    ``pki_dir`` which is correct for solo masters.

    Mirror of the ``self.pki_dir = cluster_pki_dir if cluster_id else
    pki_dir`` pattern in :class:`salt.master.Maintenance.__init__` and
    the parallel channel-server resolution --- the topology module was
    the odd-one-out that looked only at ``pki_dir`` and so never saw
    the accepted peer keys that are seeded under ``cluster_pki_dir``
    on a 3-master cluster.
    """
    base = (
        opts.get("cluster_pki_dir")
        if opts.get("cluster_id") and opts.get("cluster_pki_dir")
        else opts.get("pki_dir", "")
    )
    path = os.path.join(base, name)
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
    # Clustered masters' topology peer keys live under ``cluster_pki_dir``;
    # solo masters use ``pki_dir``.  :func:`_masters_subdir` picks the
    # right root; here just assert at least one of the two is set so a
    # missing-opts misconfig surfaces loudly instead of silently writing
    # into the current working directory.
    if not opts.get("cluster_pki_dir") and not opts.get("pki_dir"):
        log.warning(
            "topology _master_auth: both cluster_pki_dir and pki_dir "
            "missing from opts"
        )
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
    # :func:`_verify_session`.
    #
    # Generation strategy (why we do NOT increment on re-auth):
    # In a 3-master cluster each node independently connects to the peer
    # cluster, so ``_handle_master_auth`` fires once per cluster-node --
    # 3 auth calls for a 3-node cluster, all carrying
    # ``origin_cluster_id = cluster_id``.  If we incremented on every
    # call we would end up at gen=3 after the third auth while the first
    # two nodes already received gen=1 and gen=2 respectively.  Every
    # frame the first two nodes send would then fail :func:`_verify_session`
    # (expected=3, got=1 or 2).
    #
    # The correct model: only bump when creating a fresh entry
    # (``existing is None``), which signals the peer cluster is
    # connecting to us for the first time.  Re-auth calls (nodes 2..N
    # or same-node reconnects) reuse the existing generation so all N
    # cluster nodes agree on the same gen.
    #
    # Security note: the generation counter provides a soft session fence
    # (discard frames from before the last full disconnect) rather than
    # cryptographic AES integrity.  Keeping gen stable across cluster-node
    # re-auths is correct here: the new AES returned in each reply is still
    # used by the sender, and the receiver still maintains the mapping.
    #
    # Hold ``_LOCK`` around the read-modify-write: the Raft-SM apply
    # thread's :func:`remove_link` also touches ``_INBOUND`` under the
    # same lock, so an un-serialized sequence here could resurrect an
    # inbound record for a cluster_id the SM has just detached.
    with _LOCK:
        existing = _INBOUND.get(cluster_id)
        next_gen = existing.session_generation if existing is not None else 1
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
        # Carry the receiver-side session generation so the sender can
        # pin its own ``_session_generation`` to match.  Without this,
        # nodes 2..N in a clustered sender get a gen that diverges from
        # node 1's gen, causing :func:`_verify_session` failures for all
        # but the last node to authenticate.
        "session_generation": next_gen,
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
