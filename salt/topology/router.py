"""
Routing semantics for master topology.  Publish-daemon-only.

The router has three responsibilities:

1. On outgoing publishes, extract the ``C@`` cluster scope and
   decide which peer links need to receive the publish (and which,
   if any, additional transit hops are needed to reach non-adjacent
   destinations).  Writes a breadcrumb into
   :mod:`salt.topology.breadcrumbs` for each forwarded publish.
2. On incoming returns, consult the breadcrumb MmapCache and
   forward each return along the recorded inbound-link path
   toward the origin cluster.
3. On incoming events from peers, check this master's local
   event bus subscribers and re-fire the event (with
   ``cluster_path`` prefix on the tag) for consumption by local
   reactors and listeners.

Storage model
-------------
Peer registry (identity key, accepted peers, last-received
summary per peer)
    Read via :mod:`salt.topology.registry` (MmapCache).  Writes
    happen either directly (solo master) or via Raft commits
    (:class:`salt.cluster.consensus.raft.topology.TopologyStateMachine`
    applies to the same MmapCache).  Readable from any process.

Breadcrumbs (``jid -> inbound link``)
    Read/write via :mod:`salt.topology.breadcrumbs` (MmapCache).
    Publish daemon writes; MWorkers also read.  Entry
    ``expiry_at`` in the value carries TTL.

Routing table (``cluster_id -> next_hop list``)
    In-process dict on the router.  Only the publish daemon
    makes routing decisions; MWorkers don't, so no MmapCache
    needed.

Return hand-off
---------------
When a return arrives at an MWorker and the breadcrumb says
"forward upstream," the MWorker fires one
``salt/topology/return/<origin>/<jid>`` event.  The publish
daemon runs one event subscriber per outbound peer link so a
slow link does not block aggregation on the others --- see
``_handle_topology_return_event`` on this router.
"""

import logging

log = logging.getLogger(__name__)


def extract_cluster_scope(tgt):
    """
    Return the set of ``cluster_id`` strings mentioned positively
    in ``C@`` clauses of a compound target.

    Returns ``None`` when:

    * The target contains no ``C@`` clause at all -> "flood per
      transit-default".
    * The target contains ``not`` anywhere -> conservatively
      flood.  The receiving clusters' local compound evaluation
      (which still sees the ``not C@...``) correctly excludes
      themselves on local resolution, so flood-and-let-local-
      eval-sort-it-out gives correct semantics without requiring
      the router to parse negation.

    Returns the extracted set otherwise.

    :param tgt: Target string or already-tokenized list.
    """


def strip_cluster_scope(tgt):
    """
    Return a copy of ``tgt`` with every ``C@...`` token removed
    and surrounding AND operators tidied so the residual
    re-parses as a valid compound expression.

    Called by
    :meth:`salt.channel.server.MasterPubServerChannel.publish_payload`
    *after* dispatching to remote peer links, immediately
    before publishing to this cluster's own minions.  Keeps
    minion-side compound evaluation oblivious to cluster scope
    and preserves backward compatibility with pre-topology
    minions.

    Examples:

    * ``"C@east and web-*"`` -> ``"web-*"``
    * ``"C@east,west and G@os:ubuntu"`` -> ``"G@os:ubuntu"``
    * ``"(C@east and web-*) or (C@west and db-*)"`` ->
      ``"(web-*) or (db-*)"`` --- when evaluated on east this
      is equivalent to ``web-* or False``, which is correct.

    **Negation handling**: when ``not`` appears near a ``C@``
    (e.g. ``"not C@east and web-*"``), naive stripping produces
    ``"not and web-*"`` which fails to parse.  In this case,
    DO NOT strip; let the full compound (with the ``C@`` term
    intact) reach the minion if the minion is topology-aware,
    or let :func:`extract_cluster_scope` fall through to flood
    semantics so the receiving cluster evaluates the full
    expression locally and self-excludes correctly.

    If the residual after a valid strip would be empty (e.g.
    target ``"C@east"`` alone), returns ``"*"`` so the publish
    still matches every local minion on the destination cluster.

    Fuzzing against the compound grammar is part of the test
    plan --- all residuals must re-parse via
    :func:`salt.utils.minions.parse_target`.
    """


def get_router():
    """
    Module-level accessor for the process-wide
    :class:`TopologyRouter` instance.

    Returns ``None`` when topology is disabled; callers in the
    publish daemon path check this before invoking any routing
    logic.
    """


async def on_publish(load, io_loop):
    """
    Entry point called from
    :meth:`salt.channel.server.MasterPubServerChannel.publish_payload`.

    Owns the full topology fan-out so the channel class does not
    have to know about links, breadcrumbs, or scope extraction.
    Internally:

    1. Consults :func:`get_router`; returns immediately if
       topology is not active in this process.
    2. Calls :meth:`TopologyRouter.route_publish`.
    3. Schedules per-link :meth:`PeerMasterLink.send_publish`
       tasks on ``io_loop``.
    4. Gathers task results and emits a
       ``salt/topology/pub/failed/<cluster_id>`` event for any
       link that raised, so operators see per-cluster failures
       instead of swallowed task exceptions.
    """


