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
    RING_MEMBERS_VOTERS,
    RING_STATUS_ACTIVE,
    RING_STATUS_DESTROYED,
    RING_STATUS_VALID,
    LogEntryType,
    RingConfigStateMachine,
    RingRegistryStateMachine,
    RoutingStateMachine,
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
        # ``_nodes`` is the multi-ring registry: keys are Raft group
        # ids, values are the local ``Node`` instances.  Slice 1 only
        # carries the main cluster group; later slices spawn per-ring
        # Nodes here as the cluster log commits RING_REGISTRY entries.
        # ``self._node`` (singular) stays as a convenience handle to
        # the cluster Node — every existing call site reads it through
        # that name.
        self._nodes = {"cluster": self._node}
        self._scheduler = AsyncTimeoutScheduler(loop=loop)
        self._node.register_schedule_timeout(self._scheduler.schedule)

        # Wire the membership SM's on_change so we can fire on_ready once
        # this node appears in the committed voter set.
        self._node.membership_sm.on_change = self._on_membership_change

        # Ring registry SM: cluster-log inventory of named rings (one
        # per shardable cache).  Slice 2 of the multi-ring rollout —
        # bringing up / tearing down per-ring Raft groups is wired in
        # slice 3; for now we just track and persist the registry so
        # an operator can record the desired topology.
        self._ring_registry_sm = RingRegistryStateMachine(
            on_change=self._on_ring_registry_change
        )
        self._node.log.register_state_machine(
            "ring_registry_sm", self._ring_registry_sm
        )

        # Routing SM: cluster-log data-type -> ring mapping (e.g.
        # "jobs" -> "jobs_ring", "events" -> None for broadcast).
        # Gate sites consult the routing table once it's populated;
        # absent entries mean broadcast, preserving today's behaviour.
        self._routing_sm = RoutingStateMachine(on_change=self._on_route_change)
        self._node.log.register_state_machine("routing_sm", self._routing_sm)

        # ``Node.__init__`` already loaded any snapshot, but only the
        # state machines registered at construction time
        # (``membership_sm``) saw the restore.  Re-run the restore
        # now that ``ring_sm`` / ``ring_registry_sm`` / ``routing_sm``
        # are registered so a master coming back from a snapshot
        # rebuilds them from disk instead of starting empty (which
        # would be silently wrong under log compaction).
        if storage is not None:
            try:
                snap = storage.load_snapshot()
            except Exception:  # pylint: disable=broad-except
                snap = None
            if snap and "data" in snap:
                self._node.log.restore_state_machines_from_data(snap["data"])

        # The snapshot restore above populated the registry but did
        # not fire its ``on_change`` (``restore_snapshot`` is a pure
        # store).  Drive bring-up for any active rings that this
        # master was hosting before the restart so the per-ring
        # ``Node`` instances reattach to the dispatcher.  Idempotent
        # — ``_bring_up_ring`` no-ops when the ring is already up.
        for ring_id in self._ring_registry_sm.active_rings():
            entry = self._ring_registry_sm.get(ring_id) or {}
            self._on_ring_registry_change(
                ring_id,
                entry.get("founding_voters", []),
                entry.get("status", RING_STATUS_ACTIVE),
            )

        # Build SaltPeer objects - one per cluster peer (all voting at start).
        peers = [
            SaltPeer(addr, pusher, node_id) for addr, pusher in peer_pushers.items()
        ]
        self._node.peers = peers

        # Register a peer factory so Node.on_config_change can create SaltPeers
        # for addresses that appear in CONFIG entries (covers learner->voter path).
        self._node.register_peer_factory(self._make_peer)

        # peer_pushers is keyed by interface address, matching the
        # callback_node field written into RPC envelopes.  Hand the
        # dispatcher the full ``_nodes`` dict so that inbound RPCs are
        # routed by ``raft_group_id``; passing ``self._nodes``
        # (instead of a bare ``self._node``) means subsequent
        # ``register_ring_node`` calls are visible to the dispatcher
        # without extra plumbing.
        self._dispatcher = RaftDispatcher(self._nodes, node_id, self._peer_pushers)

        # If Node started from a saved snapshot the membership SM was
        # restored before this on_change wiring existed, so the cluster-
        # ready / peer-table side effects never fired.  Reconcile now so
        # _on_ready and on_config_change run for the restored view.
        self._node.reconcile_membership()

        self._heartbeat_handle = None
        # Voter health / auto-replacement state (Ongaro thesis §6.4).
        # ``_recently_demoted`` is leader-local; a new leader on failover
        # starts with an empty cooldown table and re-derives unhealthy
        # peers from incoming AppendEntries replies.
        self._recently_demoted = {}
        self._voter_health_handle = None

    # ------------------------------------------------------------------
    # Membership change / readiness
    # ------------------------------------------------------------------

    def _on_membership_change(self, voters, learners):
        """
        Called by ``MembershipStateMachine`` after every committed CONFIG entry.

        Fires ``on_ready`` (once) when this node's address first appears in the
        committed voter set, signalling that it is a full participant and may
        begin serving minion/CLI traffic.

        The default ``"cluster"`` ring is kept in lock-step with the
        cluster voter set so pre-multi-ring callers
        (``ring_membership.owns(opts, key)`` with no ring name) see a
        meaningful answer.  Per-ring sharding is driven separately by
        each per-ring ``Node``'s own ``MembershipStateMachine``.
        """
        # Lazy import keeps the consensus package independent of the
        # ring module's load order.
        import salt.cluster.ring_membership  # pylint: disable=import-outside-toplevel

        # Keep the default "cluster" ring populated with the current
        # voter set.  Empty ``voters`` shouldn't happen in steady
        # state but we tolerate it (an empty ring answers True for
        # every owns() — broadcast semantics).
        if voters:
            salt.cluster.ring_membership.rebuild(list(voters))

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

    def _on_ring_registry_change(self, ring_id, founding_voters, status):
        """
        Called by :class:`RingRegistryStateMachine` after each
        committed ``RING_REGISTRY`` entry.

        * ``status="active"`` and this master is in ``founding_voters``:
          bring up the per-ring Raft group inside this process.  The
          per-ring ``Node`` shares the same asyncio loop, scheduler,
          and peer transport as the cluster group; only the on-disk
          state and Raft state machines are independent.
        * ``status="destroyed"``: tear down the per-ring Node and
          drop it from the dispatcher's routing table.
        * Otherwise (e.g. an active entry that doesn't list this
          master): nothing to do locally.  Other masters will own the
          ring.
        """
        log.info(
            "RaftService: ring registry committed — ring=%s status=%s "
            "founding_voters=%s",
            ring_id,
            status,
            list(founding_voters or []),
        )
        if status == RING_STATUS_DESTROYED:
            self._tear_down_ring(ring_id)
            return
        if self._node.node_id not in (founding_voters or []):
            # Not a founder — this ring's data plane runs elsewhere.
            return
        self._bring_up_ring(ring_id, founding_voters)

    def _bring_up_ring(self, ring_id, founding_voters):
        """
        Construct and register the per-ring Raft ``Node`` for this
        master.  Idempotent: if the ring is already up locally the
        call is a no-op.

        The per-ring Node has its own :class:`SaltStorage` keyed by
        ``ring_id``, its own ``MembershipStateMachine`` and
        ``RingConfigStateMachine`` registered on its log, its own
        :class:`SaltPeer` instances stamping ``raft_group_id`` into
        outbound RPCs, and its own election + heartbeat path driven
        by the shared scheduler.
        """
        if ring_id == "cluster":
            log.warning(
                "RaftService: refusing to bring up a ring named 'cluster' — "
                "reserved for the main cluster Raft group"
            )
            return
        if ring_id in self._nodes:
            log.debug(
                "RaftService: ring %s already up locally, skipping bring-up",
                ring_id,
            )
            return

        node_id = self._node.node_id
        log.info(
            "RaftService: bringing up ring %s with founders=%s",
            ring_id,
            sorted(founding_voters or []),
        )
        storage = SaltStorage(node_id, self.opts, ring_id=ring_id)
        # Election windows reuse the same opts as the cluster Node —
        # if the operator tuned them for their environment, the
        # per-ring nodes inherit the tuning automatically.
        election_min = self.opts.get("cluster_election_min", 750)
        election_max = self.opts.get("cluster_election_max", 1500)
        ring_node = Node(
            node_id,
            storage=storage,
            voting=True,
            _follower_min=election_min,
            _follower_max=election_max,
            max_log_size=self.opts.get("cluster_max_log_size"),
            max_voters=self.opts.get("cluster_max_voters"),
        )
        ring_node.register_schedule_timeout(self._scheduler.schedule)
        # Per-ring RingConfigStateMachine: each ring has its own
        # members/replicas policy, persisted in its own snapshot
        # envelope.
        ring_config_sm = RingConfigStateMachine(
            on_change=lambda m, r, _ring_id=ring_id: self._on_ring_config_change_for(
                _ring_id, m, r
            )
        )
        ring_node.log.register_state_machine("ring_sm", ring_config_sm)
        # Wire the per-ring MembershipStateMachine's on_change so a
        # committed CONFIG entry on the ring's log triggers a rebuild
        # of the named HashRing.  Without this, ring policy =
        # ``"voters"`` would see the ring's voter set change without
        # the local HashRing reflecting it.
        ring_node.membership_sm.on_change = lambda voters, learners, _ring_id=ring_id: self._on_ring_membership_change_for(
            _ring_id, voters, learners
        )
        # ``Node.__init__`` ran the snapshot restore for
        # ``membership_sm`` only.  Replay it now that ``ring_sm`` is
        # registered so a master that previously hosted this ring
        # picks up its committed policy from disk instead of starting
        # at the SM default.
        try:
            snap = storage.load_snapshot()
        except Exception:  # pylint: disable=broad-except
            snap = None
        if snap and "data" in snap:
            ring_node.log.restore_state_machines_from_data(snap["data"])

        # Build peers for this ring: every founder other than self.
        peers = []
        for addr in sorted(founding_voters or []):
            if addr == node_id:
                continue
            peers.append(self._make_peer(addr, voting=True, raft_group_id=ring_id))
        ring_node.peers = peers
        # Peer factory for membership-change-driven additions.
        ring_node.register_peer_factory(
            lambda addr, voting=True, _ring_id=ring_id: self._make_peer(
                addr, voting=voting, raft_group_id=_ring_id
            )
        )

        # Replay any persisted state.  ``SaltStorage`` was loaded by
        # ``Node.__init__`` already; reconcile fires on_change to
        # rebuild peer flags.
        ring_node.reconcile_membership()

        self._nodes[ring_id] = ring_node
        # Mirror the registration into the dispatcher's routing
        # table so inbound RPCs tagged with this ``raft_group_id``
        # land on the new Node.  The dispatcher keeps its own dict
        # (constructed from a copy at start time) — pushing the
        # update explicitly keeps the two in sync without coupling
        # them.
        self._dispatcher.register_node(ring_id, ring_node)

        ring_node.become_follower()

    def _tear_down_ring(self, ring_id):
        """
        Stop the per-ring ``Node`` and drop it from ``self._nodes``.
        Idempotent.  On-disk state is left in place so an operator
        who re-creates the ring with the same id and founders can
        recover historical state.
        """
        if ring_id == "cluster":
            log.warning("RaftService: refusing to tear down the cluster Raft group")
            return
        ring_node = self._nodes.pop(ring_id, None)
        if ring_node is None:
            return
        self._dispatcher.unregister_node(ring_id)
        # Drop the per-process ring snapshot so subsequent
        # ``owns_for`` calls treat this master as a non-member of the
        # destroyed ring.
        import salt.cluster.ring_membership  # pylint: disable=import-outside-toplevel

        salt.cluster.ring_membership.drop_ring(ring_id)
        log.info("RaftService: tearing down ring %s", ring_id)
        try:
            ring_node.become_follower()
            # Cancel any pending timers stored on the Node; the
            # shared scheduler will simply not re-arm them since the
            # Node is no longer in ``self._nodes`` and the heartbeat
            # tick skips unregistered Nodes.
            if getattr(ring_node, "_follower_timeout", None):
                ring_node._follower_timeout.cancel()
                ring_node._follower_timeout = None
            if getattr(ring_node, "_leader_beacon_timeout", None):
                ring_node._leader_beacon_timeout.cancel()
                ring_node._leader_beacon_timeout = None
        except Exception:  # pylint: disable=broad-except
            log.exception("RaftService: error stopping ring %s", ring_id)

    def _on_ring_membership_change_for(self, ring_id, voters, learners):
        """
        Called by a per-ring :class:`MembershipStateMachine` after each
        committed CONFIG entry on the *ring's* log.  Mirrors the
        cluster-side ``_on_membership_change`` but routes the rebuild
        to the named ring.  Re-applies the current ring policy so the
        ``HashRing`` reflects the new voter set.
        """
        ring_node = self._nodes.get(ring_id)
        if ring_node is None:
            return
        ring_sm = ring_node.log._extra_state_machines.get("ring_sm")
        if ring_sm is None:
            return
        self._on_ring_config_change_for(ring_id, ring_sm.members, ring_sm.replicas)

    def _on_ring_config_change_for(self, ring_id, members, replicas):
        """
        Called by a per-ring :class:`RingConfigStateMachine` after a
        ``RING_CONFIG`` commit on that ring's own log.

        Rebuilds the named ring's :class:`HashRing` from the per-ring
        Raft group's committed voter set.  ``"self"`` means the
        local master is the only ring node (broadcast within the
        ring); ``"voters"`` means the ring contains every committed
        voter and the gate sites will hash by ring ownership.
        """
        import salt.cluster.ring_membership  # pylint: disable=import-outside-toplevel

        ring_node = self._nodes.get(ring_id)
        if ring_node is None:
            log.debug(
                "RaftService: ring=%s policy commit observed but local "
                "Node is not up — skipping rebuild",
                ring_id,
            )
            return
        log.info(
            "RaftService: ring=%s policy committed — members=%s replicas=%d",
            ring_id,
            members,
            replicas,
        )
        if members == RING_MEMBERS_VOTERS:
            voters = ring_node.membership_sm.current_voters()
            salt.cluster.ring_membership.rebuild(ring_id, voters, replicas=replicas)
        else:  # RING_MEMBERS_SELF (default)
            salt.cluster.ring_membership.rebuild(
                ring_id, [ring_node.node_id], replicas=replicas
            )

    def _on_route_change(self, data_type, ring_id):
        """
        Called by :class:`RoutingStateMachine` after each committed
        ``ROUTE`` entry.  Updates the process-local routing snapshot
        consulted by the gate sites in :mod:`salt.master` so a route
        flip takes effect on every master without IPC.
        """
        import salt.cluster.ring_membership  # pylint: disable=import-outside-toplevel

        salt.cluster.ring_membership.set_route(data_type, ring_id)
        if ring_id is None:
            log.info(
                "RaftService: route cleared — data_type=%s now broadcasts",
                data_type,
            )
        else:
            log.info(
                "RaftService: route committed — data_type=%s -> ring=%s",
                data_type,
                ring_id,
            )

    def propose_ring_create(self, ring_id, founding_voters, status=RING_STATUS_ACTIVE):
        """
        Propose a ``RING_REGISTRY`` entry creating (or marking
        destroyed) the named ring.

        Only valid on the leader.  Slice 2 wires the cluster-log
        replication path; the per-ring Raft group does not actually
        come up until slice 3 attaches its lifecycle to
        ``_on_ring_registry_change``.

        :param ring_id:         Operator-chosen name for the ring.
        :param founding_voters: List of master node-ids that will be
                                this ring's initial voter set.  Sorted
                                deterministically before the entry is
                                appended.
        :param status:          ``"active"`` (default) or
                                ``"destroyed"``.

        :raises ValueError:   if ``ring_id`` is empty or ``status`` is
                              unknown.
        :raises RuntimeError: if this node is not currently the leader.
        """
        if not ring_id:
            raise ValueError("propose_ring_create requires a non-empty ring_id")
        if status not in RING_STATUS_VALID:
            raise ValueError(
                f"Unknown ring status {status!r}; "
                f"expected one of {RING_STATUS_VALID}"
            )
        if self._node.state != NodeState.LEADER:
            raise RuntimeError(
                "propose_ring_create must run on the Raft leader; "
                f"this node is in state {self._node.state}"
            )
        founders = sorted(founding_voters or [])
        cmd = {
            "ring_id": ring_id,
            "founding_voters": founders,
            "status": status,
        }
        self._node.log_add(cmd, entry_type=LogEntryType.RING_REGISTRY)

    def propose_ring_destroy(self, ring_id):
        """
        Propose a ``RING_REGISTRY`` entry marking *ring_id* as
        destroyed.  Idempotent at the registry level; the on_change
        callback decides whether to tear down a per-ring Node based
        on its previous status.

        The command omits ``founding_voters`` so the registry SM
        preserves the original founder list as audit history — the
        operator can still see who founded a ring after it's been
        destroyed.
        """
        if not ring_id:
            raise ValueError("propose_ring_destroy requires a non-empty ring_id")
        if self._node.state != NodeState.LEADER:
            raise RuntimeError(
                "propose_ring_destroy must run on the Raft leader; "
                f"this node is in state {self._node.state}"
            )
        cmd = {"ring_id": ring_id, "status": RING_STATUS_DESTROYED}
        self._node.log_add(cmd, entry_type=LogEntryType.RING_REGISTRY)

    def propose_route(self, data_type, ring_id):
        """
        Propose a ``ROUTE`` entry mapping *data_type* to *ring_id*.

        Pass ``ring_id=None`` to clear the route, returning the data
        type to broadcast.  Only valid on the leader.

        :param data_type: Logical cache identifier (e.g. ``"jobs"``).
        :param ring_id:   Ring name to route to, or ``None`` for
                          broadcast.
        :raises ValueError:   if ``data_type`` is empty.
        :raises RuntimeError: if this node is not currently the leader.
        """
        if not data_type:
            raise ValueError("propose_route requires a non-empty data_type")
        if self._node.state != NodeState.LEADER:
            raise RuntimeError(
                "propose_route must run on the Raft leader; "
                f"this node is in state {self._node.state}"
            )
        cmd = {"data_type": data_type, "ring_id": ring_id}
        self._node.log_add(cmd, entry_type=LogEntryType.ROUTE)

    # ------------------------------------------------------------------
    # Peer factory (used by Node.on_config_change)
    # ------------------------------------------------------------------

    def _make_peer(self, addr, voting=True, raft_group_id="cluster"):
        """
        Create a ``SaltPeer`` for *addr*.

        If we already have a pusher for that address (from ``_peer_pushers``)
        it is reused; otherwise we create a new one using the cluster port.
        Called by :meth:`Node.on_config_change` when a CONFIG log entry is
        applied and a previously unknown address appears in the voter list.

        :param raft_group_id: Which Raft group this peer belongs to.
                              Defaults to ``"cluster"`` so the existing
                              cluster-Node call site is unchanged; per-
                              ring bring-up passes the ring's id so the
                              peer stamps every outbound RPC with the
                              ring's group id (and the dispatcher on the
                              receiver routes to the right Node).
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
        return SaltPeer(
            addr,
            pusher,
            self.opts["interface"],
            voting=voting,
            raft_group_id=raft_group_id,
        )

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
        self._schedule_voter_health_check()

    def stop(self):
        """Cancel scheduled callbacks and step the node down."""
        if self._heartbeat_handle is not None:
            self._heartbeat_handle.cancel()
            self._heartbeat_handle = None
        if self._voter_health_handle is not None:
            self._voter_health_handle.cancel()
            self._voter_health_handle = None
        log.info("RaftService: stopped node %s", self._node.node_id)

    # ------------------------------------------------------------------
    # Voter health watchdog (Ongaro thesis §6.4 single-server changes)
    # ------------------------------------------------------------------

    def _schedule_voter_health_check(self):
        """Re-arm the periodic ``_check_voter_health`` timer."""
        interval = self.opts.get("cluster_voter_health_check_interval", 1.0)
        self._voter_health_handle = self._scheduler.schedule(
            interval, self._check_voter_health
        )

    def _check_voter_health(self):
        """
        Periodic leader-side watchdog, run once per scheduled tick
        across every Raft group hosted in this process (cluster +
        per-ring).

        For each group where this master is the current leader: walk
        the voter set, flag voters whose ``last_contact`` is older
        than ``cluster_voter_timeout``, and — if
        ``cluster_auto_replace_voters`` is True — propose a single
        demotion + replacement promotion per tick (Ongaro thesis §6.4
        single-server change semantics).

        Per-group state:

        * ``self._recently_demoted`` is keyed by ``(group_id,
          peer_id)`` so a cooldown on one ring doesn't bleed into
          another.
        * The on-disk sentinel ``cachedir/cluster-health.json`` is a
          structured document with one entry per group — read by
          ``cluster.members`` for the cluster group; per-ring
          consumers can pull from the same file via ``rings.<id>``.

        Safety: relies on each ``Node.propose_voter_demotion`` to
        enforce the ``cluster_min_voters`` floor.  The watchdog
        never bypasses that.  Idempotent on re-entry — a demotion
        CONFIG already in flight leaves the demoted peer in
        ``current_voters`` until commit, so the precondition check
        inside ``propose_voter_demotion`` deduplicates.
        """
        try:
            self._voter_health_handle = None
            now = self._node.get_now()
            timeout = self.opts.get("cluster_voter_timeout", 10.0)
            cooldown = self.opts.get("cluster_demote_cooldown", 60.0)
            auto = self.opts.get("cluster_auto_replace_voters", False)
            min_voters = self.opts.get("cluster_min_voters", 3)

            # Expire cooldown entries first so a fresh tick can
            # promote a candidate that's just exited its cooldown.
            self._recently_demoted = {
                key: ts
                for key, ts in self._recently_demoted.items()
                if now - ts < cooldown
            }

            per_group_unhealthy = {}
            for group_id, node in list(self._nodes.items()):
                if node is None:
                    continue
                unhealthy = []
                if node.state == NodeState.LEADER:
                    voters = set(node.membership_sm.current_voters())
                    for peer in node.peers:
                        if peer.node_id not in voters:
                            continue
                        last = node._peer_last_contact.get(peer.node_id)
                        if last is None:
                            continue
                        if now - last > timeout:
                            unhealthy.append(peer.node_id)
                per_group_unhealthy[group_id] = unhealthy

            self._write_health_sentinel(per_group_unhealthy)

            if not auto:
                return

            for group_id, unhealthy in per_group_unhealthy.items():
                if not unhealthy:
                    continue
                node = self._nodes.get(group_id)
                if node is None or node.state != NodeState.LEADER:
                    continue
                # One demotion + replacement per group per tick.
                target = unhealthy[0]
                if node.propose_voter_demotion(target, min_voters=min_voters):
                    self._recently_demoted[(group_id, target)] = now
                    learners = node.membership_sm.current_learners()
                    for candidate in learners:
                        if (group_id, candidate) in self._recently_demoted:
                            continue
                        if node.match_index.get(candidate, -1) < node.log.index:
                            continue
                        node.propose_voter_promotion_to_replace(candidate)
                        break
        except Exception:  # pylint: disable=broad-except
            log.exception("RaftService: voter health check failed")
        finally:
            self._schedule_voter_health_check()

    def _write_health_sentinel(self, per_group_unhealthy):
        """
        Persist a structured health sentinel covering every Raft
        group hosted in this process.

        Shape (a single JSON document at
        ``cachedir/cluster-health.json``)::

            {
              "updated_at": <epoch>,
              "unhealthy_voters": [<cluster_group_unhealthy>, …],
              "recently_demoted": [<cluster_group_demoted>, …],
              "rings": {
                "<ring_id>": {
                  "unhealthy_voters": […],
                  "recently_demoted": […],
                },
                …
              }
            }

        The top-level ``unhealthy_voters`` / ``recently_demoted``
        fields preserve the pre-multi-ring shape so the
        ``cluster.members`` runner reads them unchanged.  Per-ring
        consumers reach into ``rings.<id>`` for the same view per
        ring.
        """
        import json  # pylint: disable=import-outside-toplevel
        import os  # pylint: disable=import-outside-toplevel
        import time  # pylint: disable=import-outside-toplevel

        import salt.utils.atomicfile  # pylint: disable=import-outside-toplevel

        cachedir = self.opts.get("cachedir")
        if not cachedir:
            return
        path = os.path.join(cachedir, "cluster-health.json")

        # Split the cooldown table by group for the per-ring view.
        cooldown_by_group = {}
        for (group_id, peer_id), _ts in self._recently_demoted.items():
            cooldown_by_group.setdefault(group_id, []).append(peer_id)

        cluster_unhealthy = per_group_unhealthy.get("cluster", [])
        cluster_cooldown = cooldown_by_group.get("cluster", [])

        rings = {}
        for group_id, unhealthy in per_group_unhealthy.items():
            if group_id == "cluster":
                continue
            rings[group_id] = {
                "unhealthy_voters": sorted(unhealthy),
                "recently_demoted": sorted(cooldown_by_group.get(group_id, [])),
            }

        body = {
            "updated_at": time.time(),
            "unhealthy_voters": sorted(cluster_unhealthy),
            "recently_demoted": sorted(cluster_cooldown),
            "rings": rings,
        }
        # Atomic write so the every-N-seconds watchdog rewrite
        # never overlaps an operator's ``cluster.members`` read on
        # a torn-mid-write file.
        try:
            with salt.utils.atomicfile.atomic_open(path, "w") as fp:
                json.dump(body, fp)
        except OSError as exc:
            log.warning(
                "RaftService: could not write health sentinel %s: %s", path, exc
            )

    # ------------------------------------------------------------------
    # Operator overrides
    # ------------------------------------------------------------------

    def propose_voter_demotion(self, peer_id):
        """
        Operator-facing entry point to demote a voter manually.

        Works regardless of ``cluster_auto_replace_voters`` so an operator
        can force a known-bad voter out of the set even when auto-
        replacement is disabled.  Returns the same ``bool`` as
        ``Node.propose_voter_demotion``.

        IPC story: this method runs inside the publish daemon's process,
        which is the only place the ``Node`` is reachable today.  A
        future runner -> daemon command channel can call this directly;
        until then it is callable from python hooks running inside the
        master process.
        """
        log.info("RaftService: operator-requested demotion of %s", peer_id)
        min_voters = self.opts.get("cluster_min_voters", 3)
        return self._node.propose_voter_demotion(peer_id, min_voters=min_voters)

    def propose_voter_promotion(self, peer_id):
        """
        Operator-facing entry point to promote a learner to voter.

        Same operator-override semantics as ``propose_voter_demotion``.
        Subject to the existing ``cluster_max_voters`` cap and the
        caught-up precondition; both are enforced inside
        ``Node.propose_voter_promotion_to_replace``.
        """
        log.info("RaftService: operator-requested promotion of %s", peer_id)
        return self._node.propose_voter_promotion_to_replace(peer_id)

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

        if self._node.state == NodeState.LEADER:
            # Commit the founding CONFIG *before* the new learner becomes
            # a known peer.  ``_maybe_commit_founding_config`` derives its
            # voter set from ``self._node.peers`` — if the new learner is
            # already in that list it would be incorrectly inducted into
            # the founding voter pool.  No-op when log.index >= 0.
            self._maybe_commit_founding_config()

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
            # *promotion* CONFIG that fires once the learner catches up;
            # this entry only registers the node as a learner, not a voter.
            #
            # Source the voter / learner sets from the leader's in-memory
            # peer list rather than ``membership_sm.current_voters()``:
            # ``on_config_change`` updates peer flags eagerly on the leader
            # when ``log_add`` is called, but ``membership_sm.apply()``
            # only fires after commit.  So immediately after the founding
            # CONFIG is appended (but before quorum acks come in), the
            # leader's ``peers`` already reflect the new view while the SM
            # still has the empty pre-commit state.  Reading from peers
            # avoids the gap.
            from salt.cluster.consensus.raft.log import (
                LogEntryType,  # pylint: disable=import-outside-toplevel
            )

            voters = sorted(
                {self._node.node_id} | {p.node_id for p in self._node.peers if p.voting}
            )
            learners = sorted({p.node_id for p in self._node.peers if not p.voting})
            # Also fold in any committed learners from the SM that may not
            # yet be peer entries (defensive — covers a state-sync restore
            # path).
            for known_learner in self._node.membership_sm.current_learners():
                if known_learner not in voters:
                    learners = sorted(set(learners) | {known_learner})

            # Only emit the CONFIG when this call actually changes the
            # registered set — idempotent against repeat joins.
            current_voters_sm = self._node.membership_sm.current_voters()
            current_learners_sm = self._node.membership_sm.current_learners()
            already_known = (
                peer_addr in current_voters_sm or peer_addr in current_learners_sm
            )
            if not already_known and peer_addr in learners:
                try:
                    self._node.log_add(
                        {"voters": voters, "learners": learners},
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

        Iterates every Raft group hosted in this process — the
        cluster group plus any per-ring groups — and heartbeats from
        whichever ones consider themselves leader.  On the *first*
        heartbeat after winning an election with an empty log,
        commits a founding CONFIG so the group's voter set is durably
        recorded.

        A single tick services all groups: each group's heartbeat
        load scales with peer count; even a master that hosts a dozen
        rings still issues O(peers) sends per tick.
        """
        try:
            for ring_id, node in list(self._nodes.items()):
                if node is None:
                    continue
                if node.state != NodeState.LEADER:
                    continue
                self._maybe_commit_founding_config(ring_id, node)
                for peer in node.peers:
                    try:
                        ni = node.next_index.get(peer.node_id, node.log.index + 1)
                        # Send a heartbeat (empty) only when the peer
                        # is caught up.  If it's behind, include the
                        # entries so it can advance — important for
                        # lagging learners.
                        entries = [] if ni > node.log.index else None
                        node.send_append_entries(peer, entries=entries)
                    except Exception:  # pylint: disable=broad-except
                        log.exception(
                            "RaftService: error sending heartbeat to %s (ring=%s)",
                            peer.node_id,
                            ring_id,
                        )
        except Exception:  # pylint: disable=broad-except
            log.exception("RaftService: error in heartbeat tick")
        finally:
            self._schedule_heartbeat()

    def _maybe_commit_founding_config(self, ring_id="cluster", node=None):
        """
        Propose the initial CONFIG entry for *node* when its log is
        empty.

        ``ring_id`` defaults to ``"cluster"`` (and ``node`` to
        ``self._node``) so the existing ``self._maybe_commit_founding_config()``
        call sites — heartbeat tick on the cluster Node, the
        ``notify_peer_joined`` flow — keep working without changes.
        Per-ring callers (multi-ring heartbeat tick) pass both.

        Records the founding voter set durably so that a node
        recovering from storage can reconstruct membership without
        relying solely on ``opts["cluster_peers"]`` (cluster group)
        or the registry entry (per-ring groups).

        For the cluster group the bootstrap pool comes from
        ``cluster_peers`` (the static list the operator configured).
        For a per-ring group it comes from that ring's registry
        entry on the cluster log, which records the founding voter
        set chosen by the operator when the ring was created.

        No-ops if the log already has any entries (founding entry
        already written, or this leader inherited a non-empty log).
        """
        if node is None:
            node = self._node
        if node.log.index >= 0:
            return
        # Membership already populated (e.g. via state-sync or test
        # seeding) — no need to synthesize a founding CONFIG.
        if node.membership_sm.current_voters():
            return
        from salt.cluster.consensus.raft.log import (
            LogEntryType,  # pylint: disable=import-outside-toplevel
        )

        if ring_id == "cluster":
            # Deterministic bootstrap pool: sorted set of
            # {this node} ∪ peer addresses.  Every prospective
            # founder runs this code, but only the deterministic
            # founder (lowest interface in the pool; see
            # ``salt/master.py:920`` and
            # ``salt/channel/server.py:2101``) actually writes the
            # CONFIG.
            bootstrap_pool = sorted({node.node_id, *[p.node_id for p in node.peers]})
        else:
            # Per-ring founders come from the registry entry on the
            # cluster log — the operator-chosen founding voters.
            registry_entry = self._ring_registry_sm.get(ring_id) or {}
            bootstrap_pool = sorted(registry_entry.get("founding_voters", []))
            if not bootstrap_pool:
                # Registry entry already missing or destroyed — don't
                # commit a spurious founding CONFIG.
                return

        # ``cluster_max_voters`` (default ``None``) caps the founding
        # voter set.  Excess peers go into the learner set in the
        # same CONFIG entry so they're still durably registered.
        max_voters = self.opts.get("cluster_max_voters")
        if max_voters is not None and len(bootstrap_pool) > max_voters:
            voters = bootstrap_pool[:max_voters]
            learners = bootstrap_pool[max_voters:]
        else:
            voters = bootstrap_pool
            learners = []
        log.info(
            "RaftService: committing founding CONFIG entry (ring=%s) "
            "voters=%s learners=%s",
            ring_id,
            voters,
            learners,
        )
        try:
            node.log_add(
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
