import os
from contextlib import ExitStack

import pytest
from saltfactories.utils import random_string


@pytest.fixture(scope="package")
def salt_master_factory(salt_factories):
    factory = salt_factories.salt_master_daemon(
        random_string("swarm-master-"),
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
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
def minion_count():
    # Allow this to be changed via an environment variable if needed
    return int(os.environ.get("SALT_CI_MINION_SWARM_COUNT", 20))


@pytest.fixture(scope="package")
def minion_swarm(salt_master, minion_count):
    assert salt_master.is_running()
    minions = []
    # We create and arbitrarily tall context stack to register the
    # minions stop mechanism callback
    with ExitStack() as stack:
        for idx in range(minion_count):
            minion_factory = salt_master.salt_minion_daemon(
                random_string("swarm-minion-{}-".format(idx)),
                extra_cli_arguments_after_first_start_failure=["--log-level=info"],
            )
            stack.enter_context(minion_factory.started())
            minions.append(minion_factory)
        for minion in minions:
            assert minion.is_running()
        yield minions
    for minion in minions:
        assert not minion.is_running()
