"""
Unit tests for Phase 1 of the pub-ack / pub-complete feature.

Reference:  doc/topics/master-topology/rfc-pub-ack-complete.md

These exercise, in-process:

* :meth:`salt.topology.link.PeerMasterLink.send_pub_ack` wire envelope
  shape (fields the originator loop keys on in Phase 2 consumption).
* :meth:`salt.topology.link.PeerMasterLink.send_pub_complete` wire shape.
* Health-gate on both senders: pub-ack = CONNECTED only; pub-complete
  = CONNECTED + QUIESCING, matching the RFC's "Health gating" section.
* :data:`salt.topology.link_manager._DISPATCH_TABLE` carries entries
  for both new tags so inbound traffic finds a handler.
* :func:`salt.topology.link_manager._dispatch_pub_ack` fires a local
  bus event on accept, drops with a WARNING on malformed shape.
* :func:`salt.topology.link_manager._dispatch_pub_complete` same.
* The pub-ack emission site in :func:`_dispatch_pub` fires the ack
  BEFORE :func:`_publish_to_local_minions` dispatches, and an empty
  local-match set still emits an ack (RFC: "zero-match peer still
  emits an ack").
"""

import asyncio

import pytest

import salt.topology.link_manager as link_manager
from salt.config.topology import PeerRef
from salt.topology.link import LinkHealth, LinkUnavailable, PeerMasterLink

# ---------------------------------------------------------------------------
# Helpers (mirrors tests/pytests/unit/topology/test_link.py:_make_link)
# ---------------------------------------------------------------------------


def _make_link(cluster_id="west"):
    """Build a link against a dummy peer; avoids any transport setup."""
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
    """Records the last payload passed to ``send`` so callers can inspect."""

    def __init__(self):
        self.last_payload = None
        self.send_calls = 0

    async def send(self, payload, tries=1):
        self.last_payload = payload
        self.send_calls += 1
        return {"ok": True}


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------


def test_dispatch_table_contains_pub_ack_and_pub_complete():
    """RFC Phase 1: ``topology/pub-ack`` and ``topology/pub-complete``
    must be callable from the inbound dispatcher.
    """
    table = link_manager._DISPATCH_TABLE  # pylint: disable=protected-access
    assert "topology/pub-ack" in table
    assert "topology/pub-complete" in table
    assert callable(table["topology/pub-ack"])
    assert callable(table["topology/pub-complete"])


# ---------------------------------------------------------------------------
# Wire envelope shape  (RFC "Wire format" / pub-ack)
# ---------------------------------------------------------------------------


def test_pub_ack_frame_shape():
    """``send_pub_ack`` builds the envelope the RFC specifies."""
    link = _make_link()
    link._rotate_session(b"\x00" * 32)  # pylint: disable=protected-access
    link._health = LinkHealth.CONNECTED  # pylint: disable=protected-access
    link._peer_cluster_id = "east"  # pylint: disable=protected-access
    chan = _StubReqChannel()
    link._req_channel = chan  # pylint: disable=protected-access

    asyncio.run(
        link.send_pub_ack(
            jid="20261104000000000001",
            target_cluster_id="east",
            matched_minion_ids=["m1", "m2"],
        )
    )
    payload = chan.last_payload
    assert payload is not None
    # Outer envelope (per RFC).
    assert payload["cmd"] == "topology/pub-ack"
    assert payload["tag"] == "topology/pub-ack"
    assert payload["origin_cluster_id"] == "west"
    assert payload["session_generation"] == 1
    # Inner load.
    load = payload["load"]
    assert load["jid"] == "20261104000000000001"
    assert load["target_cluster_id"] == "east"
    assert load["matched_minion_ids"] == ["m1", "m2"]
    assert load["topology"]["origin"] == "west"
    assert load["topology"]["path"] == ["west"]


