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
        nicp = profiles["nic"]["default"]
        self.assertTrue(nicp[0].get("model", "") == "virtio")
        self.assertTrue(nicp[0].get("source", "") == "br0")
        diskp = profiles["disk"]["default"]
        self.assertTrue(diskp[0]["system"].get("model", "") == "virtio")
        self.assertTrue(diskp[0]["system"].get("format", "") == "qcow2")
        self.assertTrue(diskp[0]["system"].get("size", "") == "8192")

    def test_default_esxi_profile(self):
        """
        Test virt.get_profiles with the ESX profile
        """
        profiles = self.run_function("virt.get_profiles", ["esxi"])
        nicp = profiles["nic"]["default"]
        self.assertTrue(nicp[0].get("model", "") == "e1000")
        self.assertTrue(nicp[0].get("source", "") == "DEFAULT")
        diskp = profiles["disk"]["default"]
        self.assertTrue(diskp[0]["system"].get("model", "") == "scsi")
        self.assertTrue(diskp[0]["system"].get("format", "") == "vmdk")
        self.assertTrue(diskp[0]["system"].get("size", "") == "8192")
