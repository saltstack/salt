"""
One authenticated bidirectional connection to one peer master.

A :class:`PeerMasterLink` is the semantic layer that consumes
Salt's existing channel primitives directly:

* Opens one :class:`salt.channel.client.AsyncReqChannel` per
  active endpoint for ``_master_auth`` and outbound topology
  RPCs (``topology/pub``, ``topology/ret``, ``topology/sum``).
* Opens one :class:`salt.channel.client.AsyncPubChannel` per
  active endpoint for the inbound pub stream (events, returns,
  summaries from the peer).
* Adds health state (:class:`LinkHealth`), endpoint
  multiplexing, and the quiesce / detach lifecycle.
* Dispatches inbound messages to
  :class:`salt.topology.router.TopologyRouter`.
* Builds the signed, serialized payloads for publish/return/
  summary once per outbound call so a fan-out across N links
  pays sign cost once, not N times.

The channel classes themselves are untouched --- they are used
as library primitives.  Session AES, path-stamped envelopes,
and tag dispatch are protocol concerns and live here, not in
``salt/channel/``.

The server side (inbound listener on this master's own
``topology_link_port``) lives in
:mod:`salt.topology.link_manager`, which uses the existing
:class:`salt.channel.server.ReqServerChannel` as its
transport.

Each link is logically one identity (``peer_cluster_id``) with
N reachable endpoints; the link picks one as the active
endpoint and fails over to another if the primary becomes
unreachable.  Failover doesn't require re-authentication ---
the session AES is pinned to the identity, not the endpoint.
"""

import logging

log = logging.getLogger(__name__)


class LinkHealth:
    """
    Health state of a :class:`PeerMasterLink`.

    Values are plain strings so they serialize cleanly into
    runner output and event payloads.  Follows the sibling
    pattern of ``class LogEntryType`` in
    :mod:`salt.cluster.consensus.raft.log`.
    """

    #: No connection has been attempted yet.
    INITIAL = "initial"
    #: Mid-handshake --- endpoint selected, auth RPC in progress.
    CONNECTING = "connecting"
    #: Handshake complete, actively exchanging traffic.
    CONNECTED = "connected"
    #: Previously connected; current endpoint is failing but
    #: failover candidates remain in ``PeerMasterLink.endpoints``.
    DEGRADED = "degraded"
    #: No reachable endpoint for the peer cluster.
    DISCONNECTED = "disconnected"
    #: The peer is pending acceptance on either side.  Link is
    #: parked in a retry loop like a minion waiting for
    #: ``salt-key -a``.
    PENDING_ACCEPT = "pending_accept"
    #: Operator initiated a detach via ``salt-key -d ... --master``.
    #: Link rejects new publishes but drains in-flight returns
    #: for ``topology_detach_quiesce`` seconds before transitioning
    #: to DISCONNECTED.
    QUIESCING = "quiescing"


class LinkUnavailable(Exception):
    """Raised when a send is attempted on a link that cannot deliver."""


