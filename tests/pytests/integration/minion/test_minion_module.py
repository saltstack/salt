import shutil
import time
from pathlib import Path

import pytest
from saltfactories.utils import random_string


@pytest.fixture(scope="module")
def master_minion(salt_master):
    config_overrides = {
        "root_dir": salt_master.config["root_dir"],
        "return_retry_timer_max": 0,
        "return_retry_timer": 5,
        "return_retry_tries": 30,
    }
    factory = salt_master.salt_minion_daemon(
        salt_master.id,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, factory.id
    )

    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def second_minion(salt_master):
    config_overrides = {
        "return_retry_timer_max": 0,
        "return_retry_timer": 5,
        "return_retry_tries": 30,
    }
    factory = salt_master.salt_minion_daemon(
        random_string("2nd-minion-"),
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, factory.id
    )

    with factory.started():
        yield factory


@pytest.mark.slow_test
def test_minions(
    event_listener,
    salt_master,
    master_minion,
    second_minion,
    salt_cli,
    salt_run_cli,
    salt_key_cli,
):
    master_pki_dir = Path(salt_master.config["pki_dir"])
    shutil.copy(
        master_pki_dir / "minion.pub",
        master_pki_dir / "minions" / f"{salt_master.id}",
    )
    master_minion.start()

    rtn = salt_cli.run("minion.list", minion_tgt=salt_master.id)
    assert "minions" in rtn.data
    assert "minions_pre" in rtn.data
    assert "minions_rejected" in rtn.data
    assert "minions_denied" in rtn.data
    assert salt_master.id in rtn.data["minions"]

    salt_cli.run("minion.restart", minion_tgt=second_minion.id, timeout=1)

    start_pattern = f"salt/minion/{second_minion.id}/start"
    event_pattern = (second_minion.id, start_pattern)
    matched_events = event_listener.wait_for_events(
        [event_pattern], after_time=time.time(), timeout=30
    )
    assert start_pattern in list(matched_events.missed)[0]

    rst = salt_cli.run("test.ping", minion_tgt=second_minion.id)
    assert rst.data is True

    salt_cli.run("minion.kill", minion_tgt=second_minion.id, timeout=1)
    rst = salt_cli.run("test.ping", minion_tgt=second_minion.id)
    assert "Minion did not return" in rst.data
