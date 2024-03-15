import logging
import os
import shutil
import subprocess
import time

import pytest
from pytestshellutils.exceptions import FactoryNotStarted, FactoryTimeout

import salt.utils.platform

log = logging.getLogger(__name__)


@pytest.fixture(scope="package")
def salt_mm_failover_master_1(request, salt_factories):
    config_defaults = {
        "open_mode": True,
        "transport": request.config.getoption("--transport"),
    }
    config_overrides = {
        "interface": "127.0.0.1",
        "master_sign_pubkey": True,
    }
    factory = salt_factories.salt_master_daemon(
        "mm-failover-master-1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=180):
        yield factory


@pytest.fixture(scope="package")
def mm_failover_master_1_salt_cli(salt_mm_failover_master_1):
    return salt_mm_failover_master_1.salt_cli(timeout=180)


@pytest.fixture(scope="package")
def salt_mm_failover_master_2(salt_factories, salt_mm_failover_master_1):
    if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
        subprocess.check_output(["ifconfig", "lo0", "alias", "127.0.0.2", "up"])

    config_defaults = {
        "open_mode": True,
        "transport": salt_mm_failover_master_1.config["transport"],
    }
    config_overrides = {
        "interface": "127.0.0.2",
        "master_sign_pubkey": True,
    }

    # Use the same ports for both masters, they are binding to different interfaces
    for key in (
        "ret_port",
        "publish_port",
    ):
        config_overrides[key] = salt_mm_failover_master_1.config[key]
    factory = salt_factories.salt_master_daemon(
        "mm-failover-master-2",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )

    # Both masters will share the same signing key pair
    for keyfile in ("master_sign.pem", "master_sign.pub"):
        shutil.copyfile(
            os.path.join(salt_mm_failover_master_1.config["pki_dir"], keyfile),
            os.path.join(factory.config["pki_dir"], keyfile),
        )
    with factory.started(start_timeout=180):
        yield factory


@pytest.fixture(scope="package")
def mm_failover_master_2_salt_cli(salt_mm_failover_master_2):
    return salt_mm_failover_master_2.salt_cli(timeout=180)


@pytest.fixture(scope="package")
def salt_mm_failover_minion_1(salt_mm_failover_master_1, salt_mm_failover_master_2):
    config_defaults = {
        "transport": salt_mm_failover_master_1.config["transport"],
    }

    mm_master_1_port = salt_mm_failover_master_1.config["ret_port"]
    mm_master_1_addr = salt_mm_failover_master_1.config["interface"]
    mm_master_2_port = salt_mm_failover_master_2.config["ret_port"]
    mm_master_2_addr = salt_mm_failover_master_2.config["interface"]
    config_overrides = {
        "master": [
            f"{mm_master_1_addr}:{mm_master_1_port}",
            f"{mm_master_2_addr}:{mm_master_2_port}",
        ],
        "publish_port": salt_mm_failover_master_1.config["publish_port"],
        "master_type": "failover",
        "master_alive_interval": 5,
        "master_tries": -1,
        "verify_master_pubkey_sign": True,
        "retry_dns": 1,
    }
    factory = salt_mm_failover_master_1.salt_minion_daemon(
        "mm-failover-minion-1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    # Need to grab the public signing key from the master, either will do
    shutil.copyfile(
        os.path.join(salt_mm_failover_master_1.config["pki_dir"], "master_sign.pub"),
        os.path.join(factory.config["pki_dir"], "master_sign.pub"),
    )
    with factory.started(start_timeout=180):
        yield factory


@pytest.fixture(scope="package")
def salt_mm_failover_minion_2(salt_mm_failover_master_1, salt_mm_failover_master_2):
    config_defaults = {
        "transport": salt_mm_failover_master_1.config["transport"],
    }

    mm_master_1_port = salt_mm_failover_master_1.config["ret_port"]
    mm_master_1_addr = salt_mm_failover_master_1.config["interface"]
    mm_master_2_port = salt_mm_failover_master_2.config["ret_port"]
    mm_master_2_addr = salt_mm_failover_master_2.config["interface"]
    # We put the second master first in the list so it has the right startup checks every time.
    config_overrides = {
        "master": [
            f"{mm_master_2_addr}:{mm_master_2_port}",
            f"{mm_master_1_addr}:{mm_master_1_port}",
        ],
        "publish_port": salt_mm_failover_master_1.config["publish_port"],
        "master_type": "failover",
        "master_alive_interval": 5,
        "master_tries": -1,
        "verify_master_pubkey_sign": True,
        "retry_dns": 1,
    }
    factory = salt_mm_failover_master_2.salt_minion_daemon(
        "mm-failover-minion-2",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    # Need to grab the public signing key from the master, either will do
    shutil.copyfile(
        os.path.join(salt_mm_failover_master_1.config["pki_dir"], "master_sign.pub"),
        os.path.join(factory.config["pki_dir"], "master_sign.pub"),
    )
    with factory.started(start_timeout=180):
        yield factory


@pytest.fixture(scope="package")
def run_salt_cmds():
    def _run_salt_cmds_fn(clis, minions):
        """
        Run test.ping from all clis to all minions
        """
        returned_minions = []
        minions_to_check = {minion.id: minion for minion in minions}

        attempts = 6
        timeout = 5
        if salt.utils.platform.spawning_platform():
            timeout *= 2
        while attempts:
            if not minions_to_check:
                break
            for cli in clis:
                for minion in list(minions_to_check):
                    try:
                        ret = cli.run(
                            f"--timeout={timeout}",
                            "test.ping",
                            minion_tgt=minion,
                        )
                        if ret.returncode == 0 and ret.data is True:
                            returned_minions.append((cli, minions_to_check[minion]))
                            minions_to_check.pop(minion)
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
    salt_mm_failover_master_1,
    salt_mm_failover_master_2,
    mm_failover_master_1_salt_cli,
    mm_failover_master_2_salt_cli,
    salt_mm_failover_minion_1,
    salt_mm_failover_minion_2,
    run_salt_cmds,
):
    """
    This will make sure that the minions are connected to their original masters.

    At the beginning of each test in this package, you can assume...
        - minion-1 and master-1 are connected
        - minion-2 and master-2 are connected
    """

    def _ensure_connections_fn(
        salt_mm_failover_master_1,
        salt_mm_failover_master_2,
        mm_failover_master_1_salt_cli,
        mm_failover_master_2_salt_cli,
        salt_mm_failover_minion_1,
        salt_mm_failover_minion_2,
        run_salt_cmds,
    ):
        # Force the minions to reconnect if needed
        retries = 3
        while retries:
            try:
                minion_1_alive = run_salt_cmds(
                    [mm_failover_master_1_salt_cli], [salt_mm_failover_minion_1]
                )
                minion_2_alive = run_salt_cmds(
                    [mm_failover_master_2_salt_cli], [salt_mm_failover_minion_2]
                )

                if not (minion_1_alive and minion_2_alive):
                    with salt_mm_failover_minion_1.stopped(), salt_mm_failover_minion_2.stopped():
                        with salt_mm_failover_master_1.stopped(), salt_mm_failover_master_2.stopped():
                            log.debug(
                                "All masters and minions are shutdown. Restarting."
                            )
            except FactoryNotStarted:
                log.debug("One or more minions failed to start, retrying")
            else:
                # Each minion should return to EXACTLY one master
                if minion_1_alive and minion_2_alive:
                    break
            time.sleep(10)
            retries -= 1
        else:
            pytest.fail("Could not ensure the connections were okay.")

    # run the function to ensure initial connections
    _ensure_connections_fn(
        salt_mm_failover_master_1,
        salt_mm_failover_master_2,
        mm_failover_master_1_salt_cli,
        mm_failover_master_2_salt_cli,
        salt_mm_failover_minion_1,
        salt_mm_failover_minion_2,
        run_salt_cmds,
    )

    # Give this function back for further use in test fn bodies
    return _ensure_connections_fn
