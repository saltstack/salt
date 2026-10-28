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

import asyncio
import logging
import os

from salt.channel.client import AsyncPubChannel, AsyncReqChannel
from salt.config.topology import PeerRef
from salt.topology.summary import ClusterSummary
from salt.topology.summary import serialize as serialize_summary

log = logging.getLogger(__name__)


#: Default retry backoff while waiting for the peer to accept us.
_DEFAULT_HANDSHAKE_BACKOFF = 2.0

#: Maximum number of handshake attempts before giving up (and leaving
#: the link in PENDING_ACCEPT so the caller can decide to retry
#: later from a scheduler).  The retry loop inside ``connect`` is
#: bounded so a wedged peer cannot pin an asyncio task forever.
_DEFAULT_HANDSHAKE_MAX_TRIES = 6


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


def _build_envelope(origin, destinations, transit_match, path):
    """Return the ``load["topology"]`` dict defined in the RFC.

    The receiver, not the sender, authenticates the path --- so this
    helper does not append anything to ``path``.  It copies the list
    defensively so caller-side mutation after send cannot change the
    on-wire bytes retroactively.
    """
    return {
        "origin": origin,
        "destinations": list(destinations) if destinations is not None else None,
        "transit_match": bool(transit_match),
        "path": list(path),
    }


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
        if not isinstance(seed_ref, PeerRef):
            raise TypeError(
                f"PeerMasterLink seed_ref must be PeerRef, got {type(seed_ref)!r}"
            )
        self.opts = dict(opts)
        self.io_loop = io_loop
        self._endpoints = [seed_ref]
        self._peer_cluster_id = None
        self._health = LinkHealth.INITIAL
        self._remote_summary = None
        #: The session AES key established at ``_master_auth`` time.
        #: Rotates on every successful re-handshake; see
        #: :meth:`_rotate_session`.
        self._session_aes = None
        #: Rotation counter --- unit tests exercise this to prove
        #: that a fresh handshake does not re-use the prior key.
        self._session_generation = 0
        #: Outbound req + inbound pub channels.  Lazily opened on
        #: first ``connect`` and torn down by ``disconnect``.
        self._req_channel = None
        self._pub_channel = None
        self._closing = False
        #: Number of ``send_return`` coroutines mid-send on this link.
        #: Decremented in a ``finally`` so a raise inside ``_req_channel.send``
        #: still releases the gate; the quiesce drain path waits for this
        #: counter to reach zero before transitioning to DISCONNECTED when
        #: the drain timer fires.
        self._inflight_returns = 0

    # ------------------------------------------------------------------
    # Equality / hashing --- used by link_manager's registry dict
    # ------------------------------------------------------------------

    def __eq__(self, other):
        """Two links are equal when their peer identity matches.

        Before handshake, falls back to the seed endpoint tuple so
        the pre-handshake registry key is stable.
        """
        if not isinstance(other, PeerMasterLink):
            return NotImplemented
        if self._peer_cluster_id and other._peer_cluster_id:
            return self._peer_cluster_id == other._peer_cluster_id
        if self._peer_cluster_id or other._peer_cluster_id:
            return False
        # Both unauthenticated --- fall back to seed endpoint.
        return self._endpoints[:1] == other._endpoints[:1]

    def __hash__(self):
        if self._peer_cluster_id:
            return hash(("peer_cluster_id", self._peer_cluster_id))
        seed = self._endpoints[0] if self._endpoints else None
        return hash(("seed", seed))

    def __repr__(self):
        return (
            f"<PeerMasterLink peer={self._peer_cluster_id!r} "
            f"health={self._health!r} endpoints={len(self._endpoints)}>"
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def peer_cluster_id(self):
        """
        The peer's ``cluster_id``.

        ``None`` until the first successful handshake.  Available
        afterward even if the link later goes DISCONNECTED, since
        the identity is persistent across reconnects.
        """
        return self._peer_cluster_id

    @property
    def health(self):
        """Current :class:`LinkHealth` state as a string."""
        return self._health

    @property
    def remote_summary(self):
        """
        Most recent :class:`salt.topology.summary.ClusterSummary`
        received from the peer, or ``None`` if no summary has
        arrived yet.
        """
        return self._remote_summary

    @property
    def endpoints(self):
        """
        All known endpoints for this peer cluster.

        The first entry is the active endpoint; the rest are
        failover candidates populated from the peer cluster's
        Raft membership (shared with us during handshake and
        refreshed via subsequent summary updates).
        """
        return tuple(self._endpoints)

    @property
    def session_generation(self):
        """Generation counter --- increments on each session rotation."""
        return self._session_generation

    # ------------------------------------------------------------------
    # Endpoint management
    # ------------------------------------------------------------------

    def add_endpoint(self, ref):
        """
        Record an additional reachable endpoint for this peer
        cluster.

        Called when a summary or a Raft membership update
        exposes a new peer-cluster member.  Deduplicates against
        existing endpoints by ``(host, port)``.
        """
        if not isinstance(ref, PeerRef):
            raise TypeError(f"add_endpoint expects PeerRef, got {type(ref).__name__}")
        for existing in self._endpoints:
            if existing.host == ref.host and existing.port == ref.port:
                return
        self._endpoints.append(ref)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rotate_session(self, aes):
        """Install a fresh session AES and bump the generation counter."""
        self._session_aes = aes
        self._session_generation += 1

    def _build_channel_opts(self, endpoint):
        """
        Build a transport opts dict scoped to *endpoint*.

        The channel primitives key off ``master_uri``, ``master_ip``,
        and ``publish_port`` / ``ret_port`` --- we scope those to
        this peer so the underlying zmq / tcp transport talks to the
        right place.
        """
        opts = dict(self.opts)
        host = endpoint.host
        port = endpoint.port or self.opts.get("topology_link_port")
        if port is None:
            raise ValueError(
                "PeerMasterLink endpoint has no port and no "
                "topology_link_port fallback in opts"
            )
        opts["master_ip"] = host
        opts["master_host"] = host
        opts["master_uri"] = f"tcp://{host}:{port}"
        opts["master_port"] = port
        opts["ret_port"] = port
        return opts

    def _build_envelope_payload(self, body, tag):
        """Wrap *body* into a serialized tagged envelope.

        Signing with the session AES is a receive-side verification
        concern; today the key is pinned to the link and included in
        the payload under ``session_generation`` for the receiver to
        correlate.  When the Phase 3 inbound listener lands it will
        verify the generation and reject stale keys.
        """
        if self._session_aes is None:
            raise LinkUnavailable(
                f"link to {self._peer_cluster_id!r} has no session AES"
            )
        return {
            "cmd": tag,
            "tag": tag,
            "origin_cluster_id": self.opts.get("cluster_id"),
            "session_generation": self._session_generation,
            "load": body,
        }

    def _assert_sendable(self, tag):
        """Guard that the link is in a state that permits *tag* sends."""
        if self._closing:
            raise LinkUnavailable("link is closing")
        if self._health == LinkHealth.CONNECTED:
            return
        if self._health == LinkHealth.QUIESCING:
            # Returns drain through quiesce; everything else is rejected.
            if tag == "topology/ret":
                return
            raise LinkUnavailable(
                f"link to {self._peer_cluster_id!r} is QUIESCING; "
                f"{tag} not permitted"
            )
        raise LinkUnavailable(
            f"link to {self._peer_cluster_id!r} not available "
            f"(health={self._health})"
        )

    # ------------------------------------------------------------------
    # Connect / disconnect / quiesce
    # ------------------------------------------------------------------

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
        if self._closing:
            raise LinkUnavailable("link is closing")
        endpoint = self._endpoints[0]
        channel_opts = self._build_channel_opts(endpoint)
        self._health = LinkHealth.CONNECTING

        backoff = float(
            self.opts.get("topology_handshake_backoff", _DEFAULT_HANDSHAKE_BACKOFF)
        )
        max_tries = int(
            self.opts.get("topology_handshake_max_tries", _DEFAULT_HANDSHAKE_MAX_TRIES)
        )

        # Lazily open the req channel.  We hold onto it across the
        # retry loop so the backoff doesn't allocate a fresh socket
        # on every attempt.
        if self._req_channel is None:
            self._req_channel = AsyncReqChannel.factory(
                channel_opts, io_loop=self.io_loop, crypt="clear"
            )

        attempt = 0
        last_status = None
        while attempt < max_tries:
            attempt += 1
            handshake_load = {
                "cmd": "topology/_master_auth",
                "tag": "topology/_master_auth",
                "cluster_id": self.opts.get("cluster_id"),
                "nonce": os.urandom(16).hex(),
            }
            try:
                reply = await self._req_channel.send(handshake_load)
            except asyncio.CancelledError:
                self._health = LinkHealth.DISCONNECTED
                raise
            except Exception as exc:  # pylint: disable=broad-except
                # Transport error on the handshake send.  The common case
                # is "peer master is briefly unreachable" --- a restart
                # window, a short network blip, or we raced ahead of the
                # peer's listener bind.  Back off and retry; if the loop
                # exhausts ``max_tries`` the handshake eventually gives up.
                #
                # Tear down the pooled :class:`AsyncReqChannel` between
                # attempts: zmq REQ sockets go into a bad state after a
                # failed send (expecting the matching recv) and the next
                # send on the same socket deadlocks.  Rebuilding the
                # channel resets the socket FSM cleanly.
                log.warning(
                    "topology link to %s: handshake transport error "
                    "(attempt %d/%d): %s",
                    endpoint.host,
                    attempt,
                    max_tries,
                    exc,
                )
                try:
                    close = getattr(self._req_channel, "close", None)
                    if close is not None:
                        close()
                except Exception:  # pylint: disable=broad-except
                    log.debug(
                        "topology link to %s: req channel close failed on retry",
                        endpoint.host,
                        exc_info=True,
                    )
                self._req_channel = None
                self._health = LinkHealth.CONNECTING
                if attempt >= max_tries:
                    self._health = LinkHealth.DISCONNECTED
                    return
                await asyncio.sleep(backoff)
                # Re-open the req channel for the next attempt.
                self._req_channel = AsyncReqChannel.factory(
                    channel_opts, io_loop=self.io_loop, crypt="clear"
                )
                continue

            if not isinstance(reply, dict):
                log.warning(
                    "topology link to %s: unexpected handshake reply shape: %r",
                    endpoint.host,
                    reply,
                )
                self._health = LinkHealth.DISCONNECTED
                return

            status = reply.get("status")
            last_status = status
            if status == "ok":
                aes = reply.get("aes")
                if not aes:
                    log.warning(
                        "topology link to %s: handshake ok but missing aes",
                        endpoint.host,
                    )
                    self._health = LinkHealth.DISCONNECTED
                    return
                self._peer_cluster_id = reply.get("cluster_id")
                self._rotate_session(aes)
                # Harvest any additional endpoints the peer advertised.
                for ep in reply.get("endpoints") or []:
                    if isinstance(ep, dict) and "host" in ep:
                        self.add_endpoint(
                            PeerRef(
                                host=ep["host"],
                                port=ep.get("port"),
                                finger=ep.get("finger"),
                            )
                        )
                # Open the pub channel; failures are logged but do
                # not block CONNECTED --- Phase 3 brings up the real
                # inbound listener, Phase 2 can live without pub.
                try:
                    if self._pub_channel is None:
                        self._pub_channel = AsyncPubChannel.factory(
                            channel_opts, io_loop=self.io_loop
                        )
                    await self._pub_channel.connect()
                except Exception as exc:  # pylint: disable=broad-except
                    log.debug(
                        "topology link to %s: pub channel connect skipped: %s",
                        endpoint.host,
                        exc,
                    )
                self._health = LinkHealth.CONNECTED
                return
            if status == "rejected":
                log.warning(
                    "topology link to %s: handshake rejected",
                    endpoint.host,
                )
                self._health = LinkHealth.DISCONNECTED
                return
            if status == "retry":
                # Peer has not accepted us yet; park in PENDING_ACCEPT
                # and sleep before trying again.
                self._health = LinkHealth.PENDING_ACCEPT
                if attempt >= max_tries:
                    break
                await asyncio.sleep(backoff)
                continue
            # Unknown status --- treat as disconnected.
            log.warning(
                "topology link to %s: unknown handshake status %r",
                endpoint.host,
                status,
            )
            self._health = LinkHealth.DISCONNECTED
            return
        # Exhausted retries while the peer kept replying ``retry``.
        if last_status == "retry":
            self._health = LinkHealth.PENDING_ACCEPT
        else:
            self._health = LinkHealth.DISCONNECTED

    async def disconnect(self):
        """
        Tear down the inbound subscription and the outbound req
        channel.

        Does NOT remove the peer from the registry --- that is a
        ``MASTER_PEER_DETACH`` concern separate from transient
        disconnects.  A disconnected link can be reconnected via
        :meth:`connect` without new human accept steps.
        """
        self._closing = True
        if self._req_channel is not None:
            try:
                await self._req_channel.close_async()
            except Exception:  # pylint: disable=broad-except
                try:
                    self._req_channel.close()
                except Exception:  # pylint: disable=broad-except
                    log.debug("req channel close failed", exc_info=True)
            self._req_channel = None
        if self._pub_channel is not None:
            try:
                await self._pub_channel.close_async()
            except Exception:  # pylint: disable=broad-except
                try:
                    self._pub_channel.close()
                except Exception:  # pylint: disable=broad-except
                    log.debug("pub channel close failed", exc_info=True)
            self._pub_channel = None
        self._health = LinkHealth.DISCONNECTED
        self._closing = False

    async def quiesce(self, breadcrumb_cache=None):
        """
        Transition the link to :data:`LinkHealth.QUIESCING` and
        drain in-flight returns before the final disconnect.

        Drain window duration = ``opts["topology_detach_quiesce"]``
        (falls back to ``opts["publish_timeout"]`` if the explicit
        knob is unset).  Drain exit condition is (whichever comes
        first):

        * **No active breadcrumbs reference this link** --- there
          are no returns still routable back through this link, so
          nothing is in flight.  Checked against ``breadcrumb_cache``
          (reader or writer handle from
          :mod:`salt.topology.breadcrumbs`) when the caller passes
          one; without the cache the drain simply runs the full
          timer.
        * **Timer elapses** --- fallback.  A WARNING is logged
          listing any undelivered jids whose breadcrumbs still
          point at this link so operators can investigate.

        If a :meth:`send_return` is mid-send when the timer fires
        (``self._inflight_returns > 0``), the drain waits for the
        in-flight send to complete before transitioning so a
        return already on the wire is never truncated.

        **Already-DISCONNECTED links**: no-op.  Called by
        :func:`salt.topology.link_manager.remove_link` on detach
        so returns in flight aren't dropped.

        :param breadcrumb_cache: Optional
            :class:`salt.utils.mmap_cache.MmapCache` handle; when
            present the drain exits early as soon as no breadcrumb
            still references this link's ``peer_cluster_id``.
        """
        if self._health == LinkHealth.DISCONNECTED:
            return
        self._health = LinkHealth.QUIESCING

        drain = self.opts.get("topology_detach_quiesce")
        if drain is None:
            drain = self.opts.get("publish_timeout", 0)
        try:
            drain = float(drain)
        except (TypeError, ValueError):
            drain = 0.0

        peer = self._peer_cluster_id
        timer_elapsed = False
        if drain > 0:
            poll = min(0.25, drain)
            elapsed = 0.0
            loop = asyncio.get_event_loop()
            start = loop.time()
            while elapsed < drain:
                if breadcrumb_cache is not None and peer is not None:
                    try:
                        # Local import avoids a module-level cycle:
                        # ``breadcrumbs`` imports nothing from this file,
                        # but keeping the import inside ``quiesce`` means
                        # a link opened without the cache does not pay
                        # the module import cost.
                        from salt.topology import breadcrumbs as _bc

                        if not _bc.jids_for_link(breadcrumb_cache, peer):
                            # No in-flight return still routes through
                            # this link; clean exit before the timer.
                            break
                    except Exception:  # pylint: disable=broad-except
                        log.debug(
                            "topology link quiesce: breadcrumb lookup failed",
                            exc_info=True,
                        )
                await asyncio.sleep(poll)
                elapsed = loop.time() - start
            else:
                timer_elapsed = True

        if timer_elapsed:
            # Wait for any send_return still on the wire; the active
            # send gets to finish before we tear the channel down.
            while self._inflight_returns > 0:
                await asyncio.sleep(0)
            pending = []
            if breadcrumb_cache is not None and peer is not None:
                try:
                    from salt.topology import breadcrumbs as _bc

                    pending = _bc.jids_for_link(breadcrumb_cache, peer)
                except Exception:  # pylint: disable=broad-except
                    log.debug(
                        "topology link quiesce: breadcrumb lookup failed",
                        exc_info=True,
                    )
            log.warning(
                "topology link to %r: quiesce drain timer elapsed after "
                "%.3fs with %d undelivered jids still pending: %r",
                peer,
                drain,
                len(pending),
                pending,
            )
        await self.disconnect()

    # ------------------------------------------------------------------
    # Outbound sends
    # ------------------------------------------------------------------

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
        self._assert_sendable("topology/pub")
        topology = (load.get("topology") if isinstance(load, dict) else None) or {}
        envelope = _build_envelope(
            origin=topology.get("origin", self.opts.get("cluster_id")),
            destinations=topology.get("destinations"),
            transit_match=topology.get("transit_match", True),
            path=path,
        )
        # Caller-owned ``load`` must not be mutated.
        body = dict(load) if isinstance(load, dict) else {"inner": load}
        body["topology"] = envelope
        payload = self._build_envelope_payload(body, "topology/pub")
        return await self._req_channel.send(payload)

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
        self._assert_sendable("topology/ret")
        body = {
            "batch": list(ret_batch),
            "topology": {
                "origin": self.opts.get("cluster_id"),
                "path": list(path),
            },
        }
        payload = self._build_envelope_payload(body, "topology/ret")
        # Track in-flight returns so the quiesce drain path can wait for
        # the current ``send_return`` to complete even if the drain timer
        # fires mid-send.
        self._inflight_returns += 1
        try:
            return await self._req_channel.send(payload)
        finally:
            self._inflight_returns -= 1

    async def send_event(self, event, path):
        """
        Forward a single event to the peer if the peer has
        subscribed to its tag.

        Dropped silently (TRACE log) if no subscription matches
        --- this is the normal path for the vast majority of
        events, which stay local.
        """
        self._assert_sendable("topology/evt")
        body = {
            "event": event,
            "topology": {
                "origin": self.opts.get("cluster_id"),
                "path": list(path),
            },
        }
        payload = self._build_envelope_payload(body, "topology/evt")
        return await self._req_channel.send(payload)

    async def send_summary(self, summary):
        """
        Push a fresh :class:`salt.topology.summary.ClusterSummary`
        to the peer.

        Called on ``topology_summary_interval`` by the summary
        heartbeat task and also on membership-change events
        inside this cluster (so peers get a fresh count promptly
        after minions attach/detach).
        """
        self._assert_sendable("topology/sum")
        if not isinstance(summary, ClusterSummary):
            raise TypeError(
                f"send_summary expects ClusterSummary, got {type(summary).__name__}"
            )
        body = {"summary": serialize_summary(summary)}
        payload = self._build_envelope_payload(body, "topology/sum")
        return await self._req_channel.send(payload)

    async def subscribe(self, tag_patterns):
        """
        Register the given glob tag patterns as the set of
        events this master wants forwarded from the peer.

        Replaces any previous subscription set; the peer applies
        the new set on receipt.  Propagated to the peer in-band
        on the next outbound message or on the next heartbeat,
        whichever comes first.
        """
        self._assert_sendable("topology/sub")
        patterns = list(tag_patterns)
        body = {"subscribe": patterns}
        payload = self._build_envelope_payload(body, "topology/sub")
        return await self._req_channel.send(payload)
