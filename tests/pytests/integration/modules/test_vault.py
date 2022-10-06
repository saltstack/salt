"""
Tests for the Vault module
"""

import logging
import shutil

import pytest
from saltfactories.utils import random_string

from tests.support.pytest.vault import (
    vault_delete_secret,
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
def pillar_state_tree(tmp_path_factory):
    _pillar_state_tree = tmp_path_factory.mktemp("pillar")
    try:
        yield _pillar_state_tree
    finally:
        shutil.rmtree(str(_pillar_state_tree), ignore_errors=True)


@pytest.fixture(scope="class")
def vault_salt_master(
    salt_factories, pillar_state_tree, vault_port, vault_master_config
):
    factory = salt_factories.salt_master_daemon(
        "vault-exemaster", defaults=vault_master_config
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="class")
def vault_salt_minion(vault_salt_master):
    assert vault_salt_master.is_running()
    factory = vault_salt_master.salt_minion_daemon(
        random_string("vault-exeminion", uppercase=False),
        defaults={"open_mode": True, "grains": {}},
    )
    with factory.started():
        # Sync All
        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
        yield factory


@pytest.fixture(scope="class")
def vault_salt_run_cli(vault_salt_master):
    return vault_salt_master.salt_run_cli()


@pytest.fixture(scope="class")
def vault_salt_call_cli(vault_salt_minion):
    return vault_salt_minion.salt_call_cli()


@pytest.fixture(scope="class")
def pillar_dual_use_tree(
    vault_salt_master,
    vault_salt_minion,
):
    top_pillar_contents = f"""
    base:
      '{vault_salt_minion.id}':
        - testvault
    """
    test_pillar_contents = """
    test:
      foo: bar
      jvmdump_pubkey: {{ salt["vault.read_secret"]("secret/test/jvmdump/ssh_key", "public_key") }}
      jenkins_pubkey: {{ salt["vault.read_secret"]("secret/test/jenkins/master/ssh_key", "public_key") }}
    """
    top_file = vault_salt_master.pillar_tree.base.temp_file(
        "top.sls", top_pillar_contents
    )
    test_file = vault_salt_master.pillar_tree.base.temp_file(
        "testvault.sls", test_pillar_contents
    )

    with top_file, test_file:
        yield


@pytest.fixture(scope="class")
def vault_testing_data(vault_container_version):
    vault_write_secret("secret/test/jvmdump/ssh_key", public_key="yup_dump")
    vault_write_secret("secret/test/jenkins/master/ssh_key", public_key="yup_master")
    vault_write_secret("secret/test/deleteme", pls=":)")
    try:
        yield
    finally:
        vault_delete_secret("secret/test/jvmdump/ssh_key")
        vault_delete_secret("secret/test/jenkins/master/ssh_key")
        for x in ["deleteme", "write"]:
            if x in vault_list_secrets("secret/test"):
                vault_delete_secret(f"secret/test/{x}")


@pytest.mark.usefixtures("vault_testing_data", "pillar_dual_use_tree")
@pytest.mark.parametrize("vault_container_version", ["1.3.1", "latest"], indirect=True)
class TestSingleUseToken:
    """
    Single-use tokens and read operations on versions below 0.10.0
    do not work since the necessary metadata lookup consumes a use
    there without caching metadata information (sys/internal/mounts/:path
    is not available, hence not an unauthenticated endpoint).
    It is impossible to differentiate between the endpoint not being
    available and the token not having the correct permissions.
    """

    @pytest.fixture(scope="class")
    def vault_master_config(self, pillar_state_tree, vault_port):
        return {
            "pillar_roots": {"base": [str(pillar_state_tree)]},
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
                            "uses": 1,
                        }
                    },
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
            "minion_data_cache": False,
        }

    def test_vault_read_secret(self, vault_salt_call_cli):
        """
        Test that the Vault module can fetch a single secret when tokens
        are issued with uses=1.
        """
        ret = vault_salt_call_cli.run(
            "vault.read_secret", "secret/test/jvmdump/ssh_key"
        )
        assert ret.returncode == 0
        assert ret.data == {"public_key": "yup_dump"}

    def test_vault_read_secret_can_fetch_more_than_one_secret_in_one_run(
        self,
        vault_salt_call_cli,
        vault_salt_minion,
        caplog,
    ):
        """
        Test that the Vault module can fetch multiple secrets during
        a single run when tokens are issued with uses=1.
        Issue #57561
        """
        ret = vault_salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.returncode == 0
        assert ret.data is True
        ret = vault_salt_call_cli.run("pillar.items")
        assert ret.returncode == 0
        assert ret.data
        assert "Pillar render error" not in caplog.text
        assert "test" in ret.data
        assert "jvmdump_pubkey" in ret.data["test"]
        assert ret.data["test"]["jvmdump_pubkey"] == "yup_dump"
        assert "jenkins_pubkey" in ret.data["test"]
        assert ret.data["test"]["jenkins_pubkey"] == "yup_master"

    def test_vault_write_secret(self, vault_salt_call_cli):
        """
        Test that the Vault module can write a single secret when tokens
        are issued with uses=1.
        """
        ret = vault_salt_call_cli.run(
            "vault.write_secret", "secret/test/write", success="yup"
        )
        assert ret.returncode == 0
        assert ret.data
        assert "write" in vault_list_secrets("secret/test")

    def test_vault_delete_secret(self, vault_salt_call_cli):
        """
        Test that the Vault module can delete a single secret when tokens
        are issued with uses=1.
        """
        ret = vault_salt_call_cli.run("vault.delete_secret", "secret/test/deleteme")
        assert ret.returncode == 0
        assert ret.data
        assert "delete" not in vault_list_secrets("secret/test")