class PeerMasterLink:
    """
    One peer-master link.

    A link is identified by the remote peer's ``cluster_id``,
    learned during handshake.  Multiple :class:`PeerRef` seed
    entries pointing at the same peer cluster collapse to one
    :class:`PeerMasterLink` after first handshake succeeds; later
    refs become additional endpoints on the same link.

    Lifetime: created by :mod:`salt.topology.link_manager` at
    startup from the loaded
    :class:`salt.config.topology.TopologyConfig`, or on inbound
    connection acceptance; destroyed on ``MASTER_PEER_DETACH``.

    Owned by the publish daemon only.  MWorkers do not hold link
    objects; they look up breadcrumbs via
    :mod:`salt.topology.breadcrumbs` and hand off upstream
    dispatch to the publish daemon via one event-bus message per
    return that needs forwarding.
    """

    def __init__(self, opts, seed_ref, io_loop):
        """
        :param opts: Master opts.
        :param seed_ref: Initial :class:`PeerRef` to connect to.
            More endpoints are added by :meth:`add_endpoint`
            after handshake exposes the peer cluster's full peer
            list.
        :param io_loop: Asyncio loop; must be the same loop used
            by the master's publish daemon.
        """

    @property
    def peer_cluster_id(self):
        """
        The peer's ``cluster_id``.

        ``None`` until the first successful handshake.  Available
        afterward even if the link later goes DISCONNECTED, since
        the identity is persistent across reconnects.
        """

    @property
    def health(self):
        """Current :class:`LinkHealth` state as a string."""

    @property
    def remote_summary(self):
        """
        Most recent :class:`salt.topology.summary.ClusterSummary`
        received from the peer, or ``None`` if no summary has
        arrived yet.
        """

    @property
    def endpoints(self):
        """
        All known endpoints for this peer cluster.

        The first entry is the active endpoint; the rest are
        failover candidates populated from the peer cluster's
        Raft membership (shared with us during handshake and
        refreshed via subsequent summary updates).
        """

    def add_endpoint(self, ref):
        """
        Record an additional reachable endpoint for this peer
        cluster.

        Called when a summary or a Raft membership update
        exposes a new peer-cluster member.  Deduplicates against
        existing endpoints by ``(host, port)``.
        """

    async def connect(self):
        """
        Perform the ``_master_auth`` handshake.

        On first connect, presents this master's identity public
        key.  The peer may respond ``retry`` (pending human
        accept via ``salt-key -a <cluster_id> --master``) or
        ``ok`` with the session AES.  Retries with backoff while
        the link is in :data:`LinkHealth.PENDING_ACCEPT`.

        After successful connect, subscribes to the peer's
        ``topology_link_port`` publish channel using the
        configured ``event_subscriptions`` from this master's
        ``topology.conf``.

        :raises asyncio.CancelledError: If the link is torn down
            during connect.
        """

    async def disconnect(self):
        """
        Tear down the inbound subscription and the outbound req
        channel.

        Does NOT remove the peer from the registry --- that is a
        ``MASTER_PEER_DETACH`` concern separate from transient
        disconnects.  A disconnected link can be reconnected via
        :meth:`connect` without new human accept steps.
        """

    async def quiesce(self):
        """
        Transition the link to :data:`LinkHealth.QUIESCING` and
        schedule the final disconnect after
        ``opts["topology_detach_quiesce"]`` seconds.

        During quiesce, :meth:`send_publish` raises
        :class:`LinkUnavailable` so no new publishes cross the
        link, but :meth:`send_return` continues to drain
        in-flight returns.  Called by
        :func:`salt.topology.link_manager.remove_link` on
        detach so returns in flight aren't dropped.
        """

    async def send_publish(self, load, path):
        """
        Forward a publish down this link.

        :param load: The complete publish load, including the
            ``topology`` envelope that already carries
            ``origin``, ``destinations``, ``jid_prefix``.
        :param path: ``cluster_id`` strings already traversed.
            Caller is responsible for appending the current
            ``cluster_id`` before calling; this method does not
            mutate ``path``.
        :raises LinkUnavailable: If the link is DISCONNECTED,
            QUIESCING, or PENDING_ACCEPT with no acceptable
            session yet.
        """

    async def send_return(self, ret_batch, path):
        """
        Send a batch of minion returns back up this link toward
        the origin cluster.

        Returns are aggregated at the sending cluster before
        crossing the link to amortize signing cost over the
        batch.  Caller controls batch granularity --- typically
        either time-based (every N ms) or count-based (every M
        returns), whichever comes first.

        :param ret_batch: List of individual return records.
            Each record carries its own ``cluster_path`` for
            parent-side disambiguation of duplicate minion ids.
        :param path: Cluster path the batch has traversed so
            far.  Appended at each hop and consulted at the
            origin to close breadcrumbs.
        :raises LinkUnavailable: Same conditions as
            :meth:`send_publish` except QUIESCING, which permits
            returns.  Caller is responsible for either retrying
            later or buffering.
        """

    async def send_event(self, event, path):
        """
        Forward a single event to the peer if the peer has
        subscribed to its tag.

        Dropped silently (TRACE log) if no subscription matches
        --- this is the normal path for the vast majority of
        events, which stay local.
        """

    async def send_summary(self, summary):
        """
        Push a fresh :class:`salt.topology.summary.ClusterSummary`
        to the peer.

        Called on ``topology_summary_interval`` by the summary
        heartbeat task and also on membership-change events
        inside this cluster (so peers get a fresh count promptly
        after minions attach/detach).
        """

    async def subscribe(self, tag_patterns):
        """
        Register the given glob tag patterns as the set of
        events this master wants forwarded from the peer.

        Replaces any previous subscription set; the peer applies
        the new set on receipt.  Propagated to the peer in-band
        on the next outbound message or on the next heartbeat,
        whichever comes first.
        """
