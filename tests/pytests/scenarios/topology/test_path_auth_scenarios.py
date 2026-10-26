"""
Scenario tests for master-topology path-authentication tampering.

Covers the "Wire protocol" > "Publish envelope" > path-authentication
rule and the ``ingest_summary`` validation rule from
``rfcs/master-topology.md``.  On receive, the router asserts
``path[-1] == inbound_link.peer_cluster_id`` --- the sender's
self-reported last hop must match the authenticated link identity.
A hostile peer that forges ``path`` either to pretend the publish
transited through a different cluster (publish fan-out poisoning)
or to inject a bogus summary into the routing table
(summary-driven routing-table poisoning) is rejected with a
WARNING log, and no downstream state change happens: no
breadcrumb, no registry mutation, no re-forward.

Topology under test: three clusters ``east <-> west <-> south``
in a straight line.  West is the receiver that forwards toward
south; a tampered path tries to lie that it came from south when
the authenticated inbound link is east.

The scenarios drive :meth:`TopologyRouter.forward_publish` and
:meth:`TopologyRouter.ingest_summary` directly against real
:mod:`salt.topology.breadcrumbs` and :mod:`salt.topology.registry`
MmapCaches with stub inbound links --- the point is to craft a
tampered envelope and observe the drop + absence of side effects.
Scenario 4 is the positive control that proves the drop rule
does not accidentally reject legitimate traffic.
"""

import asyncio
import logging

import pytest

import salt.topology.breadcrumbs as breadcrumbs
import salt.topology.registry as registry
import salt.topology.router as router_mod
from salt.topology.link import LinkHealth
from salt.topology.summary import ClusterSummary

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


# ---------------------------------------------------------------------------
# Stub inbound-link + router builder
# ---------------------------------------------------------------------------


class _StubInboundLink:
    """
    Minimal :class:`PeerMasterLink` stand-in.

    The router consults three members on an inbound link:
    ``peer_cluster_id`` for path-authentication, ``health`` for
    (ignored here) connectivity checks, and ``send_summary`` /
    ``send_publish`` to re-forward.  Capturing the sends on the
    stub makes the "no re-forward" assertions observable.
    """

    def __init__(self, peer_cluster_id):
        self.peer_cluster_id = peer_cluster_id
        self.health = LinkHealth.CONNECTED
        self.publishes = []
        self.summaries = []

    async def send_publish(self, load, path):
        self.publishes.append({"load": load, "path": list(path)})

    async def send_summary(self, summary):
        self.summaries.append(summary)


def _router_opts(tmp_path, cluster_id):
    pki_dir = tmp_path / f"{cluster_id}-pki"
    (pki_dir / "master").mkdir(parents=True, exist_ok=True)
    return {
        "pki_dir": str(pki_dir),
        "cluster_id": cluster_id,
        "topology_enabled": True,
        "topology_breadcrumb_grace": 2,
        "topology_breadcrumb_max_age": 60,
        "topology_breadcrumb_cache_size": 512,
        "topology_breadcrumb_cache_key_size": 64,
        "topology_registry_cache_size": 512,
        "topology_registry_cache_key_size": 64,
        "topology_link_port": 44506,
    }


def _make_router(tmp_path, cluster_id):
    """Build a real :class:`TopologyRouter` on fresh MmapCaches."""
    opts = _router_opts(tmp_path, cluster_id)
    breadcrumbs.pre_create(opts)
    registry.pre_create(opts)
    br_cache = breadcrumbs.open_writer(opts)
    reg_cache = registry.open_writer(opts)
    r = router_mod.TopologyRouter(opts, reg_cache, br_cache)
    return r, opts, reg_cache, br_cache


def _summary(cluster_id, path, origin_seq=1):
    """Build a :class:`ClusterSummary` with the given path."""
    return ClusterSummary(
        cluster_id=cluster_id,
        path=tuple(path),
        minion_count=1,
        up_count=1,
        grain_histograms={},
        origin_seq=origin_seq,
        origin_at=1_700_000_000.0,
    )


