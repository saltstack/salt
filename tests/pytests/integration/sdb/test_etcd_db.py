"""
Integration tests for the etcd modules
"""

import logging
import time

import pytest
import requests
import requests.exceptions

etcd = pytest.importorskip("etcd")


log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd"),
]


def check_etcd_responsive(timeout_at, etcd_port):
    sleeptime = 1
    while time.time() <= timeout_at:
        try:
            response = requests.get("http://localhost:{}/health".format(etcd_port))
            if response.json()["health"]:
                break
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(sleeptime)
        sleeptime *= 2
    else:
        return False
    return True


def check_successful_salt_interaction(timeout_at, salt_call_cli):
    sleeptime = 1
    while time.time() <= timeout_at:
        try:
            ret = salt_call_cli.run(
                "sdb.set", uri="sdb://sdbetcd/secret/test/test_sdb/fnord", value="bar"
            )
            if ret.returncode == 0:
                break
        except etcd.EtcdConnectionFailed:
            pass
        time.sleep(sleeptime)
        sleeptime *= 2
    else:
        return False
    return True


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
    factory.container_start_check(check_etcd_responsive, sdb_etcd_port)
    factory.container_start_check(check_successful_salt_interaction, salt_call_cli)
    with factory.started() as container:
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
