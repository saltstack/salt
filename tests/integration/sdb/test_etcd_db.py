"""
Integration tests for the etcd modules
"""

import inspect
import logging

import salt.utils.path
from tests.support.case import ModuleCase, ShellCase
from tests.support.helpers import slowTest
from tests.support.unit import skipIf

log = logging.getLogger(__name__)


@skipIf(not salt.utils.path.which("dockerd"), "Docker not installed")
class EtcdTestCase(ModuleCase, ShellCase):
    """
    Test etcd module
    """

    count = 0

    def setUp(self):
        """
        SetUp etcd container
        """

        if EtcdTestCase.count == 0:
            self.run_state("docker_image.present", name="bitnami/etcd", tag="latest")
            self.run_state(
                "docker_container.running",
                name="etcd",
                image="bitnami/etcd:latest",
                port_bindings="2379:2379",
                environment={
                    "ALLOW_NONE_AUTHENTICATION": "yes",
                    "ETCD_ENABLE_V2": "true",
                },
                cap_add="IPC_LOCK",
            )
        EtcdTestCase.count += 1

    def tearDown(self):
        """
        TearDown etcd container
        """

        def count_tests(funcobj):
            return (
                inspect.ismethod(funcobj)
                or inspect.isfunction(funcobj)
                and funcobj.__name__.startswith("test_")
            )

        numtests = len(inspect.getmembers(EtcdTestCase, predicate=count_tests))
        if EtcdTestCase.count >= numtests:
            self.run_state("docker_container.stopped", name="etcd")
            self.run_state("docker_container.absent", name="etcd")
            self.run_state("docker_image.absent", name="bitnami/etcd", force=True)

    @slowTest
    def test_sdb(self):
        set_output = self.run_function(
            "sdb.set", uri="sdb://sdbetcd/secret/test/test_sdb/foo", value="bar"
        )
        self.assertEqual(set_output, "bar")
        get_output = self.run_function(
            "sdb.get", arg=["sdb://sdbetcd/secret/test/test_sdb/foo"]
        )
        self.assertEqual(get_output, "bar")

    @slowTest
    def test_sdb_runner(self):
        set_output = self.run_run(
            "sdb.set sdb://sdbetcd/secret/test/test_sdb_runner/foo bar"
        )
        self.assertEqual(set_output, ["bar"])
        get_output = self.run_run(
            "sdb.get sdb://sdbetcd/secret/test/test_sdb_runner/foo"
        )
        self.assertEqual(get_output, ["bar"])

    @slowTest
    def test_config(self):
        set_output = self.run_function(
            "sdb.set", uri="sdb://sdbetcd/secret/test/test_pillar_sdb/foo", value="bar"
        )
        self.assertEqual(set_output, "bar")
        get_output = self.run_function("config.get", arg=["test_etcd_pillar_sdb"])
        self.assertEqual(get_output, "bar")