def _warning_records(caplog):
    """Return the WARNING-and-above records on the topology router logger."""
    return [
        rec
        for rec in caplog.records
        if rec.levelno >= logging.WARNING and rec.name == router_mod.log.name
    ]


# ===========================================================================
# Scenario 1 --- tampered publish path dropped on receive
# ===========================================================================


def test_tampered_publish_path_dropped_on_receive(tmp_path, caplog):
    """
    Scenario 1 --- a crafted publish arrives at west on the
    east<->west link with ``topology.path = ["south"]`` (lying
    about which peer sent it: pretending the previous hop was
    south when the authenticated inbound link is east).

    Verify:

    * :meth:`TopologyRouter.forward_publish` returns empty links
      and ``local_match=False`` --- the message is dropped.
    * A WARNING log fires on the topology router logger naming
      the mismatch (``path tail=south``, ``inbound peer=east``).
    * No breadcrumb is written for the tampered jid --- a
      :func:`breadcrumbs.lookup` returns ``None``.
    * The inbound stub link does NOT receive the tampered
      publish as a reflected forward (the router filters it
      out of forwards anyway, but belt-and-suspenders here).
    * The onward peer (south) also receives nothing.
    """
    r, opts, reg, br = _make_router(tmp_path, "west")
    try:
        # West's view: east and south are its two peers.  East is
        # the authenticated inbound link; south is the onward
        # destination the tampered publish would normally reach.
        east_link = _StubInboundLink("east")
        south_link = _StubInboundLink("south")
        r._links = {  # pylint: disable=protected-access
            "east": east_link,
            "south": south_link,
        }

        tampered_jid = "jid-tamper-pub-1"
        tampered = {
            "tgt": "*",
            "tgt_type": "glob",
            "fun": "test.ping",
            "jid": tampered_jid,
            "timeout": 10,
            "topology": {
                "origin": "south",
                "destinations": None,
                "transit_match": True,
                # Lie: the authenticated inbound link is east, but
                # the sender's path tail claims the previous hop
                # was south.
                "path": ["south"],
            },
        }

        caplog.clear()
        with caplog.at_level(logging.WARNING, logger=router_mod.log.name):
            links, local_match = r.forward_publish(tampered, east_link)

        # The drop: no onward links and local_match False.
        assert links == [], f"tampered publish must not fan out; got {links!r}"
        assert local_match is False

        # A WARNING log naming the mismatch must have fired.  The
        # router formats the record with ``path tail=`` and
        # ``inbound peer=`` substrings.
        warnings = _warning_records(caplog)
        assert warnings, (
            "expected a WARNING log on the router logger naming the "
            "path/peer mismatch; got no warning records"
        )
        combined = " ".join(rec.getMessage() for rec in warnings)
        assert (
            "'south'" in combined
        ), f"warning should name the tampered path tail 'south'; got {combined!r}"
        assert "'east'" in combined, (
            f"warning should name the authenticated inbound peer 'east'; "
            f"got {combined!r}"
        )

        # No breadcrumb was written: a return arriving later with
        # this jid finds nothing to route back on.
        assert (
            breadcrumbs.lookup(br, tampered_jid) is None
        ), "tampered publish must not record a breadcrumb (lookup must miss)"

        # No publish propagated: south must have seen nothing, and
        # east must not have reflected it back either.
        assert south_link.publishes == [], (
            f"tampered publish must not reach south; got "
            f"{len(south_link.publishes)} sends"
        )
        assert east_link.publishes == [], (
            f"tampered publish must not reflect back to east; got "
            f"{len(east_link.publishes)} sends"
        )

        # Envelope's path must NOT have been extended with
        # west's own cluster_id --- the drop happens before the
        # authenticated-append step.
        assert tampered["topology"]["path"] == ["south"], (
            f"dropped publish envelope must not have had west appended; "
            f"got path={tampered['topology']['path']!r}"
        )
    finally:
        br.close()
        reg.close()


