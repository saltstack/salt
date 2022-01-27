"""
    tests.e2e.compat.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Salt Compatibility PyTest Fixtures
"""
import logging
import os
import shutil

import pytest
import salt.utils.path
from saltfactories.daemons.container import Container
from saltfactories.utils import random_string
from saltfactories.utils.tempfiles import SaltPillarTree, SaltStateTree
from tests.support.runtests import RUNTIME_VARS
from tests.support.sminion import create_sminion

docker = pytest.importorskip("docker")
# pylint: disable=3rd-party-module-not-gated
from docker.errors import DockerException  # isort:skip

# pylint: enable=3rd-party-module-not-gated

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("docker"),
]


log = logging.getLogger(__name__)


@pytest.fixture(scope="package")
def docker_client():
    if salt.utils.path.which("docker") is None:
        pytest.skip("The docker binary is not available")
    try:
        client = docker.from_env()
        connectable = Container.client_connectable(client)
        if connectable is not True:  # pragma: no cover
            pytest.skip(connectable)
        return client
    except DockerException:
        pytest.skip("Failed to get a connection to docker running on the system")


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


@pytest.fixture(scope="session")
def salt_factories_config(salt_factories_config, host_docker_network_ip_address):
    """
    Return a dictionary with the keyworkd arguments for FactoriesManager
    """
    config = salt_factories_config.copy()
    config["log_server_host"] = host_docker_network_ip_address
    return config


@pytest.fixture(scope="session")
def integration_files_dir(tmp_path_factory):
    """
    Fixture which returns the salt integration files directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = tmp_path_factory.mktemp("integration-files")
    try:
        yield dirname
    finally:
        shutil.rmtree(str(dirname), ignore_errors=True)


@pytest.fixture(scope="package")
def state_tree(integration_files_dir):
    state_tree_path = integration_files_dir / "state-tree"
    state_tree_path.mkdir(exist_ok=True)
    base_state_tree_path = state_tree_path / "base"
    base_state_tree_path.mkdir(exist_ok=True)
    envs = {
        "base": [str(base_state_tree_path)],
    }
    try:
        yield SaltStateTree(envs=envs)
    finally:
        shutil.rmtree(str(state_tree_path), ignore_errors=True)


@pytest.fixture(scope="package")
def pillar_tree(integration_files_dir):
    pillar_tree_path = integration_files_dir / "pillar-tree"
    pillar_tree_path.mkdir(exist_ok=True)
    base_pillar_tree_path = pillar_tree_path / "base"
    base_pillar_tree_path.mkdir(exist_ok=True)
    envs = {
        "base": [str(base_pillar_tree_path)],
    }
    try:
        yield SaltPillarTree(envs=envs)
    finally:
        shutil.rmtree(str(pillar_tree_path), ignore_errors=True)


@pytest.fixture(scope="package")
def salt_master(
    request,
    salt_factories,
    host_docker_network_ip_address,
    state_tree,
    pillar_tree,
):
    master_id = random_string("master-compat-", uppercase=False)
    root_dir = salt_factories.get_root_dir_for_daemon(master_id)
    conf_dir = root_dir / "conf"
    conf_dir.mkdir(exist_ok=True)

    config_defaults = {
        "root_dir": str(root_dir),
        "transport": request.config.getoption("--transport"),
    }
    config_overrides = {
        "interface": host_docker_network_ip_address,
        "log_level_logfile": "quiet",
        # We also want to scrutinize the key acceptance
        "open_mode": False,
    }

    # We need to copy the extension modules into the new master root_dir or
    # it will be prefixed by it
    extension_modules_path = str(root_dir / "extension_modules")
    if not os.path.exists(extension_modules_path):
        shutil.copytree(
            os.path.join(RUNTIME_VARS.FILES, "extension_modules"),
            extension_modules_path,
        )

    config_overrides.update(
        {
            "extension_modules": extension_modules_path,
            "file_roots": state_tree.as_dict(),
            "pillar_roots": pillar_tree.as_dict(),
        }
    )
    factory = salt_factories.salt_master_daemon(
        master_id,
        defaults=config_defaults,
        overrides=config_overrides,
    )
    with factory.started():
        yield factory


@pytest.fixture
def salt_cli(salt_master):
    return salt_master.salt_cli()


@pytest.fixture
def salt_cp_cli(salt_master):
    return salt_master.salt_cp_cli()
