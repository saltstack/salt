"""
Scenario-level backward-compat test for RFC pub-ack-complete Phase 2.

Reference:  ``doc/topics/master-topology/rfc-pub-ack-complete.md``,
"Rollout" section.

Covers the mixed-deployment case the RFC explicitly promises:  one
peer runs with ``topology_pub_ack: False`` on the emit side
(simulates older code or an operator opt-out), other peers emit
normally.  The originator CLI with the consumer opt turned on must:

1. Not hang on the silent peer.
2. Use the ack+complete signals from chatty peers to grow
   ``expected_set`` and to exit early once every *ack'd* peer has
   also sent pub-complete.
3. Fall through to the generic ``--timeout`` branch iff the silent
   peer's minions never return.

The silent peer manifests on the local event bus as "no pub-ack ever
arrives for its cluster_id", so from the originator's perspective
the silent peer is counted in neither ``peers_acked`` nor
``peers_complete`` -- which is the correct and intended semantics
(the RFC's Phase 2 pseudocode only compares ``peers_complete >=
peers_acked``).
"""

import time

import pytest

import salt.client

pytestmark = [
    pytest.mark.skip_on_windows,
]


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
def mopts(tmp_path):
    """Minimal master-shaped opts for driving :class:`LocalClient`."""
    import salt.config

    conf_file = tmp_path / "master"
    conf_file.write_text("")
    opts = salt.config.master_config(str(conf_file))
    opts["sock_dir"] = str(tmp_path / "sock")
    opts["cachedir"] = str(tmp_path / "cache")
    opts["pki_dir"] = str(tmp_path / "pki")
    opts["root_dir"] = str(tmp_path)
    for key in ("sock_dir", "cachedir", "pki_dir"):
        import os

        os.makedirs(opts[key], exist_ok=True)
    return opts


def test_pub_ack_backward_compatible_with_silent_peer(mopts):
    """Mixed deployment: one peer older (no pub-ack), one Phase-1 enabled.

    Scenario timeline (all scripted onto one local event bus):

    * east-sub (Phase-1 code, opt on):  acks + completes normally.
    * west-sub (older code, opt off):  never emits pub-ack or
      pub-complete; its two minions still send job returns.

    Expected behavior:  the CLI counts east-sub in both
    ``peers_acked`` and ``peers_complete``; west-sub appears in
    neither.  Because the happy-path exit (``found >= expected_set``)
    fires once every ack'd + silent-peer minion has returned, the
    loop still exits well before ``--timeout``.
    """
    mopts["cluster_id"] = "origin"
    mopts["topology_enabled"] = True
    mopts["topology_pub_ack_consumer"] = True
    mopts["topology_pub_ack"] = True
    mopts["topology_wait"] = 0.05
    mopts["timeout"] = 30
    mopts["gather_job_timeout"] = 5
    mopts["syndic_wait"] = 1

    client = salt.client.get_local_client(mopts=mopts)
    try:
        client.returners = {
            f"{mopts['master_job_cache']}.get_load": lambda _jid: {"jid": _jid}
        }
        client.returns_for_job = lambda _jid: True

        jid = "20261104200000000001"
        script = [
            # east-sub emits both frames + one return
            _pub_ack(jid, "east-sub", ["east-m1"]),
            _pub_complete(jid, "east-sub", ["east-m1"], []),
            _job_ret(jid, "east-m1"),
            # west-sub emits NO frames (older code) but minions do return
            _job_ret(jid, "west-m1"),
            _job_ret(jid, "west-m2"),
        ]
        client.event = _ScriptedEvent(script)
        # Seed minions with the full target set the publisher's local
        # matcher would produce for an older, non-topology-aware target
        # resolution.  This models the operator issuing `salt '*' ...`
        # where the local matcher resolved these three ids directly.
        start = time.monotonic()
        results = list(
            client.get_iter_returns(jid, {"east-m1", "west-m1", "west-m2"}, timeout=30)
        )
        elapsed = time.monotonic() - start

        # Did not wait for --timeout.
        assert elapsed < 3.0, (
            f"CLI waited {elapsed:.2f}s; expected early exit when all "
            "returns were in"
        )

        # east-sub appears in both ack'd and complete; west-sub in neither.
        assert client._last_topology_peers_acked == {"east-sub"}
        assert client._last_topology_peers_complete == {"east-sub"}

        # Returns surfaced for all three minions.
        got_ids = set()
        for item in results:
            if isinstance(item, dict):
                got_ids.update(item.keys())
        assert {"east-m1", "west-m1", "west-m2"} <= got_ids

        # No peer reported any missed minion.
        assert client._last_topology_missed_by_peer == {}
    finally:
        client.destroy()