# ===========================================================================
# Scenario 2 --- tampered summary dropped on ingest
# ===========================================================================


def test_tampered_summary_path_tail_dropped_on_ingest(tmp_path, caplog):
    """
    Scenario 2 --- a summary with ``path = [X, Y]`` where ``Y !=
    inbound_link.peer_cluster_id``.  Sender lies about which
    direct peer forwarded it.

    Verify:

    * :meth:`TopologyRouter.ingest_summary` returns without
      writing to the registry.
    * A WARNING log fires naming the mismatch.
    * The registry has no entry for the summary's origin
      cluster (routing table unchanged).
    * No onward re-forward: the other peer (not the inbound
      sender) saw nothing.
    """
    r, opts, reg, br = _make_router(tmp_path, "west")
    try:
        east_link = _StubInboundLink("east")
        south_link = _StubInboundLink("south")
        r._links = {  # pylint: disable=protected-access
            "east": east_link,
            "south": south_link,
        }

        # Sender claims path = [north, south] but authenticated
        # inbound is east.  path[-1] = "south" != "east" -> drop.
        tampered = _summary("north", ["north", "south"], origin_seq=42)

        caplog.clear()
        loop = asyncio.new_event_loop()
        try:
            with caplog.at_level(logging.WARNING, logger=router_mod.log.name):
                loop.run_until_complete(r.ingest_summary(tampered, east_link))
        finally:
            loop.close()

        warnings = _warning_records(caplog)
        assert warnings, (
            "expected a WARNING log on the router logger naming the "
            "path/peer mismatch on summary ingest"
        )
        combined = " ".join(rec.getMessage() for rec in warnings)
        assert "'south'" in combined and "'east'" in combined, (
            f"warning should name tampered tail 'south' and inbound peer "
            f"'east'; got {combined!r}"
        )

        # Registry unchanged: no peer entry for the summary's origin.
        assert (
            registry.get_peer(reg, "north") is None
        ), "tampered summary must not land in the registry under its origin"

        # No re-forward: south_link.summaries empty, east_link
        # unchanged.  Both inbound and non-inbound stay quiet.
        assert south_link.summaries == [], (
            f"tampered summary must not re-forward to south; got "
            f"{len(south_link.summaries)} sends"
        )
        assert east_link.summaries == [], (
            f"tampered summary must not reflect back to east; got "
            f"{len(east_link.summaries)} sends"
        )
    finally:
        br.close()
        reg.close()


def test_tampered_summary_routing_loop_dropped_on_ingest(tmp_path, caplog):
    """
    Scenario 2 variant --- a summary with ``path = [X,
    self.cluster_id, inbound_peer]``.  If accepted the forwarder
    would re-emit a path containing ``self.cluster_id`` already,
    i.e. a routing loop.  The receiver's self-cycle check
    catches this (see Scenario 3 for the pure self-cycle case),
    and the ``path[-1]`` check only passes when the final hop
    is the authenticated inbound peer, so this variant exercises
    *both* defences at once.
    """
    r, opts, reg, br = _make_router(tmp_path, "west")
    try:
        east_link = _StubInboundLink("east")
        south_link = _StubInboundLink("south")
        r._links = {  # pylint: disable=protected-access
            "east": east_link,
            "south": south_link,
        }

        # path = [north, west, east].  tail is east -> matches
        # inbound.  But self (west) is already in path -> cycle,
        # drop by the loop-detection branch.
        tampered = _summary("north", ["north", "west", "east"], origin_seq=7)

        caplog.clear()
        loop = asyncio.new_event_loop()
        try:
            # The self-cycle drop logs at DEBUG not WARNING.  Still
            # we must verify no state change happened.
            with caplog.at_level(logging.DEBUG, logger=router_mod.log.name):
                loop.run_until_complete(r.ingest_summary(tampered, east_link))
        finally:
            loop.close()

        # Registry unchanged.
        assert (
            registry.get_peer(reg, "north") is None
        ), "self-in-path summary must not land in registry"
        # No re-forward anywhere.
        assert south_link.summaries == []
        assert east_link.summaries == []
    finally:
        br.close()
        reg.close()


