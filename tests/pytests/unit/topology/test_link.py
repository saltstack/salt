"""
Unit tests for :mod:`salt.topology.link`.

These exercise invariants that are hard to assert cleanly at the
functional layer, where ``PeerMasterLink`` is driven end-to-end
against a running master and a fake receiver:

* :class:`LinkHealth` constants are plain strings (serialize cleanly
  to runner output / event payloads).
* State-machine transitions through ``connect`` / ``quiesce`` /
  ``disconnect`` without a running peer, driven directly by setting
  the health attribute and asserting :meth:`_assert_sendable`.
* Envelope serialization: :func:`_build_envelope` copies
  ``destinations`` and ``path`` defensively so caller-side mutation
  cannot change the on-wire shape retroactively.
* Session AES rotation: each call to ``_rotate_session`` installs a
  new key *and* bumps ``session_generation`` --- this is the hook
  the receive side uses to reject stale-session frames.
* Equality / hash: links are keyed by ``peer_cluster_id`` once
  handshake has run; before handshake, by the seed ``(host, port)``.
  :mod:`salt.topology.link_manager` relies on this to maintain the
  outbound-link registry dict.
"""

import asyncio

import pytest

import salt.topology.link as link_mod
from salt.config.topology import PeerRef
from salt.topology.link import (
    LinkHealth,
    LinkUnavailable,
    PeerMasterLink,
    _build_envelope,
)

# ---------------------------------------------------------------------------
# LinkHealth constants
# ---------------------------------------------------------------------------


def test_link_health_values_are_strings():
    """All LinkHealth constants are plain ``str`` instances."""
    for name in (
        "INITIAL",
        "CONNECTING",
        "CONNECTED",
        "DEGRADED",
        "DISCONNECTED",
        "PENDING_ACCEPT",
        "QUIESCING",
    ):
        value = getattr(LinkHealth, name)
        assert isinstance(value, str), f"{name} is {type(value).__name__}"


def test_link_health_values_distinct():
    """Each LinkHealth constant maps to a distinct string."""
    values = {
        LinkHealth.INITIAL,
        LinkHealth.CONNECTING,
        LinkHealth.CONNECTED,
        LinkHealth.DEGRADED,
        LinkHealth.DISCONNECTED,
        LinkHealth.PENDING_ACCEPT,
        LinkHealth.QUIESCING,
    }
    assert len(values) == 7


# ---------------------------------------------------------------------------
# _build_envelope defensive copying
# ---------------------------------------------------------------------------


def test_build_envelope_shape():
    """The envelope has exactly the four keys defined in the RFC."""
    env = _build_envelope(
        origin="west",
        destinations=["east"],
        transit_match=True,
        path=["west"],
    )
    assert set(env.keys()) == {"origin", "destinations", "transit_match", "path"}
    assert env["origin"] == "west"
    assert env["destinations"] == ["east"]
    assert env["transit_match"] is True
    assert env["path"] == ["west"]


def test_build_envelope_destinations_copied():
    """Mutating the caller's ``destinations`` after send must not change the
    envelope's bytes."""
    dests = ["east"]
    env = _build_envelope("west", dests, True, ["west"])
    dests.append("south")
    assert env["destinations"] == ["east"]


def test_build_envelope_path_copied():
    """Mutating the caller's ``path`` must not change the envelope."""
    path = ["west"]
    env = _build_envelope("west", None, True, path)
    path.append("east")
    assert env["path"] == ["west"]


def test_build_envelope_destinations_none_preserved():
    """``destinations=None`` means "flood"; preserve that semantic as None."""
    env = _build_envelope("west", None, True, ["west"])
    assert env["destinations"] is None


def test_build_envelope_transit_match_coerced_to_bool():
    """``transit_match`` is always a plain bool on the wire."""
    env = _build_envelope("west", None, 1, ["west"])
    assert env["transit_match"] is True
    env = _build_envelope("west", None, "", ["west"])
    assert env["transit_match"] is False


# ---------------------------------------------------------------------------
# Session AES rotation
# ---------------------------------------------------------------------------


