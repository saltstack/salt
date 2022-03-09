"""
    tests.pytests.integration.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    PyTest fixtures
"""

import logging

import pytest

log = logging.getLogger(__name__)


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
        # Sync All
        salt_call_cli = salt_minion_factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.exitcode == 0, ret
        yield salt_minion_factory


@pytest.fixture(scope="module")
def salt_sub_minion(salt_master, salt_sub_minion_factory):
    """
    A second running salt-minion fixture
    """
    assert salt_master.is_running()
    with salt_sub_minion_factory.started():
        # Sync All
        salt_call_cli = salt_sub_minion_factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.exitcode == 0, ret
        yield salt_sub_minion_factory


@pytest.fixture(scope="package")
def salt_cli(salt_master):
    """
    The ``salt`` CLI as a fixture against the running master
    """
    assert salt_master.is_running()
    return salt_master.salt_cli()


@pytest.fixture(scope="package")
def salt_call_cli(salt_minion):
    """
    The ``salt-call`` CLI as a fixture against the running minion
    """
    assert salt_minion.is_running()
    return salt_minion.salt_call_cli()


@pytest.fixture(scope="package")
def salt_cp_cli(salt_master):
    """
    The ``salt-cp`` CLI as a fixture against the running master
    """
    assert salt_master.is_running()
    return salt_master.salt_cp_cli()


@pytest.fixture(scope="package")
def salt_key_cli(salt_master):
    """
    The ``salt-key`` CLI as a fixture against the running master
    """
    assert salt_master.is_running()
    return salt_master.salt_key_cli()


@pytest.fixture(scope="package")
def salt_run_cli(salt_master):
    """
    The ``salt-run`` CLI as a fixture against the running master
    """
    assert salt_master.is_running()
    return salt_master.salt_run_cli()


@pytest.fixture(scope="module")
def salt_ssh_cli(salt_master, salt_ssh_roster_file, sshd_config_dir):
    """
    The ``salt-ssh`` CLI as a fixture against the running master
    """
    assert salt_master.is_running()
    return salt_master.salt_ssh_cli(
        timeout=180,
        roster_file=salt_ssh_roster_file,
        target_host="localhost",
        client_key=str(sshd_config_dir / "client_key"),
        base_script_args=["--ignore-host-keys"],
    )
