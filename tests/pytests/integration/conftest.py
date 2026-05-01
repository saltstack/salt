"""
    tests.pytests.integration.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    PyTest fixtures
"""

import logging
import time

import pytest
from pytestshellutils.exceptions import FactoryTimeout

import salt.utils.platform

log = logging.getLogger(__name__)

# Windows integration runs are slower (I/O, antivirus, ZMQ); allow long salt-call and sync_all.
_SYNC_ALL_TIMEOUT = 300 if salt.utils.platform.is_windows() else 120
_SYNC_ALL_ATTEMPTS = 2 if salt.utils.platform.is_windows() else 1


def _sync_all_packages(salt_call_cli):
    """Run saltutil.sync_all; retry on Windows when salt-call times out (ZMQ / auth flakes)."""
    for attempt in range(1, _SYNC_ALL_ATTEMPTS + 1):
        try:
            ret = salt_call_cli.run(
                "saltutil.sync_all", saltenv="base", _timeout=_SYNC_ALL_TIMEOUT
            )
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


@pytest.fixture(scope="package")
def salt_master(salt_master_factory):
    """
    A running salt-master fixture
    """
    with salt_master_factory.started():
        yield salt_master_factory


@pytest.fixture(scope="package")
def salt_minion(salt_master, salt_minion_factory):
    """
    A running salt-minion fixture
    """
    assert salt_master.is_running()
    with salt_minion_factory.started():
        # saltenv=base skips HighState top env discovery in each sync (avoids long master RPC during salt-call).
        salt_call_cli = salt_minion_factory.salt_call_cli()
        _sync_all_packages(salt_call_cli)
        yield salt_minion_factory


@pytest.fixture(scope="module")
def salt_sub_minion(salt_master, salt_sub_minion_factory):
    """
    A second running salt-minion fixture
    """
    assert salt_master.is_running()
    with salt_sub_minion_factory.started():
        salt_call_cli = salt_sub_minion_factory.salt_call_cli()
        _sync_all_packages(salt_call_cli)
        yield salt_sub_minion_factory


@pytest.fixture(scope="package")
def salt_cli(salt_master):
    """
    The ``salt`` CLI as a fixture against the running master
    """
    assert salt_master.is_running()
    return salt_master.salt_cli(timeout=30)


@pytest.fixture(scope="package")
def salt_call_cli(salt_minion):
    """
    The ``salt-call`` CLI as a fixture against the running minion
    """
    assert salt_minion.is_running()
    return salt_minion.salt_call_cli(timeout=30)


@pytest.fixture(scope="package")
def salt_cp_cli(salt_master):
    """
    The ``salt-cp`` CLI as a fixture against the running master
    """
    assert salt_master.is_running()
    return salt_master.salt_cp_cli(timeout=30)


@pytest.fixture(scope="package")
def salt_key_cli(salt_master):
    """
    The ``salt-key`` CLI as a fixture against the running master
    """
    assert salt_master.is_running()
    return salt_master.salt_key_cli(timeout=30)


@pytest.fixture(scope="package")
def salt_run_cli(salt_master):
    """
    The ``salt-run`` CLI as a fixture against the running master
    """
    assert salt_master.is_running()
    return salt_master.salt_run_cli(timeout=30)


@pytest.fixture(scope="module")
def salt_ssh_cli(salt_master, salt_ssh_roster_file, sshd_config_dir, known_hosts_file):
    """
    The ``salt-ssh`` CLI as a fixture against the running master
    """
    assert salt_master.is_running()
    return salt_master.salt_ssh_cli(
        timeout=300,
        roster_file=salt_ssh_roster_file,
        target_host="localhost",
        client_key=str(sshd_config_dir / "client_key"),
    )


@pytest.fixture(scope="module")
def salt_auto_account(salt_auto_account_factory):
    with salt_auto_account_factory as account:
        yield account