def test_pub_ack_empty_match_list_still_emits():
    """RFC: zero-match peer still emits an ack (empty list, not silence)."""
    link = _make_link()
    link._rotate_session(b"\x00" * 32)  # pylint: disable=protected-access
    link._health = LinkHealth.CONNECTED  # pylint: disable=protected-access
    chan = _StubReqChannel()
    link._req_channel = chan  # pylint: disable=protected-access

    asyncio.run(
        link.send_pub_ack(
            jid="jid-empty",
            target_cluster_id="east",
            matched_minion_ids=[],
        )
    )
    load = chan.last_payload["load"]
    assert load["matched_minion_ids"] == []
    assert chan.send_calls == 1


def test_pub_ack_matched_list_copied_defensively():
    """Mutating the caller's list after send must not change the payload."""
    link = _make_link()
    link._rotate_session(b"\x00" * 32)  # pylint: disable=protected-access
    link._health = LinkHealth.CONNECTED  # pylint: disable=protected-access
    chan = _StubReqChannel()
    link._req_channel = chan  # pylint: disable=protected-access

    matched = ["m1"]
    asyncio.run(
        link.send_pub_ack(
            jid="jid-copy",
            target_cluster_id="east",
            matched_minion_ids=matched,
        )
    )
    matched.append("m2")
    assert chan.last_payload["load"]["matched_minion_ids"] == ["m1"]


# ---------------------------------------------------------------------------
# Wire envelope shape  (RFC "Wire format" / pub-complete)
# ---------------------------------------------------------------------------


def test_pub_complete_frame_shape():
    """``send_pub_complete`` builds the envelope the RFC specifies."""
    link = _make_link()
    link._rotate_session(b"\x00" * 32)  # pylint: disable=protected-access
    link._health = LinkHealth.CONNECTED  # pylint: disable=protected-access
    chan = _StubReqChannel()
    link._req_channel = chan  # pylint: disable=protected-access

    asyncio.run(
        link.send_pub_complete(
            jid="20261104000000000002",
            returned=["m1"],
            missed=["m2"],
            cancelled=False,
            cancel_reason=None,
        )
    )
    payload = chan.last_payload
    assert payload["cmd"] == "topology/pub-complete"
    assert payload["tag"] == "topology/pub-complete"
    assert payload["origin_cluster_id"] == "west"
    assert payload["session_generation"] == 1
    load = payload["load"]
    assert load["jid"] == "20261104000000000002"
    assert load["returned"] == ["m1"]
    assert load["missed"] == ["m2"]
    assert load["cancelled"] is False
    assert load["cancel_reason"] is None
    assert load["topology"]["origin"] == "west"
    assert load["topology"]["path"] == ["west"]


def test_pub_complete_cancelled_frame():
    """``cancelled=True`` + ``cancel_reason`` propagate on the wire."""
    link = _make_link()
    link._rotate_session(b"\x00" * 32)  # pylint: disable=protected-access
    link._health = LinkHealth.CONNECTED  # pylint: disable=protected-access
    chan = _StubReqChannel()
    link._req_channel = chan  # pylint: disable=protected-access

    asyncio.run(
        link.send_pub_complete(
            jid="jid-cancel",
            returned=[],
            missed=["m1", "m2"],
            cancelled=True,
            cancel_reason="parent-cluster-gone",
        )
    )
    load = chan.last_payload["load"]
    assert load["cancelled"] is True
    assert load["cancel_reason"] == "parent-cluster-gone"


# ---------------------------------------------------------------------------
# Health gating  (RFC "Health gating" section)
# ---------------------------------------------------------------------------


def test_pub_ack_health_gate_connected_permits():
    """pub-ack is permitted in CONNECTED."""
    link = _make_link()
    link._health = LinkHealth.CONNECTED  # pylint: disable=protected-access
    link._assert_sendable("topology/pub-ack")  # must not raise


def test_pub_ack_health_gate_quiescing_rejects():
    """pub-ack is NOT permitted in QUIESCING per RFC."""
    link = _make_link()
    link._health = LinkHealth.QUIESCING  # pylint: disable=protected-access
    with pytest.raises(LinkUnavailable):
        link._assert_sendable("topology/pub-ack")


