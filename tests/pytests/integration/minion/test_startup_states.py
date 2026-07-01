"""Test minion configuration option startup_states.

There are four valid values for this option, which are validated by checking the jobs
executed after minion start.
"""

import time

import pytest

from tests.conftest import FIPS_TESTRUN


def _fips_overrides():
    return {
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": ("PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"),
    }


@pytest.fixture
def salt_minion_startup_states_empty_string(salt_master, salt_minion_id):
    config_overrides = {
        "startup_states": "",
        **_fips_overrides(),
    }
    factory = salt_master.salt_minion_daemon(
        f"{salt_minion_id}-empty-string",
        overrides=config_overrides,
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, factory.id
    )
    with factory.started():
        time.sleep(10)
        yield factory


@pytest.fixture
def salt_minion_startup_states_highstate(salt_master, salt_minion_id):
    config_overrides = {
        "startup_states": "highstate",
        **_fips_overrides(),
    }
    factory = salt_master.salt_minion_daemon(
        f"{salt_minion_id}-highstate",
        overrides=config_overrides,
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, factory.id
    )
    with factory.started():
        time.sleep(10)
        yield factory


@pytest.fixture
def salt_minion_startup_states_sls(salt_master, salt_minion_id):
    config_overrides = {
        "startup_states": "sls",
        "sls_list": ["example-sls"],
        **_fips_overrides(),
    }
    factory = salt_master.salt_minion_daemon(
        f"{salt_minion_id}-sls",
        overrides=config_overrides,
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, factory.id
    )
    with factory.started():
        time.sleep(10)
        yield factory


@pytest.fixture
def salt_minion_startup_states_top(salt_master, salt_minion_id):
    config_overrides = {
        "startup_states": "top",
        "top_file": "example-top.sls",
        **_fips_overrides(),
    }
    factory = salt_master.salt_minion_daemon(
        f"{salt_minion_id}-top",
        overrides=config_overrides,
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, factory.id
    )
    with factory.started():
        time.sleep(10)
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
    # Minion is already running inside the fixture's ``with factory.started()``.
    # A second ``with factory`` here can stop/restart the daemon and race
    # ``jobs.list_jobs``, yielding an empty cache.
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
