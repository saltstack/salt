"""
Unit tests for :class:`salt.utils.batch_manager.BatchManager`.

The manager is written so its handlers (``_handle_event``,
``_progress_one``, ``_tick``, ``_handle_new``, ``_handle_stop``,
``_handle_recover``) can be driven directly on an instance whose
``event``, ``local``, and ``output`` dependencies have been replaced
with mocks.  That lets us assert behavior step-by-step without
forking a process, talking to a real event bus, or publishing jobs.
"""

import pytest

import salt.utils.batch_output
import salt.utils.batch_state
from salt.utils.batch_manager import BatchManager, _event_to_return
from tests.support.mock import MagicMock


@pytest.fixture
def opts(tmp_path):
    return {
        "cachedir": str(tmp_path),
        "hash_type": "sha256",
        "sock_dir": str(tmp_path),
        "conf_file": str(tmp_path / "master"),
        "batch_manager_loop_interval": 5,
    }


@pytest.fixture
def manager(opts):
    """
    BatchManager wired up with mocks instead of real event bus / client.

    We skip the ``SignalHandlingProcess.__init__`` side-effects by
    instantiating normally but manually injecting the post-fork
    collaborators so no fork or sock is required.
    """
    mgr = BatchManager(opts)
    mgr.event = MagicMock()
    mgr.local = MagicMock()
    mgr.output = MagicMock()
    mgr.active_batches = set()
    return mgr


def _write_state(opts, minions, jid, batch_size=2, **overrides):
    state = salt.utils.batch_state.create_batch_state(
        {"batch": batch_size, "fun": "test.ping", "tgt": "*"},
        minions,
        jid,
        driver="master",
        now=1000.0,
    )
    state.update(overrides)
    salt.utils.batch_state.write_batch_state(jid, state, opts)
    return state


# ---------------------------------------------------------------------------
# _event_to_return — translation from event bus payload to state-machine input
# ---------------------------------------------------------------------------


class TestEventToReturn:
    def test_maps_return_to_ret(self):
        assert _event_to_return({"return": True, "retcode": 0}) == {
            "ret": True,
            "retcode": 0,
        }

    def test_retcode_default_zero(self):
        assert _event_to_return({"return": "hi"}) == {"ret": "hi", "retcode": 0}

    def test_non_dict_wrapped(self):
        assert _event_to_return("scalar") == {"ret": "scalar", "retcode": 0}


# ---------------------------------------------------------------------------
# _handle_event — dispatch table
# ---------------------------------------------------------------------------


class TestHandleEvent:
    def test_batch_new_calls_handle_new(self, manager):
        manager._handle_new = MagicMock()
        manager._handle_event({"tag": "salt/batch/JID1/new", "data": {}})
        manager._handle_new.assert_called_once_with("JID1", {})

    def test_batch_stop_calls_handle_stop(self, manager):
        manager._handle_stop = MagicMock()
        manager._handle_event(
            {"tag": "salt/batch/JID1/stop", "data": {"reason": "user"}}
        )
        manager._handle_stop.assert_called_once_with("JID1", {"reason": "user"})

    def test_batch_recover_calls_handle_recover(self, manager):
        manager._handle_recover = MagicMock()
        manager._handle_event({"tag": "salt/batch/JID1/recover", "data": {}})
        manager._handle_recover.assert_called_once_with("JID1")

    def test_job_return_for_adopted_batch_dispatches(self, manager):
        manager.active_batches.add("JID1")
        manager._handle_batch_return = MagicMock()
        manager._handle_event(
            {
                "tag": "salt/job/JID1/ret/web1",
                "data": {"return": True, "retcode": 0},
            }
        )
        manager._handle_batch_return.assert_called_once_with(
            "JID1", "web1", {"return": True, "retcode": 0}
        )

    def test_job_return_for_unknown_jid_is_ignored(self, manager):
        manager._handle_batch_return = MagicMock()
        # Not in active_batches — this is the fast path we don't want to
        # waste I/O on.
        manager._handle_event({"tag": "salt/job/OTHER/ret/web1", "data": {}})
        manager._handle_batch_return.assert_not_called()

    def test_unrelated_event_is_ignored(self, manager):
        manager._handle_batch_return = MagicMock()
        manager._handle_new = MagicMock()
        manager._handle_event({"tag": "salt/auth/accept", "data": {}})
        manager._handle_batch_return.assert_not_called()
        manager._handle_new.assert_not_called()


