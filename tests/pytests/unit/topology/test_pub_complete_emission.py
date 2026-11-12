"""
Unit tests for Phase 1.5 of the pub-ack / pub-complete feature:
receiver-side emission of ``topology/pub-complete`` via a bounded
per-jid return collector.

Reference:  doc/topics/master-topology/rfc-pub-ack-complete.md
            (specifically the "topology/pub-complete" wire section
            and the Phase 1.5 implementation sketch:
            spawn-after-ack + bounded-collector + empty-match
            fast-path + max-inflight cap).

These exercise, in-process:

* :func:`salt.topology.link_manager._spawn_pub_complete_collector`
  -- opt gating, idempotency, max-inflight cap, empty-match fast path.
* :func:`salt.topology.link_manager._collect_and_emit_pub_complete`
  -- happy-path drain, timeout-partial-drain, subscription-cleanup
  on exception.
* :func:`salt.topology.link_manager._emit_pub_complete_once`
  -- fault isolation for a down originator link (DISCONNECTED health
  gate raises ``LinkUnavailable``).
"""

import asyncio

import pytest

import salt.topology.link_manager as link_manager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeLink:
    """Stand-in for :class:`salt.topology.link.PeerMasterLink`.

    Records each ``send_pub_complete`` call so tests can assert the
    final emission's contents.  ``raises`` -- if set to an exception
    class -- is thrown on every send, simulating a DISCONNECTED link
    without exercising the real health gate.
    """

    def __init__(self, raises=None):
        self.peer_cluster_id = "east"
        self.send_calls = []
        self.raises = raises

    async def send_pub_complete(
        self,
        jid,
        returned,
        missed,
        cancelled=False,
        cancel_reason=None,
        path=None,
    ):
        self.send_calls.append(
            {
                "jid": jid,
                "returned": list(returned),
                "missed": list(missed),
                "cancelled": cancelled,
                "cancel_reason": cancel_reason,
                "path": list(path) if path is not None else None,
            }
        )
        if self.raises is not None:
            raise self.raises("simulated link down")


class _FakeEventBus:
    """In-memory substitute for :class:`salt.utils.event.MasterEvent`.

    Tests drive returns by appending ``(tag, data)`` tuples to
    ``pending``; :meth:`get_event` pops one per call and returns the
    channel-shaped envelope the collector's drain loop consumes.
    ``get_event`` returning ``None`` once the queue is empty mimics the
    real non-blocking behaviour.  :meth:`unsubscribe` + :meth:`destroy`
    record calls so the cleanup assertion can observe them.
    """

    def __init__(self):
        self.pending = []
        self.subscribe_calls = []
        self.unsubscribe_calls = []
        self.destroy_calls = 0
        self.get_event_raises = None

    def subscribe(self, tag, match_type=None):
        self.subscribe_calls.append((tag, match_type))

    def unsubscribe(self, tag, match_type=None):
        self.unsubscribe_calls.append((tag, match_type))

    def get_event(self, wait=0, tag="", match_type=None, full=False):
        if self.get_event_raises is not None:
            raise self.get_event_raises("simulated event bus failure")
        if not self.pending:
            return None
        raw_tag, data = self.pending.pop(0)
        if full:
            return {"tag": raw_tag, "data": data}
        return data

    def destroy(self):
        self.destroy_calls += 1


@pytest.fixture
def _clean_collectors(monkeypatch):
    """Reset per-test module state the collector touches."""
    link_manager._PUB_COMPLETE_COLLECTORS.clear()  # pylint: disable=protected-access
    monkeypatch.setattr(
        link_manager,
        "_OPTS",
        {
            "cluster_id": "west",
            "topology_pub_ack": True,
            "topology_pub_complete_enabled": True,
            "topology_pub_complete_timeout": 60.0,
            "topology_pub_complete_max_inflight": 1024,
            "sock_dir": "/tmp/not-used-by-fake-bus",
        },
    )
    yield
    link_manager._PUB_COMPLETE_COLLECTORS.clear()  # pylint: disable=protected-access


