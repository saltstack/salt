# -*- coding: utf-8 -*-
"""
Integration tests for the vault execution module
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import inspect
import logging
import time

# Import Salt Libs
import salt.utils.path
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest
from tests.support.paths import FILES

# Import Salt Testing Libs
from tests.support.unit import skipIf

log = logging.getLogger(__name__)


@destructiveTest
@skipIf(not salt.utils.path.which("dockerd"), "Docker not installed")
@skipIf(not salt.utils.path.which("vault"), "Vault not installed")
class VaultTestCase(ModuleCase):
    """
    Test vault module
    """

    count = 0

    def setUp(self):
        """
        SetUp vault container
        """
        if self.count == 0:
            config = '{"backend": {"file": {"path": "/vault/file"}}, "default_lease_ttl": "168h", "max_lease_ttl": "720h", "disable_mlock": true}'
            self.run_state("docker_image.present", name="vault", tag="0.9.6")
            self.run_state(
                "docker_container.running",
                name="vault",
                image="vault:0.9.6",
                port_bindings="8200:8200",
                environment={
                    "VAULT_DEV_ROOT_TOKEN_ID": "testsecret",
                    "VAULT_LOCAL_CONFIG": config,
                },
            )
            time.sleep(5)
            ret = self.run_function(
                "cmd.retcode",
                cmd="/usr/local/bin/vault login token=testsecret",
                env={"VAULT_ADDR": "http://127.0.0.1:8200"},
            )
            if ret != 0:
                self.skipTest("unable to login to vault")
            ret = self.run_function(
                "cmd.retcode",
                cmd="/usr/local/bin/vault policy write testpolicy {0}/vault.hcl".format(
                    FILES
                ),
                env={"VAULT_ADDR": "http://127.0.0.1:8200"},
            )
            if ret != 0:
                self.skipTest("unable to assign policy to vault")
        self.count += 1

    def tearDown(self):
        """
        TearDown vault container
        """

        def count_tests(funcobj):
            return inspect.ismethod(funcobj) and funcobj.__name__.startswith("test_")

        numtests = len(inspect.getmembers(VaultTestCase, predicate=count_tests))
        if self.count >= numtests:
            self.run_state("docker_container.stopped", name="vault")
            self.run_state("docker_container.absent", name="vault")
            self.run_state("docker_image.absent", name="vault", force=True)

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


@destructiveTest
@skipIf(not salt.utils.path.which("dockerd"), "Docker not installed")
@skipIf(not salt.utils.path.which("vault"), "Vault not installed")
class VaultTestCaseCurrent(ModuleCase):
    """
    Test vault module against current vault
    """

    count = 0

    def setUp(self):
        """
        SetUp vault container
        """
        if self.count == 0:
            config = '{"backend": {"file": {"path": "/vault/file"}}, "default_lease_ttl": "168h", "max_lease_ttl": "720h", "disable_mlock": true}'
            self.run_state("docker_image.present", name="vault", tag="1.3.1")
            self.run_state(
                "docker_container.running",
                name="vault",
                image="vault:1.3.1",
                port_bindings="8200:8200",
                environment={
                    "VAULT_DEV_ROOT_TOKEN_ID": "testsecret",
                    "VAULT_LOCAL_CONFIG": config,
                },
            )
            time.sleep(5)
            ret = self.run_function(
                "cmd.retcode",
                cmd="/usr/local/bin/vault login token=testsecret",
                env={"VAULT_ADDR": "http://127.0.0.1:8200"},
            )
            if ret != 0:
                self.skipTest("unable to login to vault")
            ret = self.run_function(
                "cmd.retcode",
                cmd="/usr/local/bin/vault policy write testpolicy {0}/vault.hcl".format(
                    FILES
                ),
                env={"VAULT_ADDR": "http://127.0.0.1:8200"},
            )
            if ret != 0:
                self.skipTest("unable to assign policy to vault")
        self.count += 1

    def tearDown(self):
        """
        TearDown vault container
        """

        def count_tests(funcobj):
            return inspect.ismethod(funcobj) and funcobj.__name__.startswith("test_")

        numtests = len(inspect.getmembers(VaultTestCaseCurrent, predicate=count_tests))
        if self.count >= numtests:
            self.run_state("docker_container.stopped", name="vault")
            self.run_state("docker_container.absent", name="vault")
            self.run_state("docker_image.absent", name="vault", force=True)

    def test_write_read_secret_kv2(self):
        write_return = self.run_function(
            "vault.write_secret", path="secret/my/secret", user="foo", password="bar"
        )
        # write_secret output:
        # {'created_time': '2020-01-12T23:09:34.571294241Z', 'destroyed': False,
        # 'version': 1, 'deletion_time': ''}
        expected_write = {"destroyed": False, "deletion_time": ""}
        self.assertDictContainsSubset(expected_write, write_return)

        read_return = self.run_function("vault.read_secret", arg=["secret/my/secret"])
        # read_secret output:
        # {'data': {'password': 'bar', 'user': 'foo'},
        # 'metadata': {'created_time': '2020-01-12T23:07:18.829326918Z', 'destroyed': False,
        # 'version': 1, 'deletion_time': ''}}
        expected_read = {"data": {"password": "bar", "user": "foo"}}
        self.assertDictContainsSubset(expected_read, read_return)

        read_return = self.run_function(
            "vault.read_secret", arg=["secret/my/secret", "user"]
        )
        self.assertEqual(read_return, "foo")

    def test_list_secrets_kv2(self):
        write_return = self.run_function(
            "vault.write_secret", path="secret/my/secret", user="foo", password="bar"
        )
        expected_write = {"destroyed": False, "deletion_time": ""}
        self.assertDictContainsSubset(expected_write, write_return)

        list_return = self.run_function("vault.list_secrets", arg=["secret/my/"])
        self.assertIn("secret", list_return["keys"])

    def test_write_raw_read_secret_kv2(self):
        write_return = self.run_function(
            "vault.write_raw",
            path="secret/my/secret2",
            raw={"user2": "foo2", "password2": "bar2"},
        )
        expected_write = {"destroyed": False, "deletion_time": ""}
        self.assertDictContainsSubset(expected_write, write_return)

        read_return = self.run_function("vault.read_secret", arg=["secret/my/secret2"])
        expected_read = {"data": {"password2": "bar2", "user2": "foo2"}}
        self.assertDictContainsSubset(expected_read, read_return)

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
