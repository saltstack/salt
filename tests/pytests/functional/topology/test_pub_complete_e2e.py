"""
Functional end-to-end test for Phase 1.5: receiver-side emission of
``topology/pub-complete``.

Reference:  doc/topics/master-topology/rfc-pub-ack-complete.md
            (Phase 1.5 emission site).

Drives :func:`salt.topology.link_manager._dispatch_pub` through its
full happy path with a stubbed router (resolves local match), stubbed
``_publish_to_local_minions`` (so no real pub channel is needed), and a
monkeypatched ``get_master_event`` that hands the collector a queue-
backed fake bus pre-loaded with a minion-return event for every ack'd
minion.  The test asserts that after the dispatch runs to completion,
the inbound link received a ``send_pub_complete`` call carrying the
full ``returned`` list and an empty ``missed`` list.
"""

import asyncio
import logging

import pytest

import salt.topology.link_manager as link_manager
import salt.topology.router as router_mod

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows,
]

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fakes (same shape as the unit-level fixtures)
# ---------------------------------------------------------------------------


class _FakeInboundLink:
    """Records pub-ack + pub-complete invocations."""

    def __init__(self):
        self.peer_cluster_id = "east"
        self.pub_ack_calls = []
        self.pub_complete_calls = []

    async def send_pub_ack(self, jid, target_cluster_id, matched, path=None):
        self.pub_ack_calls.append(
            {
                "jid": jid,
                "target_cluster_id": target_cluster_id,
                "matched": list(matched or []),
                "path": list(path) if path is not None else None,
            }
        )

    async def send_pub_complete(
        self,
        jid,
        returned,
        missed,
        cancelled=False,
        cancel_reason=None,
        path=None,
    ):
        self.pub_complete_calls.append(
            {
                "jid": jid,
                "returned": list(returned),
                "missed": list(missed),
                "cancelled": cancelled,
                "cancel_reason": cancel_reason,
                "path": list(path) if path is not None else None,
            }
        )


class _FakeRouter:
    def __init__(self, cluster_id="west"):
        self.cluster_id = cluster_id

    def forward_publish(self, load, inbound_link):
        return [], True

    def lookup_breadcrumb(self, jid):
        return None


class _FakeEventBus:
    """In-memory event bus: ``pending`` queue drives the collector."""

    def __init__(self):
        self.pending = []
        self.subscribe_calls = []
        self.unsubscribe_calls = []
        self.destroy_calls = 0

    def subscribe(self, tag, match_type=None):
        self.subscribe_calls.append((tag, match_type))

    def unsubscribe(self, tag, match_type=None):
        self.unsubscribe_calls.append((tag, match_type))

    def get_event(self, wait=0, tag="", match_type=None, full=False):
        if not self.pending:
            return None
        raw_tag, data = self.pending.pop(0)
        if full:
            return {"tag": raw_tag, "data": data}
        return data

    def destroy(self):
        self.destroy_calls += 1


# ---------------------------------------------------------------------------
# End-to-end dispatch_pub -> spawn collector -> emit pub-complete
# ---------------------------------------------------------------------------


