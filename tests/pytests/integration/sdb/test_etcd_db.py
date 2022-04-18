"""
Integration tests for the etcd modules
"""

import logging

import pytest
from salt.utils.etcd_util import HAS_ETCD_V2
from saltfactories.daemons.container import Container
from saltfactories.utils import random_string

docker = pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_if_binaries_missing("dockerd"),
    pytest.mark.windows_whitelisted,
    pytest.mark.skipIf(not HAS_ETCD_V2, "no etcd library installed"),
]


@pytest.fixture(scope="module")
def docker_client():
    try:
        client = docker.from_env()
    except docker.errors.DockerException:
        pytest.skip("Failed to get a connection to docker running on the system")
    connectable = Container.client_connectable(client)
    if connectable is not True:  # pragma: nocover
        pytest.skip(connectable)
    return client


@pytest.fixture(scope="module")
def docker_image_name(docker_client):
    image_name = "bitnami/etcd:3"
    try:
        docker_client.images.pull(image_name)
    except docker.errors.APIError as exc:
        pytest.skip("Failed to pull docker image '{}': {}".format(image_name, exc))
    return image_name


# TODO: Use our own etcd image to avoid reliance on a third party
@pytest.fixture(scope="module", autouse=True)
def etcd_container(salt_factories, docker_client, sdb_etcd_port, docker_image_name):
    container = salt_factories.get_container(
        random_string("etcd-server-"),
        image_name=docker_image_name,
        docker_client=docker_client,
        check_ports=[sdb_etcd_port],
        container_run_kwargs={
            "environment": {
                "ALLOW_NONE_AUTHENTICATION": "yes",
                "ETCD_ENABLE_V2": "true",
            },
            "ports": {"2379/tcp": sdb_etcd_port},
        },
    )
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module")
def pillar_tree(base_env_pillar_tree_root_dir, salt_minion):
    top_file = """
    base:
      '{}':
        - sdb
    """.format(
        salt_minion.id
    )
    sdb_pillar_file = """
    test_vault_pillar_sdb: sdb://sdbvault/secret/test/test_pillar_sdb/foo
    test_etcd_pillar_sdb: sdb://sdbetcd/secret/test/test_pillar_sdb/foo
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_pillar_tree_root_dir
    )
    sdb_tempfile = pytest.helpers.temp_file(
        "sdb.sls", sdb_pillar_file, base_env_pillar_tree_root_dir
    )

    with top_tempfile, sdb_tempfile:
        yield


@pytest.mark.slow_test
def test_sdb(salt_call_cli):
    ret = salt_call_cli.run(
        "sdb.set", uri="sdb://sdbetcd/secret/test/test_sdb/foo", value="bar"
    )
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json == "bar"

    ret = salt_call_cli.run("sdb.get", uri="sdb://sdbetcd/secret/test/test_sdb/foo")
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json == "bar"


@pytest.mark.slow_test
def test_sdb_runner(salt_run_cli):
    ret = salt_run_cli.run(
        "sdb.set", uri="sdb://sdbetcd/secret/test/test_sdb_runner/foo", value="bar"
    )
    assert ret.exitcode == 0
    assert ret.stdout == "bar"

    ret = salt_run_cli.run(
        "sdb.get", uri="sdb://sdbetcd/secret/test/test_sdb_runner/foo"
    )
    assert ret.exitcode == 0
    assert ret.stdout == "bar"


@pytest.mark.slow_test
def test_config(salt_call_cli, pillar_tree):
    ret = salt_call_cli.run(
        "sdb.set", uri="sdb://sdbetcd/secret/test/test_pillar_sdb/foo", value="bar"
    )
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json == "bar"

    ret = salt_call_cli.run("config.get", "test_etcd_pillar_sdb")
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json == "bar"
