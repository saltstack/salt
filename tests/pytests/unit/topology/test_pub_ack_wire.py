"""
Regression tests pinning the ``topology/pub-ack`` wire shape and the
ack-precedes-local-publish ordering invariant.

Reference: ``doc/topics/master-topology/pub-ack-complete.md`` ("Wire
format" / ``topology/pub-ack`` subsection, lines 59-97).

The complementary coverage in ``test_pub_ack.py`` validates the
higher-level emission flow; this file pins the exact envelope keyset
per the RFC so future refactors cannot silently rename/drop fields
that the Phase 2 originator loop keys on.

Pinned invariants:

* Outer envelope fields: ``cmd``, ``tag``, ``origin_cluster_id``,
  ``session_generation``, ``load`` --- exact keyset, no extras.
* Inner load fields: ``jid``, ``target_cluster_id``,
  ``matched_minion_ids``, ``topology`` (with ``origin`` + ``path``)
  --- exact keyset, no extras.
* ``origin_cluster_id`` carries the SENDER cluster (RFC line 69).
* ``target_cluster_id`` carries the ORIGINATOR cluster (RFC line 73).
* ``topology.origin`` == sender cluster id (RFC line 76).
* ``topology.path`` defaults to ``[own_cluster_id]`` on the first hop
  (RFC line 77 / ``send_pub_ack`` docstring).
* The pub-ack coroutine is *scheduled* (``ensure_future`` + yield)
  before ``_publish_to_local_minions`` is awaited, so the send-to-wire
  path has begun before any local minion can start running the
  publish.  (RFC line 91-94: "an ack is guaranteed to precede any
  return from the acked peer".)
"""

import asyncio

import pytest

import salt.topology.link_manager as link_manager
from salt.config.topology import PeerRef
from salt.topology.link import LinkHealth, PeerMasterLink

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_link(cluster_id="west"):
    opts = {
        "cluster_id": cluster_id,
        "topology_link_port": 4521,
        "pki_dir": "/tmp/not-used",
    }
    seed = PeerRef(host="127.0.0.1", port=4521, finger=None)
    loop = asyncio.new_event_loop()
    try:
        return PeerMasterLink(opts, seed, loop)
    finally:
        loop.close()


class _StubReqChannel:
    def __init__(self):
        self.last_payload = None

    async def send(self, payload, tries=1):
        self.last_payload = payload
        return {"ok": True}


# ---------------------------------------------------------------------------
# Envelope keyset  (RFC "Wire format" / topology/pub-ack)
# ---------------------------------------------------------------------------


def test_pub_ack_outer_envelope_keyset_exact():
    """Outer envelope has exactly the RFC's field set --- no silent drift."""
    link = _make_link(cluster_id="west")
    link._rotate_session(b"\x00" * 32)  # pylint: disable=protected-access
    link._health = LinkHealth.CONNECTED  # pylint: disable=protected-access
    chan = _StubReqChannel()
    link._req_channel = chan  # pylint: disable=protected-access

    asyncio.run(
        link.send_pub_ack(
            jid="20261106000000000001",
            target_cluster_id="east",
            matched_minion_ids=["m1"],
        )
    )
    payload = chan.last_payload
    assert set(payload.keys()) == {
        "cmd",
        "tag",
        "origin_cluster_id",
        "session_generation",
        "load",
    }, (
        "topology/pub-ack outer envelope keyset drifted from the RFC "
        "(doc/topics/master-topology/pub-ack-complete.md). Keys were: "
        f"{sorted(payload.keys())!r}"
    )
    # cmd == tag == "topology/pub-ack" (RFC lines 67-68).
    assert payload["cmd"] == "topology/pub-ack"
    assert payload["tag"] == "topology/pub-ack"


def test_pub_ack_inner_load_keyset_exact():
    """Inner load has exactly the RFC's field set."""
    link = _make_link(cluster_id="west")
    link._rotate_session(b"\x00" * 32)  # pylint: disable=protected-access
    link._health = LinkHealth.CONNECTED  # pylint: disable=protected-access
    chan = _StubReqChannel()
    link._req_channel = chan  # pylint: disable=protected-access

    asyncio.run(
        link.send_pub_ack(
            jid="jid-keyset",
            target_cluster_id="east",
            matched_minion_ids=["m1", "m2"],
        )
    )
    load = chan.last_payload["load"]
    assert set(load.keys()) == {
        "jid",
        "target_cluster_id",
        "matched_minion_ids",
        "topology",
    }, (
        "topology/pub-ack inner load keyset drifted from the RFC. "
        f"Keys were: {sorted(load.keys())!r}"
    )
    assert set(load["topology"].keys()) == {"origin", "path"}


