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

log = logging.getLogger(__name__)

# Heartbeat interval sent by the leader (seconds).  Must be well below the
# follower election timeout floor (~0.15 s per gettimeout defaults).
_HEARTBEAT_INTERVAL = 0.05


class RaftService:
    """
    Owns the Raft ``Node`` for one Salt master process.

    :param opts:         Salt master opts dict.
    :param loop:         The *asyncio* event loop running in this process.
    :param peer_pushers: ``dict[peer_addr, PublishServer]`` — the pushers
                         ``_publish_daemon`` already created, keyed by the
                         peer's interface address (``opts["cluster_peers"]``
                         entry).
    """

    def __init__(self, opts, loop, peer_pushers):
        self.opts = opts
        self.loop = loop
        self._peer_pushers = peer_pushers  # addr -> PublishServer

        node_id = opts["id"]
        self._node = Node(node_id)
        self._scheduler = AsyncTimeoutScheduler(loop=loop)
        self._node.register_schedule_timeout(self._scheduler.schedule)

        # Build SaltPeer objects — one per cluster peer.
        peers = [
            SaltPeer(addr, pusher, node_id) for addr, pusher in peer_pushers.items()
        ]
        self._node.peers = peers

        # Pushers keyed by peer node_id for RaftDispatcher reply routing.
        # At bootstrap time the peer node_id equals the peer's interface
        # address (opts["cluster_peers"] entry); this can be refined later
        # when persistent membership data is available.
        self._dispatcher = RaftDispatcher(self._node, node_id, peer_pushers)

        self._heartbeat_handle = None

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

    @property
    def node(self):
        return self._node

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
        peer to suppress their election timers.
        """
        try:
            from salt.cluster.consensus.raft.node import NodeState

            if self._node.state == NodeState.LEADER:
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
