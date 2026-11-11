"""
Regression pins for the ``topology/pub-complete`` wire frame and its
originator-side consumer.

Reference: ``doc/topics/master-topology/pub-ack-complete.md`` --
    * "Wire format" / pub-complete section (frame shape + semantics).
    * "Originator aggregation" (expected/returned set math; the
      invariant ``set(returned) ^ set(missed) == set(matched_minion_ids)``
      is documented as "enforced at originator; a peer that violates
      it gets a WARNING log + ack-set is trusted").
    * "Semantics" bullet: "Fire-and-forget. If delivery to the
      originator fails (link down), the frame is dropped; the
      originator falls back to its own ``--timeout``".

These pins are deliberately shape-level: they lock down the fields
the consumer reads so a rename on the sender side cannot silently
break mixed-version deployments.  They complement the broader emission
coverage in ``test_pub_complete_emission.py`` and the originator-loop
coverage in ``tests/pytests/unit/client/test_topology_pub_ack.py``.
"""

import asyncio

import pytest

import salt.topology.link as link_mod
import salt.topology.link_manager as link_manager
from salt.topology.link import LinkHealth, LinkUnavailable, PeerMasterLink

# ---------------------------------------------------------------------------
# send_pub_complete frame shape
# ---------------------------------------------------------------------------


class _RecordingReqChannel:
    """Captures the serialized payload the link hands to the transport."""

    def __init__(self, raises=None):
        self.sent = []
        self.raises = raises

    async def send(self, payload, tries=1):
        self.sent.append(payload)
        if self.raises is not None:
            raise self.raises("simulated transport failure")
        return None


def _make_link(health=LinkHealth.CONNECTED):
    """Minimal CONNECTED ``PeerMasterLink`` for frame-shape assertions.

    We bypass ``connect()`` --- the only thing ``send_pub_complete``
    needs is an envelope-signable session (``_session_aes`` set) + a
    req channel + a sendable health state.  ``opts["cluster_id"]`` is
    the sender's own id (goes into ``origin_cluster_id``).
    """
    opts = {
        "cluster_id": "east-sub",
        "topology_link_port": 4521,
    }
    seed = link_mod.PeerRef(host="127.0.0.1", port=4521)
    loop = asyncio.new_event_loop()
    try:
        plm = PeerMasterLink(opts, seed, loop)
    finally:
        loop.close()
    plm._session_aes = b"\x00" * 32  # pylint: disable=protected-access
    plm._session_generation = 7  # pylint: disable=protected-access
    plm._health = health  # pylint: disable=protected-access
    plm._peer_cluster_id = "origin-cluster"  # pylint: disable=protected-access
    plm._req_channel = _RecordingReqChannel()  # pylint: disable=protected-access
    return plm


def test_pub_complete_frame_shape_pin():
    """Pin every documented field on the wire envelope.

    Matches the RFC "Wire format" / pub-complete section verbatim:
    ``cmd``, ``tag``, ``origin_cluster_id`` (SENDER cluster),
    ``session_generation`` (int), ``load`` with ``jid`` / ``returned``
    / ``missed`` / ``cancelled`` / ``cancel_reason`` / ``topology``.
    """
    plm = _make_link()
    asyncio.run(
        plm.send_pub_complete(
            jid="20261106000000000001",
            returned=["m1", "m2"],
            missed=["m3"],
            cancelled=False,
            cancel_reason=None,
            path=["east-sub"],
        )
    )
    assert len(plm._req_channel.sent) == 1  # pylint: disable=protected-access
    payload = plm._req_channel.sent[0]  # pylint: disable=protected-access
    # Outer envelope.
    assert payload["cmd"] == "topology/pub-complete"
    assert payload["tag"] == "topology/pub-complete"
    assert payload["origin_cluster_id"] == "east-sub"
    assert payload["session_generation"] == 7
    # Inner load.
    load = payload["load"]
    assert load["jid"] == "20261106000000000001"
    assert load["returned"] == ["m1", "m2"]
    assert load["missed"] == ["m3"]
    assert load["cancelled"] is False
    assert load["cancel_reason"] is None
    # Topology envelope: origin == sender cluster_id, path defaults to
    # the single sender hop if not overridden.
    assert load["topology"] == {"origin": "east-sub", "path": ["east-sub"]}


def test_pub_complete_frame_path_defaults_to_self():
    """``path=None`` must produce ``[own_cluster_id]`` not an empty list."""
    plm = _make_link()
    asyncio.run(
        plm.send_pub_complete(
            jid="jid-default-path",
            returned=[],
            missed=[],
            path=None,
        )
    )
    load = plm._req_channel.sent[0]["load"]  # pylint: disable=protected-access
    assert load["topology"]["path"] == ["east-sub"]


