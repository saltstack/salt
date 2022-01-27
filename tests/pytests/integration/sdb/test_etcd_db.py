"""
Integration tests for the etcd modules
"""

import logging

import pytest

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_if_binaries_missing("dockerd"),
]


@pytest.fixture(scope="module", autouse=True)
def etc_docker_container(salt_call_cli, sdb_etcd_port):
    container_started = False
    try:
        ret = salt_call_cli.run(
            "state.single", "docker_image.present", name="bitnami/etcd", tag="latest"
        )
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        ret = salt_call_cli.run(
            "state.single",
            "docker_container.running",
            name="etcd",
            image="bitnami/etcd:latest",
            port_bindings="{}:2379".format(sdb_etcd_port),
            environment={"ALLOW_NONE_AUTHENTICATION": "yes", "ETCD_ENABLE_V2": "true"},
            cap_add="IPC_LOCK",
        )
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        container_started = True
        yield
    finally:
        if container_started:
            ret = salt_call_cli.run(
                "state.single", "docker_container.stopped", name="etcd"
            )
            assert ret.exitcode == 0
            assert ret.json
            state_run = next(iter(ret.json.values()))
            assert state_run["result"] is True
            ret = salt_call_cli.run(
                "state.single", "docker_container.absent", name="etcd"
            )
            assert ret.exitcode == 0
            assert ret.json
            state_run = next(iter(ret.json.values()))
            assert state_run["result"] is True


@pytest.fixture(scope="module")
def module_pillar_tree(pillar_tree, salt_minion):
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
    top_tempfile = pillar_tree.base.temp_file("top.sls", top_file)
    sdb_tempfile = pillar_tree.base.temp_file("sdb.sls", sdb_pillar_file)

    with top_tempfile, sdb_tempfile:
        yield pillar_tree


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
@pytest.mark.usefixtures("module_pillar_tree")
def test_config(salt_call_cli):
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