# ---------------------------------------------------------------------------
# _handle_new — adoption from the CLI's salt/batch/<jid>/new event
# ---------------------------------------------------------------------------


class TestHandleNew:
    def test_adopts_master_driven_batch(self, manager, opts):
        _write_state(opts, ["m1", "m2"], "JID1")
        manager._handle_new("JID1")
        assert "JID1" in manager.active_batches
        assert salt.utils.batch_state.read_active_index(opts) == {"JID1"}

    def test_registers_cli_driven_batch_without_adopting(self, manager, opts):
        """
        Sync CLI batches arrive at the manager via
        ``salt/batch/<jid>/new`` carrying ``data["state"]``.  The
        manager persists them and adds to the active index so
        ``batch.status`` / ``batch.list_active`` see them, but does
        not adopt them into ``self.active_batches`` (the CLI owns
        the state machine).
        """
        # Build the state inline — the CLI never wrote .batch.p, the
        # manager is supposed to write it on receipt of the event.
        state = salt.utils.batch_state.create_batch_state(
            {"batch": 1, "fun": "test.ping", "tgt": "*"},
            ["m1"],
            "JID-CLI",
            driver="cli",
            now=1000.0,
        )
        manager._handle_new("JID-CLI", {"state": state})
        assert "JID-CLI" not in manager.active_batches
        assert salt.utils.batch_state.read_active_index(opts) == {"JID-CLI"}
        on_disk = salt.utils.batch_state.read_batch_state("JID-CLI", opts)
        assert on_disk is not None
        assert on_disk["driver"] == "cli"

    def test_cli_handle_new_falls_back_to_disk_state(self, manager, opts):
        """
        Belt-and-braces: if a ``salt/batch/<jid>/new`` event arrives
        without an embedded ``state`` payload (older CLI, or the
        event was triggered some other way) and ``.batch.p`` happens
        to already exist, we still register the JID in the index.
        """
        _write_state(opts, ["m1"], "JID-CLI", driver="cli")
        manager._handle_new("JID-CLI")
        assert "JID-CLI" not in manager.active_batches
        assert "JID-CLI" in salt.utils.batch_state.read_active_index(opts)

    def test_handles_missing_batch_file(self, manager, opts):
        manager._handle_new("NONEXISTENT")
        assert manager.active_batches == set()

    def test_adoption_is_idempotent(self, manager, opts):
        _write_state(opts, ["m1"], "JID1")
        manager._handle_new("JID1")
        manager._handle_new("JID1")
        assert manager.active_batches == {"JID1"}


# ---------------------------------------------------------------------------
# _progress_one — the core step driven by returns and ticks
# ---------------------------------------------------------------------------