def test_pub_complete_frame_cancelled_requires_opt_in():
    """Phase 1.5 emitter never sets ``cancelled=True`` on its own.

    The RFC reserves cancelled=True for Tier 2 (``topology/jid-cancel``,
    not yet implemented) + the "parent cluster disappear mid-job"
    path.  The in-tree emitter ``_emit_pub_complete_once`` hard-codes
    cancelled=False; the ``send_pub_complete`` method itself accepts
    the field so Tier 2 can toggle it without a wire change.
    """
    plm = _make_link()
    asyncio.run(
        plm.send_pub_complete(
            jid="jid-cancel",
            returned=[],
            missed=["m1"],
            cancelled=True,
            cancel_reason="peer-vanished",
        )
    )
    load = plm._req_channel.sent[0]["load"]  # pylint: disable=protected-access
    assert load["cancelled"] is True
    assert load["cancel_reason"] == "peer-vanished"


# ---------------------------------------------------------------------------
# Health gating
# ---------------------------------------------------------------------------


def test_pub_complete_permitted_while_quiescing():
    """QUIESCING is permitted for pub-complete (drains with returns)."""
    plm = _make_link(health=LinkHealth.QUIESCING)
    # Must NOT raise -- RFC "Health gating": pub-complete rides the
    # same drain allowance as topology/ret.
    asyncio.run(plm.send_pub_complete(jid="j", returned=[], missed=[]))
    assert len(plm._req_channel.sent) == 1  # pylint: disable=protected-access


def test_pub_complete_rejected_when_disconnected():
    """DISCONNECTED raises ``LinkUnavailable`` before touching transport."""
    plm = _make_link(health=LinkHealth.DISCONNECTED)
    with pytest.raises(LinkUnavailable):
        asyncio.run(plm.send_pub_complete(jid="j", returned=[], missed=[]))
    assert plm._req_channel.sent == []  # pylint: disable=protected-access


# ---------------------------------------------------------------------------
# Behavioral pin: the Phase 1.5 emitter hard-codes cancelled=False
# ---------------------------------------------------------------------------


class _RecordingLink:
    """Minimal link stub that records every ``send_pub_complete`` call."""

    def __init__(self):
        self.peer_cluster_id = "origin-cluster"
        self.calls = []

    async def send_pub_complete(
        self,
        jid,
        returned,
        missed,
        cancelled=False,
        cancel_reason=None,
        path=None,
    ):
        self.calls.append(
            {
                "jid": jid,
                "returned": list(returned),
                "missed": list(missed),
                "cancelled": cancelled,
                "cancel_reason": cancel_reason,
                "path": list(path) if path is not None else None,
            }
        )


@pytest.mark.parametrize(
    "scenario,returned,missed,path",
    [
        # Empty-match fast path: zero local matches, emit immediately.
        ("empty_match", [], [], ["east-sub"]),
        # Normal collection: all expected returned, no missed.
        ("all_returned", ["m1", "m2", "m3"], [], ["east-sub"]),
        # Timeout branch: partial returns, remainder landed in missed.
        ("timeout_partial", ["m1"], ["m2", "m3"], ["east-sub"]),
        # Path=None variant (defaults carry through).
        ("empty_path_none", [], [], None),
    ],
)
def test_emit_pub_complete_never_sets_cancelled_true(scenario, returned, missed, path):
    """Phase 1.5 behavioral pin: ``_emit_pub_complete_once`` hard-codes
    ``cancelled=False`` + ``cancel_reason=None`` on EVERY trigger.

    The RFC reserves cancelled=True for Tier 2 (``topology/jid-cancel``);
    the current emitter must not set it regardless of whether the drain
    completed via empty-match fast path, normal "all returned"
    collection, or the --timeout fallback with populated ``missed``.
    If a future refactor threads cancel semantics into the emit path, it
    MUST update this test (and the Tier-2 implementation) together.

    Complements ``test_pub_complete_frame_cancelled_requires_opt_in`` --
    that wire-level test confirms ``send_pub_complete`` *accepts*
    ``cancelled=True`` (so Tier 2 doesn't need a wire change); this
    behavioral test pins that nothing in the emit path CURRENTLY does.
    """
    link = _RecordingLink()
    asyncio.run(
        link_manager._emit_pub_complete_once(  # pylint: disable=protected-access
            link,
            f"jid-{scenario}",
            returned=returned,
            missed=missed,
            path=path,
        )
    )
    assert len(link.calls) == 1
    call = link.calls[0]
    assert call["jid"] == f"jid-{scenario}"
    assert call["returned"] == returned
    assert call["missed"] == missed
    # The pin: emit path never sets cancelled=True / cancel_reason.
    assert call["cancelled"] is False, (
        f"Phase 1.5 emitter must hard-code cancelled=False "
        f"(scenario={scenario}); got cancelled={call['cancelled']!r}"
    )
    assert call["cancel_reason"] is None, (
        f"Phase 1.5 emitter must hard-code cancel_reason=None "
        f"(scenario={scenario}); got cancel_reason={call['cancel_reason']!r}"
    )