def _make_link():
    """Build a link against a dummy peer; avoids any transport setup."""
    opts = {
        "cluster_id": "west",
        "topology_link_port": 4521,
        "pki_dir": "/tmp/not-used",
    }
    seed = PeerRef(host="127.0.0.1", port=4521, finger=None)
    loop = asyncio.new_event_loop()
    try:
        return PeerMasterLink(opts, seed, loop)
    finally:
        loop.close()


def test_session_initial_state():
    """A fresh link has no session AES and generation 0."""
    link = _make_link()
    assert link._session_aes is None
    assert link.session_generation == 0


def test_session_rotation_increments_generation():
    """Each ``_rotate_session`` bumps the generation counter."""
    link = _make_link()
    link._rotate_session(b"\x00" * 32)
    assert link.session_generation == 1
    link._rotate_session(b"\xff" * 32)
    assert link.session_generation == 2


def test_session_rotation_installs_new_key():
    """``_rotate_session`` replaces the stored AES."""
    link = _make_link()
    k1 = b"\x00" * 32
    k2 = b"\xff" * 32
    link._rotate_session(k1)
    assert link._session_aes == k1
    link._rotate_session(k2)
    assert link._session_aes == k2


# ---------------------------------------------------------------------------
# _assert_sendable gate
# ---------------------------------------------------------------------------


def test_assert_sendable_initial_rejects_everything():
    """INITIAL links refuse all outbound tags."""
    link = _make_link()
    for tag in ("topology/pub", "topology/ret", "topology/sum", "topology/evt"):
        with pytest.raises(LinkUnavailable):
            link._assert_sendable(tag)


def test_assert_sendable_connected_permits_all_tags():
    """CONNECTED links permit all outbound tags."""
    link = _make_link()
    link._health = LinkHealth.CONNECTED
    link._session_aes = b"\x00" * 32
    for tag in ("topology/pub", "topology/ret", "topology/sum", "topology/evt"):
        link._assert_sendable(tag)  # must not raise


def test_assert_sendable_quiescing_permits_only_return():
    """QUIESCING drains returns; publish/evt/sum raise."""
    link = _make_link()
    link._health = LinkHealth.QUIESCING
    link._assert_sendable("topology/ret")  # must not raise
    for tag in ("topology/pub", "topology/sum", "topology/evt"):
        with pytest.raises(LinkUnavailable):
            link._assert_sendable(tag)


def test_assert_sendable_disconnected_rejects_everything():
    """DISCONNECTED links refuse all outbound tags."""
    link = _make_link()
    link._health = LinkHealth.DISCONNECTED
    for tag in ("topology/pub", "topology/ret", "topology/sum", "topology/evt"):
        with pytest.raises(LinkUnavailable):
            link._assert_sendable(tag)


def test_assert_sendable_pending_accept_rejects_everything():
    """PENDING_ACCEPT links refuse all outbound tags (no session yet)."""
    link = _make_link()
    link._health = LinkHealth.PENDING_ACCEPT
    for tag in ("topology/pub", "topology/ret", "topology/sum", "topology/evt"):
        with pytest.raises(LinkUnavailable):
            link._assert_sendable(tag)


# ---------------------------------------------------------------------------
# Equality / hash
# ---------------------------------------------------------------------------


def test_equality_by_peer_cluster_id():
    """Two links with the same ``peer_cluster_id`` compare equal."""
    a = _make_link()
    b = _make_link()
    a._peer_cluster_id = "east"
    b._peer_cluster_id = "east"
    assert a == b
    assert hash(a) == hash(b)


def test_equality_mismatched_cluster_id():
    """Different peer_cluster_id -> not equal."""
    a = _make_link()
    b = _make_link()
    a._peer_cluster_id = "east"
    b._peer_cluster_id = "south"
    assert a != b


def test_equality_pre_handshake_by_seed():
    """Pre-handshake, links sharing the same seed endpoint compare equal."""
    opts = {
        "cluster_id": "west",
        "topology_link_port": 4521,
        "pki_dir": "/tmp/not-used",
    }
    seed = PeerRef(host="peer-a", port=4521, finger=None)
    loop = asyncio.new_event_loop()
    try:
        a = PeerMasterLink(opts, seed, loop)
        b = PeerMasterLink(opts, seed, loop)
        assert a == b
        assert hash(a) == hash(b)
    finally:
        loop.close()