def test_pub_ack_sender_vs_originator_fields():
    """``origin_cluster_id`` = sender; ``target_cluster_id`` = originator.

    RFC lines 69 / 73: the semantic split lets the originator key
    ``(jid, target_cluster_id)`` so cross-cluster jid collisions do
    not alias.  A rename / swap would silently break the Phase 2
    aggregation keying.
    """
    link = _make_link(cluster_id="west-sub")
    link._rotate_session(b"\x00" * 32)  # pylint: disable=protected-access
    link._health = LinkHealth.CONNECTED  # pylint: disable=protected-access
    chan = _StubReqChannel()
    link._req_channel = chan  # pylint: disable=protected-access

    asyncio.run(
        link.send_pub_ack(
            jid="jid-x",
            target_cluster_id="east",
            matched_minion_ids=[],
        )
    )
    payload = chan.last_payload
    # Sender = this cluster.
    assert payload["origin_cluster_id"] == "west-sub"
    assert payload["load"]["topology"]["origin"] == "west-sub"
    # Target (= originator of the original publish) stays distinct.
    assert payload["load"]["target_cluster_id"] == "east"


def test_pub_ack_default_path_is_self_single_hop():
    """Default ``path`` is ``[own_cluster_id]`` (RFC: receiver authenticates
    on recv; the sender's single-entry path is "this master is the first
    hop toward the originator").
    """
    link = _make_link(cluster_id="west")
    link._rotate_session(b"\x00" * 32)  # pylint: disable=protected-access
    link._health = LinkHealth.CONNECTED  # pylint: disable=protected-access
    chan = _StubReqChannel()
    link._req_channel = chan  # pylint: disable=protected-access

    asyncio.run(
        link.send_pub_ack(
            jid="jid-path",
            target_cluster_id="east",
            matched_minion_ids=[],
        )
    )
    assert chan.last_payload["load"]["topology"]["path"] == ["west"]


def test_pub_ack_explicit_path_preserved():
    """Caller-supplied ``path`` is round-tripped verbatim (defensive copy)."""
    link = _make_link(cluster_id="west")
    link._rotate_session(b"\x00" * 32)  # pylint: disable=protected-access
    link._health = LinkHealth.CONNECTED  # pylint: disable=protected-access
    chan = _StubReqChannel()
    link._req_channel = chan  # pylint: disable=protected-access

    path_in = ["west-sub", "west"]
    asyncio.run(
        link.send_pub_ack(
            jid="jid-path2",
            target_cluster_id="east",
            matched_minion_ids=["m1"],
            path=path_in,
        )
    )
    # Must be an equal list -- defensive copy.  Mutating ``path_in``
    # after the fact must not change the payload.
    stored = chan.last_payload["load"]["topology"]["path"]
    assert stored == ["west-sub", "west"]
    path_in.append("mutated")
    assert chan.last_payload["load"]["topology"]["path"] == ["west-sub", "west"]


# ---------------------------------------------------------------------------
# Ack-precedes-local-publish ordering  (RFC lines 89-94)
# ---------------------------------------------------------------------------


class _OrderingInbound:
    """Records the moment ``send_pub_ack`` was entered on the event loop."""

    def __init__(self):
        self.peer_cluster_id = "east"
        self.enter_order = None

    async def send_pub_ack(self, jid, target_cluster_id, matched, path=None):
        # Record the position in the global event list BEFORE awaiting
        # anything else; this marks "the ack coroutine has begun the
        # wire send".
        _EVENTS.append(("pub-ack-enter", jid))
        await asyncio.sleep(0)  # simulate at least one wire step


class _OrderingRouter:
    def __init__(self, cluster_id="west"):
        self.cluster_id = cluster_id

    def forward_publish(self, load, inbound_link):
        return [], True

    def lookup_breadcrumb(self, jid):
        return None


_EVENTS = []


@pytest.fixture
def _clean_link_manager(monkeypatch):
    monkeypatch.setattr(
        link_manager, "_OPTS", {"cluster_id": "west", "topology_pub_ack": True}
    )
    _EVENTS.clear()
    yield
    _EVENTS.clear()


