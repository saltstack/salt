"""
Scenario tests for master-topology mesh-dedup bugs.

Covers three bugs in :mod:`salt.topology.router` that only surface
on mesh (non-tree) topologies.  In a triangle ``a <-> b <-> c <-> a``
the origin cluster sends a direct copy to each peer, and each peer
also receives a transit copy from the other peer; without dedup the
same job fans out N times and the registry is rewritten per path.

Bugs under test:

1. :meth:`TopologyRouter.forward_publish` did not skip peers that
   already appeared in ``envelope["path"]``.  In a triangle, B's
   forward loop (after receiving A's publish) would include C ---
   but A sent a direct copy to C already, so C would receive two
   publishes.  Fix: match the equivalent check in ``ingest_summary``.

2. :meth:`TopologyRouter.forward_publish` did not dedup by ``jid``.
   If C receives A's publish directly AND again through B, the
   second arrival would overwrite the breadcrumb (so returns route
   via the wrong peer) and refan to the mesh.  Fix: first arrival
   wins; later arrivals with a live breadcrumb are silent no-ops.

3. :meth:`TopologyRouter.ingest_summary` did not dedup by
   ``origin_seq``.  Every path through the mesh produces a
   redundant registry write + re-forward.  Fix: track the highest
   seq seen per origin in router-local soft state; drop stale and
   duplicate seqs.  Strictly-newer seqs still overwrite.

The scenarios drive the real router against real breadcrumbs /
registry MmapCaches with stub inbound links --- the same style as
``test_path_auth_scenarios.py`` --- so each test asserts the exact
difference between pre-fix and post-fix behavior and would have
failed before the fix.
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

    Captures publish / summary sends so the "no duplicate forward"
    assertions can observe exact wire traffic.
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
        "topology_link_port": 44507,
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


def _publish_from(origin_id, jid):
    """Build a publish-envelope dict as it arrives at a transit peer."""
    return {
        "tgt": "*",
        "tgt_type": "glob",
        "fun": "test.ping",
        "jid": jid,
        "timeout": 10,
        "topology": {
            "origin": origin_id,
            "destinations": None,  # flood
            "transit_match": True,
            "path": [origin_id],
        },
    }


# ===========================================================================
# Bug 1 + Bug 2 --- forward_publish path-member skip + jid dedup
# ===========================================================================


def test_triangle_publish_breadcrumb_single_write_per_peer(tmp_path, caplog):
    """
    Bug 2 regression: in a triangle a-b-c, the publish from a
    arrives at b both directly (from a) and transitively (from c).
    First arrival wins; the second must not overwrite.  Asserts
    exactly ONE live breadcrumb for the jid at b, pointing at a.

    Pre-fix: the second arrival would re-run ``record_breadcrumb``
    and overwrite the inbound link, routing returns through c.
    """
    # Build b's router.  b's direct peers are a and c.
    r, opts, reg, br = _make_router(tmp_path, "b")
    try:
        a_link = _StubInboundLink("a")
        c_link = _StubInboundLink("c")
        r._links = {  # pylint: disable=protected-access
            "a": a_link,
            "c": c_link,
        }

        jid = "jid-triangle-1"

        # First arrival at b: direct from a.
        direct = _publish_from("a", jid)
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger=router_mod.log.name):
            links_1, local_1 = r.forward_publish(direct, a_link)

        # Second arrival at b: transited through c (path = [a, c]).
        transit = _publish_from("a", jid)
        transit["topology"]["path"] = ["a", "c"]
        with caplog.at_level(logging.DEBUG, logger=router_mod.log.name):
            links_2, local_2 = r.forward_publish(transit, c_link)

        # First arrival: writes breadcrumb, picks onward link (c).
        assert local_1 is True
        peer_1 = breadcrumbs.lookup(br, jid)
        assert peer_1 is not None, "first arrival must record a breadcrumb"
        assert (
            peer_1 == "a"
        ), f"breadcrumb inbound must be 'a' (first-arrival sender); got {peer_1!r}"

        # Second arrival: dropped as duplicate.  No onward links,
        # local_match False, and breadcrumb unchanged.
        assert (
            links_2 == []
        ), f"duplicate forward_publish must return no onward links; got {links_2!r}"
        assert (
            local_2 is False
        ), f"duplicate forward_publish must return local_match=False; got {local_2!r}"
        peer_after = breadcrumbs.lookup(br, jid)
        assert peer_after == "a", (
            f"breadcrumb must NOT be overwritten by transit arrival; "
            f"got {peer_after!r} (expected 'a')"
        )
    finally:
        br.close()
        reg.close()


def test_triangle_publish_breadcrumb_inbound_is_first_arrival(tmp_path):
    """
    Bug 2 regression (race direction swapped): if the TRANSIT copy
    arrives at b first (from c, path=[a, c]) and the direct copy
    later, the breadcrumb must stay on c --- the first-arrival
    semantics are "first wins", not "most-recent sender".

    Pre-fix: ``record_breadcrumb`` was called unconditionally so
    the second arrival (direct from a) would re-pin the breadcrumb
    on a and the return route would skip b's actual inbound c.
    """
    r, opts, reg, br = _make_router(tmp_path, "b")
    try:
        a_link = _StubInboundLink("a")
        c_link = _StubInboundLink("c")
        r._links = {  # pylint: disable=protected-access
            "a": a_link,
            "c": c_link,
        }

        jid = "jid-triangle-2"

        # First arrival at b: transited through c.
        transit = _publish_from("a", jid)
        transit["topology"]["path"] = ["a", "c"]
        links_1, _ = r.forward_publish(transit, c_link)

        # Second arrival at b: direct from a.
        direct = _publish_from("a", jid)
        links_2, _ = r.forward_publish(direct, a_link)

        # The breadcrumb must still name c (first arrival).
        peer = breadcrumbs.lookup(br, jid)
        assert (
            peer == "c"
        ), f"breadcrumb must preserve first-arrival inbound 'c'; got {peer!r}"
        assert (
            links_2 == []
        ), f"second (direct) arrival must dedup to no onward links; got {links_2!r}"
    finally:
        br.close()
        reg.close()


def test_triangle_publish_no_local_duplication(tmp_path):
    """
    Bug 2 regression --- local_match must fire exactly ONCE per
    non-origin cluster per jid.  If the forward_publish path
    returns ``local_match=True`` twice (once per arrival) the
    local pub-server double-fires the publish to its minions.

    Pre-fix: both arrivals would return ``local_match=True`` on a
    flood publish (destinations=None); minions would see two copies
    of the same job.
    """
    r, opts, reg, br = _make_router(tmp_path, "b")
    try:
        a_link = _StubInboundLink("a")
        c_link = _StubInboundLink("c")
        r._links = {  # pylint: disable=protected-access
            "a": a_link,
            "c": c_link,
        }

        jid = "jid-triangle-3"
        local_matches = []

        # Direct arrival.
        direct = _publish_from("a", jid)
        _, lm1 = r.forward_publish(direct, a_link)
        local_matches.append(lm1)

        # Transit arrival.
        transit = _publish_from("a", jid)
        transit["topology"]["path"] = ["a", "c"]
        _, lm2 = r.forward_publish(transit, c_link)
        local_matches.append(lm2)

        true_count = sum(1 for v in local_matches if v is True)
        assert true_count == 1, (
            f"local_match=True must fire exactly once per jid; "
            f"got {true_count} (local_matches={local_matches})"
        )
    finally:
        br.close()
        reg.close()


def test_triangle_publish_path_member_skip(tmp_path):
    """
    Bug 1 regression --- forward_publish must not propose an
    onward link whose peer_cluster_id already appears in the
    envelope's path.  In a triangle a-b-c, when b forwards the
    publish it received from a, b's onward loop would (pre-fix)
    include c even though a already sent a direct copy to c.

    Here we drive forward_publish with a 4-peer router whose links
    are {a, c, d, e} and envelope path = [a].  Expected onward
    links: {c, d, e} (every non-inbound peer except those in path).

    Pre-fix: links would include a (dropped by the inbound filter
    anyway) but critically would include c when path=[a,c] on the
    transit arrival.  Covered implicitly by the dedup-check tests
    above (which hit the earlier jid-dedup return path); this
    scenario drives Bug 1 in isolation by passing a path that
    includes a cluster that is in self._links.
    """
    r, opts, reg, br = _make_router(tmp_path, "b")
    try:
        a_link = _StubInboundLink("a")
        c_link = _StubInboundLink("c")
        d_link = _StubInboundLink("d")
        r._links = {  # pylint: disable=protected-access
            "a": a_link,
            "c": c_link,
            "d": d_link,
        }

        # Transit arrival at b from a with path=[a, c] (so c has
        # already seen the publish).  Pre-fix: onward links would
        # include c AND d.  Post-fix: only d.
        env = _publish_from("a", "jid-path-skip-1")
        env["topology"]["path"] = ["a", "c"]
        # Set inbound link to a but note path[-1]=c so we need the
        # inbound link to actually be c for path-auth to pass.
        # Correct the inbound link to match path tail.
        links, local_match = r.forward_publish(env, c_link)

        onward_peer_ids = {
            lnk.peer_cluster_id for lnk in links  # type: ignore[attr-defined]
        }
        assert "c" not in onward_peer_ids, (
            f"forward_publish must skip peer 'c' when path=[a,c]; "
            f"got onward peers {onward_peer_ids}"
        )
        assert "a" not in onward_peer_ids, (
            f"forward_publish must skip peer 'a' when path=[a,c]; "
            f"got onward peers {onward_peer_ids}"
        )
        assert onward_peer_ids == {
            "d"
        }, f"forward_publish must forward only to 'd'; got {onward_peer_ids}"
        assert local_match is True
    finally:
        br.close()
        reg.close()


# ===========================================================================
# Bug 3 --- ingest_summary origin_seq dedup
# ===========================================================================


def test_triangle_summary_single_registry_write_per_summary(tmp_path):
    """
    Bug 3 regression --- in a triangle a-b-c, b receives a's
    summary twice: once directly (path=[a]) and once transited
    through c (path=[a, c]).  The registry must be written at
    most ONCE per summary at b.  Pre-fix: both arrivals called
    ``registry.set_peer``, double-writing the slot and double
    fanning the re-forward.

    Observable: wrap ``registry.set_peer`` with a call-count
    accumulator and verify exactly one call per summary.
    """
    r, opts, reg, br = _make_router(tmp_path, "b")
    try:
        a_link = _StubInboundLink("a")
        c_link = _StubInboundLink("c")
        r._links = {  # pylint: disable=protected-access
            "a": a_link,
            "c": c_link,
        }

        # Wrap registry.set_peer to count invocations against the
        # 'a' origin specifically.
        calls = []
        real_set_peer = registry.set_peer

        def _counting_set_peer(cache, cluster_id, state):
            calls.append(cluster_id)
            return real_set_peer(cache, cluster_id, state)

        router_mod.registry.set_peer = _counting_set_peer
        c_sends_after_first = 0
        a_sends_after_first = 0
        try:
            s1 = _summary("a", ["a"], origin_seq=42)
            s2 = _summary("a", ["a", "c"], origin_seq=42)

            loop = asyncio.new_event_loop()
            try:
                # First (direct) arrival: writes registry + re-forwards
                # the summary to c (b's other peer).
                loop.run_until_complete(r.ingest_summary(s1, a_link))
                c_sends_after_first = len(c_link.summaries)
                a_sends_after_first = len(a_link.summaries)
                # Second (transit) arrival: must be deduped --- no
                # additional registry write, no additional forwards.
                loop.run_until_complete(r.ingest_summary(s2, c_link))
            finally:
                loop.close()
        finally:
            router_mod.registry.set_peer = real_set_peer

        a_writes = [cid for cid in calls if cid == "a"]
        assert len(a_writes) == 1, (
            f"registry.set_peer must be called exactly once per summary "
            f"from origin 'a'; got {len(a_writes)} writes (all calls: {calls})"
        )

        # Second arrival must NOT emit additional forwards: the dedup
        # branch returns before the re-forward fan-out.  Compare
        # pre/post counts so we don't false-positive on the first
        # arrival's legitimate forward to c.
        assert len(c_link.summaries) == c_sends_after_first, (
            f"duplicate summary must not add forwards via c_link; "
            f"c_link.summaries grew {c_sends_after_first} -> "
            f"{len(c_link.summaries)}"
        )
        assert len(a_link.summaries) == a_sends_after_first, (
            f"duplicate summary must not reflect back to a_link; "
            f"a_link.summaries grew {a_sends_after_first} -> "
            f"{len(a_link.summaries)}"
        )
    finally:
        br.close()
        reg.close()


def test_summary_newer_origin_seq_overwrites(tmp_path):
    """
    Bug 3 positive control --- a strictly-newer summary from the
    same origin DOES overwrite the stored state.  Guards against
    an off-by-one in the dedup check (``>`` vs ``>=``) that would
    cause the first write to lock out all future updates.
    """
    r, opts, reg, br = _make_router(tmp_path, "b")
    try:
        a_link = _StubInboundLink("a")
        c_link = _StubInboundLink("c")
        r._links = {  # pylint: disable=protected-access
            "a": a_link,
            "c": c_link,
        }

        # First summary: seq=1, minion_count=1.
        s1 = _summary("a", ["a"], origin_seq=1)

        # Second summary from same origin: seq=2 (strictly newer).
        # Payload differs so we can observe the overwrite via
        # ``attached_at`` (we stuff the newer origin_at into it).
        s2 = ClusterSummary(
            cluster_id="a",
            path=("a",),
            minion_count=99,  # different payload
            up_count=99,
            grain_histograms={},
            origin_seq=2,
            origin_at=1_700_000_500.0,  # strictly newer
        )

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(r.ingest_summary(s1, a_link))
            # Verify first state landed.
            peer_1 = registry.get_peer(reg, "a")
            assert peer_1 is not None
            assert peer_1["attached_at"] == pytest.approx(1_700_000_000.0)

            loop.run_until_complete(r.ingest_summary(s2, a_link))
            # Newer summary must overwrite.
            peer_2 = registry.get_peer(reg, "a")
            assert peer_2 is not None
            assert peer_2["attached_at"] == pytest.approx(1_700_000_500.0), (
                f"newer origin_seq must overwrite; registry attached_at "
                f"stayed at {peer_2['attached_at']!r}"
            )
        finally:
            loop.close()
    finally:
        br.close()
        reg.close()