def _install_fake_event_bus(monkeypatch, bus):
    """Monkeypatch ``get_master_event`` to hand back *bus*."""
    import salt.utils.event

    def _fake_get_master_event(*args, **kwargs):
        return bus

    monkeypatch.setattr(salt.utils.event, "get_master_event", _fake_get_master_event)


def _enqueue_return(bus, jid, minion_id):
    """Push a well-shaped minion-return event onto *bus*'s queue."""
    tag = f"salt/job/{jid}/ret/{minion_id}"
    bus.pending.append((tag, {"id": minion_id, "jid": jid, "return": True}))


# ---------------------------------------------------------------------------
# Happy path: all expected minions return, pub-complete fires with returned=expected
# ---------------------------------------------------------------------------


def test_pub_complete_emitted_when_all_expected_return(monkeypatch, _clean_collectors):
    """Every ack'd minion returns -> pub-complete fires with full ``returned`` set."""
    bus = _FakeEventBus()
    _install_fake_event_bus(monkeypatch, bus)
    link = _FakeLink()
    expected = {"m1", "m2", "m3"}

    async def _drive():
        # Pre-queue the three returns so the collector's first drain
        # tick picks them all up and exits via the "returned >=
        # expected" branch before the first sleep.
        _enqueue_return(bus, "jid-happy", "m1")
        _enqueue_return(bus, "jid-happy", "m2")
        _enqueue_return(bus, "jid-happy", "m3")
        await link_manager._collect_and_emit_pub_complete(  # pylint: disable=protected-access
            "jid-happy", set(expected), link, ["west"], timeout_s=5.0
        )

    asyncio.run(_drive())

    assert len(link.send_calls) == 1
    call = link.send_calls[0]
    assert call["jid"] == "jid-happy"
    assert set(call["returned"]) == expected
    assert call["missed"] == []
    assert call["cancelled"] is False
    assert call["cancel_reason"] is None
    assert call["path"] == ["west"]
    # Subscription established + cleaned up.
    assert bus.subscribe_calls == [("salt/job/jid-happy/ret/", "startswith")]
    assert bus.unsubscribe_calls == [("salt/job/jid-happy/ret/", "startswith")]
    assert bus.destroy_calls == 1


# ---------------------------------------------------------------------------
# Timeout branch: partial returns, collector times out, missed is populated
# ---------------------------------------------------------------------------


def test_pub_complete_emitted_on_timeout(monkeypatch, _clean_collectors):
    """Partial returns + expired timeout -> pub-complete fires with ``missed``."""
    bus = _FakeEventBus()
    _install_fake_event_bus(monkeypatch, bus)
    link = _FakeLink()
    expected = {"m1", "m2", "m3"}

    async def _drive():
        # Only m1 arrives before the (short) timeout fires.
        _enqueue_return(bus, "jid-timeout", "m1")
        await link_manager._collect_and_emit_pub_complete(  # pylint: disable=protected-access
            "jid-timeout", set(expected), link, ["west"], timeout_s=0.1
        )

    asyncio.run(_drive())

    assert len(link.send_calls) == 1
    call = link.send_calls[0]
    assert call["jid"] == "jid-timeout"
    assert call["returned"] == ["m1"]
    assert set(call["missed"]) == {"m2", "m3"}
    assert call["cancelled"] is False
    # Subscription cleanup still ran.
    assert bus.unsubscribe_calls == [("salt/job/jid-timeout/ret/", "startswith")]


# ---------------------------------------------------------------------------
# Empty-match fast path: spawn emits pub-complete immediately w/o a task
# ---------------------------------------------------------------------------


