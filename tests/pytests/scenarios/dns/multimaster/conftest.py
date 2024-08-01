import logging
import os
import shutil
import subprocess

import pytest

from tests.conftest import FIPS_TESTRUN

log = logging.getLogger(__name__)


@pytest.fixture(scope="package")
def salt_mm_master_1(request, salt_factories):

    subprocess.check_output(["ip", "addr", "add", "172.16.0.1/32", "dev", "lo"])

    config_defaults = {
        "open_mode": True,
        "transport": request.config.getoption("--transport"),
    }
    config_overrides = {
        "interface": "0.0.0.0",
        "master_sign_pubkey": True,
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        "mm-master-1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    try:
        with factory.started(start_timeout=180):
            yield factory
    finally:

        try:
            subprocess.check_output(["ip", "addr", "del", "172.16.0.1/32", "dev", "lo"])
        except subprocess.CalledProcessError:
            pass


@pytest.fixture(scope="package")
def mm_master_1_salt_cli(salt_mm_master_1):
    return salt_mm_master_1.salt_cli(timeout=180)


@pytest.fixture(scope="package")
def salt_mm_master_2(salt_factories, salt_mm_master_1):
    # if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
    #    subprocess.check_output(["ifconfig", "lo0", "alias", "127.0.0.2", "up"])

    config_defaults = {
        "open_mode": True,
        "transport": salt_mm_master_1.config["transport"],
    }
    config_overrides = {
        "interface": "0.0.0.0",
        "master_sign_pubkey": True,
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }

    # Use the same ports for both masters, they are binding to different interfaces
    for key in (
        "ret_port",
        "publish_port",
    ):
        config_overrides[key] = salt_mm_master_1.config[key] + 1
    factory = salt_factories.salt_master_daemon(
        "mm-master-2",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )

    # Both masters will share the same signing key pair
    for keyfile in ("master_sign.pem", "master_sign.pub"):
        shutil.copyfile(
            os.path.join(salt_mm_master_1.config["pki_dir"], keyfile),
            os.path.join(factory.config["pki_dir"], keyfile),
        )
    with factory.started(start_timeout=180):
        yield factory


@pytest.fixture(scope="package")
def mm_master_2_salt_cli(salt_mm_master_2):
    return salt_mm_master_2.salt_cli(timeout=180)


@pytest.fixture(scope="package")
def salt_mm_minion_1(salt_mm_master_1, salt_mm_master_2, master_alive_interval):
    config_defaults = {
        "transport": salt_mm_master_1.config["transport"],
    }

    mm_master_1_port = salt_mm_master_1.config["ret_port"]
    mm_master_2_port = salt_mm_master_2.config["ret_port"]
    config_overrides = {
        "master": [
            f"master1.local:{mm_master_1_port}",
            f"master2.local:{mm_master_2_port}",
        ],
        "publish_port": salt_mm_master_1.config["publish_port"],
        "master_alive_interval": master_alive_interval,
        "master_tries": -1,
        "verify_master_pubkey_sign": True,
        "retry_dns": True,
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = salt_mm_master_1.salt_minion_daemon(
        "mm-minion-1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    # Need to grab the public signing key from the master, either will do
    shutil.copyfile(
        os.path.join(salt_mm_master_1.config["pki_dir"], "master_sign.pub"),
        os.path.join(factory.config["pki_dir"], "master_sign.pub"),
    )
    # with factory.started(start_timeout=180):
    yield factory
