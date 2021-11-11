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
def salt_proxy(salt_master, salt_proxy_factory):
    """
    A running salt-proxy fixture
    """
    assert salt_master.is_running()
    with salt_proxy_factory.started():
        yield salt_proxy_factory


@pytest.fixture(scope="package")
def deltaproxy_pillar_tree(base_env_pillar_tree_root_dir, salt_delta_proxy_factory):
    """
    Create the pillar files for controlproxy and two dummy proxy minions
    """
    top_file = """
    base:
      '{}':
        - controlproxy
      dummy_proxy_one:
        - dummy_proxy_one
      dummy_proxy_two:
        - dummy_proxy_two
    """.format(
        salt_delta_proxy_factory.id
    )
    controlproxy_pillar_file = """
    proxy:
        proxytype: deltaproxy
        ids:
          - dummy_proxy_one
          - dummy_proxy_two
    """

    dummy_proxy_one_pillar_file = """
    proxy:
      proxytype: dummy
    """

    dummy_proxy_two_pillar_file = """
    proxy:
      proxytype: dummy
    """

    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_pillar_tree_root_dir
    )
    controlproxy_tempfile = pytest.helpers.temp_file(
        "controlproxy.sls", controlproxy_pillar_file, base_env_pillar_tree_root_dir
    )
    dummy_proxy_one_tempfile = pytest.helpers.temp_file(
        "dummy_proxy_one.sls",
        dummy_proxy_one_pillar_file,
        base_env_pillar_tree_root_dir,
    )
    dummy_proxy_two_tempfile = pytest.helpers.temp_file(
        "dummy_proxy_two.sls",
        dummy_proxy_two_pillar_file,
        base_env_pillar_tree_root_dir,
    )
    with top_tempfile, controlproxy_tempfile, dummy_proxy_one_tempfile, dummy_proxy_two_tempfile:
        yield


@pytest.fixture(scope="package")
def salt_delta_proxy(salt_master, salt_delta_proxy_factory, deltaproxy_pillar_tree):
    """
    A running salt-proxy fixture
    """
    assert salt_master.is_running()
    with salt_delta_proxy_factory.started():
        yield salt_delta_proxy_factory


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
