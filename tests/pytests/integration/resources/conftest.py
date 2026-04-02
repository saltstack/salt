"""
Integration test fixtures for Salt Resources.

Spins up a master and a minion configured with two dummy resources
(dummy-01, dummy-02).  All tests in this package run against these
two daemons.
"""

import time

import pytest

from tests.conftest import FIPS_TESTRUN

# Dummy resource IDs that the minion manages in every test in this package.
DUMMY_RESOURCES = ["dummy-01", "dummy-02"]


@pytest.fixture(scope="package")
def salt_master(request, salt_factories):
    config_overrides = {
        "interface": "127.0.0.1",
        "transport": request.config.getoption("--transport"),
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        "resources-master",
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture(scope="package")
def salt_minion(salt_master):
    config_overrides = {
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        # Configure dummy resources so the minion dispatches resource jobs.
        "resources": {"dummy": DUMMY_RESOURCES},
        # Use threads (not processes) — this is the path our Race 1/Race 2 fixes
        # target and the most common deployment mode for resource-managing minions.
        "multiprocessing": False,
    }
    factory = salt_master.salt_minion_daemon(
        "resources-minion",
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, factory.id
    )
    with factory.started(start_timeout=120):
        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
        # The minion fires _register_resources_with_master() as a background
        # task on connect.  Waiting briefly ensures the master cache is
        # populated before tests run (typically completes in < 1 s, but the
        # sync_all above already takes several seconds so this is a safety net).
        time.sleep(3)
        yield factory


@pytest.fixture(scope="package")
def salt_cli(salt_master):
    assert salt_master.is_running()
    return salt_master.salt_cli(timeout=60)


@pytest.fixture(scope="package")
def salt_call_cli(salt_minion):
    assert salt_minion.is_running()
    return salt_minion.salt_call_cli(timeout=60)
