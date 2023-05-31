"""
Salt performance tests
"""
import logging
import shutil

import pytest
from saltfactories.daemons.container import Container

import salt.utils.path
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
def network():
    return "salt-performance"


@pytest.fixture(scope="session")
def host_docker_network_ip_address(network):
    sminion = create_sminion()
    network_name = network
    network_subnet = "10.0.20.0/24"
    network_gateway = "10.0.20.1"
    try:
        ret = sminion.states.docker_network.present(
            network_name,
            driver="bridge",
            ipam_pools=[{"subnet": network_subnet, "gateway": network_gateway}],
        )
        assert isinstance(ret, dict), ret
        try:
            assert ret["result"]
        except AssertionError:
            pytest.skip("Failed to create docker network: {}".format(ret))
        yield network_gateway
    finally:
        sminion.states.docker_network.absent(network_name)


@pytest.fixture(scope="session")
def salt_factories_config(salt_factories_config, host_docker_network_ip_address):
    """
    Return a dictionary with the keyword arguments for FactoriesManager
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
    (dirname / "testfile").write_text("This is a test file")
    return dirname


@pytest.fixture(scope="package")
def sls_contents():
    return """
    add_file:
      file.managed:
        - name: {path}
        - source: salt://testfile
        - makedirs: true
        - require:
          - cmd: echo
    delete_file:
      file.absent:
        - name: {path}
        - require:
          - file: add_file
    echo:
      cmd.run:
        - name: \"echo 'This is a test!'\"
    """


@pytest.fixture(scope="package")
def file_add_delete_sls(testfile_path, state_tree):
    sls_name = "file_add"
    sls_contents = """
    add_file:
      file.managed:
        - name: {path}
        - source: salt://testfile
        - makedirs: true
        - require:
          - cmd: echo
    delete_file:
      file.absent:
        - name: {path}
        - require:
          - file: add_file
    echo:
      cmd.run:
        - name: \"echo 'This is a test!'\"
    """.format(
        path=testfile_path
    )
    with pytest.helpers.temp_file("{}.sls".format(sls_name), sls_contents, state_tree):
        yield sls_name