def test_equality_pre_vs_post_handshake():
    """A pre-handshake link is NOT equal to a post-handshake link to the same
    place: identity hasn't been proved yet."""
    opts = {
        "cluster_id": "west",
        "topology_link_port": 4521,
        "pki_dir": "/tmp/not-used",
    }
    seed = PeerRef(host="peer-a", port=4521, finger=None)
    loop = asyncio.new_event_loop()
    try:
        pre = PeerMasterLink(opts, seed, loop)
        post = PeerMasterLink(opts, seed, loop)
        post._peer_cluster_id = "east"
        assert pre != post
    finally:
        loop.close()


def test_hash_registry_dict_usable():
    """Links are usable as dict keys / set members (link_manager registry)."""
    a = _make_link()
    b = _make_link()
    a._peer_cluster_id = "east"
    b._peer_cluster_id = "east"
    registry = {a: "slot-A"}
    # b is equal to a; dict lookup must find the same slot.
    assert registry[b] == "slot-A"


# ---------------------------------------------------------------------------
# add_endpoint corner cases that are better tested in-process
# ---------------------------------------------------------------------------


def test_add_endpoint_different_ports_both_kept():
    """Same host, different ports -> both are endpoints."""
    link = _make_link()
    link.add_endpoint(PeerRef(host="127.0.0.1", port=5000, finger=None))
    assert len(link.endpoints) == 2
    assert any(e.port == 5000 for e in link.endpoints)


def test_add_endpoint_rejects_dict_input():
    """Only PeerRef is accepted; passing a dict is a TypeError."""
    link = _make_link()
    with pytest.raises(TypeError):
        link.add_endpoint({"host": "127.0.0.1", "port": 5000})


# ---------------------------------------------------------------------------
# _build_envelope_payload --- signing / session discipline
# ---------------------------------------------------------------------------


def test_build_envelope_payload_requires_session():
    """Calling _build_envelope_payload before a session rotation raises."""
    link = _make_link()
    with pytest.raises(LinkUnavailable):
        link._build_envelope_payload({"inner": 1}, "topology/pub")


def test_build_envelope_payload_carries_generation():
    """Each payload carries the current session_generation (so the receiver
    can reject stale frames after a rotation)."""
    link = _make_link()
    link._rotate_session(b"\x00" * 32)
    payload = link._build_envelope_payload({"inner": 1}, "topology/pub")
    assert payload["session_generation"] == 1
    link._rotate_session(b"\xff" * 32)
    payload2 = link._build_envelope_payload({"inner": 2}, "topology/pub")
    assert payload2["session_generation"] == 2


def test_build_envelope_payload_carries_tag_and_origin():
    """The payload wrapper carries the dispatch tag and origin cluster_id."""
    link = _make_link()
    link._rotate_session(b"\x00" * 32)
    payload = link._build_envelope_payload({"inner": 1}, "topology/pub")
    assert payload["cmd"] == "topology/pub"
    assert payload["tag"] == "topology/pub"
    assert payload["origin_cluster_id"] == "west"


# ---------------------------------------------------------------------------
# send_publish --- trace context propagation across peer links
# ---------------------------------------------------------------------------


def test_send_publish_injects_traceparent_into_body(monkeypatch):
    """Cross-cluster forwards must carry the active trace context so the
    receiving peer master can parent its spans to the originating trace
    instead of generating orphans."""
    import salt.utils.tracing as tracing

    tracing.shutdown()
    monkeypatch.setattr(tracing, "_cached_opts", None)
    tracing.configure(
        {
            "tracing": {
                "enabled": True,
                "exporter": "console",
                "sampler": "always_on",
            }
        }
    )
    try:
        link = _make_link()
        link._rotate_session(b"\x00" * 32)
        captured = {}

        class _StubReqChannel:
            async def send(self, payload, tries=1):
                captured["payload"] = payload
                return None

        link._req_channel = _StubReqChannel()
        link._health = LinkHealth.CONNECTED

        load = {"jid": "20261101000000000001", "fun": "test.ping", "tgt": "*"}

        async def _call():
            with tracing.start_span("origin.pub"):
                await link.send_publish(load, ["west"])

        asyncio.run(_call())

        body = captured["payload"]["load"]
        assert "traceparent" in body
        assert "traceparent" not in load
    finally:
        tracing.shutdown()


