"""
Integration tests for the vault modules
"""

import logging

import pytest
from saltfactories.utils import random_string

# pylint: disable=unused-import
from tests.support.pytest.vault import (
    vault_container_version,
    vault_delete_secret,
    vault_environ,
    vault_list_secrets,
    vault_write_secret,
)

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd", "vault", "getent"),
    pytest.mark.usefixtures("vault_container_version"),
]


@pytest.fixture(scope="class")
def pillar_tree(vault_salt_master, vault_salt_minion):
    top_file = f"""
    base:
      '{vault_salt_minion.id}':
        - sdb
    """
    sdb_pillar_file = """
    test_vault_pillar_sdb: sdb://sdbvault/secret/test/test_pillar_sdb/foo
    """
    top_tempfile = vault_salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    sdb_tempfile = vault_salt_master.pillar_tree.base.temp_file(
        "sdb.sls", sdb_pillar_file
    )

    with top_tempfile, sdb_tempfile:
        yield


@pytest.fixture(scope="class")
def vault_master_config(vault_port):
    return {
        "open_mode": True,
        "peer_run": {
            ".*": [
                "vault.get_config",
                "vault.generate_new_token",
            ],
        },
        "vault": {
            "auth": {
                "token": "testsecret",
            },
            "issue": {
                "token": {
                    "params": {
                        "num_uses": 0,
                    }
                }
            },
            "policies": {
                "assign": [
                    "salt_minion",
                ]
            },
            "server": {
                "url": f"http://127.0.0.1:{vault_port}",
            },
        },
        "minion_data_cache": True,
    }


@pytest.fixture(scope="class")
def vault_salt_master(salt_factories, vault_port, vault_master_config):
    factory = salt_factories.salt_master_daemon(
        "vault-sdbmaster", defaults=vault_master_config
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="class")
def sdb_profile():
    return {}


@pytest.fixture(scope="class")
def vault_salt_minion(vault_salt_master, sdb_profile):
    assert vault_salt_master.is_running()
    config = {"open_mode": True, "grains": {}, "sdbvault": {"driver": "vault"}}
    config["sdbvault"].update(sdb_profile)
    factory = vault_salt_master.salt_minion_daemon(
        random_string("vault-sdbminion", uppercase=False),
        defaults=config,
    )
    with factory.started():
        # Sync All
        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
        yield factory


@pytest.fixture(scope="class")
def vault_salt_call_cli(vault_salt_minion):
    return vault_salt_minion.salt_call_cli()


@pytest.fixture(scope="class")
def vault_salt_run_cli(vault_salt_master):
    return vault_salt_master.salt_run_cli()


@pytest.fixture
def kv_root_dual_item(vault_container_version):
    if vault_container_version == "latest":
        vault_write_secret("salt/user1", password="p4ssw0rd", desc="test user")
        vault_write_secret("salt/user/user1", password="p4ssw0rd", desc="test user")
    yield
    if vault_container_version == "latest":
        vault_delete_secret("salt/user1")
        vault_delete_secret("salt/user/user1")


@pytest.mark.parametrize("vault_container_version", ["1.3.1", "latest"], indirect=True)
def test_sdb_kv_kvv2_path_local(salt_call_cli, vault_container_version):
    ret = salt_call_cli.run(
        "--local",
        "sdb.set",
        uri="sdb://sdbvault/kv-v2/test/test_sdb_local/foo",
        value="local",
    )
    assert ret.returncode == 0
    assert ret.data is True
    ret = salt_call_cli.run(
        "--local", "sdb.get", "sdb://sdbvault/kv-v2/test/test_sdb_local/foo"
    )
    assert ret.data
    assert ret.data == "local"


@pytest.mark.usefixtures("kv_root_dual_item")
@pytest.mark.parametrize("vault_container_version", ["latest"], indirect=True)
def test_sdb_kv_dual_item(salt_call_cli, vault_container_version):
    ret = salt_call_cli.run("--local", "sdb.get", "sdb://sdbvault/salt/data/user1")
    assert ret.data
    assert ret.data == {"desc": "test user", "password": "p4ssw0rd"}


def test_sdb_runner(salt_run_cli):
    ret = salt_run_cli.run(
        "sdb.set", uri="sdb://sdbvault/secret/test/test_sdb_runner/foo", value="runner"
    )
    assert ret.returncode == 0
    assert ret.data is True
    ret = salt_run_cli.run(
        "sdb.get", uri="sdb://sdbvault/secret/test/test_sdb_runner/foo"
    )
    assert ret.returncode == 0
    assert ret.stdout
    assert ret.stdout == "runner"