class TopologyRouter:
    """
    Per-process routing hub.

    Instantiated once by :func:`salt.topology.link_manager.start`
    and held as a module-level reference accessible from
    :meth:`salt.channel.server.MasterPubServerChannel.publish_payload`
    and the publish daemon's topology inbound dispatcher.
    """

    def __init__(self, opts, registry_cache, breadcrumbs_cache):
        """
        :param opts: Master opts.
        :param registry_cache: Writer-mode handle onto the
            registry MmapCache
            (:func:`salt.topology.registry.open_writer`).  Used
            for reads of peer state and (solo master only)
            direct writes; clustered masters' writes flow
            through Raft
            :class:`salt.cluster.consensus.raft.topology.TopologyStateMachine`
            which applies into the same MmapCache.
        :param breadcrumbs_cache: Writer-mode handle onto the
            breadcrumbs MmapCache
            (:func:`salt.topology.breadcrumbs.open_writer`).
        """

    def route_publish(self, load):
        """
        Decide which links a new publish should fan out on, and
        whether this cluster should also publish locally.

        At the origin, builds the ``load["topology"]`` envelope:

        * ``origin`` = this cluster's ``cluster_id``.
        * ``destinations`` = extract_cluster_scope result (set
          of named clusters), or ``None`` for flood.
        * ``transit_match`` = True (origin always matches
          locally when it's in scope).
        * ``path`` = ``[]`` --- each hop appends its own
          authenticated ``cluster_id`` on *receive*, not on
          send.

        The jid itself stays in its native Salt format.  Earlier
        drafts prefixed the jid with ``<cluster_id>:``; that
        broke :func:`salt.utils.jid.is_jid`, ``unique_jid``,
        ``SyndicManager`` event filtering, and shipped returner
        schemas.  Origin tracking now lives in the envelope.

        :returns: ``(links_to_dispatch, local_match)``.
        """

    def forward_publish(self, load, inbound_link):
        """
        Decide forwarding for a publish received from an inbound
        peer.

        **Path authentication rule**: on receive, this method
        asserts ``load["topology"]["path"][-1]`` matches
        ``inbound_link.peer_cluster_id`` --- if the sender's
        self-reported last hop does not match the authenticated
        link identity, the message is dropped as tampered.  The
        receiver then appends its OWN authenticated
        ``cluster_id`` to the path; sender-provided paths are
        never trusted.

        **Loop detection** against the authenticated path: if
        this cluster already appears, drop.

        **Destinations-shrinking**: if ``destinations`` is a
        set (not None), remove this cluster from the forwarded
        copy so the next hop sees only remaining targets.  Also
        set ``transit_match`` for the forwarded copy based on
        whether each next-hop cluster is a destination or a
        transit stop.

        Records a breadcrumb for return routing via
        :meth:`record_breadcrumb`.

        :returns: Same shape as :meth:`route_publish`.
            ``local_match`` on THIS cluster is True when
            ``transit_match`` is True for this cluster
            (destination hit) or ``destinations`` is ``None``
            and this is a flood target.
        """

    def route_return(self, ret):
        """
        For a return record generated by a local minion whose
        originating publish came from a topology peer, consult
        the breadcrumb table using ``ret["jid"]`` (which carries
        the originating ``cluster_id`` prefix) and return the
        link to send back on.

        Returns ``None`` if there is no breadcrumb --- the
        return is either from a locally-originated publish, or
        the breadcrumb has already expired.  In both cases the
        caller falls back to normal local storage.
        """

    def route_event(self, event):
        """
        Return the set of outbound peer links that have
        subscribed to the event's tag.

        Called by the event bus hook on every locally-fired
        event (when topology is enabled).  Empty return -> event
        stays local, no wire traffic.
        """

    def record_breadcrumb(self, jid, inbound_link, timeout):
        """
        Store a ``jid -> inbound_link`` mapping for return
        routing.

        Expiry is computed as
        ``now + min(timeout + opts["topology_breadcrumb_grace"],
        opts["topology_breadcrumb_max_age"])``.

        Called by :meth:`forward_publish` after relaying a
        publish down the graph.
        """

    def lookup_breadcrumb(self, jid):
        """
        Return the inbound link previously recorded for ``jid``,
        or ``None`` if no breadcrumb exists or if the breadcrumb
        has expired.
        """

    def cleanup_breadcrumbs(self):
        """
        Remove expired breadcrumbs from the in-memory table.

        Called periodically by the publish daemon's housekeeping
        loop (typically every ``topology_breadcrumb_grace``
        seconds).  Delegates to
        :func:`salt.topology.breadcrumbs.cleanup`.
        """

    def ingest_summary(self, summary, inbound_link):
        """
        Fold an inbound summary into state.

        **Path authentication**: asserts ``summary.path[-1] ==
        inbound_link.peer_cluster_id`` AND
        ``self.opts["cluster_id"] not in summary.path`` on
        receive.  A hostile or buggy peer that sends a summary
        with ``path=[X, self, inbound]`` would otherwise
        install a route for X whose next hop is ``inbound``,
        creating a 2-hop loop as soon as X traffic arrives.
        Rejects on either assertion failure with a WARNING log.

        Three effects after validation:

        1. Write the summary into the (publish-daemon-local)
           ``last_summary`` state for the peer.
        2. If the summary's ``path`` exposes a
           newly-reachable cluster not currently in the routing
           table, update the local routing table.
        3. Re-forward (with ``path`` extended via
           :func:`salt.topology.summary.with_path_extended`) to
           this master's other peers that have not already seen
           it (loop detection via path membership).

        Note: summaries are NOT Raft-replicated (soft state).
        The routing table is likewise local to each publish
        daemon.  An earlier draft proposed ``MASTER_PEER_ROUTE``
        as a replicated entry type; that was removed to avoid
        the "snapshot replay vs live gossip replay" divergence
        it would have caused.
        """
