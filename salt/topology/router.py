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

import asyncio
import collections
import logging
import time

import salt.topology.breadcrumbs as breadcrumbs
import salt.topology.registry as registry
import salt.topology.summary as summary_mod

log = logging.getLogger(__name__)

#: Cap on the LRU of recently-forwarded ``(jid, id)`` keys used by
#: :meth:`TopologyRouter.forward_return_once` to drop duplicate return
#: forwards.  See RFC item 7 (mitigation B): a breadcrumb lookup that
#: lands on a still-mapped-but-unlinked old heap segment can resolve a
#: cleaned-up jid for one extra lookup; the LRU ensures the second
#: forward is silently dropped instead of causing a double delivery
#: upstream.  1000 entries comfortably covers the ~250ms staleness
#: window at any sane cluster return rate.
_FORWARDED_RETURN_LRU_SIZE = 1000


#: Compound-expression operators.  Mirrors the set accepted by
#: :meth:`salt.utils.minions.CkMinions._check_compound_minions`;
#: duplicated here to avoid an import cycle through salt.utils.minions
#: (which transitively pulls in heavier salt internals).
_COMPOUND_OPERATORS = frozenset({"and", "or", "not", "(", ")"})


#: Module-level singleton populated by
#: :func:`salt.topology.link_manager.start`.  ``None`` means topology
#: is disabled or not yet instantiated in this process.
_ROUTER = None


# ---------------------------------------------------------------------------
# Target-string helpers
# ---------------------------------------------------------------------------


def _tokenize(tgt):
    """Split *tgt* into compound tokens, pulling parens off neighbours.

    :meth:`CkMinions._check_compound_minions` tokenizes via plain
    ``expr.split()`` and reads parens via the opers set --- but when
    parens hug a target like ``(C@east`` they stay attached and the
    compound matcher accepts them that way.  For the router we need
    to see ``C@...`` tokens cleanly, so we normalise paren-adjacency
    into separate tokens.  The grammar is still Salt-compound-safe
    because ``(`` / ``)`` already live in the opers set the matcher
    recognises.
    """
    if tgt is None:
        return []
    if isinstance(tgt, (list, tuple)):
        tokens = list(tgt)
    elif isinstance(tgt, str):
        tokens = tgt.split()
    else:
        return []
    out = []
    for tok in tokens:
        if not isinstance(tok, str) or tok in _COMPOUND_OPERATORS:
            out.append(tok)
            continue
        # Strip leading ``(`` and trailing ``)`` into separate tokens.
        lead = 0
        while lead < len(tok) and tok[lead] == "(":
            out.append("(")
            lead += 1
        core = tok[lead:]
        trail = 0
        while trail < len(core) and core[len(core) - 1 - trail] == ")":
            trail += 1
        middle = core[: len(core) - trail] if trail else core
        if middle:
            out.append(middle)
        for _ in range(trail):
            out.append(")")
    return out


def _is_c_token(token):
    """True when *token* names a ``C@...`` cluster target."""
    return isinstance(token, str) and token.startswith("C@")


def _cluster_ids_from_token(token):
    """Return the set of cluster_ids named in a ``C@a,b,c`` token."""
    payload = token[2:]
    return {c for c in payload.split(",") if c}


def extract_cluster_scope(tgt, nodegroups=None):
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
    tokens = _tokenize(tgt)
    if nodegroups:
        tokens = _expand_nodegroup_tokens(tokens, nodegroups)
    if not tokens:
        return None
    if any(tok == "not" for tok in tokens):
        return None
    out = set()
    for tok in tokens:
        if _is_c_token(tok):
            out |= _cluster_ids_from_token(tok)
    if not out:
        return None
    return out


