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


@pytest.fixture(scope="module")
def etcd_static_port(sdb_etcd_port):  # pylint: disable=function-redefined
    return sdb_etcd_port


@pytest.fixture(
    scope="module",
    params=(EtcdVersion.v2, EtcdVersion.v3_v2_mode),
    ids=etcd_version_ids,
)
def etcd_version(request):  # pylint: disable=function-redefined
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
