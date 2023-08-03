import os
import time
import shutil
from pathlib import Path

import pytest
from saltfactories.utils import random_string


@pytest.fixture(scope="module")
def module_master(salt_master_factory):
    yield salt_master_factory


@pytest.fixture(scope="module")
def master_minion(module_master):
    config_overrides = {
        "root_dir": f"/tmp/stsuite/{module_master.id}",
        "return_retry_timer_max": 0,
        "return_retry_timer": 5,
        "return_retry_tries": 30,
    }
    factory = module_master.salt_minion_daemon(
        module_master.id,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, module_master, factory.id
    )

    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def second_minion(module_master, salt_minion_id):
    config_overrides = {
        "return_retry_timer_max": 0,
        "return_retry_timer": 5,
        "return_retry_tries": 30,
    }
    factory = module_master.salt_minion_daemon(
        salt_minion_id,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, module_master, factory.id
    )

    with factory.started():
        yield factory


def test_list_minions(event_listener, salt_master, master_minion, second_minion, salt_cli, salt_run_cli, salt_key_cli):
    master_dir = Path(f"/tmp/stsuite/{salt_master.id}")
    shutil.copy(master_dir / "pki" / "minion.pub", master_dir / "pki" / "minions" / f"{salt_master.id}")
    with master_minion.started():
        rtn = salt_cli.run("minion.list", minion_tgt=salt_master.id)
        assert "minions" in rtn.data
        assert "minions_pre" in rtn.data
        assert "minions_rejected" in rtn.data
        assert "minions_denied" in rtn.data
        assert salt_master.id in rtn.data["minions"]

        salt_cli.run("minion.restart", minion_tgt=second_minion.id, timeout=1)

        start_pattern = "salt/minion/flay/start"
        event_pattern = (second_minion.id, start_pattern)
        matched_events = event_listener.wait_for_events(
            [event_pattern], after_time=time.time(), timeout=30
        )
        assert start_pattern in list(matched_events.missed)[0]

        rst = salt_cli.run("test.ping", minion_tgt=second_minion.id)
        assert rst.data is True
