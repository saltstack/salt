"""
    tests.integration.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Integration tests PyTest configuration/fixtures
"""
import logging
import pathlib

import pytest

from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


@pytest.fixture(scope="session", autouse=True)
def _create_old_tempdir():
    pathlib.Path(RUNTIME_VARS.TMP).mkdir(exist_ok=True, parents=True)


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
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
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
        assert ret.returncode == 0, ret
        yield salt_sub_minion_factory
