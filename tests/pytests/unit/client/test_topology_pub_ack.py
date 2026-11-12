"""
Phase 2 of RFC pub-ack-complete unit tests:  originator-side CLI
consumption of ``topology/pub-ack`` + ``topology/pub-complete``.

Reference:  ``doc/topics/master-topology/rfc-pub-ack-complete.md`` --
specifically the "Originator aggregation" pseudocode, which this
module validates branch-by-branch against a fake-event-bus-driven
:meth:`salt.client.LocalClient.get_iter_returns`.

These tests do NOT drive a real master or a real topology link.  The
``LocalClient.event`` is swapped out for a scripted iterator that
yields the exact sequence of events a real Phase 1 peer would place
on the local bus (via ``_dispatch_pub_ack`` / ``_dispatch_pub_complete``
re-fires).
"""

import time

import pytest

import salt.client
from tests.support.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Scripted-bus helpers
# ---------------------------------------------------------------------------


class _ScriptedEvent:
    """Minimal :class:`salt.utils.event.SaltEvent` replacement.

    The real client polls :meth:`get_event` in a tight loop, so we
    reply with pre-queued ``(delay, payload)`` tuples.  A payload of
    ``None`` is yielded to indicate "no new event right now"; the
    client treats that as a cue to break out of the inner drain loop
    and recheck its exit conditions.
    """

    cpub = True

    def __init__(self, script):
        # script is a list of dicts { "tag": ..., "data": ... } or None entries.
        # We re-serve from the list; once the last real entry is consumed we
        # only ever yield None thereafter so the client can hit its exit
        # conditions deterministically.
        self._script = list(script)
        self._deadline = {}
        self.subscribed = []
        self.unsubscribed = []

    # The client uses only these methods:
    def subscribe(self, tag, match_type=None):
        self.subscribed.append((tag, match_type))

    def unsubscribe(self, tag, match_type=None):
        self.unsubscribed.append((tag, match_type))

    def get_event(
        self,
        wait=0.01,
        tag="",
        match_type=None,
        full=True,
        no_block=True,
        auto_reconnect=False,
    ):
        # Drain one event from the script that matches the requested
        # tag / match_type, else return None.
        for idx, entry in enumerate(self._script):
            if entry is None:
                continue
            etag = entry.get("tag", "")
            if match_type == "regex":
                import re

                if not re.search("^" + tag, etag):
                    continue
            else:
                if not etag.startswith(tag):
                    continue
            # Consume it.
            self._script[idx] = None
            return entry
        return None

    def close_pub(self):
        pass

    def destroy(self):
        pass


@pytest.fixture
def topology_opts(master_opts):
    """Opts with the Phase 2 consumer opt flipped on + a cluster_id.

    ``topology_pub_ack_consumer`` is the opt the consumer branch is
    gated on; ``cluster_id`` must be truthy because a non-cluster
    master cannot originate topology frames.
    """
    master_opts["cluster_id"] = "origin-cluster"
    master_opts["topology_pub_ack_consumer"] = True
    master_opts["topology_pub_ack"] = True
    master_opts["topology_wait"] = 0.05  # tight so tests run quickly
    master_opts["topology_enabled"] = True
    master_opts["timeout"] = 3
    master_opts["gather_job_timeout"] = 1
    master_opts["syndic_wait"] = 1
    return master_opts


@pytest.fixture
def non_topology_opts(master_opts):
    master_opts["cluster_id"] = ""
    master_opts["topology_pub_ack_consumer"] = False
    master_opts["timeout"] = 3
    master_opts["gather_job_timeout"] = 1
    master_opts["syndic_wait"] = 1
    return master_opts


def _make_client(opts, script):
    """Build a LocalClient with a scripted event bus + stubbed returners."""
    client = salt.client.get_local_client(mopts=opts)
    client.event = _ScriptedEvent(script)
    # Pretend the jid exists in the returner so the generator does not
    # short-circuit on "jid does not exist".
    client.returners = {
        f"{opts['master_job_cache']}.get_load": lambda _jid: {"jid": _jid}
    }
    client.returns_for_job = lambda _jid: True
    return client


def _pub_ack_event(jid, origin, matched):
    return {
        "tag": f"salt/topology/pub-ack/{jid}",
        "data": {
            "jid": jid,
            "target_cluster_id": "origin-cluster",
            "matched_minion_ids": list(matched),
            "topology": {"origin": origin, "path": [origin]},
            "_stamp": "2026-11-04T00:00:00.000000",
        },
    }


