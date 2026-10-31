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