def test_pub_ack_scheduled_before_local_publish_await(monkeypatch, _clean_link_manager):
    """RFC invariant: the pub-ack coroutine has entered its body
    (i.e. has begun the wire send) BEFORE the local publish's
    IPC fan-out awaits.

    This is the regression that protects the "ack precedes return"
    guarantee.  The emission site uses ``ensure_future`` + an
    explicit ``asyncio.sleep(0)`` yield to let the pub-ack coroutine
    take its first step; if that yield were removed, local publish
    could race to the wire first.
    """
    import salt.topology.router as router_mod

    fake_router = _OrderingRouter("west")
    monkeypatch.setattr(router_mod, "get_router", lambda: fake_router)

    inbound = _OrderingInbound()
    monkeypatch.setitem(
        link_manager._INBOUND,  # pylint: disable=protected-access
        "east",
        inbound,
    )

    async def _fake_publish_to_local_minions(load, matched=None):
        _EVENTS.append(("local-publish-enter", load.get("jid")))

    async def _fake_send_pub_ack(
        inbound_link, jid, target_cluster_id, matched, own_cluster_id
    ):
        # Mirror the real helper: call into the link, record entry.
        await inbound_link.send_pub_ack(
            jid, target_cluster_id, matched, path=[own_cluster_id]
        )

    monkeypatch.setattr(
        link_manager, "_publish_to_local_minions", _fake_publish_to_local_minions
    )
    monkeypatch.setattr(
        link_manager, "_send_pub_ack_fire_and_forget", _fake_send_pub_ack
    )
    monkeypatch.setattr(link_manager, "_resolve_local_match", lambda load: ["m1"])
    # pub-complete collector spawn is irrelevant for this test; stub it.
    monkeypatch.setattr(
        link_manager, "_spawn_pub_complete_collector", lambda *a, **kw: None
    )

    payload = {
        "origin_cluster_id": "east",
        "load": {
            "jid": "jid-ordering",
            "cmd": "publish",
            "tgt": "*",
            "tgt_type": "glob",
            "fun": "test.ping",
            "topology": {"origin": "east", "path": ["east", "west"]},
        },
    }

    async def _drive():
        await link_manager._dispatch_pub(payload)  # pylint: disable=protected-access
        # Drain any remaining scheduled callbacks.
        for _ in range(3):
            await asyncio.sleep(0)

    asyncio.run(_drive())

    kinds = [e[0] for e in _EVENTS]
    assert "pub-ack-enter" in kinds, f"pub-ack never entered: {_EVENTS}"
    assert "local-publish-enter" in kinds, f"local-publish never entered: {_EVENTS}"
    assert kinds.index("pub-ack-enter") < kinds.index("local-publish-enter"), (
        "RFC invariant violated: _publish_to_local_minions ran before the "
        f"pub-ack coroutine entered its body. Event order was: {_EVENTS}"
    )


def test_pub_ack_opt_disabled_also_skips_collector(monkeypatch, _clean_link_manager):
    """When ``topology_pub_ack`` is False, neither the ack nor the
    pub-complete collector fires --- the feature is a single opt gate.
    """
    import salt.topology.router as router_mod

    fake_router = _OrderingRouter("west")
    monkeypatch.setattr(router_mod, "get_router", lambda: fake_router)

    inbound = _OrderingInbound()
    monkeypatch.setitem(
        link_manager._INBOUND,  # pylint: disable=protected-access
        "east",
        inbound,
    )
    monkeypatch.setattr(
        link_manager, "_OPTS", {"cluster_id": "west", "topology_pub_ack": False}
    )

    collector_calls = []

    def _fake_collector(*args, **kw):
        collector_calls.append(args)

    async def _fake_publish_to_local_minions(load, matched=None):
        return None

    monkeypatch.setattr(
        link_manager, "_publish_to_local_minions", _fake_publish_to_local_minions
    )
    monkeypatch.setattr(link_manager, "_resolve_local_match", lambda load: ["m1"])
    monkeypatch.setattr(link_manager, "_spawn_pub_complete_collector", _fake_collector)

    payload = {
        "origin_cluster_id": "east",
        "load": {
            "jid": "jid-off",
            "cmd": "publish",
            "tgt": "*",
            "tgt_type": "glob",
            "fun": "test.ping",
            "topology": {"origin": "east", "path": ["east", "west"]},
        },
    }

    async def _drive():
        await link_manager._dispatch_pub(payload)  # pylint: disable=protected-access
        await asyncio.sleep(0)

    asyncio.run(_drive())

    # Opt-off: no pub-ack entry, no collector spawn.
    assert ("pub-ack-enter", "jid-off") not in _EVENTS
    assert collector_calls == []


