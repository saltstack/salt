import logging
import os
import shutil
import subprocess

import pytest
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
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture(scope="package")
def mm_failover_master_1_salt_cli(salt_mm_failover_master_1):
    return salt_mm_failover_master_1.salt_cli(timeout=120)


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
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )

    # Both masters will share the same signing key pair
    for keyfile in ("master_sign.pem", "master_sign.pub"):
        shutil.copyfile(
            os.path.join(salt_mm_failover_master_1.config["pki_dir"], keyfile),
            os.path.join(factory.config["pki_dir"], keyfile),
        )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture(scope="package")
def mm_failover_master_2_salt_cli(salt_mm_failover_master_2):
    return salt_mm_failover_master_2.salt_cli(timeout=120)


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
            "{}:{}".format(mm_master_1_addr, mm_master_1_port),
            "{}:{}".format(mm_master_2_addr, mm_master_2_port),
        ],
        "publish_port": salt_mm_failover_master_1.config["publish_port"],
        "master_type": "failover",
        "master_alive_interval": 15,
        "master_tries": -1,
        "verify_master_pubkey_sign": True,
    }
    factory = salt_mm_failover_master_1.salt_minion_daemon(
        "mm-failover-minion-1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    # Need to grab the public signing key from the master, either will do
    shutil.copyfile(
        os.path.join(salt_mm_failover_master_1.config["pki_dir"], "master_sign.pub"),
        os.path.join(factory.config["pki_dir"], "master_sign.pub"),
    )
    with factory.started(start_timeout=120):
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
            "{}:{}".format(mm_master_2_addr, mm_master_2_port),
            "{}:{}".format(mm_master_1_addr, mm_master_1_port),
        ],
        "publish_port": salt_mm_failover_master_1.config["publish_port"],
        "master_type": "failover",
        "master_alive_interval": 15,
        "master_tries": -1,
        "verify_master_pubkey_sign": True,
    }
    factory = salt_mm_failover_master_2.salt_minion_daemon(
        "mm-failover-minion-2",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    # Need to grab the public signing key from the master, either will do
    shutil.copyfile(
        os.path.join(salt_mm_failover_master_1.config["pki_dir"], "master_sign.pub"),
        os.path.join(factory.config["pki_dir"], "master_sign.pub"),
    )
    with factory.started(start_timeout=120):
        yield factory