# ---------------------------------------------------------------------------
# Fire-and-forget: send failure does not retry and does not raise into
# the caller when routed through ``_emit_pub_complete_once``.
# ---------------------------------------------------------------------------


class _FaultyLink:
    """Minimal link stub whose ``send_pub_complete`` always raises."""

    def __init__(self, exc):
        self.peer_cluster_id = "origin-cluster"
        self.exc = exc
        self.call_count = 0

    async def send_pub_complete(self, jid, returned, missed, **kwargs):
        self.call_count += 1
        raise self.exc("simulated link down")


def test_pub_complete_fire_and_forget_on_link_unavailable():
    """``LinkUnavailable`` from the send does not raise into the collector."""
    link = _FaultyLink(LinkUnavailable)
    # Must not raise -- fire-and-forget per RFC.
    asyncio.run(
        link_manager._emit_pub_complete_once(  # pylint: disable=protected-access
            link,
            "jid-link-down",
            returned=["m1"],
            missed=[],
            path=["east-sub"],
        )
    )
    # Exactly one attempt -- no retry loop.
    assert link.call_count == 1


def test_pub_complete_fire_and_forget_on_generic_exception():
    """Any transport exception is swallowed; still no retry."""
    link = _FaultyLink(RuntimeError)
    asyncio.run(
        link_manager._emit_pub_complete_once(  # pylint: disable=protected-access
            link,
            "jid-crash",
            returned=[],
            missed=["m1"],
            path=None,
        )
    )
    assert link.call_count == 1


# ---------------------------------------------------------------------------
# Originator set math: what the CLI loop actually enforces.
#
# RFC "Semantics" claims:
#     set(returned) ^ set(missed) == set(matched_minion_ids)
#     ... "Enforced at originator; a peer that violates this gets a
#     WARNING log + ack-set is trusted (fail-open)."
#
# As of Phase 2, the originator loop (``LocalClient.get_iter_returns``,
# salt/client/__init__.py ~L1505-1544) does NOT re-check the xor
# against the prior pub-ack.  It unconditionally:
#   - updates ``topo_expected_set`` from pub-ack ``matched_minion_ids``,
#   - records the peer in ``topo_peers_complete`` on pub-complete,
#   - stashes any non-empty ``missed`` into
#     ``self._last_topology_missed_by_peer``.
#
# These pins encode the current behavior so a future invariant-check
# PR has to update them explicitly (and the doc can be reconciled
# either by implementing the check or by softening the "Enforced at
# originator" wording).
# ---------------------------------------------------------------------------


def test_pub_complete_originator_missed_surface_pin(caplog):
    """``missed`` carries through verbatim; CLI does not filter it.

    Phase 2's only post-complete surface is
    ``_last_topology_missed_by_peer`` (dict keyed by origin_cluster_id
    with the raw list).  A peer that sends a ``missed`` not in the
    prior ack's ``matched_minion_ids`` currently is NOT rejected --
    it just lands in that dict.  Pinning the surface prevents a
    silent regression on the operator-visible output.

    This pin covers the "fail-open" claim: the RFC states that
    ``set(returned) ^ set(missed) == set(matched_minion_ids)`` is
    "enforced at originator".  As of Phase 2, the emitter checks
    this invariant but the originator-side validator/consumer does
    NOT re-verify it against the prior pub-ack -- a violator is
    accepted with the ack-set trusted (fail-open).
    """
    # The actual loop is covered end-to-end in
    # tests/pytests/unit/client/test_topology_pub_ack.py; here we pin
    # the per-frame validator's acceptance criteria, which is the
    # upstream gate before any originator aggregation.
    payload = {
        "cmd": "topology/pub-complete",
        "tag": "topology/pub-complete",
        "origin_cluster_id": "east-sub",
        "session_generation": 5,
        "load": {
            "jid": "20261106-xyz",
            "returned": ["m1"],
            # "m99" was NEVER in a prior pub-ack -- validator still
            # accepts (fail-open).  Downstream aggregation trusts the
            # ack set; this frame's missed list simply surfaces to the
            # operator via ``_last_topology_missed_by_peer``.
            "missed": ["m99"],
            "cancelled": False,
            "cancel_reason": None,
            "topology": {"origin": "east-sub", "path": ["east-sub"]},
        },
    }
    with caplog.at_level("WARNING", logger="salt.topology.link_manager"):
        assert (
            link_manager._validate_pub_complete_payload(payload) is True
        )  # pylint: disable=protected-access
    # Fail-open: no WARNING log about the invariant violation.
    assert not any(
        "pub-complete" in rec.message and rec.levelname == "WARNING"
        for rec in caplog.records
    ), f"Expected no WARNING on fail-open; got: {[r.message for r in caplog.records]}"


