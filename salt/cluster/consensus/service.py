"""
RaftService — lifecycle manager for the Raft node inside a Salt master.

Responsibilities
----------------
* Construct and own the ``Node`` instance.
* Wire ``AsyncTimeoutScheduler`` to the asyncio event loop already running
  inside ``MasterPubServerChannel._publish_daemon``.
* Build one ``SaltPeer`` per entry in ``opts["cluster_peers"]``, keyed to
  the per-peer ``PublishServer`` pushers that ``_publish_daemon`` already
  created.
* Construct ``RaftDispatcher`` and hand it to
  ``MasterPubServerChannel._raft_dispatcher`` so that
  ``handle_pool_publish`` can route inbound Raft RPCs.
* Start the Raft election timer and, when elected leader, drive periodic
  heartbeats.
* Handle dynamic peer joins: when a new master completes the Salt-level
  cluster join, ``notify_peer_joined`` adds it as a non-voting learner.
  The leader will automatically promote it to voter once its log catches up.

Threading / concurrency model
------------------------------
``RaftService`` is created and runs entirely inside the
``EventPublisher`` subprocess owned by ``MasterPubServerChannel``.  All
methods that touch the ``Node`` are called from the asyncio event loop
that Tornado wraps; the Raft core remains synchronous.

Usage (inside ``_publish_daemon``)
-----------------------------------
::

    service = RaftService(opts, aio_loop, peer_pushers)
    service.attach(channel)   # sets channel._raft_dispatcher
    service.start()           # begins election timer
"""

import logging

from salt.cluster.consensus.peer import RaftDispatcher, SaltPeer
from salt.cluster.consensus.raft import AsyncTimeoutScheduler, Node
from salt.cluster.consensus.raft.node import NodeState
from salt.cluster.consensus.storage import SaltStorage

log = logging.getLogger(__name__)

# Heartbeat interval sent by the leader (seconds).  Must be well below the
# follower election timeout floor (~0.15 s per gettimeout defaults).
_HEARTBEAT_INTERVAL = 0.05


