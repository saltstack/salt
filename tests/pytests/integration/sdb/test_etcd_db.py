"""
Integration tests for the etcd modules
"""

import logging

import pytest

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd"),
]


@pytest.fixture(scope="module", autouse=True)
def etc_docker_container(salt_factories, salt_call_cli, sdb_etcd_port):
    factory = salt_factories.get_container(
        "etcd",
        "bitnami/etcd:latest",
        check_ports=[sdb_etcd_port],
        container_run_kwargs={
            "ports": {
                "2379/tcp": sdb_etcd_port,
            },
            "environment": {
                "ALLOW_NONE_AUTHENTICATION": "yes",
                "ETCD_ENABLE_V2": "true",
            },
            "cap_add": "IPC_LOCK",
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    with factory.started() as container:
        tries_left = 10
        while tries_left > 0:
            tries_left -= 1
            ret = salt_call_cli.run(
                "sdb.set", uri="sdb://sdbetcd/secret/test/test_sdb/fnord", value="bar"
            )
            if ret.returncode == 0:
                break
        else:
            pytest.skip(
                "Failed to actually connect to etcd inside the running container - skipping test today"
            )
        yield container


@pytest.fixture(scope="module")
def pillar_tree(salt_master, salt_minion):
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
    top_tempfile = salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    sdb_tempfile = salt_master.pillar_tree.base.temp_file("sdb.sls", sdb_pillar_file)

    with top_tempfile, sdb_tempfile:
        yield


def test_sdb(salt_call_cli):
    ret = salt_call_cli.run(
        "sdb.set", uri="sdb://sdbetcd/secret/test/test_sdb/foo", value="bar"
    )
    assert ret.returncode == 0
    assert ret.data
    assert ret.data == "bar"

    ret = salt_call_cli.run("sdb.get", uri="sdb://sdbetcd/secret/test/test_sdb/foo")
    assert ret.returncode == 0
    assert ret.data
    assert ret.data == "bar"


def test_sdb_runner(salt_run_cli):
    ret = salt_run_cli.run(
        "sdb.set", uri="sdb://sdbetcd/secret/test/test_sdb_runner/foo", value="bar"
    )
    assert ret.returncode == 0
    assert ret.stdout == "bar"

    ret = salt_run_cli.run(
        "sdb.get", uri="sdb://sdbetcd/secret/test/test_sdb_runner/foo"
    )
    assert ret.returncode == 0
    assert ret.stdout == "bar"


def test_config(salt_call_cli, pillar_tree):
    ret = salt_call_cli.run(
        "sdb.set", uri="sdb://sdbetcd/secret/test/test_pillar_sdb/foo", value="bar"
    )
    assert ret.returncode == 0
    assert ret.data
    assert ret.data == "bar"

    ret = salt_call_cli.run("config.get", "test_etcd_pillar_sdb")
    assert ret.returncode == 0
    assert ret.data
    assert ret.data == "bar"