@pytest.mark.usefixtures("pillar_tree")
class TestSDB:
    def test_sdb(self, vault_salt_call_cli):
        ret = vault_salt_call_cli.run(
            "sdb.set", uri="sdb://sdbvault/secret/test/test_sdb/foo", value="bar"
        )
        assert ret.returncode == 0
        assert ret.data is True
        ret = vault_salt_call_cli.run(
            "sdb.get", uri="sdb://sdbvault/secret/test/test_sdb/foo"
        )
        assert ret.returncode == 0
        assert ret.data
        assert ret.data == "bar"

    def test_config(self, vault_salt_call_cli):
        ret = vault_salt_call_cli.run(
            "sdb.set", uri="sdb://sdbvault/secret/test/test_pillar_sdb/foo", value="baz"
        )
        assert ret.returncode == 0
        assert ret.data is True
        ret = vault_salt_call_cli.run("config.get", "test_vault_pillar_sdb")
        assert ret.returncode == 0
        assert ret.data
        assert ret.data == "baz"


class TestGetOrSetHashSingleUseToken:
    @pytest.fixture(scope="class")
    def vault_master_config(self, vault_port):
        return {
            "open_mode": True,
            "peer_run": {
                ".*": [
                    "vault.get_config",
                    "vault.generate_new_token",
                ],
            },
            "vault": {
                "auth": {"token": "testsecret"},
                "cache": {
                    "backend": "file",
                },
                "issue": {
                    "type": "token",
                    "token": {
                        "params": {
                            "num_uses": 1,
                        }
                    },
                },
                "policies": {
                    "assign": [
                        "salt_minion",
                    ],
                },
                "server": {
                    "url": f"http://127.0.0.1:{vault_port}",
                },
            },
            "minion_data_cache": True,
        }

    @pytest.fixture
    def get_or_set_absent(self):
        secret_path = "secret/test"
        secret_name = "sdb_get_or_set_hash"
        ret = vault_list_secrets(secret_path)
        if secret_name in ret:
            vault_delete_secret(f"{secret_path}/{secret_name}")
        ret = vault_list_secrets(secret_path)
        assert secret_name not in ret
        try:
            yield
        finally:
            ret = vault_list_secrets(secret_path)
            if secret_name in ret:
                vault_delete_secret(f"{secret_path}/{secret_name}")

    @pytest.mark.usefixtures("get_or_set_absent")
    @pytest.mark.parametrize(
        "vault_container_version", ["1.3.1", "latest"], indirect=True
    )
    def test_sdb_get_or_set_hash_single_use_token(self, vault_salt_call_cli):
        """
        Test that sdb.get_or_set_hash works with uses=1.
        This fails for versions that do not have the sys/internal/ui/mounts/:path
        endpoint (<0.10.0) because the path metadata lookup consumes a token use there.
        Issue #60779
        """
        ret = vault_salt_call_cli.run(
            "sdb.get_or_set_hash",
            "sdb://sdbvault/secret/test/sdb_get_or_set_hash/foo",
            10,
        )
        assert ret.returncode == 0
        result = ret.data
        assert result
        ret = vault_salt_call_cli.run(
            "sdb.get_or_set_hash",
            "sdb://sdbvault/secret/test/sdb_get_or_set_hash/foo",
            10,
        )
        assert ret.returncode == 0
        assert ret.data
        assert ret.data == result


class TestSDBSetPatch:
    @pytest.fixture(scope="class")
    def sdb_profile(self):
        return {"patch": True}

    def test_sdb_set(self, vault_salt_call_cli):
        # Write to an empty path
        ret = vault_salt_call_cli.run(
            "sdb.set", uri="sdb://sdbvault/secret/test/test_sdb_patch/foo", value="bar"
        )
        assert ret.returncode == 0
        assert ret.data is True
        # Write to an existing path, this should not overwrite the previous key
        ret = vault_salt_call_cli.run(
            "sdb.set", uri="sdb://sdbvault/secret/test/test_sdb_patch/bar", value="baz"
        )
        assert ret.returncode == 0
        assert ret.data is True
        # Ensure the first value is still there
        ret = vault_salt_call_cli.run(
            "sdb.get", uri="sdb://sdbvault/secret/test/test_sdb_patch/foo"
        )
        assert ret.returncode == 0
        assert ret.data
        assert ret.data == "bar"
        # Ensure the second value was written
        ret = vault_salt_call_cli.run(
            "sdb.get", uri="sdb://sdbvault/secret/test/test_sdb_patch/bar"
        )
        assert ret.returncode == 0
        assert ret.data
        assert ret.data == "baz"
