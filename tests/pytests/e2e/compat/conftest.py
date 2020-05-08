# -*- coding: utf-8 -*-
"""
    tests.e2e.compat.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Salt Compatibility PyTest Fixtures
"""

import logging

import pytest
import salt.utils.path
from saltfactories.factories.manager import SaltFactoriesManager
from saltfactories.utils.log_server import log_server_listener
from saltfactories.utils.ports import get_unused_localhost_port
from tests.support.runtests import RUNTIME_VARS
from tests.support.sminion import create_sminion

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def docker_client():
    if salt.utils.path.which("docker") is None:
        pytest.skip("The docker binary is not available")
    return docker.from_env()


@pytest.fixture(scope="package")
def host_docker_network_ip_address(docker_client):
    sminion = create_sminion()
    network_name = "salt-e2e"
    network_subnet = "10.0.20.0/24"
    network_gateway = "10.0.20.1"
    try:
        ret = sminion.states.docker_network.present(
            network_name,
            driver="bridge",
            ipam_pools=[{"subnet": network_subnet, "gateway": network_gateway}],
        )
        assert isinstance(ret, dict), ret
        assert ret["result"], "Failed to create docker network: {}".format(ret)
        yield network_gateway
    finally:
        sminion.states.docker_network.absent(network_name)


@pytest.fixture(scope="package")
def log_server_host(host_docker_network_ip_address):
    return host_docker_network_ip_address


@pytest.fixture(scope="package")
def log_server_port():
    return get_unused_localhost_port()


@pytest.fixture(scope="package")
def log_server(log_server_host, log_server_port):
    log.info("Starting log server")
    with log_server_listener(log_server_host, log_server_port):
        log.info("Log Server Started")
        # Run tests
        yield


@pytest.fixture(scope="package")
def salt_factories_config(log_server_host, log_server_port, log_server_level):
    """
    Return a dictionary with the keyworkd arguments for SaltFactoriesManager
    """
    return {
        "code_dir": RUNTIME_VARS.CODE_DIR,
        "inject_coverage": True,
        "inject_sitecustomize": True,
        "log_server_host": log_server_host,
        "log_server_port": log_server_port,
        "log_server_level": log_server_level,
        "start_timeout": 120,
    }


@pytest.fixture(scope="package")
def salt_factories(
    request, pytestconfig, tempdir, log_server, salt_factories_config,
):
    if not isinstance(salt_factories_config, dict):
        raise RuntimeError(
            "The 'salt_factories_config' fixture MUST return a dictionary"
        )
    _manager = SaltFactoriesManager(
        pytestconfig,
        tempdir,
        stats_processes=request.session.stats_processes,
        **salt_factories_config
    )
    yield _manager
    _manager.event_listener.stop()


@pytest.fixture(scope="package")
@pytest.mark.skip_if_binaries_missing("docker")
def salt_master(request, salt_factories, host_docker_network_ip_address):
    config_overrides = {
        "interface": host_docker_network_ip_address,
        "file_roots": {
            "base": [RUNTIME_VARS.TMP_STATE_TREE],
            # Alternate root to test __env__ choices
            "prod": [RUNTIME_VARS.TMP_PRODENV_STATE_TREE],
        },
        "pillar_roots": {
            "base": [RUNTIME_VARS.TMP_PILLAR_TREE],
            "prod": [RUNTIME_VARS.TMP_PRODENV_PILLAR_TREE],
        },
    }
    return salt_factories.spawn_master(
        request, "master", config_overrides=config_overrides,
    )


@pytest.fixture
def salt_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_cli(salt_master.config["id"])


@pytest.fixture
def salt_cp_cli(salt_factories, salt_minion, salt_master):
    return salt_factories.get_salt_cp_cli(salt_master.config["id"])