class TestProgressOne:
    def test_return_triggers_next_dispatch(self, manager, opts):
        _write_state(opts, ["m1", "m2", "m3", "m4"], "JID1", batch_size=2)
        manager.active_batches.add("JID1")
        # First progress pass — no returns yet, fills initial 2 slots.
        manager._progress_one("JID1", {}, now=1.0)
        manager.local.run_job.assert_called_once()
        first_args = manager.local.run_job.call_args.kwargs
        assert sorted(first_args["tgt"]) == ["m1", "m2"]
        assert first_args["jid"] == "JID1"

        # m1 and m2 return → state machine should publish m3, m4.
        manager.local.run_job.reset_mock()
        manager._progress_one(
            "JID1",
            {
                "m1": {"ret": True, "retcode": 0},
                "m2": {"ret": True, "retcode": 0},
            },
            now=2.0,
        )
        manager.local.run_job.assert_called_once()
        second_args = manager.local.run_job.call_args.kwargs
        assert sorted(second_args["tgt"]) == ["m3", "m4"]

    def test_completion_fires_batch_done_and_retires(self, manager, opts):
        _write_state(opts, ["m1", "m2"], "JID1", batch_size=2)
        manager.active_batches.add("JID1")
        salt.utils.batch_state.add_to_active_index("JID1", opts)

        manager._progress_one("JID1", {}, now=1.0)  # dispatch
        manager._progress_one(
            "JID1",
            {
                "m1": {"ret": True, "retcode": 0},
                "m2": {"ret": True, "retcode": 0},
            },
            now=2.0,
        )
        manager.output.on_batch_done.assert_called_once()
        assert "JID1" not in manager.active_batches
        assert salt.utils.batch_state.read_active_index(opts) == set()

    def test_failhard_halts_and_fires_halted_event(self, manager, opts):
        _write_state(opts, ["m1", "m2", "m3"], "JID1", batch_size=2, failhard=True)
        manager.active_batches.add("JID1")
        salt.utils.batch_state.add_to_active_index("JID1", opts)

        manager._progress_one("JID1", {}, now=1.0)
        manager._progress_one("JID1", {"m1": {"ret": False, "retcode": 1}}, now=2.0)

        manager.output.on_batch_done.assert_called_once()
        final_state = manager.output.on_batch_done.call_args.args[0]
        assert final_state["halted"] is True
        assert final_state["halted_reason"] == "failhard"
        assert "JID1" not in manager.active_batches

    def test_missing_batch_file_retires(self, manager, opts):
        manager.active_batches.add("GONE")
        salt.utils.batch_state.add_to_active_index("GONE", opts)
        manager._progress_one("GONE", {})
        assert "GONE" not in manager.active_batches
        assert salt.utils.batch_state.read_active_index(opts) == set()

    def test_halted_state_is_retired_without_dispatch(self, manager, opts):
        _write_state(
            opts,
            ["m1", "m2"],
            "JID1",
            batch_size=2,
            halted=True,
            halted_reason="stop",
        )
        manager.active_batches.add("JID1")
        salt.utils.batch_state.add_to_active_index("JID1", opts)
        manager._progress_one("JID1", {})
        manager.local.run_job.assert_not_called()
        assert "JID1" not in manager.active_batches


# ---------------------------------------------------------------------------
# _handle_stop — graceful halt from the batch.stop runner
# ---------------------------------------------------------------------------


class TestHandleStop:
    def test_stop_sets_halted_and_fires_event(self, manager, opts):
        _write_state(opts, ["m1", "m2"], "JID1", batch_size=2)
        manager.active_batches.add("JID1")
        salt.utils.batch_state.add_to_active_index("JID1", opts)

        manager._handle_stop("JID1", {"reason": "operator-requested"})

        state = salt.utils.batch_state.read_batch_state("JID1", opts)
        assert state["halted"] is True
        assert state["halted_reason"] == "operator-requested"
        manager.output.on_batch_halted.assert_called_once()
        assert "JID1" not in manager.active_batches

    def test_stop_is_idempotent_on_already_halted(self, manager, opts):
        _write_state(
            opts, ["m1"], "JID1", batch_size=1, halted=True, halted_reason="stop"
        )
        manager.active_batches.add("JID1")
        salt.utils.batch_state.add_to_active_index("JID1", opts)

        manager._handle_stop("JID1", {"reason": "stop"})

        # No new halted event — already halted.
        manager.output.on_batch_halted.assert_not_called()
        assert "JID1" not in manager.active_batches

    def test_stop_default_reason_is_stop(self, manager, opts):
        _write_state(opts, ["m1"], "JID1", batch_size=1)
        manager.active_batches.add("JID1")
        salt.utils.batch_state.add_to_active_index("JID1", opts)
        manager._handle_stop("JID1", {})
        state = salt.utils.batch_state.read_batch_state("JID1", opts)
        assert state["halted_reason"] == "stop"


# ---------------------------------------------------------------------------
# _handle_recover — Maintenance re-adoption path
# ---------------------------------------------------------------------------


