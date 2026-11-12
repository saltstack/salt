"""
Integration tests for the etcd sdb module
"""

import logging

import pytest

from tests.support.pytest.etcd import *  # pylint: disable=wildcard-import,unused-wildcard-import

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd"),
]


@pytest.fixture(scope="module")
def etcd_static_port(sdb_etcd_port):  # pylint: disable=function-redefined
    return sdb_etcd_port


@pytest.fixture(scope="module", autouse=True)
def _container_running(etcd_container):
    return etcd_container


def test_sdb(salt_call_cli):
    ret = salt_call_cli.run(
        "sdb.set", uri="sdb://sdbetcd/secret/test/test_sdb/foo", value="bar"
    )
    assert ret.returncode == 0
    assert ret.data == "bar"

    ret = salt_call_cli.run("sdb.get", uri="sdb://sdbetcd/secret/test/test_sdb/foo")
    assert ret.returncode == 0
    assert ret.data == "bar"

    ret = salt_call_cli.run("sdb.delete", uri="sdb://sdbetcd/secret/test/test_sdb/foo")
    assert ret.returncode == 0
    assert ret.data is True


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
    assert ret.data == "bar"

    ret = salt_call_cli.run("config.get", "test_etcd_pillar_sdb")
    assert ret.returncode == 0
    assert ret.data == "bar"