# ---------------------------------------------------------------------------
# Scoped routing: pure-transit peer (not in destination set) skips pub-ack
# ---------------------------------------------------------------------------


class _TransitRouter:
    """Router whose ``forward_publish`` reports ``local_match=False``.

    Models a pure-transit peer: the publish flows THROUGH this cluster
    on the way to some downstream destination, but this cluster is not
    itself in the originator's destination set.  Per the pub-ack RFC
    (and the ``local_match`` guard at
    ``salt/topology/link_manager.py`` line 1415), such a peer must NOT
    emit a ``topology/pub-ack`` --- the ack is a destination-side
    signal, not a forwarding receipt.
    """

    def __init__(self, cluster_id="mid"):
        self.cluster_id = cluster_id

    def forward_publish(self, load, inbound_link):
        # Downstream link list is irrelevant for the ack test; what
        # matters is local_match=False (this peer is NOT in the
        # destination set).
        return [], False

    def lookup_breadcrumb(self, jid):
        return None


def test_pub_ack_not_emitted_on_pure_transit_peer(monkeypatch, _clean_link_manager):
    """A pure-transit peer (``local_match=False``) MUST NOT emit pub-ack.

    Regression for the ``local_match`` guard at
    ``salt/topology/link_manager.py:1415``.  pub-ack semantics are
    "I am in the destination set and will publish to these minions";
    a cluster that is only forwarding the frame onward has nothing to
    acknowledge and would pollute the originator's aggregation set if
    it did ack.
    """
    import salt.topology.router as router_mod

    fake_router = _TransitRouter("mid")
    monkeypatch.setattr(router_mod, "get_router", lambda: fake_router)

    inbound = _OrderingInbound()
    monkeypatch.setitem(
        link_manager._INBOUND,  # pylint: disable=protected-access
        "east",
        inbound,
    )

    collector_calls = []

    def _fake_collector(*args, **kw):
        collector_calls.append(args)

    async def _fake_publish_to_local_minions(load, matched=None):
        _EVENTS.append(("local-publish-enter", load.get("jid")))

    async def _fake_send_pub_ack(
        inbound_link, jid, target_cluster_id, matched, own_cluster_id
    ):
        # Should NEVER be invoked on a pure-transit peer.
        await inbound_link.send_pub_ack(
            jid, target_cluster_id, matched, path=[own_cluster_id]
        )

    local_match_calls = []

    def _fake_resolve_local_match(load):
        # Should NEVER be called when local_match=False short-circuits
        # the guard; tracking this gives a crisper failure message
        # than just "no pub-ack frame".
        local_match_calls.append(load.get("jid"))
        return ["m1"]

    monkeypatch.setattr(
        link_manager, "_publish_to_local_minions", _fake_publish_to_local_minions
    )
    monkeypatch.setattr(
        link_manager, "_send_pub_ack_fire_and_forget", _fake_send_pub_ack
    )
    monkeypatch.setattr(link_manager, "_resolve_local_match", _fake_resolve_local_match)
    monkeypatch.setattr(link_manager, "_spawn_pub_complete_collector", _fake_collector)

    payload = {
        "origin_cluster_id": "east",
        "load": {
            "jid": "jid-transit",
            "cmd": "publish",
            "tgt": "west-leaf-*",
            "tgt_type": "glob",
            "fun": "test.ping",
            "topology": {"origin": "east", "path": ["east", "mid"]},
        },
    }

    async def _drive():
        await link_manager._dispatch_pub(payload)  # pylint: disable=protected-access
        # Drain any ensure_future-scheduled callbacks so we would
        # observe a (buggy) deferred pub-ack if one slipped past the
        # guard.
        for _ in range(3):
            await asyncio.sleep(0)

    asyncio.run(_drive())

    # 1. The inbound-side pub-ack coroutine must never have entered.
    kinds = [e[0] for e in _EVENTS]
    assert "pub-ack-enter" not in kinds, (
        "RFC violation: pure-transit peer (local_match=False) emitted "
        f"a pub-ack. Event order was: {_EVENTS}"
    )
    # 2. The guard must short-circuit BEFORE calling _resolve_local_match
    #    (that call is only meaningful for destined peers).
    assert local_match_calls == [], (
        "pure-transit peer should not resolve local-match for pub-ack; "
        f"got calls: {local_match_calls}"
    )
    # 3. Similarly, no pub-complete collector should spawn for a
    #    non-destination peer --- there is nothing to complete.
    assert (
        collector_calls == []
    ), f"pure-transit peer spawned pub-complete collector: {collector_calls}"
