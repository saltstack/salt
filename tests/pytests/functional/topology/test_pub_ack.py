"""
Functional tests for Phase 1 of the pub-ack / pub-complete feature.

Reference:  doc/topics/master-topology/rfc-pub-ack-complete.md

These drive the real :func:`salt.topology.link_manager._handle_inbound`
dispatch pipeline (session verify + tag lookup + handler call) against
a running :func:`salt.topology.link_manager.start`, with stubbed
``_fire_local_event`` so we can observe the re-fire without wiring up
a real master event bus.

Narrower than the unit suite:  here we validate that the inbound
wire-level envelope lands in the right handler, passes session
verification, and produces the expected local event tag + payload
shape.  The unit tests cover frame-construction side.
"""

import asyncio
import logging

import pytest

import salt.topology.link_manager as link_manager
import salt.topology.router as router_mod
from salt.topology.link import LinkHealth

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows,
]


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fixtures  (mirror of test_link_manager.py:_reserved_port + opts)
# ---------------------------------------------------------------------------


@pytest.fixture
def opts(tmp_path):
    import socket

    pki_dir = tmp_path / "pki"
    (pki_dir / "master").mkdir(parents=True, exist_ok=True)
    for sub in ("masters", "masters_pre", "masters_rejected", "masters_denied"):
        (pki_dir / sub).mkdir(parents=True, exist_ok=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return {
        "pki_dir": str(pki_dir),
        "interface": "127.0.0.1",
        "topology_enabled": True,
        "topology_link_port": port,
        "topology_peers": [],
        "topology_registry_cache_size": 512,
        "topology_registry_cache_key_size": 64,
        "topology_breadcrumb_cache_size": 1024,
        "topology_breadcrumb_cache_key_size": 64,
        "cluster_id": "west",
    }


@pytest.fixture
def clean_state(monkeypatch):
    link_manager._reset_module_state()  # pylint: disable=protected-access
    monkeypatch.setattr(router_mod, "_ROUTER", None)
    yield
    try:
        asyncio.new_event_loop().run_until_complete(link_manager.stop())
    except Exception:  # pylint: disable=broad-except
        pass
    link_manager._reset_module_state()  # pylint: disable=protected-access


def _install_fake_inbound_link(cluster_id, session_generation=1):
    """Pre-populate _INBOUND so :func:`_verify_session` passes."""

    class _Stub:
        pass

    stub = _Stub()
    stub.peer_cluster_id = cluster_id
    stub.session_generation = session_generation
    stub.health = LinkHealth.CONNECTED
    link_manager._INBOUND[cluster_id] = stub  # pylint: disable=protected-access
    return stub


# ---------------------------------------------------------------------------
# Dispatch pipeline  (inbound wire frame -> handler -> local event)
# ---------------------------------------------------------------------------


def test_inbound_pub_ack_fires_local_event(opts, clean_state, monkeypatch):
    """A wire ``topology/pub-ack`` frame that passes session verification
    fires ``salt/topology/pub-ack/<jid>`` on the local bus.
    """
    captured = []

    def _fake_fire(tag, data):
        captured.append((tag, data))

    monkeypatch.setattr(link_manager, "_fire_local_event", _fake_fire)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        _install_fake_inbound_link("east", session_generation=4)
        payload = {
            "cmd": "topology/pub-ack",
            "tag": "topology/pub-ack",
            "origin_cluster_id": "east",
            "session_generation": 4,
            "load": {
                "jid": "20261104000000000003",
                "target_cluster_id": "west",
                "matched_minion_ids": ["m1", "m2"],
                "topology": {"origin": "east", "path": ["east"]},
            },
        }
        loop.run_until_complete(
            link_manager._handle_inbound(payload)  # pylint: disable=protected-access
        )
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()

    assert len(captured) == 1
    tag, data = captured[0]
    assert tag == "salt/topology/pub-ack/20261104000000000003"
    assert data["jid"] == "20261104000000000003"
    assert data["matched_minion_ids"] == ["m1", "m2"]
    assert data["target_cluster_id"] == "west"


def test_inbound_pub_complete_fires_local_event(opts, clean_state, monkeypatch):
    """A wire ``topology/pub-complete`` frame fires
    ``salt/topology/pub-complete/<jid>`` on the local bus.
    """
    captured = []

    def _fake_fire(tag, data):
        captured.append((tag, data))

    monkeypatch.setattr(link_manager, "_fire_local_event", _fake_fire)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        _install_fake_inbound_link("east", session_generation=4)
        payload = {
            "cmd": "topology/pub-complete",
            "tag": "topology/pub-complete",
            "origin_cluster_id": "east",
            "session_generation": 4,
            "load": {
                "jid": "20261104000000000004",
                "returned": ["m1"],
                "missed": ["m2"],
                "cancelled": False,
                "cancel_reason": None,
                "topology": {"origin": "east", "path": ["east"]},
            },
        }
        loop.run_until_complete(
            link_manager._handle_inbound(payload)  # pylint: disable=protected-access
        )
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()

    assert len(captured) == 1
    tag, data = captured[0]
    assert tag == "salt/topology/pub-complete/20261104000000000004"
    assert data["jid"] == "20261104000000000004"
    assert data["returned"] == ["m1"]
    assert data["missed"] == ["m2"]
    assert data["cancelled"] is False


def test_inbound_pub_ack_stale_session_dropped(opts, clean_state, monkeypatch, caplog):
    """A pub-ack frame with a stale session is dropped at WARNING; no fire."""
    captured = []

    def _fake_fire(tag, data):
        captured.append((tag, data))

    monkeypatch.setattr(link_manager, "_fire_local_event", _fake_fire)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        _install_fake_inbound_link("east", session_generation=5)
        payload = {
            "cmd": "topology/pub-ack",
            "tag": "topology/pub-ack",
            "origin_cluster_id": "east",
            "session_generation": 1,  # stale
            "load": {
                "jid": "jid-stale",
                "target_cluster_id": "west",
                "matched_minion_ids": [],
            },
        }
        with caplog.at_level(logging.WARNING, logger="salt.topology.link_manager"):
            loop.run_until_complete(
                link_manager._handle_inbound(  # pylint: disable=protected-access
                    payload
                )
            )
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()

    assert captured == []
    assert any("bad/missing session" in rec.message for rec in caplog.records)


def test_inbound_pub_ack_malformed_dropped(opts, clean_state, monkeypatch, caplog):
    """A pub-ack frame that passes session verification but fails shape
    validation is dropped at WARNING; no local event fires.
    """
    captured = []

    def _fake_fire(tag, data):
        captured.append((tag, data))

    monkeypatch.setattr(link_manager, "_fire_local_event", _fake_fire)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        _install_fake_inbound_link("east", session_generation=4)
        # Missing jid in load.
        payload = {
            "cmd": "topology/pub-ack",
            "tag": "topology/pub-ack",
            "origin_cluster_id": "east",
            "session_generation": 4,
            "load": {
                "target_cluster_id": "west",
                "matched_minion_ids": [],
            },
        }
        with caplog.at_level(logging.WARNING, logger="salt.topology.link_manager"):
            loop.run_until_complete(
                link_manager._handle_inbound(  # pylint: disable=protected-access
                    payload
                )
            )
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()

    assert captured == []
    # The validate helper logged a WARNING naming the invalid jid.
    assert any("jid" in rec.message.lower() for rec in caplog.records)
