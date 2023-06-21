import pytest
from saltfactories.utils import random_string


@pytest.fixture(scope="package")
def salt_master_factory(salt_factories):
    factory = salt_factories.salt_master_daemon(
        random_string("reauth-master-"),
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    return factory


@pytest.fixture(scope="package")
def salt_master(salt_master_factory):
    with salt_master_factory.started():
        yield salt_master_factory


@pytest.fixture(scope="package")
def salt_minion_factory(salt_master):
    factory = salt_master.salt_minion_daemon(
        random_string("reauth-minion-"),
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    return factory


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