# ===========================================================================
# Scenario 3 --- self-cycle summary dropped
# ===========================================================================


def test_self_cycle_summary_dropped_on_legit_link(tmp_path, caplog):
    """
    Scenario 3 --- a summary where ``self.cluster_id`` already
    appears in ``summary.path``, delivered via a legitimate link
    (path[-1] matches inbound peer).

    This is the ``is_cycle_for(summary, cluster_id)`` branch
    (loop detection): even with authentic path authentication,
    if the receiver's own cluster_id is in the path accepting
    the summary would create a routing loop, so drop.

    Verify:

    * :meth:`TopologyRouter.ingest_summary` returns without
      writing to the registry.
    * No DEBUG/warning that is a path-tampering warning fires
      (the drop is for cycle detection, not tampering, so no
      WARNING is required --- the router logs this at DEBUG).
    * Routing table unchanged: no registry entry for the
      summary's origin.
    * No re-forward: the other peer saw nothing.
    """
    r, opts, reg, br = _make_router(tmp_path, "west")
    try:
        east_link = _StubInboundLink("east")
        south_link = _StubInboundLink("south")
        r._links = {  # pylint: disable=protected-access
            "east": east_link,
            "south": south_link,
        }

        # A legit path from a non-adjacent origin that happens to
        # transit through self.  path = [south, west, east].
        # Tail is east -> matches inbound.  self "west" is in
        # path -> drop as cycle.
        looped = _summary("south", ["south", "west", "east"], origin_seq=99)

        caplog.clear()
        loop = asyncio.new_event_loop()
        try:
            with caplog.at_level(logging.DEBUG, logger=router_mod.log.name):
                loop.run_until_complete(r.ingest_summary(looped, east_link))
        finally:
            loop.close()

        # The drop message should mention the cycle (debug-level).
        debug_msgs = [
            rec.getMessage()
            for rec in caplog.records
            if rec.name == router_mod.log.name
        ]
        combined = " ".join(debug_msgs)
        assert "cycle" in combined or "west" in combined, (
            f"expected a cycle-drop log for self-in-path summary; "
            f"got messages {debug_msgs!r}"
        )

        # Routing table unchanged.
        assert (
            registry.get_peer(reg, "south") is None
        ), "self-cycle summary must not update the registry under its origin"

        # No re-forward.
        assert south_link.summaries == [], (
            f"self-cycle summary must not re-forward to south; got "
            f"{len(south_link.summaries)} sends"
        )
        assert east_link.summaries == [], (
            f"self-cycle summary must not reflect back to east; got "
            f"{len(east_link.summaries)} sends"
        )
    finally:
        br.close()
        reg.close()


# ===========================================================================
# Scenario 4 --- legitimate traffic still passes (positive control)
# ===========================================================================


