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
from tests.support.helpers import destructiveTest, flaky
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
            config = '{"backend": {"file": {"path": "/vault/file"}}, "default_lease_ttl": "168h", "max_lease_ttl": "720h"}'
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
                cap_add="IPC_LOCK",
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

    @flaky
    def test_write_read_secret(self):
        assert (
            self.run_function(
                "vault.write_secret",
                path="secret/my/secret",
                user="foo",
                password="bar",
            )
            is True
        )
        assert self.run_function("vault.read_secret", arg=["secret/my/secret"]) == {
            "password": "bar",
            "user": "foo",
        }

    @flaky
    def test_write_raw_read_secret(self):
        assert (
            self.run_function(
                "vault.write_raw",
                path="secret/my/secret",
                raw={"user": "foo", "password": "bar"},
            )
            is True
        )
        assert self.run_function("vault.read_secret", arg=["secret/my/secret"]) == {
            "password": "bar",
            "user": "foo",
        }

    @flaky
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

    @flaky
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