def test_pub_complete_originator_xor_violation_accepted(caplog):
    """Fail-open pin: ``returned`` ∩ ``missed`` non-empty is still accepted.

    A direct XOR violation inside a single frame -- the same minion
    id appears in both ``returned`` and ``missed`` -- is a canonical
    "returned ⊕ missed ≠ matched_minion_ids" case (XOR semantics
    require disjointness).  The RFC says this is "Enforced at
    originator".  As of Phase 2, the originator-side validator does
    NOT reject; it is fail-open by design (emitter has already run
    the invariant; a peer that violated it on the wire is trusted
    at ack-set level and the per-frame list just surfaces to the
    operator).

    If/when the originator grows a real cross-frame invariant check
    (comparing against the prior pub-ack's ``matched_minion_ids``),
    this test must be updated explicitly -- that's the pin.
    """
    payload = {
        "cmd": "topology/pub-complete",
        "tag": "topology/pub-complete",
        "origin_cluster_id": "east-sub",
        "session_generation": 9,
        "load": {
            "jid": "20261106-xor",
            # m1 appears in BOTH -- XOR violation on the wire.
            "returned": ["m1", "m2"],
            "missed": ["m1", "m3"],
            "cancelled": False,
            "cancel_reason": None,
            "topology": {"origin": "east-sub", "path": ["east-sub"]},
        },
    }
    with caplog.at_level("WARNING", logger="salt.topology.link_manager"):
        # Fail-open: validator accepts despite the overlap.
        assert (
            link_manager._validate_pub_complete_payload(payload) is True
        )  # pylint: disable=protected-access
    # No WARNING / rejection on the invariant breach.
    assert not any(
        rec.levelname == "WARNING" for rec in caplog.records
    ), f"Expected no WARNING on fail-open XOR violation; got: {[r.message for r in caplog.records]}"


def test_pub_complete_validator_rejects_non_list_returned_missed():
    """Shape check: ``returned`` / ``missed`` MUST be lists."""
    base = {
        "cmd": "topology/pub-complete",
        "tag": "topology/pub-complete",
        "origin_cluster_id": "east-sub",
        "session_generation": 1,
        "load": {
            "jid": "j",
            "returned": ["m1"],
            "missed": ["m2"],
            "cancelled": False,
            "cancel_reason": None,
            "topology": {"origin": "east-sub", "path": ["east-sub"]},
        },
    }
    assert (
        link_manager._validate_pub_complete_payload(base) is True
    )  # pylint: disable=protected-access
    bad = dict(base, load=dict(base["load"], returned="m1"))
    assert (
        link_manager._validate_pub_complete_payload(bad) is False
    )  # pylint: disable=protected-access
    bad2 = dict(base, load=dict(base["load"], missed=None))
    assert (
        link_manager._validate_pub_complete_payload(bad2) is False
    )  # pylint: disable=protected-access


def test_pub_complete_validator_requires_origin_and_generation():
    """Outer frame must carry origin_cluster_id + session_generation."""
    load = {
        "jid": "j",
        "returned": [],
        "missed": [],
        "cancelled": False,
        "cancel_reason": None,
        "topology": {"origin": "east-sub", "path": ["east-sub"]},
    }
    no_origin = {
        "cmd": "topology/pub-complete",
        "tag": "topology/pub-complete",
        "origin_cluster_id": "",
        "session_generation": 1,
        "load": load,
    }
    no_gen = {
        "cmd": "topology/pub-complete",
        "tag": "topology/pub-complete",
        "origin_cluster_id": "east-sub",
        "session_generation": None,
        "load": load,
    }
    assert (
        link_manager._validate_pub_complete_payload(no_origin) is False
    )  # pylint: disable=protected-access
    assert (
        link_manager._validate_pub_complete_payload(no_gen) is False
    )  # pylint: disable=protected-access