def test_pub_ack_health_gate_disconnected_rejects():
    """pub-ack rejected on DISCONNECTED."""
    link = _make_link()
    link._health = LinkHealth.DISCONNECTED  # pylint: disable=protected-access
    with pytest.raises(LinkUnavailable):
        link._assert_sendable("topology/pub-ack")


def test_pub_complete_health_gate_connected_permits():
    """pub-complete permitted in CONNECTED."""
    link = _make_link()
    link._health = LinkHealth.CONNECTED  # pylint: disable=protected-access
    link._assert_sendable("topology/pub-complete")  # must not raise


def test_pub_complete_health_gate_quiescing_permits():
    """pub-complete permitted in QUIESCING (drains with returns per RFC)."""
    link = _make_link()
    link._health = LinkHealth.QUIESCING  # pylint: disable=protected-access
    link._assert_sendable("topology/pub-complete")  # must not raise


def test_pub_complete_health_gate_disconnected_rejects():
    """pub-complete rejected on DISCONNECTED."""
    link = _make_link()
    link._health = LinkHealth.DISCONNECTED  # pylint: disable=protected-access
    with pytest.raises(LinkUnavailable):
        link._assert_sendable("topology/pub-complete")


def test_pub_complete_health_gate_pending_accept_rejects():
    """pub-complete rejected on PENDING_ACCEPT (no session yet)."""
    link = _make_link()
    link._health = LinkHealth.PENDING_ACCEPT  # pylint: disable=protected-access
    with pytest.raises(LinkUnavailable):
        link._assert_sendable("topology/pub-complete")


# ---------------------------------------------------------------------------
# Dispatch handlers  (Phase 1 re-fire onto local bus)
# ---------------------------------------------------------------------------


def _install_capture_fire(monkeypatch):
    """Capture every ``_fire_local_event`` call into a list; returns it."""
    captured = []

    def _fake_fire(tag, data):
        captured.append((tag, data))

    monkeypatch.setattr(link_manager, "_fire_local_event", _fake_fire)
    return captured


def test_dispatch_pub_ack_fires_event(monkeypatch):
    """A well-formed pub-ack frame is re-fired on the local bus."""
    captured = _install_capture_fire(monkeypatch)
    inner = {
        "cmd": "topology/pub-ack",
        "tag": "topology/pub-ack",
        "origin_cluster_id": "east",
        "session_generation": 1,
        "load": {
            "jid": "jid-1",
            "target_cluster_id": "west",
            "matched_minion_ids": ["m1"],
            "topology": {"origin": "east", "path": ["east"]},
        },
    }
    link_manager._dispatch_pub_ack(inner)  # pylint: disable=protected-access
    assert len(captured) == 1
    tag, data = captured[0]
    assert tag == "salt/topology/pub-ack/jid-1"
    assert data["jid"] == "jid-1"
    assert data["matched_minion_ids"] == ["m1"]
    assert data["target_cluster_id"] == "west"


def test_dispatch_pub_complete_fires_event(monkeypatch):
    """A well-formed pub-complete frame is re-fired on the local bus."""
    captured = _install_capture_fire(monkeypatch)
    inner = {
        "cmd": "topology/pub-complete",
        "tag": "topology/pub-complete",
        "origin_cluster_id": "east",
        "session_generation": 1,
        "load": {
            "jid": "jid-2",
            "returned": ["m1"],
            "missed": ["m2"],
            "cancelled": False,
            "cancel_reason": None,
            "topology": {"origin": "east", "path": ["east"]},
        },
    }
    link_manager._dispatch_pub_complete(inner)  # pylint: disable=protected-access
    assert len(captured) == 1
    tag, data = captured[0]
    assert tag == "salt/topology/pub-complete/jid-2"
    assert data["jid"] == "jid-2"
    assert data["returned"] == ["m1"]
    assert data["missed"] == ["m2"]


# ---------------------------------------------------------------------------
# Malformed dispatch rejection (WARNING + silent drop)
# ---------------------------------------------------------------------------


