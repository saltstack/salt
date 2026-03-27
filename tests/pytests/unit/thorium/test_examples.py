"""
Unit tests for Thorium documentation examples.
"""

import json

import pytest

import salt.thorium.calc as thorium_calc
import salt.thorium.check as thorium_check
import salt.thorium.file as thorium_file
import salt.thorium.key as thorium_key
import salt.thorium.local as thorium_local
import salt.thorium.reg as thorium_reg
import salt.thorium.runner as thorium_runner
import salt.thorium.status as thorium_status
import salt.thorium.timer as thorium_timer
import salt.thorium.wheel as thorium_wheel
from tests.support.mock import MagicMock, patch


@pytest.fixture
def thorium_env(master_opts, tmp_path):
    opts = master_opts.copy()
    opts["cachedir"] = str(tmp_path / "cache")
    return {"reg": {}, "context": {}, "events": [], "opts": opts}


def test_reg_set_and_check_contains_example(thorium_env):
    """
    The basic reg.set + check.contains example should succeed once the event is seen.
    """
    event = {"tag": "my/custom/event", "data": {"bar": "somedata"}}
    with patch.object(thorium_reg, "__reg__", thorium_env["reg"], create=True), patch.object(
        thorium_reg, "__events__", [event], create=True
    ), patch.object(thorium_check, "__reg__", thorium_env["reg"], create=True):
        thorium_reg.set_("foo", add="bar", match="my/custom/event")
        ret = thorium_check.contains("foo", "somedata")

    assert ret["result"] is True
    assert thorium_env["reg"]["foo"]["val"] == {"somedata"}


def test_threshold_example_uses_register_length_gate(thorium_env):
    """
    The deployment failure example should fire once enough events were collected.
    """
    events = [
        {
            "tag": "acme/deploy/failed",
            "data": {"id": "minion-1", "reason": "timeout", "_stamp": "2026-03-27"},
        },
        {
            "tag": "acme/deploy/failed",
            "data": {"id": "minion-2", "reason": "timeout", "_stamp": "2026-03-27"},
        },
        {
            "tag": "acme/deploy/failed",
            "data": {"id": "minion-3", "reason": "timeout", "_stamp": "2026-03-27"},
        },
    ]
    with patch.object(thorium_reg, "__reg__", thorium_env["reg"], create=True), patch.object(
        thorium_reg, "__events__", events, create=True
    ), patch.object(thorium_check, "__reg__", thorium_env["reg"], create=True):
        thorium_reg.list_(
            "deploy_failures",
            add=["id", "reason"],
            match="acme/deploy/failed",
            stamp=True,
            prune=10,
        )

        ret = thorium_check.len_gte("deploy_failures", 3)

    assert ret["result"] is True
    assert len(thorium_env["reg"]["deploy_failures"]["val"]) == 3
    assert thorium_env["reg"]["deploy_failures"]["val"][0]["id"] == "minion-1"


def test_calc_mean_example_computes_threshold_on_recent_samples(thorium_env):
    """
    The rolling-average example should compute the expected mean and pass the gate.
    """
    thorium_env["reg"]["load_samples"] = {
        "val": [{"load": 1}, {"load": 3}, {"load": 5}, {"load": 7}, {"load": 9}]
    }
    with patch.object(thorium_calc, "__reg__", thorium_env["reg"], create=True):
        ret = thorium_calc.mean("load_samples", num=5, ref="load", minimum=4)

    assert ret["result"] is True
    assert ret["changes"]["Operator"] == "mean"
    assert ret["changes"]["Number of values"] == 5
    assert ret["changes"]["Answer"] == 5


def test_timer_hold_example_creates_a_cooldown_gate(thorium_env):
    """
    The cooldown example should stay false until enough time has elapsed.
    """
    with patch.object(thorium_timer, "__context__", thorium_env["context"], create=True), patch(
        "salt.thorium.timer.time.time", side_effect=[100, 1001]
    ):
        first = thorium_timer.hold("cooldown", 900)
        second = thorium_timer.hold("cooldown", 900)

    assert first["result"] is False
    assert second["result"] is True


