"""
    tests.e2e.compat.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Salt Compatibility PyTest Fixtures
"""

import logging
import os
import shutil

import pytest
from saltfactories.daemons.container import Container
from saltfactories.utils import random_string

import salt.utils.path
from tests.conftest import FIPS_TESTRUN
from tests.support.runtests import RUNTIME_VARS
from tests.support.sminion import create_sminion

docker = pytest.importorskip("docker")
# pylint: disable=3rd-party-module-not-gated,no-name-in-module
from docker.errors import DockerException  # isort:skip

# pylint: enable=3rd-party-module-not-gated,no-name-in-module

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("docker"),
]


log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def docker_client():
    if docker is None:
        pytest.skip("The docker python library is not available")

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


@pytest.fixture(scope="session")
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
        assert ret["result"], f"Failed to create docker network: {ret}"
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


@pytest.fixture(scope="package")
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
    """
    Fixture which returns the salt state tree root directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = integration_files_dir / "state-tree"
    dirname.mkdir(exist_ok=True)
    return dirname


@pytest.fixture(scope="package")
def pillar_tree(integration_files_dir):
    """
    Fixture which returns the salt pillar tree root directory path.
    Creates the directory if it does not yet exist.
    """
    dirname = integration_files_dir / "pillar-tree"
    dirname.mkdir(exist_ok=True)
    return dirname


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
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
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
            "file_roots": {"base": [str(state_tree)]},
            "pillar_roots": {"base": [str(pillar_tree)]},
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