def test_dispatch_rejects_malformed_pub_ack_missing_jid(monkeypatch, caplog):
    """pub-ack without a jid is dropped with a WARNING; no event fired."""
    captured = _install_capture_fire(monkeypatch)
    inner = {
        "cmd": "topology/pub-ack",
        "origin_cluster_id": "east",
        "session_generation": 1,
        "load": {
            "target_cluster_id": "west",
            "matched_minion_ids": [],
        },
    }
    with caplog.at_level("WARNING"):
        link_manager._dispatch_pub_ack(inner)  # pylint: disable=protected-access
    assert captured == []
    assert any("jid" in rec.message.lower() for rec in caplog.records)


def test_dispatch_rejects_malformed_pub_ack_wrong_matched_type(monkeypatch, caplog):
    """pub-ack with non-list matched_minion_ids is dropped."""
    captured = _install_capture_fire(monkeypatch)
    inner = {
        "cmd": "topology/pub-ack",
        "origin_cluster_id": "east",
        "session_generation": 1,
        "load": {
            "jid": "jid-bad",
            "target_cluster_id": "west",
            "matched_minion_ids": "not-a-list",
        },
    }
    with caplog.at_level("WARNING"):
        link_manager._dispatch_pub_ack(inner)  # pylint: disable=protected-access
    assert captured == []
    assert any("matched_minion_ids" in rec.message for rec in caplog.records)


def test_dispatch_rejects_malformed_pub_ack_missing_session_gen(monkeypatch, caplog):
    """pub-ack without session_generation is dropped."""
    captured = _install_capture_fire(monkeypatch)
    inner = {
        "cmd": "topology/pub-ack",
        "origin_cluster_id": "east",
        "load": {
            "jid": "jid-bad",
            "target_cluster_id": "west",
            "matched_minion_ids": [],
        },
    }
    with caplog.at_level("WARNING"):
        link_manager._dispatch_pub_ack(inner)  # pylint: disable=protected-access
    assert captured == []


def test_dispatch_rejects_malformed_pub_complete_missing_jid(monkeypatch, caplog):
    """pub-complete without a jid is dropped."""
    captured = _install_capture_fire(monkeypatch)
    inner = {
        "cmd": "topology/pub-complete",
        "origin_cluster_id": "east",
        "session_generation": 1,
        "load": {
            "returned": [],
            "missed": [],
            "cancelled": False,
        },
    }
    with caplog.at_level("WARNING"):
        link_manager._dispatch_pub_complete(inner)  # pylint: disable=protected-access
    assert captured == []


def test_dispatch_rejects_malformed_pub_complete_wrong_returned_type(
    monkeypatch, caplog
):
    """pub-complete with non-list ``returned`` is dropped."""
    captured = _install_capture_fire(monkeypatch)
    inner = {
        "cmd": "topology/pub-complete",
        "origin_cluster_id": "east",
        "session_generation": 1,
        "load": {
            "jid": "jid-bad",
            "returned": "not-a-list",
            "missed": [],
            "cancelled": False,
        },
    }
    with caplog.at_level("WARNING"):
        link_manager._dispatch_pub_complete(inner)  # pylint: disable=protected-access
    assert captured == []


def test_dispatch_pub_ack_does_not_raise_on_garbage(monkeypatch):
    """Non-dict payload is dropped silently --- RFC: "lossy by design".

    The dispatcher must never raise; a corrupted frame is a
    telemetry-level failure, not a dispatch-table failure.
    """
    _install_capture_fire(monkeypatch)
    for garbage in (None, "string", 42, [], ()):
        # Must not raise.
        link_manager._dispatch_pub_ack(garbage)  # pylint: disable=protected-access
        link_manager._dispatch_pub_complete(garbage)  # pylint: disable=protected-access


# ---------------------------------------------------------------------------
# Emission-site ordering  (RFC: ack precedes _publish_to_local_minions)
# ---------------------------------------------------------------------------