def test_send_publish_no_traceparent_when_disabled(monkeypatch):
    """With tracing disabled, no traceparent key should be injected
    (avoid on-the-wire bloat)."""
    import salt.utils.tracing as tracing

    tracing.shutdown()
    monkeypatch.setattr(tracing, "_cached_opts", None)

    link = _make_link()
    link._rotate_session(b"\x00" * 32)
    captured = {}

    class _StubReqChannel:
        async def send(self, payload, tries=1):
            captured["payload"] = payload
            return None

    link._req_channel = _StubReqChannel()
    link._health = LinkHealth.CONNECTED
    load = {"jid": "20261101000000000002", "fun": "test.ping", "tgt": "*"}

    async def _call():
        await link.send_publish(load, ["west"])

    asyncio.run(_call())
    body = captured["payload"]["load"]
    assert "traceparent" not in body


# ---------------------------------------------------------------------------
# Module shape --- make sure the fakes used by the functional tests still
# have the attributes they monkeypatch.
# ---------------------------------------------------------------------------


def test_module_exports_channel_names():
    """Functional tests monkeypatch ``link_mod.AsyncReqChannel``;
    make sure the name exists on the module.  ``AsyncPubChannel`` was
    an obsoleted Phase-2 import removed when the pub-channel open path
    was deleted from :meth:`PeerMasterLink.connect`; functional tests
    patch it with ``raising=False`` so its absence is tolerated."""
    assert hasattr(link_mod, "AsyncReqChannel")


# ---------------------------------------------------------------------------
# Send-fault teardown --- BUG-016 regression
# ---------------------------------------------------------------------------


from salt.exceptions import SaltReqTimeoutError as _SaltReqTimeoutError  # noqa: E402


class _WedgingReqChannel:
    """A stub req channel whose first N sends raise and the rest succeed.

    Mirrors the real transport behaviour where a ``SaltReqTimeoutError``
    leaves the REQ socket in RECV state and the next send on the same
    socket would deadlock -- but here the test owns the socket's
    identity so we can observe teardown instead of hanging.
    """

    def __init__(self, raises=1, exc=None):
        self.sends = 0
        self.closes = 0
        self._raises = raises
        self._exc = exc or _SaltReqTimeoutError("wedged")

    async def send(self, payload, tries=1):
        self.sends += 1
        if self.sends <= self._raises:
            raise self._exc
        return {"ok": True}

    def close(self):
        self.closes += 1


def test_send_publish_timeout_tears_down_channel_and_marks_degraded():
    """BUG-016: a ``SaltReqTimeoutError`` on an outbound publish MUST

    * close + null the ``_req_channel`` reference,
    * transition the link off CONNECTED (to DEGRADED), and
    * bump ``send_fault_count`` + stamp ``last_send_fault_at``.

    Before the fix, the wedged REQ channel stayed installed and every
    subsequent send on the same link also timed out at the full REQ
    timeout; ``topology.peers`` still reported ``attached`` so operators
    saw no asymmetry.
    """
    link = _make_link()
    link._peer_cluster_id = "east"
    link._rotate_session(b"\x00" * 32)
    link._health = LinkHealth.CONNECTED
    chan = _WedgingReqChannel(raises=1)
    link._req_channel = chan

    async def _call():
        with pytest.raises(_SaltReqTimeoutError):
            await link.send_publish({"jid": "j1"}, ["west"])

    asyncio.run(_call())

    assert chan.closes == 1
    assert link._req_channel is None
    assert link.health == LinkHealth.DEGRADED
    assert link.send_fault_count == 1
    assert link.last_send_fault_at is not None


