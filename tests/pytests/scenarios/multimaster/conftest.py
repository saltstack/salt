import logging
import os
import shutil
import subprocess
import time

import pytest
from pytestshellutils.exceptions import FactoryTimeout

import salt.utils.platform

log = logging.getLogger(__name__)


@pytest.fixture(scope="package")
def salt_mm_master_1(request, salt_factories):
    config_defaults = {
        "open_mode": True,
        "transport": request.config.getoption("--transport"),
    }
    config_overrides = {
        "interface": "127.0.0.1",
    }

    factory = salt_factories.salt_master_daemon(
        "mm-master-1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture(scope="package")
def mm_master_1_salt_cli(salt_mm_master_1):
    return salt_mm_master_1.salt_cli(timeout=120)


@pytest.fixture(scope="package")
def salt_mm_master_2(salt_factories, salt_mm_master_1):
    if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
        subprocess.check_output(["ifconfig", "lo0", "alias", "127.0.0.2", "up"])

    config_defaults = {
        "open_mode": True,
        "transport": salt_mm_master_1.config["transport"],
    }
    config_overrides = {
        "interface": "127.0.0.2",
    }

    # Use the same ports for both masters, they are binding to different interfaces
    for key in (
        "ret_port",
        "publish_port",
    ):
        config_overrides[key] = salt_mm_master_1.config[key]
    factory = salt_factories.salt_master_daemon(
        "mm-master-2",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )

    # The secondary salt master depends on the primarily salt master fixture
    # because we need to clone the keys
    for keyfile in ("master.pem", "master.pub"):
        shutil.copyfile(
            os.path.join(salt_mm_master_1.config["pki_dir"], keyfile),
            os.path.join(factory.config["pki_dir"], keyfile),
        )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture(scope="package")
def mm_master_2_salt_cli(salt_mm_master_2):
    return salt_mm_master_2.salt_cli(timeout=120)


@pytest.fixture(scope="package")
def salt_mm_minion_1(salt_mm_master_1, salt_mm_master_2):
    config_defaults = {
        "transport": salt_mm_master_1.config["transport"],
    }

    mm_master_1_port = salt_mm_master_1.config["ret_port"]
    mm_master_1_addr = salt_mm_master_1.config["interface"]
    mm_master_2_port = salt_mm_master_2.config["ret_port"]
    mm_master_2_addr = salt_mm_master_2.config["interface"]
    config_overrides = {
        "master": [
            f"{mm_master_1_addr}:{mm_master_1_port}",
            f"{mm_master_2_addr}:{mm_master_2_port}",
        ],
        "test.foo": "baz",
    }
    factory = salt_mm_master_1.salt_minion_daemon(
        "mm-minion-1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture(scope="package")
def salt_mm_minion_2(salt_mm_master_1, salt_mm_master_2):
    config_defaults = {
        "transport": salt_mm_master_1.config["transport"],
    }

    mm_master_1_port = salt_mm_master_1.config["ret_port"]
    mm_master_1_addr = salt_mm_master_1.config["interface"]
    mm_master_2_port = salt_mm_master_2.config["ret_port"]
    mm_master_2_addr = salt_mm_master_2.config["interface"]
    config_overrides = {
        "master": [
            f"{mm_master_1_addr}:{mm_master_1_port}",
            f"{mm_master_2_addr}:{mm_master_2_port}",
        ],
        "test.foo": "baz",
    }
    factory = salt_mm_master_2.salt_minion_daemon(
        "mm-minion-2",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture(scope="package")
def run_salt_cmds():
    def _run_salt_cmds_fn(clis, minions):
        """
        Run test.ping from all clis to all minions
        """
        returned_minions = []
        minion_instances = {minion.id: minion for minion in minions}
        clis_to_check = {minion.id: list(clis) for minion in minions}

        attempts = 6
        timeout = 5
        if salt.utils.platform.spawning_platform():
            timeout *= 2
        while attempts:
            if not clis_to_check:
                break
            for minion in list(clis_to_check):
                if not clis_to_check[minion]:
                    clis_to_check.pop(minion)
                    continue
                for cli in list(clis_to_check[minion]):
                    try:
                        ret = cli.run(
                            f"--timeout={timeout}",
                            "test.ping",
                            minion_tgt=minion,
                            _timeout=2 * timeout,
                        )
                        if ret.returncode == 0 and ret.data is True:
                            returned_minions.append((cli, minion_instances[minion]))
                            clis_to_check[minion].remove(cli)
                    except FactoryTimeout:
                        log.debug(
                            "Failed to execute test.ping from %s to %s.",
                            cli.get_display_name(),
                            minion,
                        )
            time.sleep(1)
            attempts -= 1

        return returned_minions

    return _run_salt_cmds_fn


@pytest.fixture(autouse=True)
def ensure_connections(
    salt_mm_minion_1,
    salt_mm_minion_2,
    mm_master_1_salt_cli,
    mm_master_2_salt_cli,
    run_salt_cmds,
):
    # define the function
    def _ensure_connections_fn(clis, minions):
        retries = 3
        while retries:
            returned = run_salt_cmds(clis, minions)
            if len(returned) == len(clis) * len(minions):
                break
            time.sleep(10)
            retries -= 1
        else:
            pytest.fail("Could not ensure the connections were okay.")

    # run the function to ensure initial connections
    _ensure_connections_fn(
        [mm_master_1_salt_cli, mm_master_2_salt_cli],
        [salt_mm_minion_1, salt_mm_minion_2],
    )

    # Give this function back for further use in test fn bodies
    return _ensure_connections_fn