def _expand_nodegroup_tokens(tokens, nodegroups):
    """
    Return *tokens* with every ``N@<name>`` reference expanded in-place
    via :func:`salt.utils.minions.nodegroup_comp`.

    Mirrors the expansion :meth:`CkMinions._check_compound_minions` does
    at match time, but on the raw tokens so the router can see any
    ``C@`` scope hidden inside a nodegroup definition.  Imports are
    deferred to avoid a module-import cycle through
    :mod:`salt.utils.minions`.
    """
    import salt.utils.minions as _minions  # pylint: disable=import-outside-toplevel

    out = []
    for tok in tokens:
        if not isinstance(tok, str) or not tok.startswith("N@") or len(tok) < 3:
            out.append(tok)
            continue
        try:
            expanded = _minions.nodegroup_comp(tok[2:], nodegroups)
        except Exception:  # pylint: disable=broad-except
            # nodegroup_comp is already error-tolerant (returns "" on
            # unknown / cyclic groups); any raised exception here is a
            # bug in the expander itself, not a user-visible condition.
            # Leave the token opaque so flood semantics kick in.
            log.exception("topology: nodegroup_comp raised for token %r", tok)
            out.append(tok)
            continue
        if isinstance(expanded, list):
            # Re-tokenise through _tokenize so paren-adjacency is normalised
            # and recursive nodegroup expansions (which nodegroup_comp
            # already resolved) stay well-formed for the C@ scan.
            out.extend(_tokenize(expanded))
        elif isinstance(expanded, str) and expanded:
            out.extend(_tokenize(expanded))
        else:
            # Empty expansion (unknown / cyclic nodegroup, or empty def):
            # drop the N@ token so it does not pollute the scope scan.
            continue
    return out


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
      ``"(web-*) or (db-*)"``.

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
    """
    if tgt is None:
        return tgt
    tokens = _tokenize(tgt)
    if not tokens:
        return tgt
    if any(tok == "not" for tok in tokens):
        # Skip-strip: let the receiver evaluate the full compound.
        return tgt if isinstance(tgt, str) else list(tokens)
    if not any(_is_c_token(tok) for tok in tokens):
        return tgt if isinstance(tgt, str) else list(tokens)

    # Safety net: a C@ token adjacent to ``or`` cannot be dropped
    # without changing the compound's semantics (``C@east or db-*``
    # on east means "every minion on east OR db-*", i.e. everything).
    # If any C@ token has an ``or`` as its neighbour inside the
    # tokenised form, fall through to skip-strip and let the minion-
    # side matcher evaluate the full expression --- unknown ``C@``
    # engine will match nothing on-minion, giving a safe under-match.
    for i, tok in enumerate(tokens):
        if not _is_c_token(tok):
            continue
        if i > 0 and tokens[i - 1] == "or":
            return tgt if isinstance(tgt, str) else list(tokens)
        if i + 1 < len(tokens) and tokens[i + 1] == "or":
            return tgt if isinstance(tgt, str) else list(tokens)

    # Walk tokens, dropping each C@ token and any adjacent 'and'
    # that would otherwise dangle.
    result = []
    for tok in tokens:
        if _is_c_token(tok):
            # Drop a preceding 'and' if present.
            if result and result[-1] == "and":
                result.pop()
                continue
            # Otherwise mark this slot so a following 'and' can be
            # dropped on the next iteration.
            result.append(_DROPPED)
            continue
        if tok == "and" and result and result[-1] is _DROPPED:
            # Drop the 'and' trailing a C@ we already removed.
            result.pop()
            continue
        result.append(tok)

    # Clean up any stranded sentinels.
    result = [t for t in result if t is not _DROPPED]

    # Tidy empty parens produced by ``(C@foo)`` groups.  Run to fixpoint
    # so nested wrappers like ``((C@east))`` collapse their outer group
    # once the inner one has disappeared.
    cleaned = result
    while True:
        prev = cleaned
        step = []
        i = 0
        while i < len(prev):
            tok = prev[i]
            if tok == "(" and i + 1 < len(prev) and prev[i + 1] == ")":
                i += 2
                # Drop a preceding operator left dangling by the empty
                # group's disappearance...
                if step and step[-1] in ("and", "or"):
                    step.pop()
                # ...and drop a following operator if the empty group was
                # at the head of the expression.
                if not step and i < len(prev) and prev[i] in ("and", "or"):
                    i += 1
                continue
            step.append(tok)
            i += 1
        cleaned = step
        if cleaned == prev:
            break

    # Trim leading/trailing dangling operators (an empty group at
    # the midpoint can leave ``A and or B`` after removal; the loop
    # below folds any adjacent operator pairs down to one).
    folded = []
    for tok in cleaned:
        if tok in ("and", "or") and folded and folded[-1] in ("and", "or"):
            # ``and or`` -> keep the more conservative ``and``.
            if tok == "and":
                folded[-1] = "and"
            continue
        folded.append(tok)
    cleaned = folded
    while cleaned and cleaned[0] in ("and", "or"):
        cleaned.pop(0)
    while cleaned and cleaned[-1] in ("and", "or", "not"):
        cleaned.pop()

    # Residual empty -> match-everything.
    if not cleaned:
        return "*"

    if isinstance(tgt, str):
        return _join_tokens(cleaned)
    return cleaned


def _join_tokens(tokens):
    """
    Render a token list back to a compound-expression string with
    paren hugging restored --- ``["(", "web-*", ")"]`` -> ``"(web-*)"``.

    The compound matcher accepts either spacing, but tests pin the
    canonical hugged form so round-trips are stable.
    """
    out = []
    for tok in tokens:
        if tok == ")":
            # Hug onto the previous token with no space.
            if out:
                out[-1] = out[-1] + ")"
            else:
                out.append(")")
            continue
        if tok == "(":
            out.append("(")
            continue
        if out and out[-1] == "(":
            out[-1] = "(" + tok
        else:
            out.append(tok)
    return " ".join(out)


class _Sentinel:  # pylint: disable=too-few-public-methods
    """Opaque sentinel used by :func:`strip_cluster_scope` for stripped slots."""

    __slots__ = ()

    def __repr__(self):
        return "<_DROPPED>"


_DROPPED = _Sentinel()


# ---------------------------------------------------------------------------
# Module-level accessor + publish entry point
# ---------------------------------------------------------------------------


def get_router():
    """
    Module-level accessor for the process-wide
    :class:`TopologyRouter` instance.

    Returns ``None`` when topology is disabled; callers in the
    publish daemon path check this before invoking any routing
    logic.
    """
    return _ROUTER


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
    r = get_router()
    if r is None:
        return
    links, _local_match = r.route_publish(load)
    if not links:
        return

    cluster_id = r.cluster_id

    # Each outbound send is wrapped so we can correlate exceptions
    # with the link that raised them.
    async def _one(link):
        try:
            await link.send_publish(load, [cluster_id])
            return (link, None)
        except Exception as exc:  # pylint: disable=broad-except
            return (link, exc)

    results = await asyncio.gather(
        *[_one(link) for link in links], return_exceptions=False
    )
    for link, exc in results:
        if exc is None:
            continue
        peer = getattr(link, "peer_cluster_id", None) or "unknown"
        tag = f"salt/topology/pub/failed/{peer}"
        data = {
            "cluster_id": peer,
            "jid": load.get("jid") if isinstance(load, dict) else None,
            "error": f"{type(exc).__name__}: {exc}",
        }
        try:
            r._fire_event(tag, data)  # pylint: disable=protected-access
        except Exception:  # pylint: disable=broad-except
            log.exception("topology: failed to fire pub-failed event for %s", peer)


# ---------------------------------------------------------------------------
# TopologyRouter
# ---------------------------------------------------------------------------


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
        self.opts = dict(opts)
        self.cluster_id = opts.get("cluster_id")
        self._registry = registry_cache
        self._breadcrumbs = breadcrumbs_cache
        #: ``cluster_id -> PeerMasterLink`` (or stub) for every peer
        #: link currently known to this process.  Populated by
        #: :mod:`salt.topology.link_manager`.
        self._links = {}
        #: Tag-pattern -> set of ``cluster_id`` subscriptions received
        #: from peers.  Populated by inbound ``topology/sub`` messages.
        self._event_subscriptions = {}
        #: Bounded LRU of ``(jid, minion_id)`` pairs this router has
        #: already forwarded a return for in this process.  Used by
        #: :meth:`forward_return_once` to drop duplicate forwards that
        #: would otherwise land on an upstream peer after a breadcrumb
        #: lookup hit a still-mapped-but-unlinked old heap segment
        #: (RFC item 7 mitigation B).  :class:`collections.OrderedDict`
        #: is cheap and gives O(1) LRU semantics via
        #: ``move_to_end`` + size cap.
        self._forwarded_returns: "collections.OrderedDict" = collections.OrderedDict()

    # ------------------------------------------------------------------
    # Overridable event hook
    # ------------------------------------------------------------------

    def _fire_event(self, tag, data):
        """
        Fire *tag* on the master event bus with *data* as payload.

        Default is a WARNING log because the publish daemon's real
        event-bus client is wired in by
        :mod:`salt.topology.link_manager`.  Tests override this
        attribute directly to intercept failure events.
        """
        log.warning("topology event (no event bus wired): %s %s", tag, data)

    # ------------------------------------------------------------------
    # Publish routing
    # ------------------------------------------------------------------

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

        :returns: ``(links_to_dispatch, local_match)``.
        """
        if not isinstance(load, dict):
            return [], False

        tgt = load.get("tgt")
        destinations = extract_cluster_scope(tgt)
        if destinations is None:
            local_match = True
            dest_list = None
        else:
            local_match = self.cluster_id in destinations
            dest_list = sorted(destinations)

        envelope = {
            "origin": self.cluster_id,
            "destinations": dest_list,
            "transit_match": bool(local_match),
            "path": [],
        }
        load["topology"] = envelope

        # Pick the outbound links.  Flood -> every peer link.  Scoped ->
        # only links whose peer_cluster_id is in destinations and not
        # equal to self.
        links = []
        for peer_id, link in self._links.items():
            if peer_id == self.cluster_id:
                continue
            if destinations is None:
                links.append(link)
            elif peer_id in destinations:
                links.append(link)
        return links, local_match

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
        copy so the next hop sees only remaining targets.

        Records a breadcrumb for return routing via
        :meth:`record_breadcrumb`.

        :returns: ``(links_to_dispatch, local_match)``.
        """
        if not isinstance(load, dict):
            return [], False
        envelope = load.get("topology") or {}
        path = list(envelope.get("path") or [])
        expected_peer = getattr(inbound_link, "peer_cluster_id", None)
        if not path or path[-1] != expected_peer:
            log.warning(
                "topology: forward_publish rejecting tampered path "
                "(path tail=%r, inbound peer=%r)",
                path[-1] if path else None,
                expected_peer,
            )
            return [], False
        if self.cluster_id in path:
            log.debug(
                "topology: forward_publish dropping cycle for cluster_id=%r (path=%r)",
                self.cluster_id,
                path,
            )
            return [], False

        # Authenticated-path append: receiver sticks its OWN id on.
        path.append(self.cluster_id)
        envelope["path"] = path

        destinations = envelope.get("destinations")
        if destinations is None:
            local_match = True
        else:
            dest_set = set(destinations)
            local_match = self.cluster_id in dest_set
            # Strip self so the next hop sees only remaining targets.
            dest_set.discard(self.cluster_id)
            envelope["destinations"] = sorted(dest_set)
        envelope["transit_match"] = bool(local_match)

        # Breadcrumb before we hand off to send tasks.
        jid = load.get("jid")
        timeout = load.get("timeout", 60)
        if jid is not None:
            try:
                self.record_breadcrumb(jid, inbound_link, timeout)
            except Exception:  # pylint: disable=broad-except
                log.exception("topology: breadcrumb write failed for jid=%r", jid)

        # Pick next-hop links.  Flood -> every peer other than inbound.
        # Scoped -> links whose peer_cluster_id is in the shrunken
        # destinations set.
        remaining = None if destinations is None else set(envelope["destinations"])
        links = []
        for peer_id, link in self._links.items():
            if peer_id == self.cluster_id:
                continue
            if link is inbound_link or peer_id == expected_peer:
                continue
            if remaining is None:
                links.append(link)
            elif peer_id in remaining:
                links.append(link)
        return links, local_match

    # ------------------------------------------------------------------
    # Returns
    # ------------------------------------------------------------------

    def route_return(self, ret):
        """
        For a return record generated by a local minion whose
        originating publish came from a topology peer, consult
        the breadcrumb table using ``ret["jid"]`` and return the
        link to send back on.

        Returns ``None`` if there is no breadcrumb --- the
        return is either from a locally-originated publish, or
        the breadcrumb has already expired.
        """
        if not isinstance(ret, dict):
            return None
        jid = ret.get("jid")
        if jid is None:
            return None
        return self.lookup_breadcrumb(jid)

    def forward_return_once(self, ret):
        """
        Idempotency guard for upstream return forwarding.

        A publish daemon that receives a return event
        (``salt/topology/return/<origin>/<jid>``) consults
        :meth:`route_return` to pick an outbound link, then calls
        this method **before** emitting on the wire.  The first call
        for a given ``(jid, minion_id)`` returns ``True`` and records
        the pair in the LRU; subsequent calls return ``False`` and
        the caller must drop the forward silently (DEBUG log).

        **Why**: ``MmapCache.atomic_rebuild`` renames the pre-rebuild
        heap aside and schedules its physical unlink for one staleness
        window later (RFC item 7 mitigation A).  During that window a
        cross-process reader whose mmap still points at the old inode
        can still resolve a cleaned-up breadcrumb for one more lookup
        — the writer has already dropped it from the live index, but
        the reader hasn't re-mapped.  Mitigation A keeps the file
        valid; mitigation B (this method) ensures the duplicate
        forward that the stale lookup triggers lands on a no-op path
        instead of double-delivering to the upstream peer.

        :param ret: Return record dict (``{jid, id, return, ...}``).
        :returns: ``True`` if this is the first time ``(jid, id)``
            is being forwarded, ``False`` on duplicate.
        """
        if not isinstance(ret, dict):
            return False
        jid = ret.get("jid")
        minion_id = ret.get("id")
        if jid is None or minion_id is None:
            # No key to deduplicate on — pass through; drop decisions
            # fall to the usual return pipeline.
            return True
        key = (jid, minion_id)
        if key in self._forwarded_returns:
            # Move-to-end bumps recency; the second-forward of a stale
            # jid stays "fresh" so a third one is still caught.
            self._forwarded_returns.move_to_end(key)
            log.debug(
                "topology: dropping duplicate return forward for "
                "jid=%r id=%r (seen within LRU window)",
                jid,
                minion_id,
            )
            return False
        self._forwarded_returns[key] = None
        while len(self._forwarded_returns) > _FORWARDED_RETURN_LRU_SIZE:
            self._forwarded_returns.popitem(last=False)
        return True

    def route_event(self, event):
        """
        Return the set of outbound peer links that have
        subscribed to the event's tag.

        Called by the event bus hook on every locally-fired
        event (when topology is enabled).  Empty return -> event
        stays local, no wire traffic.
        """
        if not isinstance(event, dict):
            return []
        tag = event.get("tag") or ""
        matched = []
        for pattern, peers in self._event_subscriptions.items():
            if _tag_matches(tag, pattern):
                for peer_id in peers:
                    link = self._links.get(peer_id)
                    if link is not None and link not in matched:
                        matched.append(link)
        return matched

    # ------------------------------------------------------------------
    # Breadcrumbs
    # ------------------------------------------------------------------

    def record_breadcrumb(self, jid, inbound_link, timeout):
        """
        Store a ``jid -> inbound_link`` mapping for return
        routing.

        Expiry is computed as
        ``now + min(timeout + opts["topology_breadcrumb_grace"],
        opts["topology_breadcrumb_max_age"])``.
        """
        peer = getattr(inbound_link, "peer_cluster_id", None)
        if peer is None:
            log.warning("topology: record_breadcrumb called with unauthenticated link")
            return
        try:
            breadcrumbs.put(self._breadcrumbs, jid, peer, timeout, self.opts)
        except Exception:  # pylint: disable=broad-except
            log.exception("topology: breadcrumb put failed for jid=%r", jid)

    def lookup_breadcrumb(self, jid):
        """
        Return the link previously recorded for ``jid``, or
        ``None`` if no breadcrumb exists or if the breadcrumb
        has expired.
        """
        peer = breadcrumbs.lookup(self._breadcrumbs, jid)
        if peer is None:
            return None
        return self._links.get(peer)

    def cleanup_breadcrumbs(self):
        """
        Remove expired breadcrumbs from the in-memory table.
        """
        try:
            return breadcrumbs.cleanup(self._breadcrumbs)
        except Exception:  # pylint: disable=broad-except
            log.exception("topology: breadcrumb cleanup failed")
            return 0

    # ------------------------------------------------------------------
    # Summary ingest
    # ------------------------------------------------------------------

    async def ingest_summary(self, summary, inbound_link):
        """
        Fold an inbound summary into state and re-forward to
        other peers.

        **Path authentication**: asserts ``summary.path[-1] ==
        inbound_link.peer_cluster_id`` AND
        ``self.opts["cluster_id"] not in summary.path`` on
        receive.  Rejects on either assertion failure with a
        WARNING log.

        Then:

        1. Write the summary into the registry's
           ``last_summary``-equivalent peer state.
        2. Re-forward (with ``path`` extended via
           :func:`salt.topology.summary.with_path_extended`) to
           this master's other peers that have not already seen
           it (loop detection via path membership).
        """
        peer_cluster_id = getattr(inbound_link, "peer_cluster_id", None)
        path = tuple(summary.path or ())
        if not path or path[-1] != peer_cluster_id:
            log.warning(
                "topology: ingest_summary rejecting tampered path "
                "(path tail=%r, inbound peer=%r)",
                path[-1] if path else None,
                peer_cluster_id,
            )
            return
        if self.cluster_id in path:
            log.debug(
                "topology: ingest_summary dropping cycle for cluster_id=%r "
                "(path=%r)",
                self.cluster_id,
                path,
            )
            return

        # Write to registry.  We store the peer summary under the
        # origin cluster_id with a minimal PeerState-shaped dict ---
        # the registry's encoder requires ``public_key`` and
        # ``attached_at``; soft fields the SM writes stay
        # unaffected.
        state = {
            "cluster_id": summary.cluster_id,
            "public_key": b"",
            "endpoints": (),
            "attached_at": float(summary.origin_at),
        }
        try:
            registry.set_peer(self._registry, summary.cluster_id, state)
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "topology: registry write failed for summary origin=%r",
                summary.cluster_id,
            )

        # Forward to other peers.  Extend the path so loop detection
        # works on the next hop.
        extended = summary_mod.with_path_extended(summary, self.cluster_id)
        forwards = []
        for peer_id, link in self._links.items():
            if peer_id == self.cluster_id:
                continue
            if link is inbound_link or peer_id == peer_cluster_id:
                continue
            if peer_id in extended.path:
                continue
            forwards.append(link)

        if not forwards:
            return

        async def _one(link):
            try:
                await link.send_summary(extended)
            except Exception:  # pylint: disable=broad-except
                log.exception(
                    "topology: summary forward failed to peer=%r",
                    getattr(link, "peer_cluster_id", None),
                )

        await asyncio.gather(*[_one(link) for link in forwards])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tag_matches(tag, pattern):
    """
    Return True if *tag* matches the Salt-style glob *pattern*.

    Implemented via :mod:`fnmatch`.  The topology subscription
    model is glob-based (tag_patterns handed to
    :meth:`PeerMasterLink.subscribe`), so this matches the wire
    semantics.
    """
    import fnmatch

    return fnmatch.fnmatchcase(tag, pattern)


# Silence unused-import warnings for the time helper exposed to tests
# that monkeypatch breadcrumb clocks.
_time = time
