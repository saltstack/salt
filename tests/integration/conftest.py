"""
    tests.integration.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Integration tests PyTest configuration/fixtures
"""
import logging

import pytest
import saltfactories.exceptions

log = logging.getLogger(__name__)


@pytest.fixture(scope="package", autouse=True)
def salt_master(salt_master_factory):
    """
    A running salt-master fixture
    """
    with salt_master_factory.started():
        yield salt_master_factory


@pytest.fixture(scope="package", autouse=True)
def salt_minion(salt_minion_factory):
    """
    A running salt-minion fixture
    """
    with salt_minion_factory.started():
        # Sync All
        salt_call_cli = salt_minion_factory.salt_call_cli()
        tries = 0
        while True:
            try:
                ret = salt_call_cli.run("saltutil.sync_all", _timeout=60)
            except saltfactories.exceptions.FactoryTimeout:
                if tries == 2:
                    raise
                else:
                    tries += 1
            else:
                assert ret.exitcode == 0, ret
                break
        yield salt_minion_factory


@pytest.fixture(scope="module")
def salt_sub_minion(salt_sub_minion_factory):
    """
    A second running salt-minion fixture
    """
    with salt_sub_minion_factory.started():
        # Sync All
        salt_call_cli = salt_sub_minion_factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.exitcode == 0, ret
        yield salt_sub_minion_factory
