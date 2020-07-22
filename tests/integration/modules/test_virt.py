# -*- coding: utf-8 -*-
"""
Validate the virt module
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

from numbers import Number
from xml.etree import ElementTree

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import skip_if_binaries_missing, slowTest


@skip_if_binaries_missing("docker")
@slowTest
class VirtTest(ModuleCase):
    """
    Test virt routines
    """

    cpu_models = [
        "none",
        "armv7l",
        "armv7b",
        "aarch64",
        "i686",
        "ppc64",
        "ppc64le",
        "riscv32",
        "riscv64",
        "s390",
        "s390x",
        "x86_64",
    ]

    def test_default_kvm_profile(self):
        """
        Test virt.get_profiles with the KVM profile
        """
        profiles = self.run_function(
            "virt.get_profiles", ["kvm"], minion_tgt="virt_minion_0"
        )
        self.assertIsInstance(profiles, dict)
        nic = profiles["nic"]["default"][0]
        disk = profiles["disk"]["default"][0]

        self.assertEqual(nic["name"], "eth0")
        self.assertEqual(nic["type"], "bridge")
        self.assertEqual(nic["model"], "virtio")
        self.assertEqual(nic["source"], "br0")

        self.assertEqual(disk["name"], "system")
        self.assertEqual(disk["model"], "virtio")
        self.assertEqual(disk["size"], 8192)

    def test_default_vmware_profile(self):
        """
        Test virt.get_profiles with the VMware profile
        """
        profiles = self.run_function(
            "virt.get_profiles", ["vmware"], minion_tgt="virt_minion_0"
        )
        self.assertIsInstance(profiles, dict)
        nic = profiles["nic"]["default"][0]
        disk = profiles["disk"]["default"][0]

        self.assertEqual(nic["name"], "eth0")
        self.assertEqual(nic["type"], "bridge")
        self.assertEqual(nic["model"], "e1000")
        self.assertEqual(nic["source"], "DEFAULT")

        self.assertEqual(disk["name"], "system")
        self.assertEqual(disk["model"], "scsi")
        self.assertEqual(disk["format"], "vmdk")
        self.assertEqual(disk["size"], 8192)

    def test_default_xen_profile(self):
        """
        Test virt.get_profiles with the XEN profile
        """
        profiles = self.run_function(
            "virt.get_profiles", ["xen"], minion_tgt="virt_minion_0"
        )
        self.assertIsInstance(profiles, dict)
        nic = profiles["nic"]["default"][0]
        disk = profiles["disk"]["default"][0]

        self.assertEqual(nic["name"], "eth0")
        self.assertEqual(nic["type"], "bridge")
        self.assertEqual(nic["model"], None)
        self.assertEqual(nic["source"], "br0")

        self.assertEqual(disk["name"], "system")
        self.assertEqual(disk["model"], "xen")
        self.assertEqual(disk["size"], 8192)

    def test_default_bhyve_profile(self):
        """
        Test virt.get_profiles with the Bhyve profile
        """
        profiles = self.run_function(
            "virt.get_profiles", ["bhyve"], minion_tgt="virt_minion_0"
        )
        self.assertIsInstance(profiles, dict)
        nic = profiles["nic"]["default"][0]
        disk = profiles["disk"]["default"][0]

        self.assertEqual(nic["name"], "eth0")
        self.assertEqual(nic["type"], "bridge")
        self.assertEqual(nic["model"], "virtio")
        self.assertEqual(nic["source"], "bridge0")

        self.assertEqual(disk["name"], "system")
        self.assertEqual(disk["model"], "virtio")
        self.assertEqual(disk["format"], "raw")
        self.assertEqual(disk["sparse_volume"], False)
        self.assertEqual(disk["size"], 8192)

    def test_all_capabilities(self):
        """
        Test virt.all_capabilities
        """
        caps = self.run_function("virt.all_capabilities", minion_tgt="virt_minion_0")
        self.assertIsInstance(caps, dict)
        self.assertIsInstance(caps["host"]["host"]["uuid"], str)
        self.assertEqual(36, len(caps["host"]["host"]["uuid"]))
        self.assertIn("qemu", [domainCaps["domain"] for domainCaps in caps["domains"]])

    def test_capabilities(self):
        """
        Test virt.capabilities
        """
        caps = self.run_function("virt.capabilities", minion_tgt="virt_minion_0")
        self.assertIsInstance(caps, dict)
        self.assertIsInstance(caps["host"]["uuid"], str)
        self.assertEqual(36, len(caps["host"]["uuid"]))
        self.assertGreaterEqual(len(caps["guests"]), 1)
        self.assertIn(caps["guests"][0]["os_type"], ["hvm", "xen", "xenpvh", "exe"])

    def test_cpu_baseline(self):
        """
        Test virt.cpu_baseline
        """
        vendors = ["Intel", "ARM", "AMD"]
        cpu_baseline = self.run_function(
            "virt.cpu_baseline", out="libvirt", minion_tgt="virt_minion_0"
        )
        self.assertIsInstance(cpu_baseline, str)
        cpu_baseline = ElementTree.fromstring(cpu_baseline)
        self.assertIn(cpu_baseline.find("vendor").text, vendors)

        cpu_baseline = self.run_function(
            "virt.cpu_baseline", out="salt", minion_tgt="virt_minion_0"
        )
        self.assertIsInstance(cpu_baseline, dict)
        self.assertIn(cpu_baseline["vendor"], vendors)

    def test_freemem(self):
        """
        Test virt.freemem
        """
        available_memory = self.run_function("virt.freemem", minion_tgt="virt_minion_0")
        self.assertIsInstance(available_memory, Number)
        self.assertGreater(available_memory, 0)

    def test_freecpu(self):
        """
        Test virt.freecpu
        """
        available_cpus = self.run_function("virt.freecpu", minion_tgt="virt_minion_0")
        self.assertIsInstance(available_cpus, Number)
        self.assertGreater(available_cpus, 0)

    def test_full_info(self):
        """
        Test virt.full_info
        """
        info = self.run_function("virt.full_info", minion_tgt="virt_minion_0")
        self.assertIsInstance(info, dict)
        self.assertIsInstance(info["vm_info"], dict)

        self.assertIsInstance(info["freecpu"], Number)
        self.assertIsInstance(info["freemem"], Number)
        self.assertGreater(info["freecpu"], 0)
        self.assertGreater(info["freemem"], 0)

        self.assertIsInstance(info["node_info"], dict)
        self.assertIsInstance(info["node_info"]["cpucores"], Number)
        self.assertIsInstance(info["node_info"]["cpumhz"], Number)
        self.assertIsInstance(info["node_info"]["cpus"], Number)
        self.assertIsInstance(info["node_info"]["cputhreads"], Number)
        self.assertIsInstance(info["node_info"]["numanodes"], Number)
        self.assertIsInstance(info["node_info"]["phymemory"], Number)
        self.assertIn(info["node_info"]["cpumodel"], self.cpu_models)

    def test_node_info(self):
        """
        Test virt.node_info
        """
        info = self.run_function("virt.node_info", minion_tgt="virt_minion_0")
        self.assertIsInstance(info, dict)
        self.assertIsInstance(info["cpucores"], Number)
        self.assertIsInstance(info["cpumhz"], Number)
        self.assertIsInstance(info["cpus"], Number)
        self.assertIsInstance(info["cputhreads"], Number)
        self.assertIsInstance(info["numanodes"], Number)
        self.assertIsInstance(info["phymemory"], Number)
        self.assertIsInstance(info["sockets"], Number)
        self.assertIn(info["cpumodel"], self.cpu_models)


class VirtMinion(object):
    def __init__(self, module_case, target_name, sshd_port, tcp_port, tls_port):
        self.target_name = target_name
        self.uri = "localhost:{}".format(sshd_port)
        self.ssh_uri = "qemu+ssh://{}/system".format(self.uri)
        self.tcp_uri = "qemu+tcp://localhost:{}/system".format(tcp_port)
        self.tls_uri = "qemu+tls://localhost:{}/system".format(tls_port)
        self.module_case = module_case

    def run(self, func, args=None):
        return self.module_case.run_function(func, args or [], minion_tgt=self.target_name)

@skip_if_binaries_missing("docker")
@slowTest
class VirtMigrateTest(ModuleCase):
    def setUp(self):
        super(VirtMigrateTest, self).setUp()
        self.minion_0 = VirtMinion(
            self,
            "virt_minion_0",
            sshd_port=2201,
            tcp_port=2203,
            tls_port=2204
        )
        self.minion_1 = VirtMinion(
            self,
            "virt_minion_1",
            sshd_port=2202,
            tcp_port=2205,
            tls_port=2206
        )
        self.domain = "core-vm"
        self.skipSetUpTearDown = ["test_define_xml_path"]

        if self._testMethodName not in self.skipSetUpTearDown:
            self.minion_0.run("virt.define_xml_path", ["/core-vm.xml"])
            self.minion_0.run("virt.start", [self.domain])
            self.wait_for_all_jobs(
                minions=(
                    self.minion_0.target_name,
                    self.minion_1.target_name,
                )
            )

    def tearDown(self):
        if self._testMethodName not in self.skipSetUpTearDown:
            self.minion_0.run("virt.stop", [self.domain])
            self.minion_1.run("virt.stop", [self.domain])
            self.minion_0.run("virt.undefine", [self.domain])
            self.minion_1.run("virt.undefine", [self.domain])
            self.wait_for_all_jobs(
                minions=(
                    self.minion_0.target_name,
                    self.minion_1.target_name,
                )
            )
        super(VirtMigrateTest, self).tearDown()

    def test_define_xml_path(self):
        """
        Define a new domain with virt.define_xml_path,
        verify that the new domain is shown with virt.list_domains,
        remove the domain with virt.undefine, and verifies that
        domain is no longer shown with virt.list_domains.
        """
        result = self.minion_0.run("virt.define_xml_path", ["/core-vm.xml"])
        self.assertIsInstance(result, bool)
        self.assertTrue(result)

        domains = self.minion_0.run("virt.list_domains")
        self.assertIsInstance(domains, list)
        self.assertListEqual(domains, [self.domain])

        result = self.minion_0.run("virt.undefine", [self.domain])
        self.assertTrue(result)

        domains = self.minion_0.run("virt.list_domains")
        self.assertIsInstance(domains, list)
        self.assertListEqual(domains, [])

    def test_migration(self):
        """
        Test domain migration over SSH, TCP and TLS transport protocol
        """
        # Verify that the VM has been created
        domains = self.minion_0.run("virt.list_domains")
        self.assertIsInstance(domains, list)
        self.assertListEqual(domains, [self.domain])

        domains = self.minion_1.run("virt.list_domains")
        self.assertIsInstance(domains, list)
        self.assertListEqual(domains, [])

        # Migration over SSH
        result = self.minion_0.run(
            "virt.migrate", [self.domain, self.minion_1.uri, True],
        )
        self.assertEqual(result, True)

        # Verify that the VM has been migrated
        domains = self.minion_1.run("virt.list_domains")
        self.assertIsInstance(domains, list)
        self.assertListEqual(domains, [self.domain], "Failed to migrate domain")

        domains = self.minion_0.run("virt.list_domains")
        self.assertIsInstance(domains, list)
        self.assertListEqual(domains, [], "Failed to migrate domain")

        # Migrate over TCP
        result = self.minion_1.run(
            "virt.migrate", [self.domain, self.minion_0.tcp_uri],
        )
        self.assertEqual(result, True)

        # Verify that the VM has been migrated
        domains = self.minion_0.run("virt.list_domains")
        self.assertIsInstance(domains, list)
        self.assertListEqual(domains, [self.domain])

        domains = self.minion_1.run("virt.list_domains")
        self.assertIsInstance(domains, list)
        self.assertListEqual(domains, [])

        # Migrate over TLS
        result = self.minion_0.run(
            "virt.migrate", [self.domain, self.minion_1.tls_uri],
        )
        self.assertEqual(result, True)

        # Verify that the VM has been migrated
        domains = self.minion_1.run("virt.list_domains")
        self.assertIsInstance(domains, list)
        self.assertListEqual(domains, [self.domain])

        domains = self.minion_0.run("virt.list_domains")
        self.assertIsInstance(domains, list)
        self.assertListEqual(domains, [])
