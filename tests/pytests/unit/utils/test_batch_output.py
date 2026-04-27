"""
Unit tests for :mod:`salt.utils.batch_output`.

Pins the event tag vocabulary, payload shapes, and adapter dispatch
behavior.  The tag names are user-facing API; a change to any of them
is a breaking change and should require a conscious test update.
"""

from salt.utils import batch_output
from tests.support.mock import MagicMock

# ---------------------------------------------------------------------------
# Tag vocabulary
# ---------------------------------------------------------------------------


class TestTagVocabulary:
    def test_new(self):
        assert batch_output.tag_new("JID1") == "salt/batch/JID1/new"

    def test_progress(self):
        assert batch_output.tag_progress("JID1") == "salt/batch/JID1/progress"

    def test_complete(self):
        assert batch_output.tag_complete("JID1") == "salt/batch/JID1/complete"

    def test_halted(self):
        assert batch_output.tag_halted("JID1") == "salt/batch/JID1/halted"

    def test_recover(self):
        assert batch_output.tag_recover("JID1") == "salt/batch/JID1/recover"


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------


def _sample_state():
    return {
        "jid": "JID1",
        "fun": "test.ping",
        "tgt": "*",
        "tgt_type": "glob",
        "user": "alice",
        "driver": "master",
        "all_minions": ["m1", "m2", "m3", "m4"],
        "pending": ["m3", "m4"],
        "active": {"m2": 100.0},
        "done": {"m1": {"ret": True, "retcode": 0}},
        "failed": {},
        "batch_size": 2,
        "created": 90.0,
        "last_progress": 101.0,
        "halted": False,
        "halted_reason": None,
    }


class TestPayloads:
    def test_new_payload(self):
        payload = batch_output.new_payload(_sample_state())
        assert payload["jid"] == "JID1"
        assert payload["total_minions"] == 4
        assert payload["batch_size"] == 2
        assert payload["driver"] == "master"
        assert payload["created"] == 90.0

    def test_progress_payload(self):
        payload = batch_output.progress_payload(_sample_state(), iteration=3)
        assert payload["total"] == 4
        assert payload["completed"] == 1
        assert payload["active"] == 1
        assert payload["pending"] == 2
        assert payload["failed"] == 0
        assert payload["iter"] == 3
        assert payload["last_progress"] == 101.0

    def test_complete_payload(self):
        state = _sample_state()
        payload = batch_output.complete_payload(state, now=200.0)
        assert payload["completed"] == 1
        assert payload["failed"] == 0
        assert payload["total_minions"] == 4
        assert payload["duration"] == 110.0

    def test_halted_payload(self):
        state = _sample_state()
        state["halted"] = True
        state["halted_reason"] = "failhard"
        payload = batch_output.halted_payload(state, now=200.0)
        assert payload["reason"] == "failhard"
        assert payload["abandoned_active"] == ["m2"]
        assert payload["abandoned_pending"] == ["m3", "m4"]
        assert payload["duration"] == 110.0

    def test_recover_payload(self):
        payload = batch_output.recover_payload(_sample_state(), age_seconds=120.5)
        assert payload["reason"] == "stale"
        assert payload["age_seconds"] == 120.5
        assert payload["driver"] == "master"


# ---------------------------------------------------------------------------
# EventOutput dispatch
# ---------------------------------------------------------------------------


class TestEventOutput:
    def _make(self):
        event = MagicMock()
        return batch_output.EventOutput(opts={}, event=event), event

    def test_on_batch_new_fires_new_tag(self):
        adapter, event = self._make()
        state = _sample_state()
        adapter.on_batch_new(state)
        event.fire_event.assert_called_once()
        _, kwargs = event.fire_event.call_args
        data, tag = event.fire_event.call_args.args
        assert tag == "salt/batch/JID1/new"
        assert data["total_minions"] == 4

    def test_on_batch_done_normal_fires_complete(self):
        adapter, event = self._make()
        adapter.on_batch_done(_sample_state(), now=200.0)
        data, tag = event.fire_event.call_args.args
        assert tag == "salt/batch/JID1/complete"

    def test_on_batch_done_halted_fires_halted(self):
        adapter, event = self._make()
        state = _sample_state()
        state["halted"] = True
        state["halted_reason"] = "failhard"
        adapter.on_batch_done(state, now=200.0)
        data, tag = event.fire_event.call_args.args
        assert tag == "salt/batch/JID1/halted"
        assert data["reason"] == "failhard"

    def test_on_batch_progress_fires_progress_tag(self):
        adapter, event = self._make()
        adapter.on_batch_progress(_sample_state(), iteration=5)
        data, tag = event.fire_event.call_args.args
        assert tag == "salt/batch/JID1/progress"
        assert data["iter"] == 5


class TestSilentOutput:
    def test_all_hooks_are_noops(self):
        adapter = batch_output.SilentOutput()
        state = _sample_state()
        # None of these should raise, regardless of what's passed.
        adapter.on_batch_new(state)
        adapter.on_batch_progress(state)
        adapter.on_batch_complete(state)
        adapter.on_batch_halted(state)
        adapter.on_batch_recover(state, age_seconds=0)
        adapter.on_batch_start(["m1"])
        adapter.on_minion_return("m1", {})
        adapter.on_minion_timeout("m1")
        adapter.on_batch_done(state)