class RaftService:
    """
    Owns the Raft ``Node`` for one Salt master process.

    :param opts:         Salt master opts dict.
    :param loop:         The *asyncio* event loop running in this process.
    :param peer_pushers: ``dict[peer_addr, PublishServer]`` - the pushers
                         ``_publish_daemon`` already created, keyed by the
                         peer's interface address (``opts["cluster_peers"]``
                         entry).
    """

    def __init__(self, opts, loop, peer_pushers, voting=True):
        self.opts = opts
        self.loop = loop
        self._peer_pushers = dict(peer_pushers)  # addr -> PublishServer (mutable copy)

        # Use the interface address as the Raft node-id so it matches the
        # keys in cluster_peers and the peer_pushers dict.  opts["id"] is
        # the hostname which remote masters do not share; the interface
        # address is the consistent cluster-wide identity.
        node_id = opts["interface"]
        storage = SaltStorage(node_id, opts)
        # voting=False means this node joined dynamically and must wait for a
        # CONFIG entry from the leader before participating in elections.
        self._node = Node(node_id, storage=storage, voting=voting)
        self._scheduler = AsyncTimeoutScheduler(loop=loop)
        self._node.register_schedule_timeout(self._scheduler.schedule)

        # Build SaltPeer objects - one per cluster peer (all voting at start).
        peers = [
            SaltPeer(addr, pusher, node_id) for addr, pusher in peer_pushers.items()
        ]
        self._node.peers = peers

        # Register a peer factory so Node.on_config_change can create SaltPeers
        # for addresses that appear in CONFIG entries (covers learner->voter path).
        self._node.register_peer_factory(self._make_peer)

        # peer_pushers is keyed by interface address, matching the
        # callback_node field written into RPC envelopes.
        self._dispatcher = RaftDispatcher(self._node, node_id, self._peer_pushers)

        self._heartbeat_handle = None

    # ------------------------------------------------------------------
    # Peer factory (used by Node.on_config_change)
    # ------------------------------------------------------------------

    def _make_peer(self, addr, voting=True):
        """
        Create a ``SaltPeer`` for *addr*.

        If we already have a pusher for that address (from ``_peer_pushers``)
        it is reused; otherwise we create a new one using the cluster port.
        Called by :meth:`Node.on_config_change` when a CONFIG log entry is
        applied and a previously unknown address appears in the voter list.
        """
        import salt.transport.tcp  # pylint: disable=import-outside-toplevel

        pusher = self._peer_pushers.get(addr)
        if pusher is None:
            port = self.opts.get("cluster_port", 55596)
            pusher = salt.transport.tcp.PublishServer(
                self.opts,
                pull_host=addr,
                pull_port=port,
            )
            self._peer_pushers[addr] = pusher
            # Keep the dispatcher's pusher table in sync.
            self._dispatcher._pushers[addr] = pusher
        return SaltPeer(addr, pusher, self.opts["interface"], voting=voting)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def attach(self, channel):
        """
        Wire this service into ``MasterPubServerChannel``.

        Sets ``channel._raft_dispatcher`` so that ``handle_pool_publish``
        will route ``cluster/raft/*`` messages here.
        """
        channel._raft_dispatcher = self._dispatcher

    def start(self):
        """
        Start the Raft node as a follower and arm the election timer.

        Must be called from within the running asyncio event loop.
        """
        log.info(
            "RaftService: starting node %s with %d peer(s)",
            self._node.node_id,
            len(self._node.peers),
        )
        self._node.become_follower()
        self._schedule_heartbeat()

    def stop(self):
        """Cancel scheduled callbacks and step the node down."""
        if self._heartbeat_handle is not None:
            self._heartbeat_handle.cancel()
            self._heartbeat_handle = None
        log.info("RaftService: stopped node %s", self._node.node_id)

    def notify_peer_joined(self, peer_addr):
        """
        Called when a new master completes the Salt cluster join handshake.

        Adds *peer_addr* as a **non-voting learner** in the Raft cluster.
        If this node is the current leader it immediately starts replicating
        to the learner; once the learner's log catches up the leader will
        automatically propose a CONFIG entry promoting it to voter
        (see :meth:`Node.append_entries_reply`).

        If this node is a follower the learner peer is added to its peer
        list so it will receive ``AppendEntries`` from whichever node
        eventually becomes leader.

        :param peer_addr: The joining master's interface address - the same
                          value used as ``join_peer_id`` in the
                          ``cluster/peer/join-notify`` envelope.
        """
        node_id = self._node.node_id
        if peer_addr == node_id:
            # This is the joining node learning about itself - nothing to do
            # from the peer perspective; our own voting status is controlled
            # by CONFIG entries from the leader.
            return

        existing = {p.node_id for p in self._node.peers}
        if peer_addr in existing:
            log.debug(
                "RaftService: peer %s already known, skipping notify_peer_joined",
                peer_addr,
            )
            return

        log.info("RaftService: adding learner peer %s", peer_addr)
        learner_peer = self._make_peer(peer_addr, voting=False)
        self._node.peers.append(learner_peer)

        if self._node.state == NodeState.LEADER:
            # Initialise replication tracking for the new learner.
            self._node.next_index[peer_addr] = self._node.log.index + 1
            self._node.match_index[peer_addr] = -1
            # Kick off replication immediately.
            self._node.send_append_entries(learner_peer)

    @property
    def node(self):
        return self._node

    @property
    def membership(self):
        """The :class:`~salt.cluster.consensus.raft.log.MembershipStateMachine` for this node."""
        return self._node.membership_sm

    @property
    def dispatcher(self):
        return self._dispatcher

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def _schedule_heartbeat(self):
        self._heartbeat_handle = self.loop.call_later(
            _HEARTBEAT_INTERVAL, self._heartbeat_tick
        )

    def _heartbeat_tick(self):
        """
        Called periodically by the event loop.

        If this node is the leader, send an empty AppendEntries to every
        peer to suppress their election timers.  On the *first* heartbeat
        after winning an election with an empty log, also commit a founding
        CONFIG entry so the voter set is durably recorded.
        """
        try:
            if self._node.state == NodeState.LEADER:
                self._maybe_commit_founding_config()
                for peer in self._node.peers:
                    try:
                        self._node.send_append_entries(peer, entries=[])
                    except Exception:  # pylint: disable=broad-except
                        log.exception(
                            "RaftService: error sending heartbeat to %s",
                            peer.node_id,
                        )
        except Exception:  # pylint: disable=broad-except
            log.exception("RaftService: error in heartbeat tick")
        finally:
            self._schedule_heartbeat()

    def _maybe_commit_founding_config(self):
        """
        Propose the initial CONFIG entry when this leader has an empty log.

        This records the founding voter set durably so that a node recovering
        from storage can reconstruct the cluster membership without relying
        solely on ``opts["cluster_peers"]``.

        No-ops if the log already has any entries (founding entry already
        written, or leader inherited a non-empty log).
        """
        if self._node.log.index >= 0:
            return
        from salt.cluster.consensus.raft.log import (
            LogEntryType,  # pylint: disable=import-outside-toplevel
        )

        voters = [self._node.node_id] + [
            p.node_id for p in self._node.peers if getattr(p, "voting", True)
        ]
        learners = [
            p.node_id for p in self._node.peers if not getattr(p, "voting", True)
        ]
        log.info("RaftService: committing founding CONFIG entry voters=%s", voters)
        try:
            self._node.log_add(
                {"voters": voters, "learners": learners},
                entry_type=LogEntryType.CONFIG,
            )
        except Exception:  # pylint: disable=broad-except
            log.exception("RaftService: failed to propose founding CONFIG entry")


def build_peer_pushers(opts, pushers_list):
    """
    Convert the flat ``pushers`` list from ``_publish_daemon`` into the
    ``dict[addr, PublishServer]`` that ``RaftService`` expects.

    ``_publish_daemon`` builds ``self.pushers`` as a plain list of
    ``PublishServer`` objects in the same order as
    ``opts["cluster_peers"]``.  This helper pairs them back up.

    :param opts:          Salt master opts.
    :param pushers_list:  ``self.pushers`` from ``_publish_daemon``.
    :returns:             ``{peer_addr: PublishServer}``
    """
    peers = opts.get("cluster_peers", [])
    return dict(zip(peers, pushers_list))