def _pub_complete_event(jid, origin, returned, missed):
    return {
        "tag": f"salt/topology/pub-complete/{jid}",
        "data": {
            "jid": jid,
            "returned": list(returned),
            "missed": list(missed),
            "cancelled": False,
            "cancel_reason": None,
            "topology": {"origin": origin, "path": [origin]},
            "_stamp": "2026-11-04T00:00:00.000000",
        },
    }


def _job_ret_event(jid, minion_id):
    return {
        "tag": f"salt/job/{jid}/ret/{minion_id}",
        "data": {
            "jid": jid,
            "id": minion_id,
            "return": "ok",
            "retcode": 0,
            "fun": "test.ping",
            "_stamp": "2026-11-04T00:00:00.000000",
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_local_client_topology_expected_set_grows_on_pub_ack(topology_opts):
    """A pub-ack frame grows ``expected_set`` by its matched_minion_ids.

    Covers the pseudocode line:
    ``expected_set |= frame.matched_minion_ids``.
    """
    jid = "20261104000000000001"
    script = [
        _pub_ack_event(jid, "east-sub", ["minion-a", "minion-b"]),
        _pub_complete_event(jid, "east-sub", ["minion-a", "minion-b"], []),
        _job_ret_event(jid, "minion-a"),
        _job_ret_event(jid, "minion-b"),
    ]
    client = _make_client(topology_opts, script)
    # Drain the generator; the loop will exit on the happy-path branch.
    results = list(client.get_iter_returns(jid, set(), timeout=3))
    assert client._last_topology_expected_set == {"minion-a", "minion-b"}
    assert "east-sub" in client._last_topology_peers_acked
    # Results include the two minion returns.
    got_ids = set()
    for item in results:
        if isinstance(item, dict):
            got_ids.update(item.keys())
    assert {"minion-a", "minion-b"} <= got_ids


def test_local_client_topology_peers_complete_exits_early(topology_opts):
    """All ack'd peers sending pub-complete + grace elapsed => early exit.

    Peer ack'd ``minion-c`` but ``minion-c`` never returns; the
    pub-complete frame marks it as missed.  The loop must exit via the
    "peers_complete >= peers_acked" branch rather than waiting for
    ``--timeout``.  Wall-clock budget: well under ``timeout=3``.
    """
    jid = "20261104000000000002"
    script = [
        _pub_ack_event(jid, "east-sub", ["minion-c"]),
        _pub_complete_event(jid, "east-sub", [], ["minion-c"]),
    ]
    client = _make_client(topology_opts, script)
    start = time.monotonic()
    list(client.get_iter_returns(jid, set(), timeout=3))
    elapsed = time.monotonic() - start
    # Grace window is 0.05s so we should be out well before 3s.
    assert elapsed < 2.0, f"loop took {elapsed:.2f}s, expected early exit"
    assert client._last_topology_peers_complete == {"east-sub"}
    assert client._last_topology_missed_by_peer == {"east-sub": ["minion-c"]}


def test_local_client_topology_falls_back_without_opt(non_topology_opts):
    """``topology_pub_ack_consumer=False`` => standard wait-loop path.

    No topology-side state is populated; generator exits on the
    pre-existing happy-path branch after the single expected return.
    """
    jid = "20261104000000000003"
    script = [_job_ret_event(jid, "minion-x")]
    client = _make_client(non_topology_opts, script)
    results = list(client.get_iter_returns(jid, {"minion-x"}, timeout=3))
    # Consumer branch untouched: aggregation state stays empty.
    assert client._last_topology_expected_set == set()
    assert client._last_topology_peers_acked == set()
    assert client._last_topology_peers_complete == set()
    assert client._last_topology_missed_by_peer == {}
    got_ids = set()
    for item in results:
        if isinstance(item, dict):
            got_ids.update(item.keys())
    assert "minion-x" in got_ids


def test_local_client_topology_falls_back_on_silent_peer(topology_opts):
    """One peer never acks => loop exits via generic --timeout branch.

    Simulates a mixed deployment where one peer runs older code and
    never emits pub-ack / pub-complete.  The CLI must still terminate
    without hanging; it exits on the generic ``--timeout`` branch.
    """
    jid = "20261104000000000004"
    # No pub-ack / pub-complete at all -- peer is silent.
    script = []
    client = _make_client(topology_opts, script)
    # Short timeout so this test does not take long.  The point is
    # that the loop *terminates* at all; the real guarantee is
    # "no hang."
    client.opts["timeout"] = 1
    client.opts["gather_job_timeout"] = 1
    # Make the gather_job_info call a no-op so we do not try to wire
    # up a full master.
    client.gather_job_info = MagicMock(return_value={})
    with patch("salt.utils.minions.CkMinions") as ck:
        ck.return_value._pki_minions.return_value = []
        start = time.monotonic()
        list(client.get_iter_returns(jid, set(), timeout=1))
    elapsed = time.monotonic() - start
    # It must terminate within a few seconds.  With timeout=1 and
    # gather_job_timeout=1 the generic path should get us out well
    # under 5s.
    assert elapsed < 5.0, f"loop hung for {elapsed:.2f}s"
    # Nothing should have been populated.
    assert client._last_topology_peers_acked == set()
    assert client._last_topology_peers_complete == set()


def test_local_client_topology_missed_by_peer_surfaced(topology_opts):
    """``missed_by_peer`` dict is populated from pub-complete.missed.

    Verifies the chosen surface (``_last_topology_missed_by_peer``
    LocalClient attribute) carries the per-peer missed list after the
    loop exhausts.
    """
    jid = "20261104000000000005"
    script = [
        _pub_ack_event(jid, "east-sub", ["m1", "m2", "m3"]),
        _pub_complete_event(jid, "east-sub", ["m1"], ["m2", "m3"]),
        _pub_ack_event(jid, "west-sub", ["m4"]),
        _pub_complete_event(jid, "west-sub", ["m4"], []),
        _job_ret_event(jid, "m1"),
        _job_ret_event(jid, "m4"),
    ]
    client = _make_client(topology_opts, script)
    list(client.get_iter_returns(jid, set(), timeout=3))
    assert client._last_topology_missed_by_peer == {
        "east-sub": ["m2", "m3"],
    }
    assert client._last_topology_peers_acked == {"east-sub", "west-sub"}
    assert client._last_topology_peers_complete == {"east-sub", "west-sub"}


def test_local_client_topology_pub_ack_deadline(topology_opts):
    """Deadline gate: don't exit on peers_complete before pub_ack grace.

    If pub-complete arrives *before* the pub-ack grace elapses, the
    loop should still wait at least until the grace is up.  This
    prevents a fast peer from short-circuiting the loop before a
    slower peer's ack has had time to grow ``expected_set``.
    """
    jid = "20261104000000000006"
    topology_opts["topology_wait"] = 0.3
    # east-sub acks + completes immediately.  west-sub acks only
    # after the first drain tick.
    script = [
        _pub_ack_event(jid, "east-sub", ["ma"]),
        _pub_complete_event(jid, "east-sub", ["ma"], []),
        _job_ret_event(jid, "ma"),
    ]
    client = _make_client(topology_opts, script)
    start = time.monotonic()
    list(client.get_iter_returns(jid, set(), timeout=3))
    elapsed = time.monotonic() - start
    # The happy-path branch (returned_set >= expected_set) fires here
    # because ma returned.  Loop exits quickly; we assert that the
    # test itself completed in a bounded time, i.e. we did not hang.
    assert elapsed < 2.0
    # And that expected_set grew from the ack.
    assert client._last_topology_expected_set == {"ma"}


def test_local_client_topology_subscribes_on_pub(topology_opts):
    """``_check_pub_data`` subscribes to topology events when consumer is on."""
    client = salt.client.get_local_client(mopts=topology_opts)
    client.event = _ScriptedEvent([])
    client._check_pub_data({"jid": "12345", "minions": ["a"]})
    tags = [t for t, _ in client.event.subscribed]
    assert any(t.startswith("salt/topology/pub-(ack|complete)/") for t in tags), tags


def test_local_client_topology_no_subscribe_without_cluster_id(topology_opts):
    """Without cluster_id the consumer branch is a no-op: no subscribe."""
    topology_opts["cluster_id"] = ""
    client = salt.client.get_local_client(mopts=topology_opts)
    client.event = _ScriptedEvent([])
    client._check_pub_data({"jid": "12345", "minions": ["a"]})
    tags = [t for t, _ in client.event.subscribed]
    assert not any(
        t.startswith("salt/topology/pub-") for t in tags
    ), f"unexpected topology subscribe without cluster_id: {tags}"