def test_dispatch_pub_spawns_collector_and_emits_complete(monkeypatch):
    """A forwarded publish whose local match set fully returns triggers
    ``send_pub_complete`` on the inbound link with the correct returned/missed
    split.  Simulates the happy path end-to-end through
    :func:`_dispatch_pub`.
    """
    link_manager._PUB_COMPLETE_COLLECTORS.clear()  # pylint: disable=protected-access
    monkeypatch.setattr(
        link_manager,
        "_OPTS",
        {
            "cluster_id": "west",
            "topology_pub_ack": True,
            "topology_pub_complete_enabled": True,
            "topology_pub_complete_timeout": 5.0,
            "topology_pub_complete_max_inflight": 1024,
            "sock_dir": "/tmp/not-used-functional",
        },
    )

    fake_router = _FakeRouter("west")
    monkeypatch.setattr(router_mod, "get_router", lambda: fake_router)

    inbound = _FakeInboundLink()
    monkeypatch.setitem(
        link_manager._INBOUND,  # pylint: disable=protected-access
        "east",
        inbound,
    )
    # Clean up after test.

    async def _fake_publish_to_local_minions(load, matched=None):
        # No-op: we're validating pub-complete emission, not the local
        # publish mechanics.
        return None

    monkeypatch.setattr(
        link_manager, "_publish_to_local_minions", _fake_publish_to_local_minions
    )

    # pub-ack stays fire-and-forget as in production; we only care that
    # it does not block the collector spawn.
    async def _fake_send_pub_ack(
        inbound_link, jid, target_cluster_id, matched, own_cluster_id
    ):
        await inbound_link.send_pub_ack(
            jid, target_cluster_id, matched, path=[own_cluster_id]
        )

    monkeypatch.setattr(
        link_manager, "_send_pub_ack_fire_and_forget", _fake_send_pub_ack
    )
    expected_minions = ["mA", "mB"]
    monkeypatch.setattr(
        link_manager, "_resolve_local_match", lambda load: list(expected_minions)
    )

    # Fake event bus pre-loaded with a return event per expected minion
    # so the collector's first drain tick exits the happy-path branch
    # ``returned >= expected``.
    bus = _FakeEventBus()
    jid = "20261104000000000001"
    for mid in expected_minions:
        bus.pending.append(
            (f"salt/job/{jid}/ret/{mid}", {"id": mid, "jid": jid, "return": True})
        )

    import salt.utils.event

    monkeypatch.setattr(salt.utils.event, "get_master_event", lambda *a, **kw: bus)

    payload = {
        "origin_cluster_id": "east",
        "load": {
            "jid": jid,
            "cmd": "publish",
            "tgt": "*",
            "tgt_type": "glob",
            "fun": "test.ping",
            "topology": {"origin": "east", "path": ["east", "west"]},
        },
    }

    async def _drive():
        await link_manager._dispatch_pub(payload)  # pylint: disable=protected-access
        # Drive the collector task to completion: give it a chance to
        # drain + emit within a bounded wait so the test doesn't hang if
        # something regresses.
        deadline = asyncio.get_event_loop().time() + 2.0
        while (
            not inbound.pub_complete_calls
            and asyncio.get_event_loop().time() < deadline
        ):
            await asyncio.sleep(0.02)

    try:
        asyncio.run(_drive())
    finally:
        # Cancel any stray collector tasks the dispatch may have spawned.
        for task in list(
            link_manager._PUB_COMPLETE_COLLECTORS.values()  # pylint: disable=protected-access
        ):
            task.cancel()
        link_manager._PUB_COMPLETE_COLLECTORS.clear()  # pylint: disable=protected-access
        link_manager._INBOUND.pop("east", None)  # pylint: disable=protected-access

    # One pub-ack + one pub-complete fired, in that order.
    assert len(inbound.pub_ack_calls) == 1
    assert inbound.pub_ack_calls[0]["jid"] == jid
    assert set(inbound.pub_ack_calls[0]["matched"]) == set(expected_minions)

    assert len(inbound.pub_complete_calls) == 1
    complete = inbound.pub_complete_calls[0]
    assert complete["jid"] == jid
    assert set(complete["returned"]) == set(expected_minions)
    assert complete["missed"] == []
    assert complete["cancelled"] is False
    assert complete["cancel_reason"] is None
    # Path carries this cluster's single-entry id.
    assert complete["path"] == ["west"]

    # Subscription established and cleaned up.
    assert bus.subscribe_calls == [(f"salt/job/{jid}/ret/", "startswith")]
    assert bus.unsubscribe_calls == [(f"salt/job/{jid}/ret/", "startswith")]
    assert bus.destroy_calls == 1
