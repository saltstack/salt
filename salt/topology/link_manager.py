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

import logging
import threading

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

_LOCK = threading.RLock()


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


async def start(opts, io_loop):
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


async def stop():
    """
    Shut down the topology subsystem at process exit.

    Closes the inbound listener, disconnects every outbound
    link, and clears all registries.  Idempotent; safe to call
    multiple times.
    """


def get_link(cluster_id):
    """
    Return the active link to ``cluster_id`` (inbound or
    outbound, whichever exists), or ``None``.

    When both an inbound and outbound link exist to the same peer
    (both sides initiated independently and the race was close),
    returns the one that completed handshake first.  The other
    is marked for teardown at the next housekeeping tick.
    """


def get_all_links():
    """
    Return every active link, inbound and outbound,
    deduplicated by peer ``cluster_id``.
    """


def outbound_links():
    """
    Return only links initiated by this master.

    Used by the router when flooding a publish (we send down the
    outbound channel) and when pushing summaries.  Peer masters
    do the symmetric thing on their side; this master receives
    those on its inbound links.
    """


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