class TestHandleRecover:
    def test_recover_readopts_and_ticks(self, manager, opts):
        _write_state(opts, ["m1", "m2"], "JID1", batch_size=2)
        # Manager has no memory of this batch (simulate crash/restart).
        assert "JID1" not in manager.active_batches
        manager._handle_recover("JID1")
        assert "JID1" in manager.active_batches
        # Recover should have kicked a progress pass, dispatching m1/m2.
        manager.local.run_job.assert_called_once()

    def test_recover_on_halted_batch_is_noop(self, manager, opts):
        _write_state(
            opts, ["m1"], "JID1", batch_size=1, halted=True, halted_reason="stop"
        )
        manager._handle_recover("JID1")
        assert "JID1" not in manager.active_batches
        manager.local.run_job.assert_not_called()

    def test_recover_on_cli_driven_batch_is_noop(self, manager, opts):
        _write_state(opts, ["m1"], "JID-CLI", batch_size=1, driver="cli")
        manager._handle_recover("JID-CLI")
        assert "JID-CLI" not in manager.active_batches


# ---------------------------------------------------------------------------
# _tick — housekeeping drives timeout and batch_wait expiry
# ---------------------------------------------------------------------------


class TestTick:
    def test_tick_progresses_every_active_batch(self, manager, opts):
        _write_state(opts, ["m1", "m2"], "JID-A", batch_size=2)
        _write_state(opts, ["x1", "x2"], "JID-B", batch_size=2)
        manager.active_batches.update(["JID-A", "JID-B"])

        manager._tick(now=1.0)

        # Both batches should have received their initial dispatch.
        assert manager.local.run_job.call_count == 2

    def test_tick_adopts_batches_from_index_added_externally(self, manager, opts):
        # Simulates the CLI having added the batch and indexed it while
        # the manager's salt/batch/<jid>/new event handling missed the
        # signal (or the manager was restarting).  The reconciliation
        # step in _tick must close this gap.
        _write_state(opts, ["m1", "m2"], "JID1", batch_size=2)
        salt.utils.batch_state.add_to_active_index("JID1", opts)
        assert "JID1" not in manager.active_batches
        manager._tick(now=1.0)
        assert "JID1" in manager.active_batches
        manager.local.run_job.assert_called_once()

    def test_tick_drives_timeout_detection(self, manager, opts):
        # Two minions dispatched at t=0; tick at t=1000 is way past the
        # timeout + gather_job_timeout window (70s default).
        _write_state(
            opts,
            ["m1", "m2"],
            "JID1",
            batch_size=2,
            active={"m1": 0.0, "m2": 0.0},
            pending=[],
        )
        manager.active_batches.add("JID1")
        salt.utils.batch_state.add_to_active_index("JID1", opts)

        manager._tick(now=1000.0)

        # Both timeouts → batch drains → on_batch_done fires → retired.
        manager.output.on_batch_done.assert_called_once()
        state = manager.output.on_batch_done.call_args.args[0]
        assert set(state["failed"].keys()) == {"m1", "m2"}
        assert state["failed"]["m1"] == "timeout"
        assert "JID1" not in manager.active_batches

    def test_tick_does_not_adopt_cli_driven_batches(self, manager, opts):
        """
        ``_tick`` reconciles the in-memory active set with the
        on-disk index but must never adopt a sync CLI batch
        (``driver="cli"``).  The CLI process owns the state machine
        for those — adopting them would cause the manager to either
        re-publish or false-timeout in-flight minions (issue #69418).
        """
        _write_state(opts, ["m1", "m2"], "JID-CLI", batch_size=1, driver="cli")
        salt.utils.batch_state.add_to_active_index("JID-CLI", opts)

        manager._tick(now=1.0)

        assert "JID-CLI" not in manager.active_batches
        manager.local.run_job.assert_not_called()
        # The index entry is preserved so ``batch.list_active``
        # still sees it.
        assert "JID-CLI" in salt.utils.batch_state.read_active_index(opts)

    def test_tick_prunes_index_entries_with_no_state_file(self, manager, opts):
        """
        Reconcile-time housekeeping: if an active-index entry has
        no readable ``.batch.p`` (e.g. left over from a crashed
        process), drop it.  Maintenance does the same pass on its
        slower cadence; this just lets ``_tick`` close the gap.
        """
        salt.utils.batch_state.add_to_active_index("GHOST", opts)
        manager._tick(now=1.0)
        assert "GHOST" not in salt.utils.batch_state.read_active_index(opts)
        assert "GHOST" not in manager.active_batches


# ---------------------------------------------------------------------------
# _handle_progress / _handle_terminal — sync CLI persistence handoff
# ---------------------------------------------------------------------------


