"""
Integration tests for the etcd modules
"""

import logging

import pytest
from tests.support.pytest.etcd import *  # pylint: disable=wildcard-import,unused-wildcard-import

etcd = pytest.importorskip("etcd")


log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
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

        # The following segment attempts to communicate with the container. If
        # we can't actually contact it, we're going to go ahead and skip this,
        # as it passes when running locally -- it's just some sort of
        # flakiness causing the failure.
        tries_left = 10
        while tries_left > 0:
            tries_left -= 1
            ret = salt_call_cli.run(
                "sdb.set", uri="sdb://sdbetcd/secret/test/test_sdb/fnord", value="bar"
            )
            if ret.exitcode == 0:
                break
        else:
            pytest.skip("Failed to get a useful etcd container")
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
def etcd_static_port(sdb_etcd_port):  # pylint: disable=function-redefined
    return sdb_etcd_port


@pytest.fixture(
    scope="module",
    params=(EtcdVersion.v2, EtcdVersion.v3_v2_mode),
    ids=etcd_version_ids,
)  # pylint: disable=function-redefined
def etcd_version(request):
    # The only parameter is True because the salt integration
    # configuration for the salt-master and salt-minion defaults
    # to v2.
    # The alternative would be to start a separate master and minion
    # to try both versions.
    # Maybe at another time, though, we're deprecating version 2, so,
    # it might not be worth it.
    if request.param == EtcdVersion.v2 and not HAS_ETCD_V2:
        pytest.skip("No etcd library installed")
    if request.param != EtcdVersion.v2 and not HAS_ETCD_V3:
        pytest.skip("No etcd3 library installed")
    return request.param


@pytest.fixture(scope="module", autouse=True)
def _container_running(etcd_container):
    return etcd_container


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
