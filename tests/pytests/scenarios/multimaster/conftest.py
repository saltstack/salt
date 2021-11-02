import logging
import os
import shutil
import subprocess

import pytest
import salt.utils.platform

log = logging.getLogger(__name__)


@pytest.fixture(scope="package", autouse=True)
def skip_on_tcp_transport(request):
    if request.config.getoption("--transport") == "tcp":
        pytest.skip("Multimaster under the TPC transport is not working. See #59053")


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
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
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
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
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
            "{}:{}".format(mm_master_1_addr, mm_master_1_port),
            "{}:{}".format(mm_master_2_addr, mm_master_2_port),
        ],
        "test.foo": "baz",
    }
    factory = salt_mm_master_1.salt_minion_daemon(
        "mm-minion-1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
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
            "{}:{}".format(mm_master_1_addr, mm_master_1_port),
            "{}:{}".format(mm_master_2_addr, mm_master_2_port),
        ],
        "test.foo": "baz",
    }
    factory = salt_mm_master_2.salt_minion_daemon(
        "mm-minion-2",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    with factory.started(start_timeout=120):
        yield factory
