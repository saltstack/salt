"""
Unit tests for :mod:`salt.runners.batch`.

The runner depends on ``__opts__`` being injected by the loader.  We
don't go through the loader in unit tests; instead we set the module
global directly on the imported module.
"""

import pytest

import salt.runners.batch as batch_runner
import salt.utils.batch_state
from tests.support.mock import MagicMock, patch


@pytest.fixture
def opts(tmp_path):
    return {
        "cachedir": str(tmp_path),
        "hash_type": "sha256",
        "sock_dir": str(tmp_path),
        "conf_file": str(tmp_path / "master"),
    }


@pytest.fixture(autouse=True)
def inject_opts(opts, monkeypatch):
    """Emulate the loader's ``__opts__`` injection."""
    monkeypatch.setattr(batch_runner, "__opts__", opts, raising=False)


def _write_state(opts, **overrides):
    state = salt.utils.batch_state.create_batch_state(
        {"batch": 2, "fun": "test.ping", "tgt": "*"},
        overrides.pop("minions", ["m1", "m2", "m3"]),
        overrides.pop("jid", "JID1"),
        driver=overrides.pop("driver", "master"),
        now=1000.0,
    )
    state.update(overrides)
    salt.utils.batch_state.write_batch_state(state["jid"], state, opts)
    return state


class TestStatus:
    def test_returns_summary_for_existing_batch(self, opts):
        _write_state(opts, jid="JID1", minions=["m1", "m2"])
        summary = batch_runner.status("JID1")
        assert summary is not None
        assert summary["jid"] == "JID1"
        assert summary["total"] == 2
        assert summary["completed"] == 0
        assert summary["pending"] == 2
        assert summary["halted"] is False
        assert summary["driver"] == "master"

    def test_returns_none_for_missing_jid(self):
        assert batch_runner.status("NOPE") is None


class TestListActive:
    def test_lists_indexed_batches(self, opts):
        _write_state(opts, jid="JID-A", minions=["m1"])
        _write_state(opts, jid="JID-B", minions=["m1", "m2"])
        salt.utils.batch_state.add_to_active_index("JID-A", opts)
        salt.utils.batch_state.add_to_active_index("JID-B", opts)
        active = batch_runner.list_active()
        assert [b["jid"] for b in active] == ["JID-A", "JID-B"]

    def test_drops_index_entries_missing_batch_file(self, opts):
        _write_state(opts, jid="JID-A", minions=["m1"])
        salt.utils.batch_state.add_to_active_index("JID-A", opts)
        salt.utils.batch_state.add_to_active_index("JID-GHOST", opts)
        active = batch_runner.list_active()
        assert [b["jid"] for b in active] == ["JID-A"]

    def test_empty_index_returns_empty_list(self):
        assert batch_runner.list_active() == []


class TestStopGraceful:
    def test_fires_stop_event(self, opts):
        _write_state(opts, jid="JID1", minions=["m1", "m2"])
        fake_event = MagicMock()
        fake_event.__enter__.return_value = fake_event
        fake_event.__exit__.return_value = False
        with patch(
            "salt.runners.batch.salt.utils.event.get_master_event",
            return_value=fake_event,
        ):
            assert batch_runner.stop("JID1") is True
        fake_event.fire_event.assert_called_once()
        data, tag = fake_event.fire_event.call_args.args
        assert tag == "salt/batch/JID1/stop"
        assert data["reason"] == "stop"

    def test_returns_false_for_missing_jid(self):
        with patch("salt.runners.batch.salt.utils.event.get_master_event") as get_event:
            assert batch_runner.stop("NOPE") is False
        get_event.assert_not_called()

    def test_returns_false_for_already_halted(self, opts):
        _write_state(
            opts, jid="JID1", minions=["m1"], halted=True, halted_reason="stop"
        )
        with patch("salt.runners.batch.salt.utils.event.get_master_event") as get_event:
            assert batch_runner.stop("JID1") is False
        get_event.assert_not_called()


class TestStopKill:
    def test_kill_publishes_saltutil_kill_job(self, opts):
        _write_state(
            opts,
            jid="JID1",
            minions=["m1", "m2", "m3"],
            active={"m1": 1.0, "m2": 1.0},
            pending=["m3"],
        )
        fake_local = MagicMock()
        fake_local.__enter__.return_value = fake_local
        fake_local.__exit__.return_value = False
        fake_event = MagicMock()
        fake_event.__enter__.return_value = fake_event
        fake_event.__exit__.return_value = False

        with patch(
            "salt.runners.batch.salt.client.get_local_client",
            return_value=fake_local,
        ), patch(
            "salt.runners.batch.salt.utils.event.get_master_event",
            return_value=fake_event,
        ):
            assert batch_runner.stop("JID1", kill=True) is True

        fake_local.cmd_async.assert_called_once()
        call_args = fake_local.cmd_async.call_args
        assert sorted(call_args.args[0]) == ["m1", "m2"]
        assert call_args.args[1] == "saltutil.kill_job"
        assert call_args.kwargs["arg"] == ["JID1"]
        assert call_args.kwargs["tgt_type"] == "list"
        # The halt event must still be fired.
        fake_event.fire_event.assert_called_once()

    def test_kill_with_no_active_skips_publish(self, opts):
        _write_state(opts, jid="JID1", minions=["m1"], active={}, pending=["m1"])
        fake_local = MagicMock()
        fake_local.__enter__.return_value = fake_local
        fake_local.__exit__.return_value = False
        fake_event = MagicMock()
        fake_event.__enter__.return_value = fake_event
        fake_event.__exit__.return_value = False

        with patch(
            "salt.runners.batch.salt.client.get_local_client",
            return_value=fake_local,
        ), patch(
            "salt.runners.batch.salt.utils.event.get_master_event",
            return_value=fake_event,
        ):
            assert batch_runner.stop("JID1", kill=True) is True

        fake_local.cmd_async.assert_not_called()
        fake_event.fire_event.assert_called_once()