def test_pub_complete_empty_match_emits_immediately(monkeypatch, _clean_collectors):
    """Zero local matches -> emit pub-complete synchronously, no task registered."""
    link = _FakeLink()

    async def _drive():
        link_manager._spawn_pub_complete_collector(  # pylint: disable=protected-access
            "jid-empty", [], link, ["west"]
        )
        # One loop yield is enough for the ensure_future-scheduled
        # _emit_pub_complete_once to run through its single await.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(_drive())

    assert len(link.send_calls) == 1
    call = link.send_calls[0]
    assert call["jid"] == "jid-empty"
    assert call["returned"] == []
    assert call["missed"] == []
    # No long-running task was registered -- the fast path does not
    # touch _PUB_COMPLETE_COLLECTORS.
    assert (
        "jid-empty"
        not in link_manager._PUB_COMPLETE_COLLECTORS  # pylint: disable=protected-access
    )


# ---------------------------------------------------------------------------
# Link-down path: send_pub_complete raises -> collector exits cleanly
# ---------------------------------------------------------------------------


def test_pub_complete_stops_if_originator_link_down(monkeypatch, _clean_collectors):
    """A DISCONNECTED originator link makes ``send_pub_complete`` raise;
    the collector swallows the exception (fire-and-forget per RFC) and
    does NOT retry.
    """
    bus = _FakeEventBus()
    _install_fake_event_bus(monkeypatch, bus)

    from salt.topology.link import LinkUnavailable

    link = _FakeLink(raises=LinkUnavailable)
    expected = {"m1"}

    async def _drive():
        _enqueue_return(bus, "jid-down", "m1")
        # Must not raise despite the link being down.
        await link_manager._collect_and_emit_pub_complete(  # pylint: disable=protected-access
            "jid-down", set(expected), link, ["west"], timeout_s=2.0
        )

    # Must complete without raising.
    asyncio.run(_drive())

    # Send was attempted exactly once -- no retry on DISCONNECTED.
    assert len(link.send_calls) == 1
    # Cleanup still ran even though the send failed.
    assert bus.unsubscribe_calls == [("salt/job/jid-down/ret/", "startswith")]
    assert bus.destroy_calls == 1


# ---------------------------------------------------------------------------
# Subscription cleanup on exception: unsubscribe + destroy always run
# ---------------------------------------------------------------------------


def test_pub_complete_subscription_cleanup_on_exception(monkeypatch, _clean_collectors):
    """If the drain loop raises mid-collection, the ``finally`` block
    still unsubscribes and closes the bus client.
    """
    bus = _FakeEventBus()
    # ``get_event`` raises -- the collector's inner try/except logs and
    # moves on, but the subscription-cleanup path must still run.
    bus.get_event_raises = RuntimeError
    _install_fake_event_bus(monkeypatch, bus)
    link = _FakeLink()

    async def _drive():
        await link_manager._collect_and_emit_pub_complete(  # pylint: disable=protected-access
            "jid-crash", {"m1"}, link, ["west"], timeout_s=0.1
        )

    asyncio.run(_drive())
    # Timeout fires with no returns -> complete emitted with missed=[m1].
    assert len(link.send_calls) == 1
    assert link.send_calls[0]["missed"] == ["m1"]
    # And the subscription was torn down despite the inner raise.
    assert bus.unsubscribe_calls == [("salt/job/jid-crash/ret/", "startswith")]
    assert bus.destroy_calls == 1


# ---------------------------------------------------------------------------
# Max-inflight cap: excess spawns skip + WARNING, do not queue
# ---------------------------------------------------------------------------