def test_degraded_link_rejects_follow_on_sends_without_timeout():
    """After a send fault, the next send MUST raise ``LinkUnavailable``
    immediately -- not time out again against the wedged socket.

    This is the "fail loud, don't silent-timeout" half of the BUG-016
    acceptance: callers (``_summary_emit_loop``, ``_transit_send``)
    get a prompt error back and the link is excluded from fan-out
    until the reconnector drives a fresh handshake.
    """
    link = _make_link()
    link._peer_cluster_id = "east"
    link._rotate_session(b"\x00" * 32)
    link._health = LinkHealth.CONNECTED
    link._req_channel = _WedgingReqChannel(raises=1)

    async def _first():
        with pytest.raises(_SaltReqTimeoutError):
            await link.send_publish({"jid": "j1"}, ["west"])

    asyncio.run(_first())

    # Second send: no stub channel attached (teardown nulled it).  The
    # pre-send gate must raise LinkUnavailable, not re-enter the
    # transport.
    async def _second():
        with pytest.raises(LinkUnavailable):
            await link.send_publish({"jid": "j2"}, ["west"])

    asyncio.run(_second())


def test_rotate_session_clears_fault_timestamp_after_reconnect():
    """A successful re-handshake (which calls ``_rotate_session``) MUST
    clear ``last_send_fault_at`` and bump ``session_generation``.

    This is the sender's half of the invariant the receiver verifies in
    :func:`salt.topology.link_manager._verify_session`: both ends must
    converge on the same ``session_generation`` after rotation.  Without
    the clear-on-rotate semantic, ``topology.peers`` could report a
    stale fault timestamp indefinitely after recovery.
    """
    link = _make_link()
    link._peer_cluster_id = "east"
    link._rotate_session(b"\x00" * 32)
    link._health = LinkHealth.CONNECTED
    link._req_channel = _WedgingReqChannel(raises=1)

    async def _first():
        with pytest.raises(_SaltReqTimeoutError):
            await link.send_publish({"jid": "j1"}, ["west"])

    asyncio.run(_first())
    assert link.last_send_fault_at is not None
    gen_before = link.session_generation

    # Simulate a successful re-handshake: a fresh session AES.
    link._rotate_session(b"\xff" * 32)
    assert link.session_generation == gen_before + 1
    assert link.last_send_fault_at is None
    # The fault count is cumulative across sessions -- it is the ops
    # signal that a link has flapped historically, not whether it is
    # currently faulting.  ``last_send_fault_at is None`` is the "is
    # it faulting now" signal.
    assert link.send_fault_count == 1


def test_send_summary_timeout_also_tears_down_channel():
    """BUG-016 regression for the summary emit path.  ``send_summary``
    runs on a background loop (``_summary_emit_loop``); a wedge there
    is the first symptom operators see in the master log because the
    summary cadence is tighter than the ``C@`` publish cadence."""
    from salt.topology.summary import ClusterSummary

    link = _make_link()
    link._peer_cluster_id = "east"
    link._rotate_session(b"\x00" * 32)
    link._health = LinkHealth.CONNECTED
    chan = _WedgingReqChannel(raises=1)
    link._req_channel = chan
    summary = ClusterSummary(
        cluster_id="west",
        path=("west",),
        minion_count=0,
        up_count=0,
        grain_histograms={},
        origin_seq=1,
        origin_at=1.0,
    )

    async def _call():
        with pytest.raises(_SaltReqTimeoutError):
            await link.send_summary(summary)

    asyncio.run(_call())
    assert chan.closes == 1
    assert link._req_channel is None
    assert link.health == LinkHealth.DEGRADED


def test_successful_send_records_last_send_success_at():
    """On the happy path, a successful send stamps
    ``last_send_success_at`` so ``topology.peers`` can surface the
    "last confirmed delivery" timestamp alongside the fault counters.
    """
    link = _make_link()
    link._peer_cluster_id = "east"
    link._rotate_session(b"\x00" * 32)
    link._health = LinkHealth.CONNECTED
    link._req_channel = _WedgingReqChannel(raises=0)  # never raises

    async def _call():
        await link.send_publish({"jid": "j1"}, ["west"])

    assert link.last_send_success_at is None
    asyncio.run(_call())
    assert link.last_send_success_at is not None
    assert link.send_fault_count == 0
    assert link.last_send_fault_at is None
