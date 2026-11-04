"""
Phase 2 functional tests for RFC pub-ack-complete.

Reference:  ``doc/topics/master-topology/rfc-pub-ack-complete.md``.

These exercise the originator-side CLI loop end-to-end against a
scripted event bus:  the scripted bus simulates what a real Phase 1
peer would place on the local master bus via
:func:`salt.topology.link_manager._dispatch_pub_ack` /
``_dispatch_pub_complete`` re-fires.  A single-file test file so we
can keep the scope narrow -- unit tests cover branch-by-branch
semantics; functional tests cover the multi-peer flood shape.
"""

import logging
import time

import pytest

import salt.client

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.skip_on_windows,
]


# ---------------------------------------------------------------------------
# Scripted event bus (mirror of unit test helper, standalone here so the
# functional test file is self-contained).
# ---------------------------------------------------------------------------


class _ScriptedEvent:
    cpub = True

    def __init__(self, script):
        self._script = list(script)
        self.subscribed = []
        self.unsubscribed = []

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
        import re

        for idx, entry in enumerate(self._script):
            if entry is None:
                continue
            etag = entry.get("tag", "")
            if match_type == "regex":
                if not re.search("^" + tag, etag):
                    continue
            else:
                if not etag.startswith(tag):
                    continue
            self._script[idx] = None
            return entry
        return None

    def close_pub(self):
        pass

    def destroy(self):
        pass


def _pub_ack(jid, origin, matched):
    return {
        "tag": f"salt/topology/pub-ack/{jid}",
        "data": {
            "jid": jid,
            "target_cluster_id": "origin",
            "matched_minion_ids": list(matched),
            "topology": {"origin": origin, "path": [origin]},
        },
    }


def _pub_complete(jid, origin, returned, missed):
    return {
        "tag": f"salt/topology/pub-complete/{jid}",
        "data": {
            "jid": jid,
            "returned": list(returned),
            "missed": list(missed),
            "cancelled": False,
            "cancel_reason": None,
            "topology": {"origin": origin, "path": [origin]},
        },
    }


def _job_ret(jid, mid):
    return {
        "tag": f"salt/job/{jid}/ret/{mid}",
        "data": {
            "jid": jid,
            "id": mid,
            "return": "ok",
            "retcode": 0,
            "fun": "test.ping",
        },
    }


@pytest.fixture
def topo_client(master_opts):
    master_opts["cluster_id"] = "origin"
    master_opts["topology_enabled"] = True
    master_opts["topology_pub_ack_consumer"] = True
    master_opts["topology_pub_ack"] = True
    master_opts["topology_wait"] = 0.05
    master_opts["timeout"] = 30
    master_opts["gather_job_timeout"] = 5
    master_opts["syndic_wait"] = 1
    client = salt.client.get_local_client(mopts=master_opts)
    client.returners = {
        f"{master_opts['master_job_cache']}.get_load": lambda _jid: {"jid": _jid}
    }
    client.returns_for_job = lambda _jid: True
    yield client
    client.destroy()


def test_cli_terminates_on_pub_complete_before_timeout(topo_client):
    """2-peer topology:  both peers ack+complete within 1s; CLI exits
    in <1s instead of waiting for ``--timeout=30``.
    """
    jid = "20261104100000000001"
    script = [
        _pub_ack(jid, "east-sub", ["ma", "mb"]),
        _pub_ack(jid, "west-sub", ["mc"]),
        _pub_complete(jid, "east-sub", ["ma", "mb"], []),
        _pub_complete(jid, "west-sub", ["mc"], []),
        _job_ret(jid, "ma"),
        _job_ret(jid, "mb"),
        _job_ret(jid, "mc"),
    ]
    topo_client.event = _ScriptedEvent(script)
    start = time.monotonic()
    results = list(topo_client.get_iter_returns(jid, set(), timeout=30))
    elapsed = time.monotonic() - start
    assert (
        elapsed < 2.0
    ), f"CLI waited {elapsed:.2f}s after all peers completed; expected <2s"
    # All returns surfaced.
    ids = set()
    for item in results:
        if isinstance(item, dict):
            ids.update(item.keys())
    assert {"ma", "mb", "mc"} <= ids


def test_cli_sees_expected_set_grow_from_ack(topo_client):
    """3-peer flood: ``expected_set`` matches union of per-peer matches."""
    jid = "20261104100000000002"
    script = [
        _pub_ack(jid, "east", ["e1", "e2"]),
        _pub_ack(jid, "west", ["w1"]),
        _pub_ack(jid, "north", ["n1", "n2", "n3"]),
        _pub_complete(jid, "east", ["e1", "e2"], []),
        _pub_complete(jid, "west", ["w1"], []),
        _pub_complete(jid, "north", ["n1", "n2", "n3"], []),
        _job_ret(jid, "e1"),
        _job_ret(jid, "e2"),
        _job_ret(jid, "w1"),
        _job_ret(jid, "n1"),
        _job_ret(jid, "n2"),
        _job_ret(jid, "n3"),
    ]
    topo_client.event = _ScriptedEvent(script)
    list(topo_client.get_iter_returns(jid, set(), timeout=30))
    assert topo_client._last_topology_expected_set == {
        "e1",
        "e2",
        "w1",
        "n1",
        "n2",
        "n3",
    }
    assert topo_client._last_topology_peers_acked == {"east", "west", "north"}
    assert topo_client._last_topology_peers_complete == {"east", "west", "north"}