class _FakeInboundLink:
    """Records the order of sent calls so emission order is observable."""

    def __init__(self):
        self.peer_cluster_id = "east"
        self.pub_ack_calls = []

    async def send_pub_ack(self, jid, target_cluster_id, matched, path=None):
        self.pub_ack_calls.append(
            {
                "jid": jid,
                "target_cluster_id": target_cluster_id,
                "matched": list(matched or []),
                "path": list(path) if path is not None else None,
            }
        )


class _FakeRouter:
    def __init__(self, cluster_id="west"):
        self.cluster_id = cluster_id

    def forward_publish(self, load, inbound_link):
        # Simulate successful local match on this transit/leaf peer.
        return [], True

    def lookup_breadcrumb(self, jid):
        return None


@pytest.fixture
def _clean_link_manager(monkeypatch):
    """Reset module state so one test does not leak into the next."""
    monkeypatch.setattr(
        link_manager, "_OPTS", {"cluster_id": "west", "topology_pub_ack": True}
    )
    yield


def test_pub_ack_sent_before_local_publish(monkeypatch, _clean_link_manager):
    """RFC: pub-ack is emitted BEFORE ``_publish_to_local_minions`` runs.

    We verify by capturing the call-order of ``send_pub_ack`` vs the
    local-minion fan-out helper.  The sequence inside
    :func:`_dispatch_pub` must be: ``forward_publish`` -> schedule
    pub-ack -> ``_publish_to_local_minions``.
    """
    import salt.topology.router as router_mod

    fake_router = _FakeRouter("west")
    monkeypatch.setattr(router_mod, "get_router", lambda: fake_router)

    inbound = _FakeInboundLink()
    monkeypatch.setitem(
        link_manager._INBOUND,  # pylint: disable=protected-access
        "east",
        inbound,
    )

    events = []

    async def _fake_publish_to_local_minions(load, matched=None):
        events.append(("publish-local", matched))

    async def _fake_send_pub_ack(
        inbound_link, jid, target_cluster_id, matched, own_cluster_id
    ):
        events.append(("pub-ack", jid, list(matched)))
        await inbound_link.send_pub_ack(
            jid, target_cluster_id, matched, path=[own_cluster_id]
        )

    monkeypatch.setattr(
        link_manager, "_publish_to_local_minions", _fake_publish_to_local_minions
    )
    monkeypatch.setattr(
        link_manager, "_send_pub_ack_fire_and_forget", _fake_send_pub_ack
    )
    monkeypatch.setattr(link_manager, "_resolve_local_match", lambda load: ["m1", "m2"])

    payload = {
        "origin_cluster_id": "east",
        "load": {
            "jid": "jid-order",
            "cmd": "publish",
            "tgt": "*",
            "tgt_type": "glob",
            "fun": "test.ping",
            "topology": {"origin": "east", "path": ["east", "west"]},
        },
    }

    async def _drive():
        await link_manager._dispatch_pub(payload)  # pylint: disable=protected-access
        # Allow any ensure_future-scheduled pub-ack coroutine to run.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(_drive())

    # First event recorded must be the pub-ack call (scheduled via
    # ensure_future before the awaited _publish_to_local_minions).
    assert events, "no pub-ack or publish-local events were recorded"
    # The ensure_future for pub-ack runs when the loop yields; the
    # explicit await on _publish_to_local_minions follows.  Both must
    # have run, and ``pub-ack`` must appear strictly before
    # ``publish-local`` in the sequence.
    kinds = [e[0] for e in events]
    assert "pub-ack" in kinds, f"pub-ack never emitted: {events}"
    assert "publish-local" in kinds, f"publish-local never ran: {events}"
    assert kinds.index("pub-ack") < kinds.index(
        "publish-local"
    ), f"pub-ack did not precede publish-local: {events}"
    # And the pub-ack carried the matched_minion_ids that
    # publish-local was then passed, so the originator sees the exact
    # set that will fire.
    pub_ack_event = next(e for e in events if e[0] == "pub-ack")
    publish_event = next(e for e in events if e[0] == "publish-local")
    assert pub_ack_event[2] == ["m1", "m2"]
    assert publish_event[1] == ["m1", "m2"]
    # The inbound link received the actual ack.
    assert len(inbound.pub_ack_calls) == 1
    call = inbound.pub_ack_calls[0]
    assert call["jid"] == "jid-order"
    # path[0] from the authenticated path is the originator; forward_publish
    # already appended self so the inbound payload carries ["east", "west"].
    assert call["target_cluster_id"] == "east"
    assert call["matched"] == ["m1", "m2"]
    assert call["path"] == ["west"]


