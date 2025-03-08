"""Test minion configuration option startup_states.

There are four valid values for this option, which are validated by checking the jobs
executed after minion start.
"""

import pytest


@pytest.fixture
def salt_minion_startup_states_empty_string(salt_master, salt_minion_id):
    config_overrides = {
        "startup_states": "",
    }
    factory = salt_master.salt_minion_daemon(
        f"{salt_minion_id}-empty-string",
        overrides=config_overrides,
    )
    with factory.started():
        yield factory


@pytest.fixture
def salt_minion_startup_states_highstate(salt_master, salt_minion_id):
    config_overrides = {
        "startup_states": "highstate",
    }
    factory = salt_master.salt_minion_daemon(
        f"{salt_minion_id}-highstate",
        overrides=config_overrides,
    )
    with factory.started():
        yield factory


@pytest.fixture
def salt_minion_startup_states_sls(salt_master, salt_minion_id):
    config_overrides = {"startup_states": "sls", "sls_list": ["example-sls"]}
    factory = salt_master.salt_minion_daemon(
        f"{salt_minion_id}-sls",
        overrides=config_overrides,
    )
    with factory.started():
        yield factory


@pytest.fixture
def salt_minion_startup_states_top(salt_master, salt_minion_id):
    config_overrides = {"startup_states": "top", "top_file": "example-top.sls"}
    factory = salt_master.salt_minion_daemon(
        f"{salt_minion_id}-top",
        overrides=config_overrides,
    )
    with factory.started():
        yield factory


def test_startup_states_empty_string(
    salt_run_cli, salt_minion_startup_states_empty_string
):
    # Get jobs for this minion
    ret = salt_run_cli.run(
        "jobs.list_jobs", f"search_target={salt_minion_startup_states_empty_string.id}"
    )
    # Check no job was run
    assert len(ret.data.keys()) == 0


def test_startup_states_highstate(salt_run_cli, salt_minion_startup_states_highstate):
    with salt_minion_startup_states_highstate:
        # Get jobs for this minion
        ret = salt_run_cli.run(
            "jobs.list_jobs", f"search_target={salt_minion_startup_states_highstate.id}"
        )
        # Check there is exactly one job
        assert len(ret.data.keys()) == 1
        # Check that job executes state.highstate
        job_ret = next(iter(ret.data.values()))
        assert "Function" in job_ret
        assert job_ret["Function"] == "state.highstate"
        assert "Arguments" in job_ret
        assert job_ret["Arguments"] == []


def test_startup_states_sls(salt_run_cli, salt_minion_startup_states_sls):
    with salt_minion_startup_states_sls:
        # Get jobs for this minion
        ret = salt_run_cli.run(
            "jobs.list_jobs", f"search_target={salt_minion_startup_states_sls.id}"
        )
        # Check there is exactly one job
        assert len(ret.data.keys()) == 1
        # Check that job executes state.sls
        job_ret = next(iter(ret.data.values()))
        assert "Function" in job_ret
        assert job_ret["Function"] == "state.sls"
        assert "Arguments" in job_ret
        assert job_ret["Arguments"] == [["example-sls"]]


def test_startup_states_top(salt_run_cli, salt_minion_startup_states_top):
    with salt_minion_startup_states_top:
        # Get jobs for this minion
        ret = salt_run_cli.run(
            "jobs.list_jobs", f"search_target={salt_minion_startup_states_top.id}"
        )
        # Check there is exactly one job
        assert len(ret.data.keys()) == 1
        # Check that job executes state.top
        job_ret = next(iter(ret.data.values()))
        assert "Function" in job_ret
        assert job_ret["Function"] == "state.top"
        assert "Arguments" in job_ret
        assert job_ret["Arguments"] == ["example-top.sls"]
