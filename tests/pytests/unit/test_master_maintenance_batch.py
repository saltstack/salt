"""
Unit tests for :meth:`salt.master.Maintenance.handle_batch_jobs`.

We don't start a real master or fork; instead we invoke the unbound
method against a lightweight object that exposes just the two
attributes ``handle_batch_jobs`` reads (``self.opts`` and
``self.event``).  That keeps the test focused on the scheduling
policy — what counts as "stale", what gets recovered, what gets
pruned — and decouples it from the rest of the master process tree.
"""

from types import SimpleNamespace

import pytest

import salt.master
import salt.utils.batch_state
from tests.support.mock import MagicMock


@pytest.fixture
def opts(tmp_path):
    return {
        "cachedir": str(tmp_path),
        "hash_type": "sha256",
        "sock_dir": str(tmp_path),
        "batch_manager_loop_interval": 5,
    }


def _fake_maintenance(opts):
    """Bare object with the two attributes handle_batch_jobs touches."""
    return SimpleNamespace(opts=opts, event=MagicMock())


def _write_state(opts, jid, *, last_progress, halted=False, timeout=60):
    state = salt.utils.batch_state.create_batch_state(
        {"batch": 2, "fun": "test.ping", "tgt": "*", "timeout": timeout},
        ["m1", "m2"],
        jid,
        driver="master",
        now=0.0,
    )
    state["last_progress"] = last_progress
    state["halted"] = halted
    if halted:
        state["halted_reason"] = "stop"
    salt.utils.batch_state.write_batch_state(jid, state, opts)
    return state


def _call(opts):
    """Invoke handle_batch_jobs against a fake Maintenance instance."""
    fake = _fake_maintenance(opts)
    salt.master.Maintenance.handle_batch_jobs(fake)
    return fake


class TestHandleBatchJobs:
    def test_empty_index_is_noop(self, opts):
        fake = _call(opts)
        fake.event.fire_event.assert_not_called()

    def test_fresh_batch_is_not_flagged(self, opts):
        # Fresh = last_progress very recent.
        import time

        _write_state(opts, "JID1", last_progress=time.time())
        salt.utils.batch_state.add_to_active_index("JID1", opts)
        fake = _call(opts)
        fake.event.fire_event.assert_not_called()

    def test_stale_batch_fires_recover(self, opts):
        # last_progress = 0 makes the batch arbitrarily old.
        _write_state(opts, "JID1", last_progress=0.0)
        salt.utils.batch_state.add_to_active_index("JID1", opts)
        fake = _call(opts)
        fake.event.fire_event.assert_called_once()
        _data, tag = fake.event.fire_event.call_args.args
        assert tag == "salt/batch/JID1/recover"

    def test_halted_batch_is_pruned_from_index(self, opts):
        _write_state(opts, "JID1", last_progress=0.0, halted=True)
        salt.utils.batch_state.add_to_active_index("JID1", opts)
        _call(opts)
        assert salt.utils.batch_state.read_active_index(opts) == set()

    def test_missing_batch_file_is_pruned(self, opts):
        # Index entry without a corresponding .batch.p — treated as dead.
        salt.utils.batch_state.add_to_active_index("GHOST", opts)
        fake = _call(opts)
        assert salt.utils.batch_state.read_active_index(opts) == set()
        fake.event.fire_event.assert_not_called()

    def test_mix_of_fresh_stale_halted(self, opts):
        import time

        _write_state(opts, "JID-FRESH", last_progress=time.time())
        _write_state(opts, "JID-STALE", last_progress=0.0)
        _write_state(opts, "JID-HALT", last_progress=0.0, halted=True)
        for j in ("JID-FRESH", "JID-STALE", "JID-HALT"):
            salt.utils.batch_state.add_to_active_index(j, opts)

        fake = _call(opts)

        # Only STALE triggers recover.
        tags = [c.args[1] for c in fake.event.fire_event.call_args_list]
        assert tags == ["salt/batch/JID-STALE/recover"]
        # HALT pruned; FRESH and STALE remain.
        assert salt.utils.batch_state.read_active_index(opts) == {
            "JID-FRESH",
            "JID-STALE",
        }