def test_status_and_key_timeout_example_rejects_stale_keys(thorium_env):
    """
    The status + key.timeout example should reject a minion once its status is stale.
    """
    event = {
        "tag": "salt/beacon/minion-1/status/update",
        "data": {
            "id": "minion-1",
            "data": {"loadavg": [0.1, 0.2, 0.3], "cpupercent": [1, 2, 3]},
        },
    }
    with patch.object(thorium_status, "__reg__", thorium_env["reg"], create=True), patch.object(
        thorium_status, "__events__", [event], create=True
    ), patch("salt.thorium.status.time.time", return_value=1000):
        thorium_status.reg("status_register")

    fake_keyapi = MagicMock()
    fake_keyapi.list_status.return_value = {"minions": ["minion-1"]}
    with patch.object(thorium_key, "__reg__", thorium_env["reg"], create=True), patch.object(
        thorium_key, "__context__", thorium_env["context"], create=True
    ), patch.object(thorium_key, "__opts__", thorium_env["opts"], create=True), patch.object(
        thorium_key, "_get_key_api", return_value=fake_keyapi
    ), patch("salt.thorium.key.time.time", return_value=1401):
        ret = thorium_key.timeout("reject_stale_keys", reject=300)

    assert ret["result"] is True
    fake_keyapi.reject.assert_called_once_with("minion-1")
    assert "minion-1" not in thorium_env["reg"]["status"]["val"]


def test_file_save_filter_example_writes_json_safe_register_snapshot(tmp_path, thorium_env):
    """
    The register snapshot example should serialize filtered register data to disk.
    """
    target = tmp_path / "tracked_ids.json"
    thorium_env["reg"]["tracked_ids"] = {"val": {"minion-1", "minion-2"}}

    with patch.object(thorium_file, "__reg__", thorium_env["reg"], create=True), patch.object(
        thorium_file, "__opts__", thorium_env["opts"], create=True
    ):
        ret = thorium_file.save(str(target), filter=True)

    assert ret["result"] is True
    assert target.exists()
    payload = json.loads(target.read_text())
    assert isinstance(payload["tracked_ids"]["val"], str)
    assert "minion-1" in payload["tracked_ids"]["val"]
    assert "minion-2" in payload["tracked_ids"]["val"]


def test_local_cmd_example_queues_a_minion_execution(thorium_env):
    """
    The local.cmd wrapper example should queue the requested execution call.
    """
    client = MagicMock()
    client.cmd_async.return_value = "20260327120000000000"
    client_cm = MagicMock()
    client_cm.__enter__.return_value = client
    client_cm.__exit__.return_value = False

    with patch.object(thorium_local, "__opts__", thorium_env["opts"], create=True), patch(
        "salt.client.get_local_client", return_value=client_cm
    ):
        ret = thorium_local.cmd(
            "gated_restart",
            tgt="G@roles:web",
            tgt_type="compound",
            func="service.restart",
            arg=("nginx",),
        )

    assert ret["result"] is True
    assert ret["changes"]["jid"] == "20260327120000000000"
    client.cmd_async.assert_called_once()
    assert client.cmd_async.call_args.args == (
        "G@roles:web",
        "service.restart",
        ("nginx",),
    )
    assert client.cmd_async.call_args.kwargs["tgt_type"] == "compound"
    assert client.cmd_async.call_args.kwargs["kwarg"] is None
    assert client.cmd_async.call_args.kwargs["ret"]["name"] == "gated_restart"
    assert client.cmd_async.call_args.kwargs["ret"]["changes"]["jid"] == (
        "20260327120000000000"
    )


def test_runner_cmd_example_forwards_kwargs_to_async_runner(thorium_env):
    """
    The runner.cmd example should pass kwargs through to the runner invocation.
    """
    runner_instance = MagicMock()

    with patch.object(thorium_runner, "__opts__", thorium_env["opts"], create=True), patch(
        "salt.runner.Runner", return_value=runner_instance
    ) as runner_cls:
        ret = thorium_runner.cmd(
            "orchestrate_remediation",
            func="state.orchestrate",
            mods="orch.remediate",
            pillar={"target": "db01"},
        )

    assert ret["result"] is True
    runner_cls.assert_called_once()
    runner_opts = runner_cls.call_args.args[0]
    assert runner_opts["async"] is True
    assert runner_opts["fun"] == "state.orchestrate"
    assert runner_opts["arg"] == ()
    assert runner_opts["kwarg"] == {
        "mods": "orch.remediate",
        "pillar": {"target": "db01"},
    }
    runner_instance.run.assert_called_once()


def test_wheel_cmd_example_queues_master_side_wheel_action(thorium_env):
    """
    The wheel.cmd example should queue the expected wheel low data.
    """
    wheel_client = MagicMock()

    with patch.object(thorium_wheel, "__opts__", thorium_env["opts"], create=True), patch(
        "salt.wheel.WheelClient", return_value=wheel_client
    ):
        ret = thorium_wheel.cmd(
            "reject_stale_key", fun="key.reject", match="old-minion"
        )

    assert ret["result"] is True
    wheel_client.cmd_async.assert_called_once_with(
        {"fun": "key.reject", "arg": (), "kwargs": {"match": "old-minion"}}
    )