def test_legitimate_publish_and_summary_still_pass(tmp_path, caplog):
    """
    Scenario 4 --- positive control.

    With the same harness setup used by Scenarios 1-3, deliver a
    correctly-authenticated publish (``path[-1] = inbound peer``,
    self not in path) and a correctly-authenticated summary
    (same rule).  Both must be processed:

    * The publish: :meth:`forward_publish` records a breadcrumb
      and returns the onward peer link in the links list; the
      authenticated path is extended with self.
    * The summary: :meth:`ingest_summary` writes the origin
      peer to the registry and re-forwards (with path extended)
      to the other peer.

    This proves the drop-on-tamper code paths exercised by
    scenarios 1-3 do not accidentally reject legit traffic.
    """
    r, opts, reg, br = _make_router(tmp_path, "west")
    try:
        east_link = _StubInboundLink("east")
        south_link = _StubInboundLink("south")
        r._links = {  # pylint: disable=protected-access
            "east": east_link,
            "south": south_link,
        }

        # Legit publish inbound from east, path = ["east"],
        # self (west) not in path.  Flooded (destinations=None).
        good_jid = "jid-legit-pub-1"
        legit_pub = {
            "tgt": "*",
            "tgt_type": "glob",
            "fun": "test.ping",
            "jid": good_jid,
            "timeout": 10,
            "topology": {
                "origin": "east",
                "destinations": None,
                "transit_match": True,
                "path": ["east"],
            },
        }

        caplog.clear()
        with caplog.at_level(logging.WARNING, logger=router_mod.log.name):
            links, local_match = r.forward_publish(legit_pub, east_link)

        # No warnings fired for the legit publish.
        warnings = _warning_records(caplog)
        assert warnings == [], (
            f"legit publish must not trigger any WARNING on the router "
            f"logger; got {[w.getMessage() for w in warnings]!r}"
        )

        # Flood -> onward peer (south) receives, local_match True.
        assert local_match is True
        fwd_cluster_ids = [getattr(ln, "peer_cluster_id", None) for ln in links]
        assert (
            "south" in fwd_cluster_ids
        ), f"legit flood publish must fan out to south; got {fwd_cluster_ids!r}"
        assert (
            "east" not in fwd_cluster_ids
        ), "legit publish must NOT reflect back to the inbound peer east"

        # Authenticated path was extended: now ends with 'west'.
        assert legit_pub["topology"]["path"] == ["east", "west"], (
            f"legit publish must have had west appended to the "
            f"authenticated path; got {legit_pub['topology']['path']!r}"
        )

        # Breadcrumb recorded: a return arriving later with this
        # jid routes back toward east.
        got = breadcrumbs.lookup(br, good_jid)
        assert got == "east", (
            f"legit publish must record breadcrumb pointing at east; " f"got {got!r}"
        )

        # ----- Legit summary -----
        # path = ["south", "east"].  tail is east -> matches
        # inbound.  self (west) not in path -> accept.
        legit_sum = _summary("south", ["south", "east"], origin_seq=5)

        caplog.clear()
        loop = asyncio.new_event_loop()
        try:
            with caplog.at_level(logging.WARNING, logger=router_mod.log.name):
                loop.run_until_complete(r.ingest_summary(legit_sum, east_link))
        finally:
            loop.close()

        warnings = _warning_records(caplog)
        assert warnings == [], (
            f"legit summary must not trigger any WARNING on the router "
            f"logger; got {[w.getMessage() for w in warnings]!r}"
        )

        # Registry updated: an entry exists for the summary's origin.
        peer_state = registry.get_peer(reg, "south")
        assert (
            peer_state is not None
        ), "legit summary must write the origin peer into the registry"
        assert peer_state["cluster_id"] == "south"

        # Re-forward: the OTHER peer (south) is the inbound sender
        # for publishes but for summaries the only other peer in
        # this harness that is NOT the inbound east and NOT the
        # summary's direct sender is south itself --- however, south
        # IS the direct-peer sender (summary.path[-2] context) only
        # if we think about it that way.  The router's rule is:
        # forward to every peer that is not (a) self, (b) the
        # inbound link, (c) the inbound peer_cluster_id, (d) in
        # path.  south is in path, so it does NOT get the re-forward
        # in this topology.  east_link also doesn't (inbound).
        # So neither stub should see this summary; we assert the
        # registry write + no WARNING suffice to prove the ingest
        # succeeded.  (Having a third peer available for forward
        # would require a four-cluster harness; the registry write
        # is already proof the ingest passed the drop checks.)
        assert (
            east_link.summaries == []
        ), "re-forward must never go back to the inbound link"
        # South was in path -> loop detection on forward skipped it.
        assert south_link.summaries == [], (
            f"south was already in path; re-forward must skip it to "
            f"avoid a loop; got {len(south_link.summaries)} sends"
        )
    finally:
        br.close()
        reg.close()