class TestHandleProgressAndTerminal:
    def test_handle_progress_persists_cli_state(self, manager, opts):
        """
        ``salt/batch/<jid>/progress`` from the sync CLI carries the
        full post-tick state in ``data["state"]``.  The manager
        writes it so ``batch.status <jid>`` reflects the latest
        snapshot.
        """
        state = salt.utils.batch_state.create_batch_state(
            {"batch": 1, "fun": "test.ping", "tgt": "*"},
            ["m1", "m2"],
            "JID-CLI",
            driver="cli",
            now=1000.0,
        )
        state["done"] = {"m1": {"ret": True, "retcode": 0}}
        manager._handle_progress("JID-CLI", {"state": state})

        on_disk = salt.utils.batch_state.read_batch_state("JID-CLI", opts)
        assert on_disk is not None
        assert on_disk["done"] == {"m1": {"ret": True, "retcode": 0}}

    def test_handle_progress_ignores_master_driven_state(self, manager, opts):
        """
        Master-driven batches don't fire ``salt/batch/<jid>/progress``
        from outside the manager — guard against a misuse that would
        let an external actor overwrite the manager's own state.
        """
        state = salt.utils.batch_state.create_batch_state(
            {"batch": 1, "fun": "test.ping", "tgt": "*"},
            ["m1"],
            "JID-MGR",
            driver="master",
            now=1000.0,
        )
        manager._handle_progress("JID-MGR", {"state": state})
        # Nothing written.
        assert salt.utils.batch_state.read_batch_state("JID-MGR", opts) is None

    def test_handle_progress_drops_payload_without_state(self, manager):
        # No raise, no write.
        manager._handle_progress("JID-CLI", {})

    def test_handle_terminal_complete_removes_index_entry(self, manager, opts):
        state = salt.utils.batch_state.create_batch_state(
            {"batch": 1, "fun": "test.ping", "tgt": "*"},
            ["m1"],
            "JID-CLI",
            driver="cli",
            now=1000.0,
        )
        salt.utils.batch_state.add_to_active_index("JID-CLI", opts)
        manager._handle_terminal("JID-CLI", {"state": state}, "complete")

        assert "JID-CLI" not in salt.utils.batch_state.read_active_index(opts)
        on_disk = salt.utils.batch_state.read_batch_state("JID-CLI", opts)
        assert on_disk is not None
        assert on_disk["driver"] == "cli"

    def test_handle_terminal_halted_removes_index_entry(self, manager, opts):
        state = salt.utils.batch_state.create_batch_state(
            {"batch": 1, "fun": "test.ping", "tgt": "*"},
            ["m1"],
            "JID-CLI",
            driver="cli",
            now=1000.0,
        )
        state["halted"] = True
        state["halted_reason"] = "stop"
        salt.utils.batch_state.add_to_active_index("JID-CLI", opts)
        manager._handle_terminal("JID-CLI", {"state": state}, "halted")

        assert "JID-CLI" not in salt.utils.batch_state.read_active_index(opts)


# ---------------------------------------------------------------------------
# Event dispatch — sync CLI events route to the right handlers
# ---------------------------------------------------------------------------


class TestSyncCLIEventDispatch:
    def test_batch_progress_dispatches_to_handle_progress(self, manager):
        manager._handle_progress = MagicMock()
        manager._handle_event(
            {
                "tag": "salt/batch/JID1/progress",
                "data": {"state": {"jid": "JID1", "driver": "cli"}},
            }
        )
        manager._handle_progress.assert_called_once_with(
            "JID1", {"state": {"jid": "JID1", "driver": "cli"}}
        )

    def test_batch_complete_dispatches_to_handle_terminal(self, manager):
        manager._handle_terminal = MagicMock()
        manager._handle_event(
            {"tag": "salt/batch/JID1/complete", "data": {"state": {}}}
        )
        manager._handle_terminal.assert_called_once_with(
            "JID1", {"state": {}}, "complete"
        )

    def test_batch_halted_dispatches_to_handle_terminal(self, manager):
        manager._handle_terminal = MagicMock()
        manager._handle_event({"tag": "salt/batch/JID1/halted", "data": {"state": {}}})
        manager._handle_terminal.assert_called_once_with(
            "JID1", {"state": {}}, "halted"
        )
