import os
import time

import pytest
import salt.utils.files
import salt.utils.platform
from salt.serializers import yaml
from tests.support.helpers import get_virtualenv_binary_path, slowTest
from tests.support.runtests import RUNTIME_VARS


@pytest.fixture(scope="function")
def salt_minion_retry(salt_master_factory, salt_minion_id):
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "minion")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())
    config_defaults["hosts.file"] = os.path.join(RUNTIME_VARS.TMP, "hosts")
    config_defaults["aliases.file"] = os.path.join(RUNTIME_VARS.TMP, "aliases")
    config_defaults["transport"] = salt_master_factory.config["transport"]

    config_overrides = {
        "file_roots": salt_master_factory.config["file_roots"].copy(),
        "pillar_roots": salt_master_factory.config["pillar_roots"].copy(),
    }

    virtualenv_binary = get_virtualenv_binary_path()
    if virtualenv_binary:
        config_overrides["venv_bin"] = virtualenv_binary

    # override the defaults for this test
    config_overrides["return_retry_timer_max"] = 0
    config_overrides["return_retry_timer"] = 60

    factory = salt_master_factory.get_salt_minion_daemon(
        salt_minion_id,
        config_defaults=config_defaults,
        config_overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    factory.register_after_terminate_callback(
        pytest.helpers.remove_stale_minion_key, salt_master_factory, factory.id
    )

    with factory.started():
        yield factory


@slowTest
def test_publish_retry(salt_master, salt_minion_retry, salt_cli, salt_run_cli):
    # run job that takes some time for warmup
    rtn = salt_cli.run("test.sleep", "5", "--async", minion_tgt=salt_minion_retry.id)
    # obtain JID
    jid = rtn.stdout.strip().split(" ")[-1]

    # stop the salt master for some time
    with salt_master.stopped():
        # verify we don't yet have the result and sleep
        assert salt_run_cli.run("jobs.lookup_jid", jid, _timeout=60).json == {}
        time.sleep(70)

    data = None
    for i in range(1, 30):
        time.sleep(10)
        data = salt_run_cli.run("jobs.lookup_jid", jid, _timeout=60).json
        if data:
            break

    assert salt_minion_retry.id in data
    assert data[salt_minion_retry.id] is True
