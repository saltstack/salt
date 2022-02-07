"""
Integration tests for the vault execution module
"""

import logging
import time

import pytest
import salt.utils.path
from tests.support.case import ModuleCase
from tests.support.runtests import RUNTIME_VARS
from tests.support.sminion import create_sminion
from tests.support.unit import SkipTest, skipIf

log = logging.getLogger(__name__)

VAULT_BINARY_PATH = salt.utils.path.which("vault")


@skipIf(not salt.utils.path.which("dockerd"), "Docker not installed")
@skipIf(not VAULT_BINARY_PATH, "Vault not installed")
@pytest.mark.destructive_test
class VaultTestCase(ModuleCase):
    """
    Test vault module
    """

    @classmethod
    def setUpClass(cls):
        cls.sminion = sminion = create_sminion()
        config = (
            '{"backend": {"file": {"path": "/vault/file"}}, "default_lease_ttl":'
            ' "168h", "max_lease_ttl": "720h", "disable_mlock": true}'
        )
        sminion.states.docker_image.present(name="vault", tag="0.9.6")
        login_attempts = 1
        container_created = False
        while True:
            if container_created:
                sminion.states.docker_container.stopped(name="vault")
                sminion.states.docker_container.absent(name="vault")
            ret = sminion.states.docker_container.running(
                name="vault",
                image="vault:0.9.6",
                port_bindings="8200:8200",
                environment={
                    "VAULT_DEV_ROOT_TOKEN_ID": "testsecret",
                    "VAULT_LOCAL_CONFIG": config,
                },
            )
            log.debug("docker_container.running return: %s", ret)
            container_created = ret["result"]
            time.sleep(5)
            ret = sminion.functions.cmd.run_all(
                cmd="{} login token=testsecret".format(VAULT_BINARY_PATH),
                env={"VAULT_ADDR": "http://127.0.0.1:8200"},
                hide_output=False,
            )
            if ret["retcode"] == 0:
                break
            log.debug("Vault login failed. Return: %s", ret)
            login_attempts += 1

            if login_attempts >= 3:
                raise SkipTest("unable to login to vault")

        ret = sminion.functions.cmd.retcode(
            cmd="{} policy write testpolicy {}/vault.hcl".format(
                VAULT_BINARY_PATH, RUNTIME_VARS.FILES
            ),
            env={"VAULT_ADDR": "http://127.0.0.1:8200"},
        )
        if ret != 0:
            raise SkipTest("unable to assign policy to vault")

    @classmethod
    def tearDownClass(cls):
        cls.sminion.states.docker_container.stopped(name="vault")
        cls.sminion.states.docker_container.absent(name="vault")
        cls.sminion.states.docker_image.absent(name="vault", force=True)
        cls.sminion = None

    @pytest.mark.slow_test
    def test_write_read_secret(self):
        write_return = self.run_function(
            "vault.write_secret", path="secret/my/secret", user="foo", password="bar"
        )
        self.assertEqual(write_return, True)
        assert self.run_function("vault.read_secret", arg=["secret/my/secret"]) == {
            "password": "bar",
            "user": "foo",
        }
        assert (
            self.run_function("vault.read_secret", arg=["secret/my/secret", "user"])
            == "foo"
        )

    @pytest.mark.slow_test
    def test_write_raw_read_secret(self):
        assert (
            self.run_function(
                "vault.write_raw",
                path="secret/my/secret2",
                raw={"user2": "foo2", "password2": "bar2"},
            )
            is True
        )
        assert self.run_function("vault.read_secret", arg=["secret/my/secret2"]) == {
            "password2": "bar2",
            "user2": "foo2",
        }

    @pytest.mark.slow_test
    def test_delete_secret(self):
        assert (
            self.run_function(
                "vault.write_secret",
                path="secret/my/secret",
                user="foo",
                password="bar",
            )
            is True
        )
        assert (
            self.run_function("vault.delete_secret", arg=["secret/my/secret"]) is True
        )

    @pytest.mark.slow_test
    def test_list_secrets(self):
        assert (
            self.run_function(
                "vault.write_secret",
                path="secret/my/secret",
                user="foo",
                password="bar",
            )
            is True
        )
        assert self.run_function("vault.list_secrets", arg=["secret/my/"]) == {
            "keys": ["secret"]
        }


