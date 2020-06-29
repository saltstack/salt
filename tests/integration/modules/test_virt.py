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

    def test_define_xml_path(self):
        """
        Define a new domain with virt.define_xml_path,
        verify that the new domain is shown with virt.list_domains,
        remove the domain with virt.undefine, and verifies that
        domain is no longer shown with virt.list_domains.
        """
        result = self.run_function(
            "virt.define_xml_path", ["/core-vm.xml"], minion_tgt="virt_minion_0"
        )
        self.assertEqual(result, True)
        domains = self.run_function("virt.list_domains", minion_tgt="virt_minion_0")
        self.assertIsInstance(domains, list)
        self.assertEqual(domains, ["core-vm"])
        result = self.run_function("virt.undefine", ["core-vm"], minion_tgt="virt_minion_0")
        self.assertEqual(result, True)
        domains = self.run_function("virt.list_domains", minion_tgt="virt_minion_0")
        self.assertIsInstance(domains, list)
        self.assertEqual(domains, [])
