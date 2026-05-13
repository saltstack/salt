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
from salt.cluster.consensus.raft.log import (
    RING_MEMBERS_SELF,
    RING_MEMBERS_VOTERS,
    LogEntryType,
    RingConfigStateMachine,
)
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

    def __init__(self, opts, loop, peer_pushers, voting=True, on_ready=None):
        self.opts = opts
        self.loop = loop
        self._peer_pushers = dict(peer_pushers)  # addr -> PublishServer (mutable copy)
        self._on_ready = on_ready

        # Use the interface address as the Raft node-id so it matches the
        # keys in cluster_peers and the peer_pushers dict.  opts["id"] is
        # the hostname which remote masters do not share; the interface
        # address is the consistent cluster-wide identity.
        node_id = opts["interface"]
        storage = SaltStorage(node_id, opts)
        # voting=False means this node joined dynamically and must wait for a
        # CONFIG entry from the leader before participating in elections.
        #
        # The default Node election window of 150–300 ms is too tight for
        # multi-process Salt masters running over real sockets — a single
        # delayed heartbeat in CI can cause a follower to step up and fight
        # the existing leader for the term.  At ``_HEARTBEAT_INTERVAL`` =
        # 50 ms the rule of thumb is election >= 10× heartbeat, so default
        # to 750–1500 ms here.  ``cluster_election_min`` /
        # ``cluster_election_max`` opts let deployments tune further.
        election_min = opts.get("cluster_election_min", 750)
        election_max = opts.get("cluster_election_max", 1500)
        # ``cluster_max_log_size`` (default ``None``) gates Raft log
        # compaction.  When unset, the log keeps every committed entry
        # forever and snapshots never fire — fine for small clusters
        # but pathological for any long-running deployment.  When set,
        # the membership SM round-trips through the snapshot envelope
        # (raft.snapshot.v1); CONSENSUS_BUGS.md #1's fix and the
        # reconcile_membership hook ensure peer state survives.
        max_log_size = opts.get("cluster_max_log_size")
        # ``cluster_max_voters`` (default ``None``) caps how many peers
        # the leader will auto-promote out of the learner pool.  When
        # the cap is hit, additional joiners stay as non-voting log
        # replicas indefinitely.
        max_voters = opts.get("cluster_max_voters")
        self._node = Node(
            node_id,
            storage=storage,
            voting=voting,
            _follower_min=election_min,
            _follower_max=election_max,
            max_log_size=max_log_size,
            max_voters=max_voters,
        )
        self._scheduler = AsyncTimeoutScheduler(loop=loop)
        self._node.register_schedule_timeout(self._scheduler.schedule)

        # Wire the membership SM's on_change so we can fire on_ready once
        # this node appears in the committed voter set.
        self._node.membership_sm.on_change = self._on_membership_change

        # Ring config SM: tracks the cluster's ring policy (members
        # source + replication factor).  Registered on the Log so its
        # state survives compaction.  Default policy ("self", 1) means
        # the per-process ring contains only this master and writes
        # broadcast as they do today; an operator flips to ("voters",
        # N) by committing a RING_CONFIG entry through Raft.
        self._ring_config_sm = RingConfigStateMachine(
            on_change=self._on_ring_config_change
        )
        self._node.log.register_state_machine("ring_sm", self._ring_config_sm)

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

        # If Node started from a saved snapshot the membership SM was
        # restored before this on_change wiring existed, so the cluster-
        # ready / peer-table side effects never fired.  Reconcile now so
        # _on_ready and on_config_change run for the restored view.
        self._node.reconcile_membership()

        self._heartbeat_handle = None

    # ------------------------------------------------------------------
    # Membership change / readiness
    # ------------------------------------------------------------------

    def _on_membership_change(self, voters, learners):
        """
        Called by ``MembershipStateMachine`` after every committed CONFIG entry.

        Fires ``on_ready`` (once) when this node's address first appears in the
        committed voter set, signalling that it is a full participant and may
        begin serving minion/CLI traffic.

        Also reapplies the current ring policy: when ``members=voters`` the
        ring contents track the new voter set.  In ``members=self`` (default)
        the ring stays self-only regardless of voters, which preserves the
        broadcast-everywhere stage-0 behaviour.
        """
        self._apply_ring_policy()

        if self._on_ready is None:
            return
        node_id = self._node.node_id
        if node_id in voters:
            log.info(
                "RaftService: node %s is now a committed voter — marking cluster ready",
                node_id,
            )
            self._on_ready()
            self._on_ready = None  # fire only once

    def _on_ring_config_change(self, members, replicas):
        """
        Called by ``RingConfigStateMachine`` after every committed
        RING_CONFIG entry.  Rebuilds this process's ring with the new
        policy applied to the current voter set.

        Replication factor is tracked in the SM but not yet honoured by
        the rebuild — stage 1 ships the policy plumbing; stage 2 will
        teach the ring to use ``replicas > 1`` for fault tolerance.
        """
        log.info(
            "RaftService: ring policy committed — members=%s replicas=%d",
            members,
            replicas,
        )
        self._apply_ring_policy()

    def _apply_ring_policy(self):
        """
        Rebuild the per-process ring from current SM state.

        Resolves ``ring_config_sm.members``:

        * ``"self"`` — ring contains only this master; ``owns`` returns
          True for every key.  Default; matches today's broadcast.
        * ``"voters"`` — ring contains the current Raft voter set
          (``membership_sm.current_voters()``); ``owns`` shards by
          consistent hash.

        Called from both the membership-change and ring-config-change
        paths because either can shift the ring's contents under the
        ``"voters"`` policy.
        """
        # Lazy import keeps the consensus package independent of the
        # ring module's load order.
        import salt.cluster.ring_membership  # pylint: disable=import-outside-toplevel

        if self._ring_config_sm.members == RING_MEMBERS_VOTERS:
            voters = self._node.membership_sm.current_voters()
            salt.cluster.ring_membership.rebuild(voters)
        else:  # RING_MEMBERS_SELF (default)
            # Self-only ring: contains just this master so owns()
            # answers True for everything.  Empty ring would also do —
            # we use the explicit single-node form so logs are clear.
            salt.cluster.ring_membership.rebuild([self._node.node_id])

    def propose_ring_config(self, members=None, replicas=None):
        """
        Propose a RING_CONFIG entry through Raft.

        Only valid on the leader; followers will see a future commit
        once the leader replicates the entry.  Either argument can be
        omitted to keep the existing value (the SM merges partial
        updates).

        :param members: ``"self"`` or ``"voters"`` (or ``None`` to
                        keep current).
        :param replicas: integer >= 1 (or ``None`` to keep current).
        :raises ValueError: if *members* is set to an unknown value.
        :raises RuntimeError: if this node is not currently the
                              leader (the entry would not commit).
        """
        if members is not None and members not in (
            RING_MEMBERS_SELF,
            RING_MEMBERS_VOTERS,
        ):
            raise ValueError(
                f"Unknown ring members policy {members!r}; "
                f"expected 'self' or 'voters'"
            )
        if self._node.state != NodeState.LEADER:
            raise RuntimeError(
                "propose_ring_config must run on the Raft leader; "
                f"this node is in state {self._node.state}"
            )
        cmd = {}
        if members is not None:
            cmd["members"] = members
        if replicas is not None:
            cmd["replicas"] = int(replicas)
        if not cmd:
            return  # no-op
        self._node.log_add(cmd, entry_type=LogEntryType.RING_CONFIG)

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
            # Persist the learner registration in a CONFIG entry so that a
            # subsequent leader failover preserves the learner roster.  Without
            # this, new leaders rebuild ``peers`` only from the committed
            # voter+learner sets in the membership SM; a learner that was only
            # added in the previous leader's in-memory state would disappear
            # and its subsequent RPC replies would trip CandidacyError ("X is
            # not a peer") on the new leader.
            #
            # The cap on ``cluster_max_voters`` applies separately to the
            # *promotion* CONFIG that fires once the learner catches up; this
            # entry only registers the node as a learner, not a voter.
            from salt.cluster.consensus.raft.log import (
                LogEntryType,  # pylint: disable=import-outside-toplevel
            )

            committed_voters = self._node.membership_sm.current_voters()
            committed_learners = list(self._node.membership_sm.current_learners())
            if (
                peer_addr not in committed_voters
                and peer_addr not in committed_learners
            ):
                committed_learners.append(peer_addr)
                try:
                    self._node.log_add(
                        {
                            "voters": committed_voters,
                            "learners": sorted(committed_learners),
                        },
                        entry_type=LogEntryType.CONFIG,
                    )
                except Exception:  # pylint: disable=broad-except
                    log.exception(
                        "RaftService: failed to persist learner registration for %s",
                        peer_addr,
                    )
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
                        ni = self._node.next_index.get(
                            peer.node_id, self._node.log.index + 1
                        )
                        # Send a heartbeat (empty) only when the peer is
                        # caught up.  If it's behind, include the entries so
                        # it can advance — important for lagging learners.
                        entries = [] if ni > self._node.log.index else None
                        self._node.send_append_entries(peer, entries=entries)
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

        # Deterministic bootstrap pool: sorted set of {this node} ∪ peer
        # addresses.  Every prospective founder runs this code, but only
        # the deterministic founder (lowest interface in the pool; see
        # ``salt/master.py:920`` and ``salt/channel/server.py:2101``)
        # actually writes the CONFIG.  Tying the founding-voter selection
        # to the same sort means every node agrees on the partition
        # regardless of startup order.
        bootstrap_pool = sorted(
            {self._node.node_id, *[p.node_id for p in self._node.peers]}
        )
        # ``cluster_max_voters`` (default ``None``) caps the founding voter
        # set.  Excess peers go into the learner set in the same CONFIG
        # entry so they're still durably registered (see also the
        # ``notify_peer_joined`` learner-registration path).
        max_voters = self.opts.get("cluster_max_voters")
        if max_voters is not None and len(bootstrap_pool) > max_voters:
            voters = bootstrap_pool[:max_voters]
            learners = bootstrap_pool[max_voters:]
        else:
            voters = bootstrap_pool
            learners = []
        log.info(
            "RaftService: committing founding CONFIG entry voters=%s learners=%s",
            voters,
            learners,
        )
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