def test_pub_ack_emitted_even_with_empty_match(monkeypatch, _clean_link_manager):
    """RFC: zero-match peer still emits an ack (distinguishable from unreachable)."""
    import salt.topology.router as router_mod

    fake_router = _FakeRouter("west")
    monkeypatch.setattr(router_mod, "get_router", lambda: fake_router)

    inbound = _FakeInboundLink()
    monkeypatch.setitem(
        link_manager._INBOUND,  # pylint: disable=protected-access
        "east",
        inbound,
    )

    async def _fake_publish_to_local_minions(load, matched=None):
        return None

    monkeypatch.setattr(
        link_manager, "_publish_to_local_minions", _fake_publish_to_local_minions
    )
    # Resolve to an empty list --- zero minions matched locally.
    monkeypatch.setattr(link_manager, "_resolve_local_match", lambda load: [])

    payload = {
        "origin_cluster_id": "east",
        "load": {
            "jid": "jid-empty",
            "cmd": "publish",
            "tgt": "nomatch*",
            "tgt_type": "glob",
            "fun": "test.ping",
            "topology": {"origin": "east", "path": ["east", "west"]},
        },
    }

    async def _drive():
        await link_manager._dispatch_pub(payload)  # pylint: disable=protected-access
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(_drive())
    # Even with an empty local match the peer still emits an ack.
    assert len(inbound.pub_ack_calls) == 1
    assert inbound.pub_ack_calls[0]["matched"] == []


def test_pub_ack_opt_disabled_skips_emission(monkeypatch, _clean_link_manager):
    """``topology_pub_ack=False`` suppresses the ack frame entirely."""
    import salt.topology.router as router_mod

    fake_router = _FakeRouter("west")
    monkeypatch.setattr(router_mod, "get_router", lambda: fake_router)

    inbound = _FakeInboundLink()
    monkeypatch.setitem(
        link_manager._INBOUND,  # pylint: disable=protected-access
        "east",
        inbound,
    )
    monkeypatch.setattr(
        link_manager,
        "_OPTS",
        {"cluster_id": "west", "topology_pub_ack": False},
    )

    async def _fake_publish_to_local_minions(load, matched=None):
        return None

    monkeypatch.setattr(
        link_manager, "_publish_to_local_minions", _fake_publish_to_local_minions
    )
    monkeypatch.setattr(link_manager, "_resolve_local_match", lambda load: ["m1"])

    payload = {
        "origin_cluster_id": "east",
        "load": {
            "jid": "jid-off",
            "cmd": "publish",
            "tgt": "*",
            "fun": "test.ping",
            "topology": {"origin": "east", "path": ["east", "west"]},
        },
    }

    async def _drive():
        await link_manager._dispatch_pub(payload)  # pylint: disable=protected-access
        await asyncio.sleep(0)

    asyncio.run(_drive())
    assert inbound.pub_ack_calls == []


# ---------------------------------------------------------------------------
# Backward compat: module exports the expected names so downstream
# callers (functional tests, Phase 2 CLI) can import by name.
# ---------------------------------------------------------------------------


def test_link_module_exposes_send_pub_ack_and_complete():
    """Phase 2's CLI loop + functional tests import these by name."""
    assert hasattr(PeerMasterLink, "send_pub_ack")
    assert hasattr(PeerMasterLink, "send_pub_complete")


def test_link_manager_exposes_dispatch_handlers():
    """Phase 2 subscribes to the fired events; dispatch helpers must stay."""
    assert hasattr(link_manager, "_dispatch_pub_ack")
    assert hasattr(link_manager, "_dispatch_pub_complete")
    assert hasattr(link_manager, "_fire_local_event")
