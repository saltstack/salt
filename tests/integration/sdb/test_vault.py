"""
Integration tests for the vault modules
"""

import inspect
import logging
import time

import salt.utils.path
from tests.support.case import ModuleCase, ShellCase
from tests.support.helpers import destructiveTest, flaky, slowTest
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf

log = logging.getLogger(__name__)


@skipIf(not salt.utils.path.which("dockerd"), "Docker not installed")
@skipIf(not salt.utils.path.which("vault"), "Vault not installed")
class VaultTestCase(ModuleCase, ShellCase):
    """
    Test vault module
    """

    count = 0

    def setUp(self):
        """
        SetUp vault container
        """

        vault_binary = salt.utils.path.which("vault")
        if VaultTestCase.count == 0:
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
                cmd="{} login token=testsecret".format(vault_binary),
                env={"VAULT_ADDR": "http://127.0.0.1:8200"},
            )
            login_attempts = 1
            # If the login failed, container might have stopped
            # attempt again, maximum of three times before
            # skipping.
            while ret != 0:
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
                    cmd="{} login token=testsecret".format(vault_binary),
                    env={"VAULT_ADDR": "http://127.0.0.1:8200"},
                )
                login_attempts += 1
                if login_attempts >= 3:
                    self.skipTest("unable to login to vault")
            ret = self.run_function(
                "cmd.retcode",
                cmd="{} policy write testpolicy {}/vault.hcl".format(
                    vault_binary, RUNTIME_VARS.FILES
                ),
                env={"VAULT_ADDR": "http://127.0.0.1:8200"},
            )
            if ret != 0:
                self.skipTest("unable to assign policy to vault")
        VaultTestCase.count += 1

    def tearDown(self):
        """
        TearDown vault container
        """

        def count_tests(funcobj):
            return (
                inspect.ismethod(funcobj)
                or inspect.isfunction(funcobj)
                and funcobj.__name__.startswith("test_")
            )

        numtests = len(inspect.getmembers(VaultTestCase, predicate=count_tests))
        if VaultTestCase.count >= numtests:
            self.run_state("docker_container.stopped", name="vault")
            self.run_state("docker_container.absent", name="vault")
            self.run_state("docker_image.absent", name="vault", force=True)

    @flaky
    @slowTest
    def test_sdb(self):
        set_output = self.run_function(
            "sdb.set", uri="sdb://sdbvault/secret/test/test_sdb/foo", value="bar"
        )
        self.assertEqual(set_output, True)
        get_output = self.run_function(
            "sdb.get", arg=["sdb://sdbvault/secret/test/test_sdb/foo"]
        )
        self.assertEqual(get_output, "bar")

    @flaky
    @slowTest
    def test_sdb_runner(self):
        set_output = self.run_run(
            "sdb.set sdb://sdbvault/secret/test/test_sdb_runner/foo bar"
        )
        self.assertEqual(set_output, ["True"])
        get_output = self.run_run(
            "sdb.get sdb://sdbvault/secret/test/test_sdb_runner/foo"
        )
        self.assertEqual(get_output, ["bar"])

    @flaky
    @slowTest
    def test_config(self):
        set_output = self.run_function(
            "sdb.set", uri="sdb://sdbvault/secret/test/test_pillar_sdb/foo", value="bar"
        )
        self.assertEqual(set_output, True)
        get_output = self.run_function("config.get", arg=["test_vault_pillar_sdb"])
        self.assertEqual(get_output, "bar")


@destructiveTest
@skipIf(not salt.utils.path.which("dockerd"), "Docker not installed")
@skipIf(not salt.utils.path.which("vault"), "Vault not installed")
class VaultTestCaseCurrent(ModuleCase, ShellCase):
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
                cap_add="IPC_LOCK",
            )
            time.sleep(5)
            ret = self.run_function(
                "cmd.retcode",
                cmd="/usr/local/bin/vault login token=testsecret",
                env={"VAULT_ADDR": "http://127.0.0.1:8200"},
            )
            login_attempts = 1
            # If the login failed, container might have stopped
            # attempt again, maximum of three times before
            # skipping.
            while ret != 0:
                self.run_state(
                    "docker_container.running",
                    name="vault",
                    image="vault:1.3.1",
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
                login_attempts += 1
                if login_attempts >= 3:
                    self.skipTest("unable to login to vault")
            ret = self.run_function(
                "cmd.retcode",
                cmd="/usr/local/bin/vault policy write testpolicy {}/vault.hcl".format(
                    RUNTIME_VARS.FILES
                ),
                env={"VAULT_ADDR": "http://127.0.0.1:8200"},
            )
            if ret != 0:
                self.skipTest("unable to assign policy to vault")
            ret = self.run_function(
                "cmd.run",
                cmd="/usr/local/bin/vault secrets enable kv-v2",
                env={"VAULT_ADDR": "http://127.0.0.1:8200"},
            )
            if "path is already in use at kv-v2/" in ret:
                pass
            elif "Success" in ret:
                pass
            else:
                self.skipTest("unable to enable kv-v2 {}".format(ret))
        self.count += 1

    def tearDown(self):
        """
        TearDown vault container
        """

        def count_tests(funcobj):
            return (
                inspect.ismethod(funcobj)
                or inspect.isfunction(funcobj)
                and funcobj.__name__.startswith("test_")
            )

        numtests = len(inspect.getmembers(VaultTestCaseCurrent, predicate=count_tests))
        if self.count >= numtests:
            self.run_state("docker_container.stopped", name="vault")
            self.run_state("docker_container.absent", name="vault")
            self.run_state("docker_image.absent", name="vault", force=True)

    @flaky
    @slowTest
    def test_sdb_kv2(self):
        set_output = self.run_function(
            "sdb.set", uri="sdb://sdbvault/secret/test/test_sdb/foo", value="bar"
        )
        self.assertEqual(set_output, True)
        get_output = self.run_function(
            "sdb.get", arg=["sdb://sdbvault/secret/test/test_sdb/foo"]
        )
        self.assertEqual(get_output, "bar")

    @flaky
    @slowTest
    def test_sdb_kv2_kvv2_path_local(self):
        set_output = self.run_function(
            "sdb.set", uri="sdb://sdbvault/kv-v2/test/test_sdb/foo", value="bar"
        )
        self.assertEqual(set_output, True)
        import copy

        opts = copy.copy(self.minion_opts)
        get_output = ShellCase.run_function(
            self,
            function="sdb.get",
            arg=["sdb://sdbvault/kv-v2/test/test_sdb/foo"],
            local=True,
        )
        self.assertEqual(get_output[1], "    bar")

    @flaky
    @slowTest
    def test_sdb_runner_kv2(self):
        set_output = self.run_run(
            "sdb.set sdb://sdbvault/secret/test/test_sdb_runner/foo bar"
        )
        self.assertEqual(set_output, ["True"])
        get_output = self.run_run(
            "sdb.get sdb://sdbvault/secret/test/test_sdb_runner/foo"
        )
        self.assertEqual(get_output, ["bar"])

    @flaky
    @slowTest
    def test_config_kv2(self):
        set_output = self.run_function(
            "sdb.set", uri="sdb://sdbvault/secret/test/test_pillar_sdb/foo", value="bar"
        )
        self.assertEqual(set_output, True)
        get_output = self.run_function("config.get", arg=["test_vault_pillar_sdb"])
        self.assertEqual(get_output, "bar")
