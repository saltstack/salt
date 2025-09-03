import logging

import pytest

from tests.conftest import FIPS_TESTRUN

log = logging.getLogger(__name__)


@pytest.fixture(scope="package")
def master(request, salt_factories):
    config_defaults = {
        "transport": request.config.getoption("--transport"),
    }
    config_overrides = {
        "interface": "127.0.0.1",
        "auto_accept": True,
        "order_masters": True,
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        "master",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=180):
        yield factory


@pytest.fixture(scope="package")
def salt_cli(master):
    return master.salt_cli(timeout=180)


@pytest.fixture(scope="package")
def syndic(master, salt_factories):

    ret_port = master.config["ret_port"]
    port = master.config["publish_port"]
    addr = master.config["interface"]

    # Force both master's publish port to be the same, this is a drawback of
    # the current syndic design.
    config_defaults = {
        "transport": master.config["transport"],
        "interface": "127.0.0.2",
        "publish_port": f"{port}",
    }
    master_overrides = {
        "interface": "127.0.0.2",
        "auto_accept": True,
        "syndic_master": f"{addr}",
        "syndic_master_port": f"{ret_port}",
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    minion_overrides = {
        "master": "127.0.0.2",
        "publish_port": f"{port}",
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = master.salt_syndic_daemon(
        "syndic",
        defaults=config_defaults,
        master_overrides=master_overrides,
        minion_overrides=minion_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=180):
        yield factory


@pytest.fixture(scope="package")
def minion(syndic, salt_factories):
    config_defaults = {
        "transport": syndic.config["transport"],
    }
    port = syndic.master.config["ret_port"]
    addr = syndic.master.config["interface"]
    config_overrides = {
        "master": f"{addr}:{port}",
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = syndic.master.salt_minion_daemon(
        "minion",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=180):
        yield factory
