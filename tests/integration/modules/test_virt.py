# -*- coding: utf-8 -*-
"""
Validate the virt module
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import requires_salt_modules


@requires_salt_modules("virt.get_profiles")
class VirtTest(ModuleCase):
    """
    Test virt routines
    """

    def test_default_kvm_profile(self):
        """
        Test virt.get_profiles with the KVM profile
        """
        profiles = self.run_function("virt.get_profiles", ["kvm"])
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
        profiles = self.run_function("virt.get_profiles", ["vmware"])
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
        profiles = self.run_function("virt.get_profiles", ["xen"])
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
        profiles = self.run_function("virt.get_profiles", ["bhyve"])
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
        caps = self.run_function("virt.all_capabilities")
        self.assertIsInstance(caps, dict)
        self.assertIsInstance(caps["host"]["host"]["uuid"], str)
        self.assertEqual(36, len(caps["host"]["host"]["uuid"]))
        self.assertIn("qemu", [domainCaps["domain"] for domainCaps in caps["domains"]])
