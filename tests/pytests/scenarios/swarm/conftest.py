import os
from contextlib import ExitStack

import pytest
from saltfactories.utils import random_string

from tests.conftest import FIPS_TESTRUN


@pytest.fixture(scope="package")
def salt_master_factory(salt_factories):
    config_overrides = {
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        random_string("swarm-master-"),
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
        overrides=config_overrides,
    )
    return factory


@pytest.fixture(scope="package")
def salt_master(salt_master_factory):
    with salt_master_factory.started():
        yield salt_master_factory


@pytest.fixture(scope="package")
def salt_minion(salt_minion_factory):
    with salt_minion_factory.started():
        yield salt_minion_factory


@pytest.fixture(scope="package")
def salt_key_cli(salt_master):
    assert salt_master.is_running()
    return salt_master.salt_key_cli()


@pytest.fixture(scope="package")
def salt_cli(salt_master):
    assert salt_master.is_running()
    return salt_master.salt_cli()


@pytest.fixture(scope="package")
def _minion_count(grains):
    # Allow this to be changed via an environment variable if needed
    env_count = os.environ.get("SALT_CI_MINION_SWARM_COUNT")
    if env_count is not None:
        return int(env_count)
    # Default to 15 swarm minions
    count = 15
    if grains["osarch"] != "aarch64":
        return count
    if grains["os"] != "Amazon":
        return count
    if grains["osmajorrelease"] != 2023:
        return count
    # Looks like the test suite on Amazon 2023 under ARM64 get's OOM killed
    # Let's reduce the number of swarm minions
    return count - 5


@pytest.fixture(scope="package")
def minion_swarm(salt_master, _minion_count):
    assert salt_master.is_running()
    minions = []
    # We create and arbitrarily tall context stack to register the
    # minions stop mechanism callback
    with ExitStack() as stack:
        for idx in range(_minion_count):
            minion_factory = salt_master.salt_minion_daemon(
                random_string(f"swarm-minion-{idx}-"),
                extra_cli_arguments_after_first_start_failure=["--log-level=info"],
                overrides={
                    "fips_mode": FIPS_TESTRUN,
                    "encryption_algorithm": (
                        "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1"
                    ),
                    "signing_algorithm": (
                        "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
                    ),
                },
            )
            stack.enter_context(minion_factory.started())
            minions.append(minion_factory)
        for minion in minions:
            assert minion.is_running()
        yield minions
    for minion in minions:
        assert not minion.is_running()