@skipIf(not salt.utils.path.which("dockerd"), "Docker not installed")
@skipIf(not salt.utils.path.which("vault"), "Vault not installed")
@pytest.mark.destructive_test
class VaultTestCaseCurrent(ModuleCase):
    """
    Test vault module against current vault
    """

    @classmethod
    def setUpClass(cls):
        cls.sminion = sminion = create_sminion()
        config = (
            '{"backend": {"file": {"path": "/vault/file"}}, "default_lease_ttl":'
            ' "168h", "max_lease_ttl": "720h", "disable_mlock": true}'
        )
        sminion.states.docker_image.present(name="vault", tag="1.3.1")
        login_attempts = 1
        container_created = False
        while True:
            if container_created:
                sminion.states.docker_container.stopped(name="vault")
                sminion.states.docker_container.absent(name="vault")
            ret = sminion.states.docker_container.running(
                name="vault",
                image="vault:1.3.1",
                port_bindings="8200:8200",
                environment={
                    "VAULT_DEV_ROOT_TOKEN_ID": "testsecret",
                    "VAULT_LOCAL_CONFIG": config,
                },
            )
            log.debug("docker_container.running return: %s", ret)
            container_created = ret["result"]
            time.sleep(5)
            ret = sminion.functions.cmd.run_all(
                cmd="{} login token=testsecret".format(VAULT_BINARY_PATH),
                env={"VAULT_ADDR": "http://127.0.0.1:8200"},
                hide_output=False,
            )
            if ret["retcode"] == 0:
                break
            log.debug("Vault login failed. Return: %s", ret)
            login_attempts += 1

            if login_attempts >= 3:
                raise SkipTest("unable to login to vault")

        ret = sminion.functions.cmd.retcode(
            cmd="{} policy write testpolicy {}/vault.hcl".format(
                VAULT_BINARY_PATH, RUNTIME_VARS.FILES
            ),
            env={"VAULT_ADDR": "http://127.0.0.1:8200"},
        )
        if ret != 0:
            raise SkipTest("unable to assign policy to vault")

    @classmethod
    def tearDownClass(cls):
        cls.sminion.states.docker_container.stopped(name="vault")
        cls.sminion.states.docker_container.absent(name="vault")
        cls.sminion.states.docker_image.absent(name="vault", force=True)
        cls.sminion = None

    @pytest.mark.slow_test
    def test_write_read_secret_kv2(self):
        write_return = self.run_function(
            "vault.write_secret", path="secret/my/secret", user="foo", password="bar"
        )
        # write_secret output:
        # {'created_time': '2020-01-12T23:09:34.571294241Z', 'destroyed': False,
        # 'version': 1, 'deletion_time': ''}
        expected_write = {"destroyed": False, "deletion_time": ""}
        self.assertDictContainsSubset(expected_write, write_return)

        read_return = self.run_function(
            "vault.read_secret", arg=["secret/my/secret"], metadata=True
        )
        # read_secret output:
        # {'data': {'password': 'bar', 'user': 'foo'},
        # 'metadata': {'created_time': '2020-01-12T23:07:18.829326918Z', 'destroyed': False,
        # 'version': 1, 'deletion_time': ''}}
        expected_read = {"data": {"password": "bar", "user": "foo"}}
        self.assertDictContainsSubset(expected_read, read_return)
        expected_read = {"password": "bar", "user": "foo"}
        read_return = self.run_function("vault.read_secret", arg=["secret/my/secret"])
        self.assertDictContainsSubset(expected_read, read_return)

        read_return = self.run_function(
            "vault.read_secret", arg=["secret/my/secret", "user"]
        )
        self.assertEqual(read_return, "foo")

    @pytest.mark.slow_test
    def test_list_secrets_kv2(self):
        write_return = self.run_function(
            "vault.write_secret", path="secret/my/secret", user="foo", password="bar"
        )
        expected_write = {"destroyed": False, "deletion_time": ""}
        self.assertDictContainsSubset(expected_write, write_return)

        list_return = self.run_function("vault.list_secrets", arg=["secret/my/"])
        self.assertIn("secret", list_return["keys"])

    @pytest.mark.slow_test
    def test_write_raw_read_secret_kv2(self):
        write_return = self.run_function(
            "vault.write_raw",
            path="secret/my/secret2",
            raw={"user2": "foo2", "password2": "bar2"},
        )
        expected_write = {"destroyed": False, "deletion_time": ""}
        self.assertDictContainsSubset(expected_write, write_return)

        read_return = self.run_function(
            "vault.read_secret", arg=["secret/my/secret2"], metadata=True
        )
        expected_read = {"data": {"password2": "bar2", "user2": "foo2"}}
        self.assertDictContainsSubset(expected_read, read_return)

        read_return = self.run_function("vault.read_secret", arg=["secret/my/secret2"])
        expected_read = {"password2": "bar2", "user2": "foo2"}
        self.assertDictContainsSubset(expected_read, read_return)

    @pytest.mark.slow_test
    def test_delete_secret_kv2(self):
        write_return = self.run_function(
            "vault.write_secret",
            path="secret/my/secret3",
            user3="foo3",
            password3="bar3",
        )
        expected_write = {"destroyed": False, "deletion_time": ""}
        self.assertDictContainsSubset(expected_write, write_return)

        delete_return = self.run_function(
            "vault.delete_secret", arg=["secret/my/secret3"]
        )
        self.assertEqual(delete_return, True)

    @pytest.mark.slow_test
    def test_destroy_secret_kv2(self):
        write_return = self.run_function(
            "vault.write_secret",
            path="secret/my/secret4",
            user3="foo4",
            password4="bar4",
        )
        expected_write = {"destroyed": False, "deletion_time": ""}
        self.assertDictContainsSubset(expected_write, write_return)

        destroy_return = self.run_function(
            "vault.destroy_secret", arg=["secret/my/secret4", "1"]
        )
        self.assertEqual(destroy_return, True)
        # self.assertIsNone(self.run_function('vault.read_secret', arg=['secret/my/secret4']))
        # list_return = self.run_function('vault.list_secrets', arg=['secret/my/'])
        # self.assertNotIn('secret4', list_return['keys'])
