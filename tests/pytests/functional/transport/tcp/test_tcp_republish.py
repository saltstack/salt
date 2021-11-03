import os
import shutil
import stat
import time

import pytest
import salt.utils.files
from salt.serializers import yaml
from saltfactories.utils import random_string
from tests.support.runtests import RUNTIME_VARS


@pytest.fixture
def tcp_master_factory(
    salt_factories,
    salt_syndic_master_factory,
    base_env_state_tree_root_dir,
    base_env_pillar_tree_root_dir,
    prod_env_state_tree_root_dir,
    prod_env_pillar_tree_root_dir,
    ext_pillar_file_tree_root_dir,
):
    root_dir = salt_factories.get_root_dir_for_daemon("master")
    conf_dir = root_dir / "conf"
    conf_dir.mkdir(exist_ok=True)

    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "master")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())

    config_defaults["root_dir"] = str(root_dir)
    config_defaults["transport"] = "tcp"
    config_defaults["tcp_publish_retries"] = 600
    config_defaults["tcp_publish_backoff"] = 0.1

    config_overrides = {"log_level_logfile": "quiet"}

    # We need to copy the extension modules into the new master root_dir or
    # it will be prefixed by it
    extension_modules_path = str(root_dir / "extension_modules")
    if not os.path.exists(extension_modules_path):
        shutil.copytree(
            os.path.join(RUNTIME_VARS.FILES, "extension_modules"),
            extension_modules_path,
        )

    # Copy the autosign_file to the new  master root_dir
    autosign_file_path = str(root_dir / "autosign_file")
    shutil.copyfile(
        os.path.join(RUNTIME_VARS.FILES, "autosign_file"), autosign_file_path
    )
    # all read, only owner write
    autosign_file_permissions = (
        stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
    )
    os.chmod(autosign_file_path, autosign_file_permissions)

    config_overrides.update(
        {
            "extension_modules": extension_modules_path,
            "file_roots": {
                "base": [
                    str(base_env_state_tree_root_dir),
                    os.path.join(RUNTIME_VARS.FILES, "file", "base"),
                ],
            },
            "pillar_roots": {
                "base": [
                    str(base_env_pillar_tree_root_dir),
                    os.path.join(RUNTIME_VARS.FILES, "pillar", "base"),
                ],
            },
        }
    )

    factory = salt_syndic_master_factory.salt_master_daemon(
        random_string("tcp-master-"),
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    return factory


@pytest.fixture
def tcp_master(tcp_master_factory):
    """
    A running salt-master fixture
    """
    with tcp_master_factory.started():
        yield tcp_master_factory


@pytest.fixture
def tcp_minion_factory(tcp_master_factory):
    with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.CONF_DIR, "minion")) as rfh:
        config_defaults = yaml.deserialize(rfh.read())
    config_defaults["transport"] = "tcp"

    config_overrides = {
        "log_level_logfile": "quiet",
        "file_roots": tcp_master_factory.config["file_roots"].copy(),
        "pillar_roots": tcp_master_factory.config["pillar_roots"].copy(),
    }

    factory = tcp_master_factory.salt_minion_daemon(
        random_string("tcp-minion-"),
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    return factory


@pytest.fixture
def tcp_minion(tcp_minion_factory):
    """
    A running salt-minion fixture
    """
    with tcp_minion_factory.started():
        # Sync All
        salt_call_cli = tcp_minion_factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.exitcode == 0, ret
        yield tcp_minion_factory


@pytest.fixture
def tcp_run_cli(tcp_master):
    """
    The ``salt-run`` CLI as a fixture against the running master
    """
    assert tcp_master.is_running()
    return tcp_master.salt_run_cli()


@pytest.fixture
def tcp_client(tcp_master):
    assert tcp_master.is_running()
    return tcp_master.salt_client()


@pytest.mark.slow_test
def test_publish_retry_on_inaccessible_minion(tcp_client, tcp_minion, tcp_run_cli):
    """
    Test if minion is able to run job even if it was fired when minion was disconnected at that moment
    """

    # stop minion and run the job
    with tcp_minion.stopped():
        # Note: this is very ugly access of the attr.s-managed client, but the other option is using salt_cli
        #       factory, passing "-L" as minion_tgt and actual minion id as first arg, so ... yeah
        jid = tcp_client._LocalClient__client.cmd_async(
            tcp_minion.id, "test.ping", tgt_type="list"
        )
        assert jid
        assert int(jid)

        time.sleep(1)

        # fetch JID result
        job = tcp_run_cli.run("jobs.print_job", jid)

        assert jid in job.json
        # minion result should not be in, it should be off
        assert tcp_minion.id not in job.json[jid]["Result"]

    # start minion and check few times until the job is finished
    with tcp_minion.started():
        for i in range(1, 60):
            time.sleep(1)
            job = tcp_run_cli.run("jobs.print_job", jid)

            assert jid in job.json

            if tcp_minion.id not in job.json[jid]["Result"]:
                # probably not yet returned
                continue

            assert job.json[jid]["Result"][tcp_minion.id]["return"]

            # all ok
            return

        assert (
            False
        ), "Minion return was not found in job data (minion {}, JID {})".format(
            tcp_minion.id, jid
        )
