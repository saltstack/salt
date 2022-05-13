import time

import pytest
from saltfactories.utils import random_string


@pytest.fixture(scope="function")
def salt_minion_retry(salt_master_factory, salt_minion_id):
    # override the defaults for this test
    config_overrides = {
        "return_retry_timer_max": 0,
        "return_retry_timer": 5,
        "return_retry_tries": 30,
    }
    factory = salt_master_factory.salt_minion_daemon(
        random_string("retry-minion-"),
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master_factory, factory.id
    )

    with factory.started():
        yield factory


@pytest.mark.slow_test
def test_publish_retry(salt_master, salt_minion_retry, salt_cli, salt_run_cli):
    # run job that takes some time for warmup
    rtn = salt_cli.run("test.sleep", "5", "--async", minion_tgt=salt_minion_retry.id)
    # obtain JID
    jid = rtn.stdout.strip().split(" ")[-1]

    # stop the salt master for some time
    with salt_master.stopped():
        # verify we don't yet have the result and sleep
        assert salt_run_cli.run("jobs.lookup_jid", jid, _timeout=60).json == {}

        # the 70s sleep (and 60s timer value) is to reduce flakiness due to slower test runs
        # and should be addresses when number of tries is configurable through minion opts
        time.sleep(5)

    data = None
    for i in range(1, 30):
        time.sleep(1)
        data = salt_run_cli.run("jobs.lookup_jid", jid, _timeout=60).json
        if data:
            break

    assert salt_minion_retry.id in data
    assert data[salt_minion_retry.id] is True