def test_pub_complete_max_inflight_cap(monkeypatch, _clean_collectors, caplog):
    """Over-cap jids skip spawning with a WARNING log; no task is created."""
    # Set a tiny cap and pre-fill the dict with sentinel "live" tasks so
    # the length check hits the cap on the next call.
    monkeypatch.setitem(link_manager._OPTS, "topology_pub_complete_max_inflight", 2)

    class _DummyTask:
        def cancel(self):
            pass

    link_manager._PUB_COMPLETE_COLLECTORS["jid-a"] = (
        _DummyTask()
    )  # pylint: disable=protected-access
    link_manager._PUB_COMPLETE_COLLECTORS["jid-b"] = (
        _DummyTask()
    )  # pylint: disable=protected-access

    bus = _FakeEventBus()
    _install_fake_event_bus(monkeypatch, bus)
    link = _FakeLink()

    import logging

    with caplog.at_level(logging.WARNING, logger="salt.topology.link_manager"):
        link_manager._spawn_pub_complete_collector(  # pylint: disable=protected-access
            "jid-over", ["m1"], link, ["west"]
        )

    # The new jid was NOT inserted.
    assert (
        "jid-over"
        not in link_manager._PUB_COMPLETE_COLLECTORS  # pylint: disable=protected-access
    )
    # And a WARNING names the cap.
    assert any(
        "cap reached" in rec.message and "jid-over" in rec.message
        for rec in caplog.records
    )


# ---------------------------------------------------------------------------
# Opt gating: topology_pub_complete_enabled=False -> no spawn, no emit
# ---------------------------------------------------------------------------


def test_pub_complete_enabled_opt_false_skips_spawn(monkeypatch, _clean_collectors):
    """With ``topology_pub_complete_enabled=False`` the spawn is a no-op."""
    monkeypatch.setitem(link_manager._OPTS, "topology_pub_complete_enabled", False)
    link = _FakeLink()

    async def _drive():
        link_manager._spawn_pub_complete_collector(  # pylint: disable=protected-access
            "jid-off", ["m1", "m2"], link, ["west"]
        )
        await asyncio.sleep(0)

    asyncio.run(_drive())

    assert link.send_calls == []
    assert (
        "jid-off"
        not in link_manager._PUB_COMPLETE_COLLECTORS  # pylint: disable=protected-access
    )


# ---------------------------------------------------------------------------
# Opt gating: topology_pub_ack=False also disables complete emission
# ---------------------------------------------------------------------------


def test_pub_complete_pub_ack_opt_false_also_skips(monkeypatch, _clean_collectors):
    """If ``topology_pub_ack=False`` the originator can't consume complete
    either -- the spawn is a no-op so a receiver with ack disabled doesn't
    emit mismatched frames.
    """
    monkeypatch.setitem(link_manager._OPTS, "topology_pub_ack", False)
    link = _FakeLink()

    link_manager._spawn_pub_complete_collector(  # pylint: disable=protected-access
        "jid-no-ack", ["m1"], link, ["west"]
    )
    assert (
        "jid-no-ack"
        not in link_manager._PUB_COMPLETE_COLLECTORS  # pylint: disable=protected-access
    )
    assert link.send_calls == []


# ---------------------------------------------------------------------------
# Idempotency: a second spawn for the same jid is a no-op
# ---------------------------------------------------------------------------


def test_pub_complete_spawn_idempotent_on_same_jid(monkeypatch, _clean_collectors):
    """A duplicate spawn for the same jid must not create a second task."""
    bus = _FakeEventBus()
    _install_fake_event_bus(monkeypatch, bus)
    link = _FakeLink()

    async def _drive():
        link_manager._spawn_pub_complete_collector(  # pylint: disable=protected-access
            "jid-dup", ["m1"], link, ["west"]
        )
        first_task = link_manager._PUB_COMPLETE_COLLECTORS[
            "jid-dup"
        ]  # pylint: disable=protected-access
        link_manager._spawn_pub_complete_collector(  # pylint: disable=protected-access
            "jid-dup", ["m1"], link, ["west"]
        )
        # Dict entry is still the same task -- second call did nothing.
        assert (
            link_manager._PUB_COMPLETE_COLLECTORS[
                "jid-dup"
            ]  # pylint: disable=protected-access
            is first_task
        )
        # Cancel to let the test end cleanly.
        first_task.cancel()
        try:
            await first_task
        except asyncio.CancelledError:
            pass

    asyncio.run(_drive())
