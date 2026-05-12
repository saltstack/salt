"""
    tests.integration.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Integration tests PyTest configuration/fixtures
"""

import logging
import pathlib
import time

import pytest
from pytestshellutils.exceptions import FactoryTimeout

import salt.utils.platform
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)

_SYNC_ALL_TIMEOUT = 300 if salt.utils.platform.is_windows() else 120
_SYNC_ALL_ATTEMPTS = 2 if salt.utils.platform.is_windows() else 1


def _sync_all_packages(salt_call_cli):
    for attempt in range(1, _SYNC_ALL_ATTEMPTS + 1):
        try:
            kwargs = {"_timeout": _SYNC_ALL_TIMEOUT}
            if salt.utils.platform.is_windows():
                kwargs["saltenv"] = "base"
            ret = salt_call_cli.run("saltutil.sync_all", **kwargs)
            assert ret.returncode == 0, ret
            return
        except FactoryTimeout as exc:
            if attempt >= _SYNC_ALL_ATTEMPTS:
                raise
            log.warning(
                "saltutil.sync_all timed out (attempt %s/%s), retrying: %s",
                attempt,
                _SYNC_ALL_ATTEMPTS,
                exc,
            )
            time.sleep(15)


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
        salt_call_cli = salt_minion_factory.salt_call_cli()
        _sync_all_packages(salt_call_cli)
        yield salt_minion_factory


@pytest.fixture(scope="module")
def salt_sub_minion(salt_sub_minion_factory):
    """
    A second running salt-minion fixture
    """
    with salt_sub_minion_factory.started():
        salt_call_cli = salt_sub_minion_factory.salt_call_cli()
        _sync_all_packages(salt_call_cli)
        yield salt_sub_minion_factory
