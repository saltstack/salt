"""
Integration tests for the vault modules
"""
import logging

import pytest

from tests.support.pytest.vault import vault_delete_secret, vault_write_secret

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd", "vault", "getent"),
    pytest.mark.usefixtures("vault_container_version"),
]


@pytest.fixture(scope="module")
def kv_root_dual_item(vault_container_version):
    if vault_container_version == "latest":
        vault_write_secret("salt/user1", password="p4ssw0rd", desc="test user")
        vault_write_secret("salt/user/user1", password="p4ssw0rd", desc="test user")
    yield
    if vault_container_version == "latest":
        vault_delete_secret("salt/user1")
        vault_delete_secret("salt/user/user1")


def test_sdb(salt_call_cli):
    ret = salt_call_cli.run(
        "sdb.set", uri="sdb://sdbvault/secret/test/test_sdb/foo", value="bar"
    )
    assert ret.returncode == 0
    assert ret.data is True
    ret = salt_call_cli.run("sdb.get", uri="sdb://sdbvault/secret/test/test_sdb/foo")
    assert ret.returncode == 0
    assert ret.data
    assert ret.data == "bar"


def test_sdb_runner(salt_run_cli):
    ret = salt_run_cli.run(
        "sdb.set", uri="sdb://sdbvault/secret/test/test_sdb_runner/foo", value="bar"
    )
    assert ret.returncode == 0
    assert ret.data is True
    ret = salt_run_cli.run(
        "sdb.get", uri="sdb://sdbvault/secret/test/test_sdb_runner/foo"
    )
    assert ret.returncode == 0
    assert ret.stdout
    assert ret.stdout == "bar"


def test_config(salt_call_cli, pillar_tree):
    ret = salt_call_cli.run(
        "sdb.set", uri="sdb://sdbvault/secret/test/test_pillar_sdb/foo", value="bar"
    )
    assert ret.returncode == 0
    assert ret.data is True
    ret = salt_call_cli.run("config.get", "test_vault_pillar_sdb")
    assert ret.returncode == 0
    assert ret.data
    assert ret.data == "bar"


def test_sdb_kv2_kvv2_path_local(salt_call_cli, vault_container_version):
    if vault_container_version not in ["1.3.1", "latest"]:
        pytest.skip(f"Test not applicable to vault {vault_container_version}")

    ret = salt_call_cli.run(
        "sdb.set", uri="sdb://sdbvault/kv-v2/test/test_sdb/foo", value="bar"
    )
    assert ret.returncode == 0
    assert ret.data is True
    ret = salt_call_cli.run(
        "--local", "sdb.get", "sdb://sdbvault/kv-v2/test/test_sdb/foo"
    )
    assert ret.data
    assert ret.data == "bar"


@pytest.mark.usefixtures("kv_root_dual_item")
def test_sdb_kv_dual_item(salt_call_cli, vault_container_version):
    if vault_container_version not in ["latest"]:
        pytest.skip(f"Test not applicable to vault {vault_container_version}")
    ret = salt_call_cli.run("--local", "sdb.get", "sdb://sdbvault/salt/data/user1")
    assert ret.data
    assert ret.data == {"desc": "test user", "password": "p4ssw0rd"}
