"""
virt execution module unit tests
"""

# pylint: disable=3rd-party-module-not-gated


import datetime
import os
import shutil
import tempfile

import salt.config
import salt.modules.config as config
import salt.modules.virt as virt
import salt.syspaths
import salt.utils.yaml
from salt._compat import ElementTree as ET
from salt.exceptions import CommandExecutionError, SaltInvocationError

# pylint: disable=import-error
from salt.ext.six.moves import range  # pylint: disable=redefined-builtin
from tests.support.helpers import dedent
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

# pylint: disable=invalid-name,protected-access,attribute-defined-outside-init,too-many-public-methods,unused-argument


class LibvirtMock(MagicMock):  # pylint: disable=too-many-ancestors
    """
    Libvirt library mock
    """

    class virDomain(MagicMock):
        """
        virDomain mock
        """

    class libvirtError(Exception):
        """
        libvirtError mock
        """

        def __init__(self, msg):
            super().__init__(msg)
            self.msg = msg

        def get_error_message(self):
            return self.msg


class VirtTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.module.virt
    """

    def setup_loader_modules(self):
        self.mock_libvirt = LibvirtMock()
        self.mock_conn = MagicMock()
        self.mock_conn.getStoragePoolCapabilities.return_value = (
            "<storagepoolCapabilities/>"
        )
        self.mock_libvirt.openAuth.return_value = self.mock_conn
        self.mock_popen = MagicMock()
        self.addCleanup(delattr, self, "mock_libvirt")
        self.addCleanup(delattr, self, "mock_conn")
        self.addCleanup(delattr, self, "mock_popen")
        self.mock_subprocess = MagicMock()
        self.mock_subprocess.return_value = (
            self.mock_subprocess
        )  # pylint: disable=no-member
        self.mock_subprocess.Popen.return_value = (
            self.mock_popen
        )  # pylint: disable=no-member
        loader_globals = {
            "__salt__": {"config.get": config.get, "config.option": config.option},
            "libvirt": self.mock_libvirt,
            "subprocess": self.mock_subprocess,
        }
        return {virt: loader_globals, config: loader_globals}

    def set_mock_vm(self, name, xml):
        """
        Define VM to use in tests
        """
        self.mock_conn.listDefinedDomains.return_value = [
            name
        ]  # pylint: disable=no-member
        mock_domain = self.mock_libvirt.virDomain()
        self.mock_conn.lookupByName.return_value = (
            mock_domain  # pylint: disable=no-member
        )
        mock_domain.XMLDesc.return_value = xml  # pylint: disable=no-member

        # Return state as shutdown
        mock_domain.info.return_value = [
            4,
            2048 * 1024,
            1024 * 1024,
            2,
            1234,
        ]  # pylint: disable=no-member
        mock_domain.ID.return_value = 1
        mock_domain.name.return_value = name
        return mock_domain

    def test_disk_profile_merge(self):
        """
        Test virt._disk_profile() when merging with user-defined disks
        """
        root_dir = os.path.join(salt.syspaths.ROOT_DIR, "srv", "salt-images")
        userdisks = [
            {"name": "system", "image": "/path/to/image"},
            {"name": "data", "size": 16384, "format": "raw"},
        ]

        disks = virt._disk_profile(self.mock_conn, "default", "kvm", userdisks, "myvm")
        self.assertEqual(
            [
                {
                    "name": "system",
                    "device": "disk",
                    "size": 8192,
                    "format": "qcow2",
                    "model": "virtio",
                    "filename": "myvm_system.qcow2",
                    "image": "/path/to/image",
                    "source_file": "{}{}myvm_system.qcow2".format(root_dir, os.sep),
                },
                {
                    "name": "data",
                    "device": "disk",
                    "size": 16384,
                    "format": "raw",
                    "model": "virtio",
                    "filename": "myvm_data.raw",
                    "source_file": "{}{}myvm_data.raw".format(root_dir, os.sep),
                },
            ],
            disks,
        )

    def test_boot_default_dev(self):
        """
        Test virt._gen_xml() default boot device
        """
        diskp = virt._disk_profile(self.mock_conn, "default", "kvm", [], "hello")
        nicp = virt._nic_profile("default", "kvm")
        xml_data = virt._gen_xml(
            self.mock_conn, "hello", 1, 512, diskp, nicp, "kvm", "hvm", "x86_64"
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("os/boot").attrib["dev"], "hd")
        self.assertEqual(root.find("os/type").attrib["arch"], "x86_64")
        self.assertEqual(root.find("os/type").text, "hvm")

    def test_boot_custom_dev(self):
        """
        Test virt._gen_xml() custom boot device
        """
        diskp = virt._disk_profile(self.mock_conn, "default", "kvm", [], "hello")
        nicp = virt._nic_profile("default", "kvm")
        xml_data = virt._gen_xml(
            self.mock_conn,
            "hello",
            1,
            512,
            diskp,
            nicp,
            "kvm",
            "hvm",
            "x86_64",
            boot_dev="cdrom",
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("os/boot").attrib["dev"], "cdrom")

    def test_boot_multiple_devs(self):
        """
        Test virt._gen_xml() multiple boot devices
        """
        diskp = virt._disk_profile(self.mock_conn, "default", "kvm", [], "hello")
        nicp = virt._nic_profile("default", "kvm")
        xml_data = virt._gen_xml(
            self.mock_conn,
            "hello",
            1,
            512,
            diskp,
            nicp,
            "kvm",
            "hvm",
            "x86_64",
            boot_dev="cdrom network",
        )
        root = ET.fromstring(xml_data)
        devs = root.findall(".//boot")
        self.assertTrue(len(devs) == 2)

    def test_gen_xml_no_nic(self):
        """
        Test virt._gen_xml() serial console
        """
        diskp = virt._disk_profile(self.mock_conn, "default", "kvm", [], "hello")
        nicp = virt._nic_profile("default", "kvm")
        xml_data = virt._gen_xml(
            self.mock_conn,
            "hello",
            1,
            512,
            diskp,
            nicp,
            "kvm",
            "hvm",
            "x86_64",
            serial_type="pty",
            console=True,
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("devices/serial").attrib["type"], "pty")
        self.assertEqual(root.find("devices/console").attrib["type"], "pty")

    def test_gen_xml_for_serial_console(self):
        """
        Test virt._gen_xml() serial console
        """
        diskp = virt._disk_profile(self.mock_conn, "default", "kvm", [], "hello")
        nicp = virt._nic_profile("default", "kvm")
        xml_data = virt._gen_xml(
            self.mock_conn,
            "hello",
            1,
            512,
            diskp,
            nicp,
            "kvm",
            "hvm",
            "x86_64",
            serial_type="pty",
            console=True,
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("devices/serial").attrib["type"], "pty")
        self.assertEqual(root.find("devices/console").attrib["type"], "pty")

    def test_gen_xml_for_telnet_console(self):
        """
        Test virt._gen_xml() telnet console
        """
        diskp = virt._disk_profile(self.mock_conn, "default", "kvm", [], "hello")
        nicp = virt._nic_profile("default", "kvm")
        xml_data = virt._gen_xml(
            self.mock_conn,
            "hello",
            1,
            512,
            diskp,
            nicp,
            "kvm",
            "hvm",
            "x86_64",
            serial_type="tcp",
            console=True,
            telnet_port=22223,
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("devices/serial").attrib["type"], "tcp")
        self.assertEqual(root.find("devices/console").attrib["type"], "tcp")
        self.assertEqual(root.find("devices/console/source").attrib["service"], "22223")

    def test_gen_xml_for_telnet_console_unspecified_port(self):
        """
        Test virt._gen_xml() telnet console without any specified port
        """
        diskp = virt._disk_profile(self.mock_conn, "default", "kvm", [], "hello")
        nicp = virt._nic_profile("default", "kvm")
        xml_data = virt._gen_xml(
            self.mock_conn,
            "hello",
            1,
            512,
            diskp,
            nicp,
            "kvm",
            "hvm",
            "x86_64",
            serial_type="tcp",
            console=True,
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("devices/serial").attrib["type"], "tcp")
        self.assertEqual(root.find("devices/console").attrib["type"], "tcp")
        self.assertIsInstance(
            int(root.find("devices/console/source").attrib["service"]), int
        )

    def test_gen_xml_for_serial_no_console(self):
        """
        Test virt._gen_xml() with no serial console
        """
        diskp = virt._disk_profile(self.mock_conn, "default", "kvm", [], "hello")
        nicp = virt._nic_profile("default", "kvm")
        xml_data = virt._gen_xml(
            self.mock_conn,
            "hello",
            1,
            512,
            diskp,
            nicp,
            "kvm",
            "hvm",
            "x86_64",
            serial_type="pty",
            console=False,
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("devices/serial").attrib["type"], "pty")
        self.assertEqual(root.find("devices/console"), None)

    def test_gen_xml_for_telnet_no_console(self):
        """
        Test virt._gen_xml() with no telnet console
        """
        diskp = virt._disk_profile(self.mock_conn, "default", "kvm", [], "hello")
        nicp = virt._nic_profile("default", "kvm")
        xml_data = virt._gen_xml(
            self.mock_conn,
            "hello",
            1,
            512,
            diskp,
            nicp,
            "kvm",
            "hvm",
            "x86_64",
            serial_type="tcp",
            console=False,
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("devices/serial").attrib["type"], "tcp")
        self.assertEqual(root.find("devices/console"), None)

    def test_gen_xml_nographics_default(self):
        """
        Test virt._gen_xml() with default no graphics device
        """
        diskp = virt._disk_profile(self.mock_conn, "default", "kvm", [], "hello")
        nicp = virt._nic_profile("default", "kvm")
        xml_data = virt._gen_xml(
            self.mock_conn, "hello", 1, 512, diskp, nicp, "kvm", "hvm", "x86_64"
        )
        root = ET.fromstring(xml_data)
        self.assertIsNone(root.find("devices/graphics"))

    def test_gen_xml_noloader_default(self):
        """
        Test virt._gen_xml() with default no loader
        """
        diskp = virt._disk_profile(self.mock_conn, "default", "kvm", [], "hello")
        nicp = virt._nic_profile("default", "kvm")
        xml_data = virt._gen_xml(
            self.mock_conn, "hello", 1, 512, diskp, nicp, "kvm", "hvm", "x86_64"
        )
        root = ET.fromstring(xml_data)
        self.assertIsNone(root.find("os/loader"))

    def test_gen_xml_vnc_default(self):
        """
        Test virt._gen_xml() with default vnc graphics device
        """
        diskp = virt._disk_profile(self.mock_conn, "default", "kvm", [], "hello")
        nicp = virt._nic_profile("default", "kvm")
        xml_data = virt._gen_xml(
            self.mock_conn,
            "hello",
            1,
            512,
            diskp,
            nicp,
            "kvm",
            "hvm",
            "x86_64",
            graphics={
                "type": "vnc",
                "port": 1234,
                "tlsPort": 5678,
                "listen": {"type": "address", "address": "myhost"},
            },
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("devices/graphics").attrib["type"], "vnc")
        self.assertEqual(root.find("devices/graphics").attrib["autoport"], "no")
        self.assertEqual(root.find("devices/graphics").attrib["port"], "1234")
        self.assertFalse("tlsPort" in root.find("devices/graphics").attrib)
        self.assertEqual(root.find("devices/graphics").attrib["listen"], "myhost")
        self.assertEqual(root.find("devices/graphics/listen").attrib["type"], "address")
        self.assertEqual(
            root.find("devices/graphics/listen").attrib["address"], "myhost"
        )

    def test_gen_xml_spice_default(self):
        """
        Test virt._gen_xml() with default spice graphics device
        """
        diskp = virt._disk_profile(self.mock_conn, "default", "kvm", [], "hello")
        nicp = virt._nic_profile("default", "kvm")
        xml_data = virt._gen_xml(
            self.mock_conn,
            "hello",
            1,
            512,
            diskp,
            nicp,
            "kvm",
            "hvm",
            "x86_64",
            graphics={"type": "spice"},
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("devices/graphics").attrib["type"], "spice")
        self.assertEqual(root.find("devices/graphics").attrib["autoport"], "yes")
        self.assertEqual(root.find("devices/graphics").attrib["listen"], "0.0.0.0")
        self.assertEqual(root.find("devices/graphics/listen").attrib["type"], "address")
        self.assertEqual(
            root.find("devices/graphics/listen").attrib["address"], "0.0.0.0"
        )

    def test_gen_xml_spice(self):
        """
        Test virt._gen_xml() with spice graphics device
        """
        diskp = virt._disk_profile(self.mock_conn, "default", "kvm", [], "hello")
        nicp = virt._nic_profile("default", "kvm")
        xml_data = virt._gen_xml(
            self.mock_conn,
            "hello",
            1,
            512,
            diskp,
            nicp,
            "kvm",
            "hvm",
            "x86_64",
            graphics={
                "type": "spice",
                "port": 1234,
                "tls_port": 5678,
                "listen": {"type": "none"},
            },
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("devices/graphics").attrib["type"], "spice")
        self.assertEqual(root.find("devices/graphics").attrib["autoport"], "no")
        self.assertEqual(root.find("devices/graphics").attrib["port"], "1234")
        self.assertEqual(root.find("devices/graphics").attrib["tlsPort"], "5678")
        self.assertFalse("listen" in root.find("devices/graphics").attrib)
        self.assertEqual(root.find("devices/graphics/listen").attrib["type"], "none")
        self.assertFalse("address" in root.find("devices/graphics/listen").attrib)

    def test_default_disk_profile_hypervisor_esxi(self):
        """
        Test virt._disk_profile() default ESXi profile
        """
        mock = MagicMock(return_value={})
        with patch.dict(
            virt.__salt__, {"config.get": mock}  # pylint: disable=no-member
        ):
            ret = virt._disk_profile(
                self.mock_conn, "nonexistent", "vmware", None, "test-vm"
            )
            self.assertTrue(len(ret) == 1)
            found = [disk for disk in ret if disk["name"] == "system"]
            self.assertTrue(bool(found))
            system = found[0]
            self.assertEqual(system["format"], "vmdk")
            self.assertEqual(system["model"], "scsi")
            self.assertTrue(int(system["size"]) >= 1)

    def test_default_disk_profile_hypervisor_kvm(self):
        """
        Test virt._disk_profile() default KVM profile
        """
        mock = MagicMock(side_effect=[{}, "/images/dir"])
        with patch.dict(
            virt.__salt__, {"config.get": mock}  # pylint: disable=no-member
        ):
            ret = virt._disk_profile(
                self.mock_conn, "nonexistent", "kvm", None, "test-vm"
            )
            self.assertTrue(len(ret) == 1)
            found = [disk for disk in ret if disk["name"] == "system"]
            self.assertTrue(bool(found))
            system = found[0]
            self.assertEqual(system["format"], "qcow2")
            self.assertEqual(system["model"], "virtio")
            self.assertTrue(int(system["size"]) >= 1)

    def test_default_disk_profile_hypervisor_xen(self):
        """
        Test virt._disk_profile() default XEN profile
        """
        mock = MagicMock(side_effect=[{}, "/images/dir"])
        with patch.dict(
            virt.__salt__, {"config.get": mock}  # pylint: disable=no-member
        ):
            ret = virt._disk_profile(
                self.mock_conn, "nonexistent", "xen", None, "test-vm"
            )
            self.assertTrue(len(ret) == 1)
            found = [disk for disk in ret if disk["name"] == "system"]
            self.assertTrue(bool(found))
            system = found[0]
            self.assertEqual(system["format"], "qcow2")
            self.assertEqual(system["model"], "xen")
            self.assertTrue(int(system["size"]) >= 1)

    def test_default_nic_profile_hypervisor_esxi(self):
        """
        Test virt._nic_profile() default ESXi profile
        """
        mock = MagicMock(return_value={})
        with patch.dict(
            virt.__salt__, {"config.get": mock}  # pylint: disable=no-member
        ):
            ret = virt._nic_profile("nonexistent", "vmware")
            self.assertTrue(len(ret) == 1)
            eth0 = ret[0]
            self.assertEqual(eth0["name"], "eth0")
            self.assertEqual(eth0["type"], "bridge")
            self.assertEqual(eth0["source"], "DEFAULT")
            self.assertEqual(eth0["model"], "e1000")

    def test_default_nic_profile_hypervisor_kvm(self):
        """
        Test virt._nic_profile() default KVM profile
        """
        mock = MagicMock(return_value={})
        with patch.dict(
            virt.__salt__, {"config.get": mock}  # pylint: disable=no-member
        ):
            ret = virt._nic_profile("nonexistent", "kvm")
            self.assertTrue(len(ret) == 1)
            eth0 = ret[0]
            self.assertEqual(eth0["name"], "eth0")
            self.assertEqual(eth0["type"], "bridge")
            self.assertEqual(eth0["source"], "br0")
            self.assertEqual(eth0["model"], "virtio")

    def test_default_nic_profile_hypervisor_xen(self):
        """
        Test virt._nic_profile() default XEN profile
        """
        mock = MagicMock(return_value={})
        with patch.dict(
            virt.__salt__, {"config.get": mock}  # pylint: disable=no-member
        ):
            ret = virt._nic_profile("nonexistent", "xen")
            self.assertTrue(len(ret) == 1)
            eth0 = ret[0]
            self.assertEqual(eth0["name"], "eth0")
            self.assertEqual(eth0["type"], "bridge")
            self.assertEqual(eth0["source"], "br0")
            self.assertFalse(eth0["model"])

    def test_gen_vol_xml_esx(self):
        """
        Test virt._get_vol_xml() for the ESX case
        """
        xml_data = virt._gen_vol_xml("vmname/system.vmdk", 8192, format="vmdk")
        root = ET.fromstring(xml_data)
        self.assertIsNone(root.get("type"))
        self.assertEqual(root.find("name").text, "vmname/system.vmdk")
        self.assertEqual(root.find("capacity").attrib["unit"], "KiB")
        self.assertEqual(root.find("capacity").text, str(8192 * 1024))
        self.assertEqual(root.find("allocation").text, str(0))
        self.assertEqual(root.find("target/format").get("type"), "vmdk")
        self.assertIsNone(root.find("target/permissions"))
        self.assertIsNone(root.find("target/nocow"))
        self.assertIsNone(root.find("backingStore"))

    def test_gen_vol_xml_file(self):
        """
        Test virt._get_vol_xml() for a file volume
        """
        xml_data = virt._gen_vol_xml(
            "myvm_system.qcow2",
            8192,
            format="qcow2",
            allocation=4096,
            type="file",
            permissions={
                "mode": "0775",
                "owner": "123",
                "group": "456",
                "label": "sec_label",
            },
            backing_store={"path": "/backing/image", "format": "raw"},
            nocow=True,
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.get("type"), "file")
        self.assertEqual(root.find("name").text, "myvm_system.qcow2")
        self.assertIsNone(root.find("key"))
        self.assertIsNone(root.find("target/path"))
        self.assertEqual(root.find("target/format").get("type"), "qcow2")
        self.assertEqual(root.find("capacity").attrib["unit"], "KiB")
        self.assertEqual(root.find("capacity").text, str(8192 * 1024))
        self.assertEqual(root.find("capacity").attrib["unit"], "KiB")
        self.assertEqual(root.find("allocation").text, str(4096 * 1024))
        self.assertEqual(root.find("target/permissions/mode").text, "0775")
        self.assertEqual(root.find("target/permissions/owner").text, "123")
        self.assertEqual(root.find("target/permissions/group").text, "456")
        self.assertEqual(root.find("target/permissions/label").text, "sec_label")
        self.assertIsNotNone(root.find("target/nocow"))
        self.assertEqual(root.find("backingStore/path").text, "/backing/image")
        self.assertEqual(root.find("backingStore/format").get("type"), "raw")

    def test_gen_xml_for_kvm_default_profile(self):
        """
        Test virt._gen_xml(), KVM default profile case
        """
        diskp = virt._disk_profile(self.mock_conn, "default", "kvm", [], "hello")
        nicp = virt._nic_profile("default", "kvm")
        xml_data = virt._gen_xml(
            self.mock_conn, "hello", 1, 512, diskp, nicp, "kvm", "hvm", "x86_64",
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.attrib["type"], "kvm")
        self.assertEqual(root.find("vcpu").text, "1")
        self.assertEqual(root.find("memory").text, str(512 * 1024))
        self.assertEqual(root.find("memory").attrib["unit"], "KiB")

        disks = root.findall(".//disk")
        self.assertEqual(len(disks), 1)
        disk = disks[0]
        root_dir = salt.config.DEFAULT_MINION_OPTS.get("root_dir")
        self.assertTrue(disk.find("source").attrib["file"].startswith(root_dir))
        self.assertTrue("hello_system" in disk.find("source").attrib["file"])
        self.assertEqual(disk.find("target").attrib["dev"], "vda")
        self.assertEqual(disk.find("target").attrib["bus"], "virtio")
        self.assertEqual(disk.find("driver").attrib["name"], "qemu")
        self.assertEqual(disk.find("driver").attrib["type"], "qcow2")

        interfaces = root.findall(".//interface")
        self.assertEqual(len(interfaces), 1)
        iface = interfaces[0]
        self.assertEqual(iface.attrib["type"], "bridge")
        self.assertEqual(iface.find("source").attrib["bridge"], "br0")
        self.assertEqual(iface.find("model").attrib["type"], "virtio")

    def test_gen_xml_for_esxi_default_profile(self):
        """
        Test virt._gen_xml(), ESXi/vmware default profile case
        """
        diskp = virt._disk_profile(self.mock_conn, "default", "vmware", [], "hello")
        nicp = virt._nic_profile("default", "vmware")
        xml_data = virt._gen_xml(
            self.mock_conn, "hello", 1, 512, diskp, nicp, "vmware", "hvm", "x86_64",
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.attrib["type"], "vmware")
        self.assertEqual(root.find("vcpu").text, "1")
        self.assertEqual(root.find("memory").text, str(512 * 1024))
        self.assertEqual(root.find("memory").attrib["unit"], "KiB")

        disks = root.findall(".//disk")
        self.assertEqual(len(disks), 1)
        disk = disks[0]
        self.assertTrue("[0]" in disk.find("source").attrib["file"])
        self.assertTrue("hello_system" in disk.find("source").attrib["file"])
        self.assertEqual(disk.find("target").attrib["dev"], "sda")
        self.assertEqual(disk.find("target").attrib["bus"], "scsi")
        self.assertEqual(disk.find("address").attrib["unit"], "0")

        interfaces = root.findall(".//interface")
        self.assertEqual(len(interfaces), 1)
        iface = interfaces[0]
        self.assertEqual(iface.attrib["type"], "bridge")
        self.assertEqual(iface.find("source").attrib["bridge"], "DEFAULT")
        self.assertEqual(iface.find("model").attrib["type"], "e1000")

    def test_gen_xml_for_xen_default_profile(self):
        """
        Test virt._gen_xml(), XEN PV default profile case
        """
        diskp = virt._disk_profile(self.mock_conn, "default", "xen", [], "hello")
        nicp = virt._nic_profile("default", "xen")
        with patch.dict(
            virt.__grains__, {"os_family": "Suse"}  # pylint: disable=no-member
        ):
            xml_data = virt._gen_xml(
                self.mock_conn,
                "hello",
                1,
                512,
                diskp,
                nicp,
                "xen",
                "xen",
                "x86_64",
                boot=None,
            )
            root = ET.fromstring(xml_data)
            self.assertEqual(root.attrib["type"], "xen")
            self.assertEqual(root.find("vcpu").text, "1")
            self.assertEqual(root.find("memory").text, str(512 * 1024))
            self.assertEqual(root.find("memory").attrib["unit"], "KiB")
            self.assertEqual(
                root.find(".//kernel").text, "/usr/lib/grub2/x86_64-xen/grub.xen"
            )

            disks = root.findall(".//disk")
            self.assertEqual(len(disks), 1)
            disk = disks[0]
            root_dir = salt.config.DEFAULT_MINION_OPTS.get("root_dir")
            self.assertTrue(disk.find("source").attrib["file"].startswith(root_dir))
            self.assertTrue("hello_system" in disk.find("source").attrib["file"])
            self.assertEqual(disk.find("target").attrib["dev"], "xvda")
            self.assertEqual(disk.find("target").attrib["bus"], "xen")
            self.assertEqual(disk.find("driver").attrib["name"], "qemu")
            self.assertEqual(disk.find("driver").attrib["type"], "qcow2")

            interfaces = root.findall(".//interface")
            self.assertEqual(len(interfaces), 1)
            iface = interfaces[0]
            self.assertEqual(iface.attrib["type"], "bridge")
            self.assertEqual(iface.find("source").attrib["bridge"], "br0")
            self.assertIsNone(iface.find("model"))

    def test_gen_xml_for_esxi_custom_profile(self):
        """
        Test virt._gen_xml(), ESXi/vmware custom profile case
        """
        disks = {
            "noeffect": [
                {"first": {"size": 8192, "pool": "datastore1"}},
                {"second": {"size": 4096, "pool": "datastore2"}},
            ]
        }
        nics = {
            "noeffect": [
                {"name": "eth1", "source": "ONENET"},
                {"name": "eth2", "source": "TWONET"},
            ]
        }
        with patch.dict(
            virt.__salt__,  # pylint: disable=no-member
            {"config.get": MagicMock(side_effect=[disks, nics])},
        ):
            diskp = virt._disk_profile(
                self.mock_conn, "noeffect", "vmware", [], "hello"
            )
            nicp = virt._nic_profile("noeffect", "vmware")
            xml_data = virt._gen_xml(
                self.mock_conn, "hello", 1, 512, diskp, nicp, "vmware", "hvm", "x86_64",
            )
            root = ET.fromstring(xml_data)
            self.assertEqual(root.attrib["type"], "vmware")
            self.assertEqual(root.find("vcpu").text, "1")
            self.assertEqual(root.find("memory").text, str(512 * 1024))
            self.assertEqual(root.find("memory").attrib["unit"], "KiB")
            self.assertTrue(len(root.findall(".//disk")) == 2)
            self.assertTrue(len(root.findall(".//interface")) == 2)

    def test_gen_xml_for_kvm_custom_profile(self):
        """
        Test virt._gen_xml(), KVM custom profile case
        """
        disks = {
            "noeffect": [
                {"first": {"size": 8192, "pool": "/var/lib/images"}},
                {"second": {"size": 4096, "pool": "/var/lib/images"}},
            ]
        }
        nics = {
            "noeffect": [
                {"name": "eth1", "source": "b2"},
                {"name": "eth2", "source": "b2"},
            ]
        }
        with patch.dict(
            virt.__salt__,  # pylint: disable=no-member
            {"config.get": MagicMock(side_effect=[disks, nics])},
        ):
            diskp = virt._disk_profile(self.mock_conn, "noeffect", "kvm", [], "hello")
            nicp = virt._nic_profile("noeffect", "kvm")
            xml_data = virt._gen_xml(
                self.mock_conn, "hello", 1, 512, diskp, nicp, "kvm", "hvm", "x86_64",
            )
            root = ET.fromstring(xml_data)
            self.assertEqual(root.attrib["type"], "kvm")
            self.assertEqual(root.find("vcpu").text, "1")
            self.assertEqual(root.find("memory").text, str(512 * 1024))
            self.assertEqual(root.find("memory").attrib["unit"], "KiB")
            disks = root.findall(".//disk")
            self.assertTrue(len(disks) == 2)
            self.assertEqual(disks[0].find("target").get("dev"), "vda")
            self.assertEqual(disks[1].find("target").get("dev"), "vdb")
            self.assertTrue(len(root.findall(".//interface")) == 2)

    def test_disk_profile_kvm_disk_pool(self):
        """
        Test virt._disk_profile(), KVM case with pools defined.
        """
        disks = {
            "noeffect": [
                {"first": {"size": 8192, "pool": "mypool"}},
                {"second": {"size": 4096}},
            ]
        }

        # pylint: disable=no-member
        with patch.dict(
            virt.__salt__,
            {
                "config.get": MagicMock(
                    side_effect=[
                        disks,
                        os.path.join(salt.syspaths.ROOT_DIR, "default", "path"),
                    ]
                )
            },
        ):

            diskp = virt._disk_profile(self.mock_conn, "noeffect", "kvm", [], "hello")

            pools_path = (
                os.path.join(salt.syspaths.ROOT_DIR, "pools", "mypool") + os.sep
            )
            default_path = (
                os.path.join(salt.syspaths.ROOT_DIR, "default", "path") + os.sep
            )

            self.assertEqual(len(diskp), 2)
            self.assertTrue(diskp[1]["source_file"].startswith(default_path))
        # pylint: enable=no-member

    def test_disk_profile_kvm_disk_external_image(self):
        """
        Test virt._gen_xml(), KVM case with an external image.
        """
        with patch.dict(os.path.__dict__, {"exists": MagicMock(return_value=True)}):
            diskp = virt._disk_profile(
                self.mock_conn,
                None,
                "kvm",
                [{"name": "mydisk", "source_file": "/path/to/my/image.qcow2"}],
                "hello",
            )

            self.assertEqual(len(diskp), 1)
            self.assertEqual(diskp[0]["source_file"], ("/path/to/my/image.qcow2"))

    def test_disk_profile_cdrom_default(self):
        """
        Test virt._gen_xml(), KVM case with cdrom.
        """
        with patch.dict(os.path.__dict__, {"exists": MagicMock(return_value=True)}):
            diskp = virt._disk_profile(
                self.mock_conn,
                None,
                "kvm",
                [
                    {
                        "name": "mydisk",
                        "device": "cdrom",
                        "source_file": "/path/to/my.iso",
                    }
                ],
                "hello",
            )

            self.assertEqual(len(diskp), 1)
            self.assertEqual(diskp[0]["model"], "ide")
            self.assertEqual(diskp[0]["format"], "raw")

    def test_disk_profile_pool_disk_type(self):
        """
        Test virt._disk_profile(), with a disk pool of disk type
        """
        self.mock_conn.listStoragePools.return_value = ["test-vdb"]
        self.mock_conn.storagePoolLookupByName.return_value.XMLDesc.return_value = """
            <pool type="disk">
              <name>test-vdb</name>
              <source>
                <device path='/dev/vdb'/>
              </source>
              <target>
                <path>/dev</path>
              </target>
            </pool>
        """

        # No existing disk case
        self.mock_conn.storagePoolLookupByName.return_value.listVolumes.return_value = (
            []
        )
        diskp = virt._disk_profile(
            self.mock_conn,
            None,
            "kvm",
            [{"name": "mydisk", "pool": "test-vdb"}],
            "hello",
        )
        self.assertEqual(diskp[0]["filename"], ("vdb1"))

        # Append to the end case
        self.mock_conn.storagePoolLookupByName.return_value.listVolumes.return_value = [
            "vdb1",
            "vdb2",
        ]
        diskp = virt._disk_profile(
            self.mock_conn,
            None,
            "kvm",
            [{"name": "mydisk", "pool": "test-vdb"}],
            "hello",
        )
        self.assertEqual(diskp[0]["filename"], ("vdb3"))

        # Hole in the middle case
        self.mock_conn.storagePoolLookupByName.return_value.listVolumes.return_value = [
            "vdb1",
            "vdb3",
        ]
        diskp = virt._disk_profile(
            self.mock_conn,
            None,
            "kvm",
            [{"name": "mydisk", "pool": "test-vdb"}],
            "hello",
        )
        self.assertEqual(diskp[0]["filename"], ("vdb2"))

        # Reuse existing volume case
        diskp = virt._disk_profile(
            self.mock_conn,
            None,
            "kvm",
            [{"name": "mydisk", "pool": "test-vdb", "source_file": "vdb1"}],
            "hello",
        )
        self.assertEqual(diskp[0]["filename"], ("vdb1"))

    def test_gen_xml_volume(self):
        """
        Test virt._gen_xml(), generating a disk of volume type
        """
        self.mock_conn.listStoragePools.return_value = ["default"]
        self.mock_conn.storagePoolLookupByName.return_value.XMLDesc.return_value = (
            "<pool type='dir'/>"
        )
        self.mock_conn.storagePoolLookupByName.return_value.listVolumes.return_value = [
            "myvolume"
        ]
        diskp = virt._disk_profile(
            self.mock_conn,
            None,
            "kvm",
            [
                {"name": "system", "pool": "default"},
                {"name": "data", "pool": "default", "source_file": "myvolume"},
            ],
            "hello",
        )
        self.mock_conn.storagePoolLookupByName.return_value.XMLDesc.return_value = (
            "<pool type='dir'/>"
        )
        nicp = virt._nic_profile(None, "kvm")
        xml_data = virt._gen_xml(
            self.mock_conn, "hello", 1, 512, diskp, nicp, "kvm", "hvm", "x86_64",
        )
        root = ET.fromstring(xml_data)
        disk = root.findall(".//disk")[0]
        self.assertEqual(disk.attrib["device"], "disk")
        self.assertEqual(disk.attrib["type"], "volume")
        source = disk.find("source")
        self.assertEqual("default", source.attrib["pool"])
        self.assertEqual("hello_system", source.attrib["volume"])
        self.assertEqual("myvolume", root.find(".//disk[2]/source").get("volume"))

        # RBD volume usage auth test case
        self.mock_conn.listStoragePools.return_value = ["test-rbd"]
        self.mock_conn.storagePoolLookupByName.return_value.XMLDesc.return_value = """
            <pool type='rbd'>
              <name>test-rbd</name>
              <uuid>ede33e0a-9df0-479f-8afd-55085a01b244</uuid>
              <capacity unit='bytes'>526133493760</capacity>
              <allocation unit='bytes'>589928</allocation>
              <available unit='bytes'>515081306112</available>
              <source>
                <host name='ses2.tf.local'/>
                <host name='ses3.tf.local' port='1234'/>
                <name>libvirt-pool</name>
                <auth type='ceph' username='libvirt'>
                  <secret usage='pool_test-rbd'/>
                </auth>
              </source>
            </pool>
        """
        self.mock_conn.getStoragePoolCapabilities.return_value = """
            <storagepoolCapabilities>
              <pool type='rbd' supported='yes'>
                <volOptions>
                  <defaultFormat type='raw'/>
                  <enum name='targetFormatType'>
                  </enum>
                </volOptions>
              </pool>
            </storagepoolCapabilities>
        """
        diskp = virt._disk_profile(
            self.mock_conn,
            None,
            "kvm",
            [{"name": "system", "pool": "test-rbd"}],
            "test-vm",
        )
        xml_data = virt._gen_xml(
            self.mock_conn, "hello", 1, 512, diskp, nicp, "kvm", "hvm", "x86_64",
        )
        root = ET.fromstring(xml_data)
        disk = root.findall(".//disk")[0]
        self.assertDictEqual(
            {
                "type": "network",
                "device": "disk",
                "source": {
                    "protocol": "rbd",
                    "name": "libvirt-pool/test-vm_system",
                    "host": [
                        {"name": "ses2.tf.local"},
                        {"name": "ses3.tf.local", "port": "1234"},
                    ],
                    "auth": {
                        "username": "libvirt",
                        "secret": {"type": "ceph", "usage": "pool_test-rbd"},
                    },
                },
                "target": {"dev": "vda", "bus": "virtio"},
                "driver": {
                    "name": "qemu",
                    "type": "raw",
                    "cache": "none",
                    "io": "native",
                },
            },
            salt.utils.xmlutil.to_dict(disk, True),
        )

        # RBD volume UUID auth test case
        self.mock_conn.storagePoolLookupByName.return_value.XMLDesc.return_value = """
            <pool type='rbd'>
              <name>test-rbd</name>
              <uuid>ede33e0a-9df0-479f-8afd-55085a01b244</uuid>
              <capacity unit='bytes'>526133493760</capacity>
              <allocation unit='bytes'>589928</allocation>
              <available unit='bytes'>515081306112</available>
              <source>
                <host name='ses2.tf.local'/>
                <host name='ses3.tf.local' port='1234'/>
                <name>libvirt-pool</name>
                <auth type='ceph' username='libvirt'>
                  <secret uuid='some-uuid'/>
                </auth>
              </source>
            </pool>
        """
        self.mock_conn.secretLookupByUUIDString.return_value.usageID.return_value = (
            "pool_test-rbd"
        )
        diskp = virt._disk_profile(
            self.mock_conn,
            None,
            "kvm",
            [{"name": "system", "pool": "test-rbd"}],
            "test-vm",
        )
        xml_data = virt._gen_xml(
            self.mock_conn, "hello", 1, 512, diskp, nicp, "kvm", "hvm", "x86_64",
        )
        root = ET.fromstring(xml_data)
        self.assertDictEqual(
            {
                "username": "libvirt",
                "secret": {"type": "ceph", "usage": "pool_test-rbd"},
            },
            salt.utils.xmlutil.to_dict(root.find(".//disk/source/auth"), True),
        )
        self.mock_conn.secretLookupByUUIDString.assert_called_once_with("some-uuid")

        # Disk volume test case
        self.mock_conn.getStoragePoolCapabilities.return_value = """
            <storagepoolCapabilities>
              <pool type='disk' supported='yes'>
                <volOptions>
                  <defaultFormat type='none'/>
                  <enum name='targetFormatType'>
                    <value>none</value>
                    <value>linux</value>
                    <value>fat16</value>
                  </enum>
                </volOptions>
              </pool>
            </storagepoolCapabilities>
        """
        self.mock_conn.storagePoolLookupByName.return_value.XMLDesc.return_value = """
            <pool type='disk'>
              <name>test-vdb</name>
              <source>
                <device path='/dev/vdb'/>
                <format type='gpt'/>
              </source>
            </pool>
        """
        self.mock_conn.listStoragePools.return_value = ["test-vdb"]
        self.mock_conn.storagePoolLookupByName.return_value.listVolumes.return_value = [
            "vdb1",
        ]
        diskp = virt._disk_profile(
            self.mock_conn,
            None,
            "kvm",
            [{"name": "system", "pool": "test-vdb"}],
            "test-vm",
        )
        xml_data = virt._gen_xml(
            self.mock_conn, "hello", 1, 512, diskp, nicp, "kvm", "hvm", "x86_64",
        )
        root = ET.fromstring(xml_data)
        disk = root.findall(".//disk")[0]
        self.assertEqual(disk.attrib["type"], "volume")
        source = disk.find("source")
        self.assertEqual("test-vdb", source.attrib["pool"])
        self.assertEqual("vdb2", source.attrib["volume"])
        self.assertEqual("raw", disk.find("driver").get("type"))

    def test_get_xml_volume_xen_dir(self):
        """
        Test virt._gen_xml generating disks for a Xen hypervisor
        """
        self.mock_conn.listStoragePools.return_value = ["default"]
        pool_mock = MagicMock()
        pool_mock.XMLDesc.return_value = (
            "<pool type='dir'><target><path>/path/to/images</path></target></pool>"
        )
        volume_xml = "<volume><target><path>/path/to/images/hello_system</path></target></volume>"
        pool_mock.storageVolLookupByName.return_value.XMLDesc.return_value = volume_xml
        self.mock_conn.storagePoolLookupByName.return_value = pool_mock
        diskp = virt._disk_profile(
            self.mock_conn,
            None,
            "xen",
            [{"name": "system", "pool": "default"}],
            "hello",
        )
        xml_data = virt._gen_xml(
            self.mock_conn, "hello", 1, 512, diskp, [], "xen", "hvm", "x86_64",
        )
        root = ET.fromstring(xml_data)
        disk = root.findall(".//disk")[0]
        self.assertEqual(disk.attrib["type"], "file")
        self.assertEqual(
            "/path/to/images/hello_system", disk.find("source").attrib["file"]
        )

    def test_get_xml_volume_xen_block(self):
        """
        Test virt._gen_xml generating disks for a Xen hypervisor
        """
        self.mock_conn.listStoragePools.return_value = ["default"]
        pool_mock = MagicMock()
        pool_mock.listVolumes.return_value = ["vol01"]
        volume_xml = "<volume><target><path>/dev/to/vol01</path></target></volume>"
        pool_mock.storageVolLookupByName.return_value.XMLDesc.return_value = volume_xml
        self.mock_conn.storagePoolLookupByName.return_value = pool_mock

        for pool_type in ["logical", "disk", "iscsi", "scsi"]:
            pool_mock.XMLDesc.return_value = "<pool type='{}'><source><device path='/dev/sda'/></source></pool>".format(
                pool_type
            )
            diskp = virt._disk_profile(
                self.mock_conn,
                None,
                "xen",
                [{"name": "system", "pool": "default", "source_file": "vol01"}],
                "hello",
            )
            xml_data = virt._gen_xml(
                self.mock_conn, "hello", 1, 512, diskp, [], "xen", "hvm", "x86_64",
            )
            root = ET.fromstring(xml_data)
            disk = root.findall(".//disk")[0]
            self.assertEqual(disk.attrib["type"], "block")
            self.assertEqual("/dev/to/vol01", disk.find("source").attrib["dev"])

    def test_gen_xml_cdrom(self):
        """
        Test virt._gen_xml(), generating a cdrom device (different disk type, no source)
        """
        self.mock_conn.storagePoolLookupByName.return_value.XMLDesc.return_value = (
            "<pool type='dir'/>"
        )
        diskp = virt._disk_profile(
            self.mock_conn,
            None,
            "kvm",
            [
                {"name": "system", "pool": "default"},
                {
                    "name": "tested",
                    "device": "cdrom",
                    "source_file": None,
                    "model": "ide",
                },
                {
                    "name": "remote",
                    "device": "cdrom",
                    "source_file": "http://myhost:8080/url/to/image?query=foo&filter=bar",
                    "model": "ide",
                },
            ],
            "hello",
        )
        nicp = virt._nic_profile(None, "kvm")
        xml_data = virt._gen_xml(
            self.mock_conn, "hello", 1, 512, diskp, nicp, "kvm", "hvm", "x86_64",
        )
        root = ET.fromstring(xml_data)
        disk = root.findall(".//disk")[1]
        self.assertEqual(disk.get("type"), "file")
        self.assertEqual(disk.attrib["device"], "cdrom")
        self.assertIsNone(disk.find("source"))
        self.assertEqual(disk.find("target").get("dev"), "hda")

        disk = root.findall(".//disk")[2]
        self.assertEqual(disk.get("type"), "network")
        self.assertEqual(disk.attrib["device"], "cdrom")
        self.assertEqual(
            {
                "protocol": "http",
                "name": "/url/to/image",
                "query": "query=foo&filter=bar",
                "host": {"name": "myhost", "port": "8080"},
            },
            salt.utils.xmlutil.to_dict(disk.find("source"), True),
        )

    def test_controller_for_esxi(self):
        """
        Test virt._gen_xml() generated device controller for ESXi/vmware
        """
        diskp = virt._disk_profile(self.mock_conn, "default", "vmware", [], "hello")
        nicp = virt._nic_profile("default", "vmware")
        xml_data = virt._gen_xml(
            self.mock_conn, "hello", 1, 512, diskp, nicp, "vmware", "hvm", "x86_64",
        )
        root = ET.fromstring(xml_data)
        controllers = root.findall(".//devices/controller")
        self.assertTrue(len(controllers) == 1)
        controller = controllers[0]
        self.assertEqual(controller.attrib["model"], "lsilogic")

    def test_controller_for_kvm(self):
        """
        Test virt._gen_xml() generated device controller for KVM
        """
        diskp = virt._disk_profile(self.mock_conn, "default", "kvm", [], "hello")
        nicp = virt._nic_profile("default", "kvm")
        xml_data = virt._gen_xml(
            self.mock_conn, "hello", 1, 512, diskp, nicp, "kvm", "hvm", "x86_64",
        )
        root = ET.fromstring(xml_data)
        controllers = root.findall(".//devices/controller")
        # There should be no controller
        self.assertTrue(len(controllers) == 0)

    def test_diff_disks(self):
        """
        Test virt._diff_disks()
        """
        old_disks = ET.fromstring(
            """
            <devices>
              <disk type='file' device='disk'>
                <source file='/path/to/img0.qcow2'/>
                <target dev='vda' bus='virtio'/>
              </disk>
              <disk type='file' device='disk'>
                <source file='/path/to/img1.qcow2'/>
                <target dev='vdb' bus='virtio'/>
              </disk>
              <disk type='file' device='disk'>
                <source file='/path/to/img2.qcow2'/>
                <target dev='hda' bus='ide'/>
              </disk>
              <disk type='file' device='disk'>
                <source file='/path/to/img4.qcow2'/>
                <target dev='hdb' bus='ide'/>
              </disk>
              <disk type='file' device='cdrom'>
                <target dev='hdc' bus='ide'/>
              </disk>
            </devices>
        """
        ).findall("disk")

        new_disks = ET.fromstring(
            """
            <devices>
              <disk type='file' device='disk'>
                <source file='/path/to/img3.qcow2'/>
                <target dev='vda' bus='virtio'/>
              </disk>
              <disk type='file' device='disk' cache='default'>
                <source file='/path/to/img0.qcow2'/>
                <target dev='vda' bus='virtio'/>
              </disk>
              <disk type='file' device='disk'>
                <source file='/path/to/img4.qcow2'/>
                <target dev='vda' bus='virtio'/>
              </disk>
              <disk type='file' device='cdrom'>
                <target dev='hda' bus='ide'/>
              </disk>
            </devices>
        """
        ).findall("disk")
        ret = virt._diff_disk_lists(old_disks, new_disks)
        self.assertEqual(
            [
                disk.find("source").get("file")
                if disk.find("source") is not None
                else None
                for disk in ret["unchanged"]
            ],
            [],
        )
        self.assertEqual(
            [
                disk.find("source").get("file")
                if disk.find("source") is not None
                else None
                for disk in ret["new"]
            ],
            ["/path/to/img3.qcow2", "/path/to/img0.qcow2", "/path/to/img4.qcow2", None],
        )
        self.assertEqual(
            [disk.find("target").get("dev") for disk in ret["sorted"]],
            ["vda", "vdb", "vdc", "hda"],
        )
        self.assertEqual(
            [
                disk.find("source").get("file")
                if disk.find("source") is not None
                else None
                for disk in ret["sorted"]
            ],
            ["/path/to/img3.qcow2", "/path/to/img0.qcow2", "/path/to/img4.qcow2", None],
        )
        self.assertEqual(ret["new"][1].find("target").get("bus"), "virtio")
        self.assertEqual(
            [
                disk.find("source").get("file")
                if disk.find("source") is not None
                else None
                for disk in ret["deleted"]
            ],
            [
                "/path/to/img0.qcow2",
                "/path/to/img1.qcow2",
                "/path/to/img2.qcow2",
                "/path/to/img4.qcow2",
                None,
            ],
        )

    def test_diff_nics(self):
        """
        Test virt._diff_nics()
        """
        old_nics = ET.fromstring(
            """
            <devices>
               <interface type='network'>
                 <mac address='52:54:00:39:02:b1'/>
                 <source network='default'/>
                 <model type='virtio'/>
                 <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
               </interface>
               <interface type='network'>
                 <mac address='52:54:00:39:02:b2'/>
                 <source network='admin'/>
                 <model type='virtio'/>
                 <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
               </interface>
               <interface type='network'>
                 <mac address='52:54:00:39:02:b3'/>
                 <source network='admin'/>
                 <model type='virtio'/>
                 <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
               </interface>
            </devices>
        """
        ).findall("interface")

        new_nics = ET.fromstring(
            """
            <devices>
               <interface type='network'>
                 <mac address='52:54:00:39:02:b1'/>
                 <source network='default'/>
                 <model type='virtio'/>
               </interface>
               <interface type='network'>
                 <mac address='52:54:00:39:02:b2'/>
                 <source network='default'/>
                 <model type='virtio'/>
               </interface>
               <interface type='network'>
                 <mac address='52:54:00:39:02:b4'/>
                 <source network='admin'/>
                 <model type='virtio'/>
               </interface>
            </devices>
        """
        ).findall("interface")
        ret = virt._diff_interface_lists(old_nics, new_nics)
        self.assertEqual(
            [nic.find("mac").get("address") for nic in ret["unchanged"]],
            ["52:54:00:39:02:b1"],
        )
        self.assertEqual(
            [nic.find("mac").get("address") for nic in ret["new"]],
            ["52:54:00:39:02:b2", "52:54:00:39:02:b4"],
        )
        self.assertEqual(
            [nic.find("mac").get("address") for nic in ret["deleted"]],
            ["52:54:00:39:02:b2", "52:54:00:39:02:b3"],
        )

    def test_init(self):
        """
        Test init() function
        """
        xml = """
<capabilities>
  <host>
    <uuid>44454c4c-3400-105a-8033-b3c04f4b344a</uuid>
    <cpu>
      <arch>x86_64</arch>
      <model>Nehalem</model>
      <vendor>Intel</vendor>
      <microcode version='25'/>
      <topology sockets='1' cores='4' threads='2'/>
      <feature name='vme'/>
      <feature name='ds'/>
      <feature name='acpi'/>
      <pages unit='KiB' size='4'/>
      <pages unit='KiB' size='2048'/>
    </cpu>
    <power_management>
      <suspend_mem/>
      <suspend_disk/>
      <suspend_hybrid/>
    </power_management>
    <migration_features>
      <live/>
      <uri_transports>
        <uri_transport>tcp</uri_transport>
        <uri_transport>rdma</uri_transport>
      </uri_transports>
    </migration_features>
    <topology>
      <cells num='1'>
        <cell id='0'>
          <memory unit='KiB'>12367120</memory>
          <pages unit='KiB' size='4'>3091780</pages>
          <pages unit='KiB' size='2048'>0</pages>
          <distances>
            <sibling id='0' value='10'/>
          </distances>
          <cpus num='8'>
            <cpu id='0' socket_id='0' core_id='0' siblings='0,4'/>
            <cpu id='1' socket_id='0' core_id='1' siblings='1,5'/>
            <cpu id='2' socket_id='0' core_id='2' siblings='2,6'/>
            <cpu id='3' socket_id='0' core_id='3' siblings='3,7'/>
            <cpu id='4' socket_id='0' core_id='0' siblings='0,4'/>
            <cpu id='5' socket_id='0' core_id='1' siblings='1,5'/>
            <cpu id='6' socket_id='0' core_id='2' siblings='2,6'/>
            <cpu id='7' socket_id='0' core_id='3' siblings='3,7'/>
          </cpus>
        </cell>
      </cells>
    </topology>
    <cache>
      <bank id='0' level='3' type='both' size='8' unit='MiB' cpus='0-7'/>
    </cache>
    <secmodel>
      <model>apparmor</model>
      <doi>0</doi>
    </secmodel>
    <secmodel>
      <model>dac</model>
      <doi>0</doi>
      <baselabel type='kvm'>+487:+486</baselabel>
      <baselabel type='qemu'>+487:+486</baselabel>
    </secmodel>
  </host>

  <guest>
    <os_type>hvm</os_type>
    <arch name='i686'>
      <wordsize>32</wordsize>
      <emulator>/usr/bin/qemu-system-i386</emulator>
      <machine maxCpus='255'>pc-i440fx-2.6</machine>
      <machine canonical='pc-i440fx-2.6' maxCpus='255'>pc</machine>
      <machine maxCpus='255'>pc-0.12</machine>
      <domain type='qemu'/>
      <domain type='kvm'>
        <emulator>/usr/bin/qemu-kvm</emulator>
        <machine maxCpus='255'>pc-i440fx-2.6</machine>
        <machine canonical='pc-i440fx-2.6' maxCpus='255'>pc</machine>
        <machine maxCpus='255'>pc-0.12</machine>
      </domain>
    </arch>
    <features>
      <cpuselection/>
      <deviceboot/>
      <disksnapshot default='on' toggle='no'/>
      <acpi default='on' toggle='yes'/>
      <apic default='on' toggle='no'/>
      <pae/>
      <nonpae/>
    </features>
  </guest>

  <guest>
    <os_type>hvm</os_type>
    <arch name='x86_64'>
      <wordsize>64</wordsize>
      <emulator>/usr/bin/qemu-system-x86_64</emulator>
      <machine maxCpus='255'>pc-i440fx-2.6</machine>
      <machine canonical='pc-i440fx-2.6' maxCpus='255'>pc</machine>
      <machine maxCpus='255'>pc-0.12</machine>
      <domain type='qemu'/>
      <domain type='kvm'>
        <emulator>/usr/bin/qemu-kvm</emulator>
        <machine maxCpus='255'>pc-i440fx-2.6</machine>
        <machine canonical='pc-i440fx-2.6' maxCpus='255'>pc</machine>
        <machine maxCpus='255'>pc-0.12</machine>
      </domain>
    </arch>
    <features>
      <cpuselection/>
      <deviceboot/>
      <disksnapshot default='on' toggle='no'/>
      <acpi default='on' toggle='yes'/>
      <apic default='on' toggle='no'/>
    </features>
  </guest>

</capabilities>
        """
        self.mock_conn.getCapabilities.return_value = xml  # pylint: disable=no-member

        root_dir = os.path.join(salt.syspaths.ROOT_DIR, "srv", "salt-images")

        defineMock = MagicMock(return_value=1)
        self.mock_conn.defineXML = defineMock
        mock_chmod = MagicMock()
        mock_run = MagicMock()
        with patch.dict(
            os.__dict__, {"chmod": mock_chmod, "makedirs": MagicMock()}
        ):  # pylint: disable=no-member
            with patch.dict(
                virt.__salt__, {"cmd.run": mock_run}
            ):  # pylint: disable=no-member

                # Ensure the init() function allows creating VM without NIC and disk
                virt.init(
                    "test vm", 2, 1234, nic=None, disk=None, seed=False, start=False
                )
                definition = defineMock.call_args_list[0][0][0]
                self.assertFalse("<interface" in definition)
                self.assertFalse("<disk" in definition)

                # Ensure the init() function allows creating VM without NIC and
                # disk but with boot parameters.

                defineMock.reset_mock()
                mock_run.reset_mock()
                boot = {
                    "kernel": "/root/f8-i386-vmlinuz",
                    "initrd": "/root/f8-i386-initrd",
                    "cmdline": "console=ttyS0 ks=http://example.com/f8-i386/os/",
                }
                retval = virt.init(
                    "test vm boot params",
                    2,
                    1234,
                    nic=None,
                    disk=None,
                    seed=False,
                    start=False,
                    boot=boot,
                )
                definition = defineMock.call_args_list[0][0][0]
                self.assertEqual("<kernel" in definition, True)
                self.assertEqual("<initrd" in definition, True)
                self.assertEqual("<cmdline" in definition, True)
                self.assertEqual(retval, True)

                # Verify that remote paths are downloaded and the xml has been
                # modified
                mock_response = MagicMock()
                mock_response.read = MagicMock(return_value="filecontent")
                cache_dir = tempfile.mkdtemp()

                with patch.dict(virt.__dict__, {"CACHE_DIR": cache_dir}):
                    with patch(
                        "salt.ext.six.moves.urllib.request.urlopen",
                        MagicMock(return_value=mock_response),
                    ):
                        with patch(
                            "salt.utils.files.fopen", return_value=mock_response
                        ):

                            defineMock.reset_mock()
                            mock_run.reset_mock()
                            boot = {
                                "kernel": "https://www.example.com/download/vmlinuz",
                                "initrd": "",
                                "cmdline": "console=ttyS0 "
                                "ks=http://example.com/f8-i386/os/",
                            }

                            retval = virt.init(
                                "test remote vm boot params",
                                2,
                                1234,
                                nic=None,
                                disk=None,
                                seed=False,
                                start=False,
                                boot=boot,
                            )
                            definition = defineMock.call_args_list[0][0][0]
                            self.assertEqual(cache_dir in definition, True)

                    shutil.rmtree(cache_dir)

                # Test case creating disks
                defineMock.reset_mock()
                mock_run.reset_mock()
                pool_mock = MagicMock()
                pool_mock.XMLDesc.return_value = '<pool type="dir"/>'
                self.mock_conn.storagePoolLookupByName.return_value = pool_mock
                virt.init(
                    "test vm",
                    2,
                    1234,
                    nic=None,
                    disk=None,
                    disks=[
                        {"name": "system", "size": 10240},
                        {
                            "name": "cddrive",
                            "device": "cdrom",
                            "source_file": None,
                            "model": "ide",
                        },
                    ],
                    seed=False,
                    start=False,
                )
                definition = ET.fromstring(defineMock.call_args_list[0][0][0])
                expected_disk_path = os.path.join(root_dir, "test vm_system.qcow2")
                self.assertEqual(
                    expected_disk_path,
                    definition.find("./devices/disk[1]/source").get("file"),
                )
                self.assertIsNone(definition.find("./devices/disk[2]/source"))
                self.assertEqual(
                    mock_run.call_args[0][0],
                    'qemu-img create -f qcow2 "{}" 10240M'.format(expected_disk_path),
                )
                self.assertEqual(mock_chmod.call_args[0][0], expected_disk_path)

                # Test case creating disks volumes
                defineMock.reset_mock()
                mock_run.reset_mock()
                vol_mock = MagicMock()
                pool_mock.storageVolLookupByName.return_value = vol_mock
                pool_mock.listVolumes.return_value = ["test vm_data"]
                stream_mock = MagicMock()
                self.mock_conn.newStream.return_value = stream_mock
                self.mock_conn.listStoragePools.return_value = ["default", "test"]
                with patch.dict(
                    os.__dict__, {"open": MagicMock(), "close": MagicMock()}
                ):
                    cache_mock = MagicMock()
                    with patch.dict(virt.__salt__, {"cp.cache_file": cache_mock}):
                        virt.init(
                            "test vm",
                            2,
                            1234,
                            nic=None,
                            disk=None,
                            disks=[
                                {
                                    "name": "system",
                                    "size": 10240,
                                    "image": "/path/to/image",
                                    "pool": "test",
                                },
                                {"name": "data", "size": 10240, "pool": "default"},
                                {
                                    "name": "test",
                                    "size": 1024,
                                    "pool": "default",
                                    "format": "qcow2",
                                    "backing_store_path": "/backing/path",
                                    "backing_store_format": "raw",
                                },
                            ],
                            seed=False,
                            start=False,
                        )
                        definition = ET.fromstring(defineMock.call_args_list[0][0][0])
                        self.assertTrue(
                            all(
                                [
                                    disk.get("type") == "volume"
                                    for disk in definition.findall("./devices/disk")
                                ]
                            )
                        )
                        self.assertEqual(
                            ["test", "default", "default"],
                            [
                                src.get("pool")
                                for src in definition.findall("./devices/disk/source")
                            ],
                        )
                        self.assertEqual(
                            ["test vm_system", "test vm_data", "test vm_test"],
                            [
                                src.get("volume")
                                for src in definition.findall("./devices/disk/source")
                            ],
                        )

                        create_calls = pool_mock.createXML.call_args_list
                        vol_names = [
                            ET.fromstring(call[0][0]).find("name").text
                            for call in create_calls
                        ]
                        self.assertEqual(
                            ["test vm_system", "test vm_test"], vol_names,
                        )

                        stream_mock.sendAll.assert_called_once()
                        stream_mock.finish.assert_called_once()
                        vol_mock.upload.assert_called_once_with(stream_mock, 0, 0, 0)

    def test_update(self):
        """
        Test virt.update()
        """
        root_dir = os.path.join(salt.syspaths.ROOT_DIR, "srv", "salt-images")
        xml = """
            <domain type='kvm' id='7'>
              <name>my_vm</name>
              <memory unit='KiB'>1048576</memory>
              <currentMemory unit='KiB'>1048576</currentMemory>
              <vcpu placement='auto'>1</vcpu>
              <os>
                <type arch='x86_64' machine='pc-i440fx-2.6'>hvm</type>
                <boot dev="hd"/>
              </os>
              <devices>
                <disk type='file' device='disk'>
                  <driver name='qemu' type='qcow2'/>
                  <source file='{}{}my_vm_system.qcow2'/>
                  <backingStore/>
                  <target dev='vda' bus='virtio'/>
                  <alias name='virtio-disk0'/>
                  <address type='pci' domain='0x0000' bus='0x00' slot='0x07' function='0x0'/>
                </disk>
                <disk type='volume' device='disk'>
                  <driver name='qemu' type='qcow2'/>
                  <source pool='default' volume='my_vm_data'/>
                  <backingStore/>
                  <target dev='vdb' bus='virtio'/>
                  <alias name='virtio-disk1'/>
                  <address type='pci' domain='0x0000' bus='0x00' slot='0x07' function='0x1'/>
                </disk>
                <disk type="network" device="disk">
                  <driver name='raw' type='qcow2'/>
                  <source protocol='rbd' name='libvirt-pool/my_vm_data2'>
                    <host name='ses2.tf.local'/>
                    <host name='ses3.tf.local' port='1234'/>
                    <auth username='libvirt'>
                      <secret type='ceph' usage='pool_test-rbd'/>
                    </auth>
                  </source>
                  <target dev='vdc' bus='virtio'/>
                  <alias name='virtio-disk2'/>
                  <address type='pci' domain='0x0000' bus='0x00' slot='0x07' function='0x2'/>
                </disk>
                <interface type='network'>
                  <mac address='52:54:00:39:02:b1'/>
                  <source network='default' bridge='virbr0'/>
                  <target dev='vnet0'/>
                  <model type='virtio'/>
                  <alias name='net0'/>
                  <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
                </interface>
                <interface type='network'>
                  <mac address='52:54:00:39:02:b2'/>
                  <source network='oldnet' bridge='virbr1'/>
                  <target dev='vnet1'/>
                  <model type='virtio'/>
                  <alias name='net1'/>
                  <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x1'/>
                </interface>
                <graphics type='spice' listen='127.0.0.1' autoport='yes'>
                  <listen type='address' address='127.0.0.1'/>
                </graphics>
                <video>
                  <model type='qxl' ram='65536' vram='65536' vgamem='16384' heads='1' primary='yes'/>
                  <alias name='video0'/>
                  <address type='pci' domain='0x0000' bus='0x00' slot='0x02' function='0x0'/>
                </video>
              </devices>
            </domain>
        """.format(
            root_dir, os.sep
        )
        domain_mock = self.set_mock_vm("my_vm", xml)
        domain_mock.OSType = MagicMock(return_value="hvm")
        define_mock = MagicMock(return_value=True)
        self.mock_conn.defineXML = define_mock

        # No parameter passed case
        self.assertEqual(
            {
                "definition": False,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("my_vm"),
        )

        # mem + cpu case
        define_mock.reset_mock()
        domain_mock.setMemoryFlags.return_value = 0
        domain_mock.setVcpusFlags.return_value = 0
        self.assertEqual(
            {
                "definition": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
                "mem": True,
                "cpu": True,
            },
            virt.update("my_vm", mem=2048, cpu=2),
        )
        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual("2", setxml.find("vcpu").text)
        self.assertEqual("2147483648", setxml.find("memory").text)
        self.assertEqual(2048 * 1024, domain_mock.setMemoryFlags.call_args[0][0])

        # Same parameters passed than in default virt.defined state case
        self.assertEqual(
            {
                "definition": False,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update(
                "my_vm",
                cpu=None,
                mem=None,
                disk_profile=None,
                disks=None,
                nic_profile=None,
                interfaces=None,
                graphics=None,
                live=True,
                connection=None,
                username=None,
                password=None,
                boot=None,
            ),
        )

        # Update vcpus case
        setvcpus_mock = MagicMock(return_value=0)
        domain_mock.setVcpusFlags = setvcpus_mock
        self.assertEqual(
            {
                "definition": True,
                "cpu": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("my_vm", cpu=2),
        )
        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual(setxml.find("vcpu").text, "2")
        self.assertEqual(setvcpus_mock.call_args[0][0], 2)

        boot = {
            "kernel": "/root/f8-i386-vmlinuz",
            "initrd": "/root/f8-i386-initrd",
            "cmdline": "console=ttyS0 ks=http://example.com/f8-i386/os/",
        }

        # Update boot devices case
        define_mock.reset_mock()
        self.assertEqual(
            {
                "definition": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("my_vm", boot_dev="cdrom network hd"),
        )
        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual(
            ["cdrom", "network", "hd"],
            [node.get("dev") for node in setxml.findall("os/boot")],
        )

        # Update unchanged boot devices case
        define_mock.reset_mock()
        self.assertEqual(
            {
                "definition": False,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("my_vm", boot_dev="hd"),
        )
        define_mock.assert_not_called()

        # Update with boot parameter case
        define_mock.reset_mock()
        self.assertEqual(
            {
                "definition": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("my_vm", boot=boot),
        )
        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual(setxml.find("os").find("kernel").text, "/root/f8-i386-vmlinuz")
        self.assertEqual(setxml.find("os").find("initrd").text, "/root/f8-i386-initrd")
        self.assertEqual(
            setxml.find("os").find("cmdline").text,
            "console=ttyS0 ks=http://example.com/f8-i386/os/",
        )
        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual(setxml.find("os").find("kernel").text, "/root/f8-i386-vmlinuz")
        self.assertEqual(setxml.find("os").find("initrd").text, "/root/f8-i386-initrd")
        self.assertEqual(
            setxml.find("os").find("cmdline").text,
            "console=ttyS0 ks=http://example.com/f8-i386/os/",
        )

        boot_uefi = {
            "loader": "/usr/share/OVMF/OVMF_CODE.fd",
            "nvram": "/usr/share/OVMF/OVMF_VARS.ms.fd",
        }

        self.assertEqual(
            {
                "definition": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("my_vm", boot=boot_uefi),
        )
        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual(
            setxml.find("os").find("loader").text, "/usr/share/OVMF/OVMF_CODE.fd"
        )
        self.assertEqual(setxml.find("os").find("loader").attrib.get("readonly"), "yes")
        self.assertEqual(setxml.find("os").find("loader").attrib["type"], "pflash")
        self.assertEqual(
            setxml.find("os").find("nvram").attrib["template"],
            "/usr/share/OVMF/OVMF_VARS.ms.fd",
        )

        self.assertEqual(
            {
                "definition": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("my_vm", boot={"efi": True}),
        )
        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual(setxml.find("os").attrib.get("firmware"), "efi")

        invalid_boot = {
            "loader": "/usr/share/OVMF/OVMF_CODE.fd",
            "initrd": "/root/f8-i386-initrd",
        }

        with self.assertRaises(SaltInvocationError):
            virt.update("my_vm", boot=invalid_boot)

        with self.assertRaises(SaltInvocationError):
            virt.update("my_vm", boot={"efi": "Not a boolean value"})

        # Update memtune parameter case
        memtune = {
            "soft_limit": "0.5g",
            "hard_limit": "1024",
            "swap_hard_limit": "2048m",
            "min_guarantee": "1 g",
        }

        self.assertEqual(
            {
                "definition": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("my_vm", mem=memtune),
        )

        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual(
            setxml.find("memtune").find("soft_limit").text, str(int(0.5 * 1024 ** 3))
        )
        self.assertEqual(setxml.find("memtune").find("soft_limit").get("unit"), "bytes")
        self.assertEqual(
            setxml.find("memtune").find("hard_limit").text, str(1024 * 1024 ** 2)
        )
        self.assertEqual(
            setxml.find("memtune").find("swap_hard_limit").text, str(2048 * 1024 ** 2)
        )
        self.assertEqual(
            setxml.find("memtune").find("min_guarantee").text, str(1 * 1024 ** 3)
        )

        invalid_unit = {"soft_limit": "2HB"}

        with self.assertRaises(SaltInvocationError):
            virt.update("my_vm", mem=invalid_unit)

        invalid_number = {
            "soft_limit": "3.4.MB",
        }

        with self.assertRaises(SaltInvocationError):
            virt.update("my_vm", mem=invalid_number)

        # Update memory case
        setmem_mock = MagicMock(return_value=0)
        domain_mock.setMemoryFlags = setmem_mock

        self.assertEqual(
            {
                "definition": True,
                "mem": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("my_vm", mem=2048),
        )
        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual(setxml.find("memory").text, str(2048 * 1024 ** 2))
        self.assertEqual(setxml.find("memory").get("unit"), "bytes")
        self.assertEqual(setmem_mock.call_args[0][0], 2048 * 1024)

        mem_dict = {"boot": "0.5g", "current": "2g", "max": "1g", "slots": 12}
        self.assertEqual(
            {
                "definition": True,
                "mem": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("my_vm", mem=mem_dict),
        )

        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual(setxml.find("memory").get("unit"), "bytes")
        self.assertEqual(setxml.find("memory").text, str(int(0.5 * 1024 ** 3)))
        self.assertEqual(setxml.find("maxMemory").text, str(1 * 1024 ** 3))
        self.assertEqual(setxml.find("currentMemory").text, str(2 * 1024 ** 3))

        max_slot_reverse = {
            "slots": "10",
            "max": "3096m",
        }
        self.assertEqual(
            {
                "definition": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("my_vm", mem=max_slot_reverse),
        )
        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual(setxml.find("maxMemory").text, str(3096 * 1024 ** 2))
        self.assertEqual(setxml.find("maxMemory").attrib.get("slots"), "10")

        # Update disks case
        devattach_mock = MagicMock(return_value=0)
        devdetach_mock = MagicMock(return_value=0)
        domain_mock.attachDevice = devattach_mock
        domain_mock.detachDevice = devdetach_mock
        mock_chmod = MagicMock()
        mock_run = MagicMock()
        with patch.dict(
            os.__dict__, {"chmod": mock_chmod, "makedirs": MagicMock()}
        ):  # pylint: disable=no-member
            with patch.dict(
                virt.__salt__, {"cmd.run": mock_run}
            ):  # pylint: disable=no-member
                ret = virt.update(
                    "my_vm",
                    disk_profile="default",
                    disks=[
                        {
                            "name": "cddrive",
                            "device": "cdrom",
                            "source_file": None,
                            "model": "ide",
                        },
                        {"name": "added", "size": 2048},
                    ],
                )
                added_disk_path = os.path.join(
                    virt.__salt__["config.get"]("virt:images"), "my_vm_added.qcow2"
                )  # pylint: disable=no-member
                self.assertEqual(
                    mock_run.call_args[0][0],
                    'qemu-img create -f qcow2 "{}" 2048M'.format(added_disk_path),
                )
                self.assertEqual(mock_chmod.call_args[0][0], added_disk_path)
                self.assertListEqual(
                    [None, os.path.join(root_dir, "my_vm_added.qcow2")],
                    [
                        ET.fromstring(disk).find("source").get("file")
                        if str(disk).find("<source") > -1
                        else None
                        for disk in ret["disk"]["attached"]
                    ],
                )

                self.assertListEqual(
                    ["my_vm_data", "libvirt-pool/my_vm_data2"],
                    [
                        ET.fromstring(disk).find("source").get("volume")
                        or ET.fromstring(disk).find("source").get("name")
                        for disk in ret["disk"]["detached"]
                    ],
                )
                self.assertEqual(devattach_mock.call_count, 2)
                self.assertEqual(devdetach_mock.call_count, 2)

        # Update nics case
        yaml_config = """
          virt:
             nic:
                myprofile:
                   - network: default
                     name: eth0
        """
        mock_config = salt.utils.yaml.safe_load(yaml_config)
        devattach_mock.reset_mock()
        devdetach_mock.reset_mock()
        with patch.dict(
            salt.modules.config.__opts__, mock_config  # pylint: disable=no-member
        ):
            ret = virt.update(
                "my_vm",
                nic_profile="myprofile",
                interfaces=[
                    {
                        "name": "eth0",
                        "type": "network",
                        "source": "default",
                        "mac": "52:54:00:39:02:b1",
                    },
                    {"name": "eth1", "type": "network", "source": "newnet"},
                ],
            )
            self.assertEqual(
                ["newnet"],
                [
                    ET.fromstring(nic).find("source").get("network")
                    for nic in ret["interface"]["attached"]
                ],
            )
            self.assertEqual(
                ["oldnet"],
                [
                    ET.fromstring(nic).find("source").get("network")
                    for nic in ret["interface"]["detached"]
                ],
            )
            devattach_mock.assert_called_once()
            devdetach_mock.assert_called_once()

        # Remove nics case
        devattach_mock.reset_mock()
        devdetach_mock.reset_mock()
        ret = virt.update("my_vm", nic_profile=None, interfaces=[])
        self.assertEqual([], ret["interface"]["attached"])
        self.assertEqual(2, len(ret["interface"]["detached"]))
        devattach_mock.assert_not_called()
        devdetach_mock.assert_called()

        # Remove disks case (yeah, it surely is silly)
        devattach_mock.reset_mock()
        devdetach_mock.reset_mock()
        ret = virt.update("my_vm", disk_profile=None, disks=[])
        self.assertEqual([], ret["disk"]["attached"])
        self.assertEqual(3, len(ret["disk"]["detached"]))
        devattach_mock.assert_not_called()
        devdetach_mock.assert_called()

        # Graphics change test case
        self.assertEqual(
            {
                "definition": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("my_vm", graphics={"type": "vnc"}),
        )
        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual("vnc", setxml.find("devices/graphics").get("type"))

        # Update with no diff case
        pool_mock = MagicMock()
        default_pool_desc = "<pool type='dir'></pool>"
        rbd_pool_desc = """
            <pool type='rbd'>
              <name>test-rbd</name>
              <source>
                <host name='ses2.tf.local'/>
                <host name='ses3.tf.local' port='1234'/>
                <name>libvirt-pool</name>
                <auth type='ceph' username='libvirt'>
                  <secret usage='pool_test-rbd'/>
                </auth>
              </source>
            </pool>
            """
        pool_mock.XMLDesc.side_effect = [
            default_pool_desc,
            rbd_pool_desc,
            default_pool_desc,
            rbd_pool_desc,
        ]
        self.mock_conn.storagePoolLookupByName.return_value = pool_mock
        self.mock_conn.listStoragePools.return_value = ["test-rbd", "default"]
        self.assertEqual(
            {
                "definition": False,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update(
                "my_vm",
                cpu=1,
                mem=1024,
                disk_profile="default",
                disks=[
                    {"name": "data", "size": 2048, "pool": "default"},
                    {
                        "name": "data2",
                        "size": 4096,
                        "pool": "test-rbd",
                        "format": "raw",
                    },
                ],
                nic_profile="myprofile",
                interfaces=[
                    {
                        "name": "eth0",
                        "type": "network",
                        "source": "default",
                        "mac": "52:54:00:39:02:b1",
                    },
                    {"name": "eth1", "type": "network", "source": "oldnet"},
                ],
                graphics={
                    "type": "spice",
                    "listen": {"type": "address", "address": "127.0.0.1"},
                },
            ),
        )

        # Failed XML description update case
        self.mock_conn.defineXML.side_effect = self.mock_libvirt.libvirtError(
            "Test error"
        )
        setmem_mock.reset_mock()
        with self.assertRaises(self.mock_libvirt.libvirtError):
            virt.update("my_vm", mem=2048)

        # Failed single update failure case
        self.mock_conn.defineXML = MagicMock(return_value=True)
        setmem_mock.side_effect = self.mock_libvirt.libvirtError(
            "Failed to live change memory"
        )
        self.assertEqual(
            {
                "definition": True,
                "errors": ["Failed to live change memory"],
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("my_vm", mem=2048),
        )

        # Failed multiple updates failure case
        self.assertEqual(
            {
                "definition": True,
                "errors": ["Failed to live change memory"],
                "cpu": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("my_vm", cpu=4, mem=2048),
        )

    def test_update_backing_store(self):
        """
        Test updating a disk with a backing store
        """
        xml = """
            <domain type='kvm' id='7'>
              <name>my_vm</name>
              <memory unit='KiB'>1048576</memory>
              <currentMemory unit='KiB'>1048576</currentMemory>
              <vcpu placement='auto'>1</vcpu>
              <os>
                <type arch='x86_64' machine='pc-i440fx-2.6'>hvm</type>
              </os>
              <devices>
                <disk type='volume' device='disk'>
                  <driver name='qemu' type='qcow2' cache='none' io='native'/>
                  <source pool='default' volume='my_vm_system' index='1'/>
                  <backingStore type='file' index='2'>
                    <format type='qcow2'/>
                    <source file='/path/to/base.qcow2'/>
                    <backingStore/>
                  </backingStore>
                  <target dev='vda' bus='virtio'/>
                  <alias name='virtio-disk0'/>
                  <address type='pci' domain='0x0000' bus='0x00' slot='0x04' function='0x0'/>
                </disk>
              </devices>
            </domain>
        """
        domain_mock = self.set_mock_vm("my_vm", xml)
        domain_mock.OSType.return_value = "hvm"
        self.mock_conn.defineXML.return_value = True
        updatedev_mock = MagicMock(return_value=0)
        domain_mock.updateDeviceFlags = updatedev_mock
        self.mock_conn.listStoragePools.return_value = ["default"]
        self.mock_conn.storagePoolLookupByName.return_value.XMLDesc.return_value = (
            "<pool type='dir'/>"
        )

        ret = virt.update(
            "my_vm",
            disks=[
                {
                    "name": "system",
                    "pool": "default",
                    "backing_store_path": "/path/to/base.qcow2",
                    "backing_store_format": "qcow2",
                },
            ],
        )
        self.assertFalse(ret["definition"])
        self.assertFalse(ret["disk"]["attached"])
        self.assertFalse(ret["disk"]["detached"])

    def test_update_removables(self):
        """
        Test attaching, detaching, changing removable devices
        """
        xml = """
            <domain type='kvm' id='7'>
              <name>my_vm</name>
              <memory unit='KiB'>1048576</memory>
              <currentMemory unit='KiB'>1048576</currentMemory>
              <vcpu placement='auto'>1</vcpu>
              <os>
                <type arch='x86_64' machine='pc-i440fx-2.6'>hvm</type>
              </os>
              <devices>
                <disk type='network' device='cdrom'>
                  <driver name='qemu' type='raw' cache='none' io='native'/>
                  <source protocol='https' name='/dvd-image-1.iso'>
                    <host name='test-srv.local' port='80'/>
                  </source>
                  <backingStore/>
                  <target dev='hda' bus='ide'/>
                  <readonly/>
                  <alias name='ide0-0-0'/>
                  <address type='drive' controller='0' bus='0' target='0' unit='0'/>
                </disk>
                <disk type='file' device='cdrom'>
                  <driver name='qemu' type='raw' cache='none' io='native'/>
                  <target dev='hdb' bus='ide'/>
                  <readonly/>
                  <alias name='ide0-0-1'/>
                  <address type='drive' controller='0' bus='0' target='0' unit='1'/>
                </disk>
                <disk type='file' device='cdrom'>
                  <driver name='qemu' type='raw' cache='none' io='native'/>
                  <source file='/srv/dvd-image-2.iso'/>
                  <backingStore/>
                  <target dev='hdc' bus='ide'/>
                  <readonly/>
                  <alias name='ide0-0-2'/>
                  <address type='drive' controller='0' bus='0' target='0' unit='2'/>
                </disk>
                <disk type='file' device='cdrom'>
                  <driver name='qemu' type='raw' cache='none' io='native'/>
                  <source file='/srv/dvd-image-3.iso'/>
                  <backingStore/>
                  <target dev='hdd' bus='ide'/>
                  <readonly/>
                  <alias name='ide0-0-3'/>
                  <address type='drive' controller='0' bus='0' target='0' unit='3'/>
                </disk>
                <disk type='network' device='cdrom'>
                  <driver name='qemu' type='raw' cache='none' io='native'/>
                  <source protocol='https' name='/dvd-image-6.iso'>
                    <host name='test-srv.local' port='80'/>
                  </source>
                  <backingStore/>
                  <target dev='hde' bus='ide'/>
                  <readonly/>
                </disk>
              </devices>
            </domain>
        """
        domain_mock = self.set_mock_vm("my_vm", xml)
        domain_mock.OSType.return_value = "hvm"
        self.mock_conn.defineXML.return_value = True
        updatedev_mock = MagicMock(return_value=0)
        domain_mock.updateDeviceFlags = updatedev_mock

        ret = virt.update(
            "my_vm",
            disks=[
                {
                    "name": "dvd1",
                    "device": "cdrom",
                    "source_file": None,
                    "model": "ide",
                },
                {
                    "name": "dvd2",
                    "device": "cdrom",
                    "source_file": "/srv/dvd-image-4.iso",
                    "model": "ide",
                },
                {
                    "name": "dvd3",
                    "device": "cdrom",
                    "source_file": "/srv/dvd-image-2.iso",
                    "model": "ide",
                },
                {
                    "name": "dvd4",
                    "device": "cdrom",
                    "source_file": "/srv/dvd-image-5.iso",
                    "model": "ide",
                },
                {
                    "name": "dvd5",
                    "device": "cdrom",
                    "source_file": "/srv/dvd-image-6.iso",
                    "model": "ide",
                },
            ],
        )

        self.assertTrue(ret["definition"])
        self.assertFalse(ret["disk"]["attached"])
        self.assertFalse(ret["disk"]["detached"])
        self.assertEqual(
            [
                {
                    "type": "file",
                    "device": "cdrom",
                    "driver": {
                        "name": "qemu",
                        "type": "raw",
                        "cache": "none",
                        "io": "native",
                    },
                    "backingStore": None,
                    "target": {"dev": "hda", "bus": "ide"},
                    "readonly": None,
                    "alias": {"name": "ide0-0-0"},
                    "address": {
                        "type": "drive",
                        "controller": "0",
                        "bus": "0",
                        "target": "0",
                        "unit": "0",
                    },
                },
                {
                    "type": "file",
                    "device": "cdrom",
                    "driver": {
                        "name": "qemu",
                        "type": "raw",
                        "cache": "none",
                        "io": "native",
                    },
                    "target": {"dev": "hdb", "bus": "ide"},
                    "readonly": None,
                    "alias": {"name": "ide0-0-1"},
                    "address": {
                        "type": "drive",
                        "controller": "0",
                        "bus": "0",
                        "target": "0",
                        "unit": "1",
                    },
                    "source": {"file": "/srv/dvd-image-4.iso"},
                },
                {
                    "type": "file",
                    "device": "cdrom",
                    "driver": {
                        "name": "qemu",
                        "type": "raw",
                        "cache": "none",
                        "io": "native",
                    },
                    "backingStore": None,
                    "target": {"dev": "hdd", "bus": "ide"},
                    "readonly": None,
                    "alias": {"name": "ide0-0-3"},
                    "address": {
                        "type": "drive",
                        "controller": "0",
                        "bus": "0",
                        "target": "0",
                        "unit": "3",
                    },
                    "source": {"file": "/srv/dvd-image-5.iso"},
                },
                {
                    "type": "file",
                    "device": "cdrom",
                    "driver": {
                        "name": "qemu",
                        "type": "raw",
                        "cache": "none",
                        "io": "native",
                    },
                    "backingStore": None,
                    "target": {"dev": "hde", "bus": "ide"},
                    "readonly": None,
                    "source": {"file": "/srv/dvd-image-6.iso"},
                },
            ],
            [
                salt.utils.xmlutil.to_dict(ET.fromstring(disk), True)
                for disk in ret["disk"]["updated"]
            ],
        )

    def test_update_xen_boot_params(self):
        """
        Test virt.update() a Xen definition no boot parameter.
        """
        root_dir = os.path.join(salt.syspaths.ROOT_DIR, "srv", "salt-images")
        xml_boot = """
            <domain type='xen' id='8'>
              <name>vm</name>
              <memory unit='KiB'>1048576</memory>
              <currentMemory unit='KiB'>1048576</currentMemory>
              <vcpu placement='auto'>1</vcpu>
              <os>
                <type arch='x86_64' machine='xenfv'>hvm</type>
                <loader type='rom'>/usr/lib/xen/boot/hvmloader</loader>
              </os>
            </domain>
        """
        domain_mock_boot = self.set_mock_vm("vm", xml_boot)
        domain_mock_boot.OSType = MagicMock(return_value="hvm")
        define_mock_boot = MagicMock(return_value=True)
        define_mock_boot.setVcpusFlags = MagicMock(return_value=0)
        self.mock_conn.defineXML = define_mock_boot
        self.assertEqual(
            {
                "cpu": False,
                "definition": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("vm", cpu=2),
        )
        setxml = ET.fromstring(define_mock_boot.call_args[0][0])
        self.assertEqual(setxml.find("os").find("loader").attrib.get("type"), "rom")
        self.assertEqual(
            setxml.find("os").find("loader").text, "/usr/lib/xen/boot/hvmloader"
        )

    def test_update_existing_boot_params(self):
        """
        Test virt.update() with existing boot parameters.
        """
        xml_boot = """
            <domain type='kvm' id='8'>
              <name>vm_with_boot_param</name>
              <memory unit='KiB'>1048576</memory>
              <currentMemory unit='KiB'>1048576</currentMemory>
              <vcpu placement='auto'>1</vcpu>
              <os>
                <type arch='x86_64' machine='pc-i440fx-2.6'>hvm</type>
                <kernel>/boot/oldkernel</kernel>
                <initrd>/boot/initrdold.img</initrd>
                <cmdline>console=ttyS0 ks=http://example.com/old/os/</cmdline>
                <loader>/usr/share/old/OVMF_CODE.fd</loader>
                <nvram>/usr/share/old/OVMF_VARS.ms.fd</nvram>
              </os>
              <devices>
                <disk type='file' device='disk'>
                  <driver name='qemu' type='qcow2'/>
                  <source file='{0}{1}vm_with_boot_param_system.qcow2'/>
                  <backingStore/>
                  <target dev='vda' bus='virtio'/>
                  <alias name='virtio-disk0'/>
                  <address type='pci' domain='0x0000' bus='0x00' slot='0x07' function='0x0'/>
                </disk>
                <disk type='file' device='disk'>
                  <driver name='qemu' type='qcow2'/>
                  <source file='{0}{1}vm_with_boot_param_data.qcow2'/>
                  <backingStore/>
                  <target dev='vdb' bus='virtio'/>
                  <alias name='virtio-disk1'/>
                  <address type='pci' domain='0x0000' bus='0x00' slot='0x07' function='0x1'/>
                </disk>
                <interface type='network'>
                  <mac address='52:54:00:39:02:b1'/>
                  <source network='default' bridge='virbr0'/>
                  <target dev='vnet0'/>
                  <model type='virtio'/>
                  <alias name='net0'/>
                  <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
                </interface>
                <interface type='network'>
                  <mac address='52:54:00:39:02:b2'/>
                  <source network='oldnet' bridge='virbr1'/>
                  <target dev='vnet1'/>
                  <model type='virtio'/>
                  <alias name='net1'/>
                  <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x1'/>
                </interface>
                <graphics type='spice' port='5900' autoport='yes' listen='127.0.0.1'>
                  <listen type='address' address='127.0.0.1'/>
                </graphics>
                <video>
                  <model type='qxl' ram='65536' vram='65536' vgamem='16384' heads='1' primary='yes'/>
                  <alias name='video0'/>
                  <address type='pci' domain='0x0000' bus='0x00' slot='0x02' function='0x0'/>
                </video>
              </devices>
            </domain>
        """
        domain_mock_boot = self.set_mock_vm("vm_with_boot_param", xml_boot)
        domain_mock_boot.OSType = MagicMock(return_value="hvm")
        define_mock_boot = MagicMock(return_value=True)
        self.mock_conn.defineXML = define_mock_boot
        boot_new = {
            "kernel": "/root/new-vmlinuz",
            "initrd": "/root/new-initrd",
            "cmdline": "console=ttyS0 ks=http://example.com/new/os/",
        }

        uefi_boot_new = {
            "loader": "/usr/share/new/OVMF_CODE.fd",
            "nvram": "/usr/share/new/OVMF_VARS.ms.fd",
        }

        self.assertEqual(
            {
                "definition": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("vm_with_boot_param", boot=boot_new),
        )
        setxml_boot = ET.fromstring(define_mock_boot.call_args[0][0])
        self.assertEqual(
            setxml_boot.find("os").find("kernel").text, "/root/new-vmlinuz"
        )
        self.assertEqual(setxml_boot.find("os").find("initrd").text, "/root/new-initrd")
        self.assertEqual(
            setxml_boot.find("os").find("cmdline").text,
            "console=ttyS0 ks=http://example.com/new/os/",
        )

        self.assertEqual(
            {
                "definition": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("vm_with_boot_param", boot=uefi_boot_new),
        )

        setxml = ET.fromstring(define_mock_boot.call_args[0][0])
        self.assertEqual(
            setxml.find("os").find("loader").text, "/usr/share/new/OVMF_CODE.fd"
        )
        self.assertEqual(setxml.find("os").find("loader").attrib.get("readonly"), "yes")
        self.assertEqual(setxml.find("os").find("loader").attrib["type"], "pflash")
        self.assertEqual(
            setxml.find("os").find("nvram").attrib["template"],
            "/usr/share/new/OVMF_VARS.ms.fd",
        )

        kernel_none = {
            "kernel": None,
            "initrd": None,
            "cmdline": None,
        }

        uefi_none = {"loader": None, "nvram": None}

        self.assertEqual(
            {
                "definition": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("vm_with_boot_param", boot=kernel_none),
        )

        setxml = ET.fromstring(define_mock_boot.call_args[0][0])
        self.assertEqual(setxml.find("os").find("kernel"), None)
        self.assertEqual(setxml.find("os").find("initrd"), None)
        self.assertEqual(setxml.find("os").find("cmdline"), None)

        self.assertEqual(
            {
                "definition": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("vm_with_boot_param", boot={"efi": False}),
        )
        setxml = ET.fromstring(define_mock_boot.call_args[0][0])
        self.assertEqual(setxml.find("os").find("nvram"), None)
        self.assertEqual(setxml.find("os").find("loader"), None)

        self.assertEqual(
            {
                "definition": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("vm_with_boot_param", boot=uefi_none),
        )

        setxml = ET.fromstring(define_mock_boot.call_args[0][0])
        self.assertEqual(setxml.find("os").find("loader"), None)
        self.assertEqual(setxml.find("os").find("nvram"), None)

    def test_update_memtune_params(self):
        """
        Test virt.update() with memory tuning parameters.
        """
        xml_with_memtune_params = """
            <domain type='kvm' id='8'>
              <name>vm_with_boot_param</name>
              <memory unit='KiB'>1048576</memory>
              <currentMemory unit='KiB'>1048576</currentMemory>
              <maxMemory slots="12" unit="bytes">1048576</maxMemory>
              <vcpu placement='auto'>1</vcpu>
              <memtune>
                <hard_limit unit="KiB">1048576</hard_limit>
                <soft_limit unit="KiB">2097152</soft_limit>
                <swap_hard_limit unit="KiB">2621440</swap_hard_limit>
                <min_guarantee unit='KiB'>671088</min_guarantee>
              </memtune>
              <os>
                <type arch='x86_64' machine='pc-i440fx-2.6'>hvm</type>
              </os>
            </domain>
        """
        domain_mock = self.set_mock_vm("vm_with_memtune_param", xml_with_memtune_params)
        domain_mock.OSType = MagicMock(return_value="hvm")
        define_mock = MagicMock(return_value=True)
        self.mock_conn.defineXML = define_mock

        memtune_new_val = {
            "boot": "0.7g",
            "current": "2.5g",
            "max": "3096m",
            "slots": "10",
            "soft_limit": "2048m",
            "hard_limit": "1024",
            "swap_hard_limit": "2.5g",
            "min_guarantee": "1 g",
        }

        domain_mock.setMemoryFlags.return_value = 0
        self.assertEqual(
            {
                "definition": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
                "mem": True,
            },
            virt.update("vm_with_memtune_param", mem=memtune_new_val),
        )
        self.assertEqual(
            domain_mock.setMemoryFlags.call_args[0][0], int(2.5 * 1024 ** 2)
        )

        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual(
            setxml.find("memtune").find("soft_limit").text, str(2048 * 1024)
        )
        self.assertEqual(
            setxml.find("memtune").find("hard_limit").text, str(1024 * 1024)
        )
        self.assertEqual(
            setxml.find("memtune").find("swap_hard_limit").text,
            str(int(2.5 * 1024 ** 2)),
        )
        self.assertEqual(
            setxml.find("memtune").find("swap_hard_limit").get("unit"), "KiB",
        )
        self.assertEqual(
            setxml.find("memtune").find("min_guarantee").text, str(1 * 1024 ** 3)
        )
        self.assertEqual(
            setxml.find("memtune").find("min_guarantee").attrib.get("unit"), "bytes"
        )
        self.assertEqual(setxml.find("maxMemory").text, str(3096 * 1024 ** 2))
        self.assertEqual(setxml.find("maxMemory").attrib.get("slots"), "10")
        self.assertEqual(setxml.find("currentMemory").text, str(int(2.5 * 1024 ** 3)))
        self.assertEqual(setxml.find("memory").text, str(int(0.7 * 1024 ** 3)))

        max_slot_reverse = {
            "slots": "10",
            "max": "3096m",
        }
        self.assertEqual(
            {
                "definition": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("vm_with_memtune_param", mem=max_slot_reverse),
        )
        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual(setxml.find("maxMemory").text, str(3096 * 1024 ** 2))
        self.assertEqual(setxml.find("maxMemory").get("unit"), "bytes")
        self.assertEqual(setxml.find("maxMemory").attrib.get("slots"), "10")

        max_swap_none = {
            "boot": "0.7g",
            "current": "2.5g",
            "max": None,
            "slots": "10",
            "soft_limit": "2048m",
            "hard_limit": "1024",
            "swap_hard_limit": None,
            "min_guarantee": "1 g",
        }

        domain_mock.setMemoryFlags.reset_mock()
        self.assertEqual(
            {
                "definition": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
                "mem": True,
            },
            virt.update("vm_with_memtune_param", mem=max_swap_none),
        )
        self.assertEqual(
            domain_mock.setMemoryFlags.call_args[0][0], int(2.5 * 1024 ** 2)
        )

        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual(
            setxml.find("memtune").find("soft_limit").text, str(2048 * 1024)
        )
        self.assertEqual(
            setxml.find("memtune").find("hard_limit").text, str(1024 * 1024)
        )
        self.assertEqual(setxml.find("memtune").find("swap_hard_limit"), None)
        self.assertEqual(
            setxml.find("memtune").find("min_guarantee").text, str(1 * 1024 ** 3)
        )
        self.assertEqual(
            setxml.find("memtune").find("min_guarantee").attrib.get("unit"), "bytes"
        )
        self.assertEqual(setxml.find("maxMemory").text, None)
        self.assertEqual(setxml.find("currentMemory").text, str(int(2.5 * 1024 ** 3)))
        self.assertEqual(setxml.find("memory").text, str(int(0.7 * 1024 ** 3)))

        memtune_none = {
            "soft_limit": None,
            "hard_limit": None,
            "swap_hard_limit": None,
            "min_guarantee": None,
        }

        self.assertEqual(
            {
                "definition": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("vm_with_memtune_param", mem=memtune_none),
        )

        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual(setxml.find("memtune").find("soft_limit"), None)
        self.assertEqual(setxml.find("memtune").find("hard_limit"), None)
        self.assertEqual(setxml.find("memtune").find("swap_hard_limit"), None)
        self.assertEqual(setxml.find("memtune").find("min_guarantee"), None)

        max_none = {
            "max": None,
        }

        self.assertEqual(
            {
                "definition": True,
                "disk": {"attached": [], "detached": [], "updated": []},
                "interface": {"attached": [], "detached": []},
            },
            virt.update("vm_with_memtune_param", mem=max_none),
        )

        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual(setxml.find("maxMemory"), None)
        self.assertEqual(setxml.find("currentMemory").text, str(int(1 * 1024 ** 2)))
        self.assertEqual(setxml.find("memory").text, str(int(1 * 1024 ** 2)))

    def test_handle_unit(self):
        """
        Test regex function for handling units
        """
        valid_case = [
            ("2", 2097152),
            ("42", 44040192),
            ("5b", 5),
            ("2.3Kib", 2355),
            ("5.8Kb", 5800),
            ("16MiB", 16777216),
            ("20 GB", 20000000000),
            ("16KB", 16000),
            (".5k", 512),
            ("2.k", 2048),
        ]

        for key, val in valid_case:
            self.assertEqual(virt._handle_unit(key), val)

        invalid_case = [
            ("9ib", "invalid units"),
            ("8byte", "invalid units"),
            ("512bytes", "invalid units"),
            ("4 Kbytes", "invalid units"),
            ("3.4.MB", "invalid number"),
            ("", "invalid number"),
            ("bytes", "invalid number"),
            ("2HB", "invalid units"),
        ]

        for key, val in invalid_case:
            with self.assertRaises(SaltInvocationError):
                virt._handle_unit(key)

    def test_mixed_dict_and_list_as_profile_objects(self):
        """
        Test virt._nic_profile with mixed dictionaries and lists as input.
        """
        yaml_config = """
          virt:
             nic:
                new-listonly-profile:
                   - bridge: br0
                     name: eth0
                   - model: virtio
                     name: eth1
                     source: test_network
                     type: network
                new-list-with-legacy-names:
                   - eth0:
                        bridge: br0
                   - eth1:
                        bridge: br1
                        model: virtio
                non-default-legacy-profile:
                   eth0:
                      bridge: br0
                   eth1:
                      bridge: br1
                      model: virtio
        """
        mock_config = salt.utils.yaml.safe_load(yaml_config)
        with patch.dict(
            salt.modules.config.__opts__, mock_config  # pylint: disable=no-member
        ):

            for name in mock_config["virt"]["nic"].keys():
                profile = salt.modules.virt._nic_profile(name, "kvm")
                self.assertEqual(len(profile), 2)

                interface_attrs = profile[0]
                self.assertIn("source", interface_attrs)
                self.assertIn("type", interface_attrs)
                self.assertIn("name", interface_attrs)
                self.assertIn("model", interface_attrs)
                self.assertEqual(interface_attrs["model"], "virtio")

    def test_get_xml(self):
        """
        Test virt.get_xml()
        """
        xml = """<domain type='kvm' id='7'>
              <name>test-vm</name>
              <devices>
                <graphics type='vnc' port='5900' autoport='yes' listen='0.0.0.0'>
                  <listen type='address' address='0.0.0.0'/>
                </graphics>
              </devices>
            </domain>
        """
        domain = self.set_mock_vm("test-vm", xml)
        self.assertEqual(xml, virt.get_xml("test-vm"))
        self.assertEqual(xml, virt.get_xml(domain))

    def test_get_loader(self):
        """
        Test virt.get_loader()
        """
        xml = """<domain type='kvm' id='7'>
              <name>test-vm</name>
              <os>
                <loader readonly='yes' type='pflash'>/foo/bar</loader>
              </os>
            </domain>
        """
        self.set_mock_vm("test-vm", xml)

        loader = virt.get_loader("test-vm")
        self.assertEqual("/foo/bar", loader["path"])
        self.assertEqual("yes", loader["readonly"])

    def test_cpu_baseline(self):
        """
        Test virt.cpu_baseline()
        """
        capabilities_xml = dedent(
            """<capabilities>
                  <host>
                    <uuid>44454c4c-3400-105a-8033-b3c04f4b344a</uuid>
                    <cpu>
                      <arch>x86_64</arch>
                      <vendor>Intel</vendor>
                    </cpu>
                  </host>
                </capabilities>"""
        )

        baseline_cpu_xml = b"""<cpu match="exact" mode="custom">
                                  <vendor>Intel</vendor>
                                </cpu>"""

        self.mock_conn.getCapabilities.return_value = capabilities_xml
        self.mock_conn.baselineCPU.return_value = baseline_cpu_xml
        self.assertMultiLineEqual(str(baseline_cpu_xml), str(virt.cpu_baseline()))

    def test_parse_qemu_img_info(self):
        """
        Make sure that qemu-img info output is properly parsed
        """
        qemu_infos = """[{
            "snapshots": [
                {
                    "vm-clock-nsec": 0,
                    "name": "first-snap",
                    "date-sec": 1528877587,
                    "date-nsec": 380589000,
                    "vm-clock-sec": 0,
                    "id": "1",
                    "vm-state-size": 1234
                },
                {
                    "vm-clock-nsec": 0,
                    "name": "second snap",
                    "date-sec": 1528877592,
                    "date-nsec": 933509000,
                    "vm-clock-sec": 0,
                    "id": "2",
                    "vm-state-size": 4567
                }
            ],
            "virtual-size": 25769803776,
            "filename": "/disks/test.qcow2",
            "cluster-size": 65536,
            "format": "qcow2",
            "actual-size": 217088,
            "format-specific": {
                "type": "qcow2",
                "data": {
                    "compat": "1.1",
                    "lazy-refcounts": false,
                    "refcount-bits": 16,
                    "corrupt": false
                }
            },
            "full-backing-filename": "/disks/mybacking.qcow2",
            "backing-filename": "mybacking.qcow2",
            "dirty-flag": false
        },
        {
            "virtual-size": 25769803776,
            "filename": "/disks/mybacking.qcow2",
            "cluster-size": 65536,
            "format": "qcow2",
            "actual-size": 393744384,
            "format-specific": {
                "type": "qcow2",
                "data": {
                    "compat": "1.1",
                    "lazy-refcounts": false,
                    "refcount-bits": 16,
                    "corrupt": false
                }
            },
            "full-backing-filename": "/disks/root.qcow2",
            "backing-filename": "root.qcow2",
            "dirty-flag": false
        },
        {
            "virtual-size": 25769803776,
            "filename": "/disks/root.qcow2",
            "cluster-size": 65536,
            "format": "qcow2",
            "actual-size": 196872192,
            "format-specific": {
                "type": "qcow2",
                "data": {
                    "compat": "1.1",
                    "lazy-refcounts": false,
                    "refcount-bits": 16,
                    "corrupt": false
                }
            },
            "dirty-flag": false
        }]"""

        self.assertEqual(
            {
                "file": "/disks/test.qcow2",
                "file format": "qcow2",
                "backing file": {
                    "file": "/disks/mybacking.qcow2",
                    "file format": "qcow2",
                    "disk size": 393744384,
                    "virtual size": 25769803776,
                    "cluster size": 65536,
                    "backing file": {
                        "file": "/disks/root.qcow2",
                        "file format": "qcow2",
                        "disk size": 196872192,
                        "virtual size": 25769803776,
                        "cluster size": 65536,
                    },
                },
                "disk size": 217088,
                "virtual size": 25769803776,
                "cluster size": 65536,
                "snapshots": [
                    {
                        "id": "1",
                        "tag": "first-snap",
                        "vmsize": 1234,
                        "date": datetime.datetime.fromtimestamp(
                            float("{}.{}".format(1528877587, 380589000))
                        ).isoformat(),
                        "vmclock": "00:00:00",
                    },
                    {
                        "id": "2",
                        "tag": "second snap",
                        "vmsize": 4567,
                        "date": datetime.datetime.fromtimestamp(
                            float("{}.{}".format(1528877592, 933509000))
                        ).isoformat(),
                        "vmclock": "00:00:00",
                    },
                ],
            },
            virt._parse_qemu_img_info(qemu_infos),
        )

    @patch("salt.modules.virt.stop", return_value=True)
    @patch("salt.modules.virt.undefine")
    @patch("os.remove")
    def test_purge_default(self, mock_remove, mock_undefine, mock_stop):
        """
        Test virt.purge() with default parameters
        """
        xml = """<domain type='kvm' id='7'>
              <name>test-vm</name>
              <devices>
                <disk type='file' device='disk'>
                <driver name='qemu' type='qcow2'/>
                <source file='/disks/test.qcow2'/>
                <target dev='vda' bus='virtio'/>
              </disk>
              <disk type='file' device='cdrom'>
                <driver name='qemu' type='raw'/>
                <source file='/disks/test-cdrom.iso'/>
                <target dev='hda' bus='ide'/>
                <readonly/>
              </disk>
              </devices>
            </domain>
        """
        self.set_mock_vm("test-vm", xml)

        qemu_infos = """[{
            "virtual-size": 25769803776,
            "filename": "/disks/test.qcow2",
            "cluster-size": 65536,
            "format": "qcow2",
            "actual-size": 217088,
            "format-specific": {
                "type": "qcow2",
                "data": {
                    "compat": "1.1",
                    "lazy-refcounts": false,
                    "refcount-bits": 16,
                    "corrupt": false
                }
            },
            "dirty-flag": false
        }]"""

        self.mock_popen.communicate.return_value = [
            qemu_infos
        ]  # pylint: disable=no-member

        with patch.dict(os.path.__dict__, {"exists": MagicMock(return_value=True)}):
            res = virt.purge("test-vm")
            self.assertTrue(res)
            mock_remove.assert_called_once()
            mock_remove.assert_any_call("/disks/test.qcow2")

    @patch("salt.modules.virt.stop", return_value=True)
    @patch("salt.modules.virt.undefine")
    def test_purge_volumes(self, mock_undefine, mock_stop):
        """
        Test virt.purge() with volume disks
        """
        xml = """<domain type='kvm' id='7'>
              <name>test-vm</name>
              <devices>
                <disk type='volume' device='disk'>
                  <driver name='qemu' type='qcow2' cache='none' io='native'/>
                  <source pool='default' volume='vm05_system'/>
                  <backingStore type='file' index='1'>
                    <format type='qcow2'/>
                    <source file='/var/lib/libvirt/images/vm04_system.qcow2'/>
                    <backingStore type='file' index='2'>
                      <format type='qcow2'/>
                      <source file='/var/testsuite-data/disk-image-template.qcow2'/>
                      <backingStore/>
                    </backingStore>
                  </backingStore>
                  <target dev='vda' bus='virtio'/>
                  <alias name='virtio-disk0'/>
                  <address type='pci' domain='0x0000' bus='0x00' slot='0x04' function='0x0'/>
                </disk>
              </devices>
            </domain>
        """
        self.set_mock_vm("test-vm", xml)

        pool_mock = MagicMock()
        pool_mock.storageVolLookupByName.return_value.info.return_value = [
            0,
            1234567,
            12345,
        ]
        pool_mock.storageVolLookupByName.return_value.XMLDesc.return_value = [
            """
            <volume type='file'>
              <name>vm05_system</name>
              <target>
                <path>/var/lib/libvirt/images/vm05_system</path>
                <format type='qcow2'/>
              </target>
              <backingStore>
                <path>/var/lib/libvirt/images/vm04_system.qcow2</path>
                <format type='qcow2'/>
              </backingStore>
            </volume>
            """,
        ]
        pool_mock.listVolumes.return_value = ["vm05_system", "vm04_system.qcow2"]
        self.mock_conn.storagePoolLookupByName.return_value = pool_mock
        self.mock_conn.listStoragePools.return_value = ["default"]

        with patch.dict(os.path.__dict__, {"exists": MagicMock(return_value=False)}):
            res = virt.purge("test-vm")
            self.assertTrue(res)
            pool_mock.storageVolLookupByName.return_value.delete.assert_called_once()

    @patch("salt.modules.virt.stop", return_value=True)
    @patch("salt.modules.virt.undefine")
    def test_purge_rbd(self, mock_undefine, mock_stop):
        """
        Test virt.purge() with RBD disks
        """
        xml = """<domain type='kvm' id='7'>
              <name>test-vm</name>
              <devices>
                <disk type="network" device="disk">
                  <driver name='raw' type='qcow2'/>
                  <source protocol='rbd' name='libvirt-pool/my_vm_data2'>
                    <host name='ses2.tf.local'/>
                    <host name='ses3.tf.local' port='1234'/>
                    <auth username='libvirt'>
                      <secret type='ceph' usage='pool_test-rbd'/>
                    </auth>
                  </source>
                  <target dev='vdc' bus='virtio'/>
                  <alias name='virtio-disk2'/>
                  <address type='pci' domain='0x0000' bus='0x00' slot='0x07' function='0x2'/>
                </disk>
              </devices>
            </domain>
        """
        self.set_mock_vm("test-vm", xml)

        pool_mock = MagicMock()
        pool_mock.storageVolLookupByName.return_value.info.return_value = [
            0,
            1234567,
            12345,
        ]
        pool_mock.XMLDesc.return_value = """
        <pool type='rbd'>
          <name>test-ses</name>
          <source>
            <host name='ses2.tf.local'/>
            <name>libvirt-pool</name>
            <auth type='ceph' username='libvirt'>
              <secret usage='pool_test-ses'/>
            </auth>
          </source>
        </pool>
        """
        pool_mock.name.return_value = "test-ses"
        pool_mock.storageVolLookupByName.return_value.XMLDesc.return_value = [
            """
            <volume type='network'>
              <name>my_vm_data2</name>
              <source>
              </source>
              <capacity unit='bytes'>536870912</capacity>
              <allocation unit='bytes'>0</allocation>
              <target>
                <path>libvirt-pool/my_vm_data2</path>
                <format type='raw'/>
              </target>
            </volume>
            """,
        ]
        pool_mock.listVolumes.return_value = ["my_vm_data2"]
        self.mock_conn.listAllStoragePools.return_value = [pool_mock]
        self.mock_conn.listStoragePools.return_value = ["test-ses"]
        self.mock_conn.storagePoolLookupByName.return_value = pool_mock

        with patch.dict(os.path.__dict__, {"exists": MagicMock(return_value=False)}):
            res = virt.purge("test-vm")
            self.assertTrue(res)
            pool_mock.storageVolLookupByName.return_value.delete.assert_called_once()

    @patch("salt.modules.virt.stop", return_value=True)
    @patch("salt.modules.virt.undefine")
    @patch("os.remove")
    def test_purge_removable(self, mock_remove, mock_undefine, mock_stop):
        """
        Test virt.purge(removables=True)
        """
        xml = """<domain type="kvm" id="7">
              <name>test-vm</name>
              <devices>
                <disk type='file' device='disk'>
                <driver name='qemu' type='qcow2'/>
                <source file='/disks/test.qcow2'/>
                <target dev='vda' bus='virtio'/>
              </disk>
              <disk type='file' device='cdrom'>
                <driver name='qemu' type='raw'/>
                <source file='/disks/test-cdrom.iso'/>
                <target dev='hda' bus='ide'/>
                <readonly/>
              </disk>
              <disk type='file' device='floppy'>
                <driver name='qemu' type='raw'/>
                <source file='/disks/test-floppy.iso'/>
                <target dev='hdb' bus='ide'/>
                <readonly/>
              </disk>
              </devices>
            </domain>
        """
        self.set_mock_vm("test-vm", xml)

        qemu_infos = """[{
            "virtual-size": 25769803776,
            "filename": "/disks/test.qcow2",
            "cluster-size": 65536,
            "format": "qcow2",
            "actual-size": 217088,
            "format-specific": {
                "type": "qcow2",
                "data": {
                    "compat": "1.1",
                    "lazy-refcounts": false,
                    "refcount-bits": 16,
                    "corrupt": false
                }
            },
            "dirty-flag": false
        }]"""

        self.mock_popen.communicate.return_value = [
            qemu_infos
        ]  # pylint: disable=no-member

        with patch.dict(os.path.__dict__, {"exists": MagicMock(return_value=True)}):
            res = virt.purge("test-vm", removables=True)
            self.assertTrue(res)
            mock_remove.assert_any_call("/disks/test.qcow2")
            mock_remove.assert_any_call("/disks/test-cdrom.iso")

    def test_capabilities(self):
        """
        Test the virt.capabilities parsing
        """
        xml = """
<capabilities>
  <host>
    <uuid>44454c4c-3400-105a-8033-b3c04f4b344a</uuid>
    <cpu>
      <arch>x86_64</arch>
      <model>Nehalem</model>
      <vendor>Intel</vendor>
      <microcode version='25'/>
      <topology sockets='1' cores='4' threads='2'/>
      <feature name='vme'/>
      <feature name='ds'/>
      <feature name='acpi'/>
      <pages unit='KiB' size='4'/>
      <pages unit='KiB' size='2048'/>
    </cpu>
    <power_management>
      <suspend_mem/>
      <suspend_disk/>
      <suspend_hybrid/>
    </power_management>
    <migration_features>
      <live/>
      <uri_transports>
        <uri_transport>tcp</uri_transport>
        <uri_transport>rdma</uri_transport>
      </uri_transports>
    </migration_features>
    <topology>
      <cells num='1'>
        <cell id='0'>
          <memory unit='KiB'>12367120</memory>
          <pages unit='KiB' size='4'>3091780</pages>
          <pages unit='KiB' size='2048'>0</pages>
          <distances>
            <sibling id='0' value='10'/>
          </distances>
          <cpus num='8'>
            <cpu id='0' socket_id='0' core_id='0' siblings='0,4'/>
            <cpu id='1' socket_id='0' core_id='1' siblings='1,5'/>
            <cpu id='2' socket_id='0' core_id='2' siblings='2,6'/>
            <cpu id='3' socket_id='0' core_id='3' siblings='3,7'/>
            <cpu id='4' socket_id='0' core_id='0' siblings='0,4'/>
            <cpu id='5' socket_id='0' core_id='1' siblings='1,5'/>
            <cpu id='6' socket_id='0' core_id='2' siblings='2,6'/>
            <cpu id='7' socket_id='0' core_id='3' siblings='3,7'/>
          </cpus>
        </cell>
      </cells>
    </topology>
    <cache>
      <bank id='0' level='3' type='both' size='8' unit='MiB' cpus='0-7'/>
    </cache>
    <secmodel>
      <model>apparmor</model>
      <doi>0</doi>
    </secmodel>
    <secmodel>
      <model>dac</model>
      <doi>0</doi>
      <baselabel type='kvm'>+487:+486</baselabel>
      <baselabel type='qemu'>+487:+486</baselabel>
    </secmodel>
  </host>

  <guest>
    <os_type>hvm</os_type>
    <arch name='i686'>
      <wordsize>32</wordsize>
      <emulator>/usr/bin/qemu-system-i386</emulator>
      <machine maxCpus='255'>pc-i440fx-2.6</machine>
      <machine canonical='pc-i440fx-2.6' maxCpus='255'>pc</machine>
      <machine maxCpus='255'>pc-0.12</machine>
      <domain type='qemu'/>
      <domain type='kvm'>
        <emulator>/usr/bin/qemu-kvm</emulator>
        <machine maxCpus='255'>pc-i440fx-2.6</machine>
        <machine canonical='pc-i440fx-2.6' maxCpus='255'>pc</machine>
        <machine maxCpus='255'>pc-0.12</machine>
      </domain>
    </arch>
    <features>
      <cpuselection/>
      <deviceboot/>
      <disksnapshot default='on' toggle='no'/>
      <acpi default='off' toggle='yes'/>
      <apic default='on' toggle='no'/>
      <pae/>
      <nonpae/>
    </features>
  </guest>

  <guest>
    <os_type>hvm</os_type>
    <arch name='x86_64'>
      <wordsize>64</wordsize>
      <emulator>/usr/bin/qemu-system-x86_64</emulator>
      <machine maxCpus='255'>pc-i440fx-2.6</machine>
      <machine canonical='pc-i440fx-2.6' maxCpus='255'>pc</machine>
      <machine maxCpus='255'>pc-0.12</machine>
      <domain type='qemu'/>
      <domain type='kvm'>
        <emulator>/usr/bin/qemu-kvm</emulator>
        <machine maxCpus='255'>pc-i440fx-2.6</machine>
        <machine canonical='pc-i440fx-2.6' maxCpus='255'>pc</machine>
        <machine maxCpus='255'>pc-0.12</machine>
      </domain>
    </arch>
    <features>
      <cpuselection/>
      <deviceboot/>
      <disksnapshot default='on' toggle='no'/>
      <acpi default='on' toggle='yes'/>
      <apic default='off' toggle='no'/>
    </features>
  </guest>

  <guest>
    <os_type>xen</os_type>
    <arch name='x86_64'>
      <wordsize>64</wordsize>
      <emulator>/usr/bin/qemu-system-x86_64</emulator>
      <machine>xenpv</machine>
      <domain type='xen'/>
    </arch>
  </guest>

</capabilities>
        """
        self.mock_conn.getCapabilities.return_value = xml  # pylint: disable=no-member
        caps = virt.capabilities()

        expected = {
            "host": {
                "uuid": "44454c4c-3400-105a-8033-b3c04f4b344a",
                "cpu": {
                    "arch": "x86_64",
                    "model": "Nehalem",
                    "vendor": "Intel",
                    "microcode": "25",
                    "sockets": 1,
                    "cores": 4,
                    "threads": 2,
                    "features": ["vme", "ds", "acpi"],
                    "pages": [{"size": "4 KiB"}, {"size": "2048 KiB"}],
                },
                "power_management": ["suspend_mem", "suspend_disk", "suspend_hybrid"],
                "migration": {"live": True, "transports": ["tcp", "rdma"]},
                "topology": {
                    "cells": [
                        {
                            "id": 0,
                            "memory": "12367120 KiB",
                            "pages": [
                                {"size": "4 KiB", "available": 3091780},
                                {"size": "2048 KiB", "available": 0},
                            ],
                            "distances": {0: 10},
                            "cpus": [
                                {
                                    "id": 0,
                                    "socket_id": 0,
                                    "core_id": 0,
                                    "siblings": "0,4",
                                },
                                {
                                    "id": 1,
                                    "socket_id": 0,
                                    "core_id": 1,
                                    "siblings": "1,5",
                                },
                                {
                                    "id": 2,
                                    "socket_id": 0,
                                    "core_id": 2,
                                    "siblings": "2,6",
                                },
                                {
                                    "id": 3,
                                    "socket_id": 0,
                                    "core_id": 3,
                                    "siblings": "3,7",
                                },
                                {
                                    "id": 4,
                                    "socket_id": 0,
                                    "core_id": 0,
                                    "siblings": "0,4",
                                },
                                {
                                    "id": 5,
                                    "socket_id": 0,
                                    "core_id": 1,
                                    "siblings": "1,5",
                                },
                                {
                                    "id": 6,
                                    "socket_id": 0,
                                    "core_id": 2,
                                    "siblings": "2,6",
                                },
                                {
                                    "id": 7,
                                    "socket_id": 0,
                                    "core_id": 3,
                                    "siblings": "3,7",
                                },
                            ],
                        }
                    ]
                },
                "cache": {
                    "banks": [
                        {
                            "id": 0,
                            "level": 3,
                            "type": "both",
                            "size": "8 MiB",
                            "cpus": "0-7",
                        }
                    ]
                },
                "security": [
                    {"model": "apparmor", "doi": "0", "baselabels": []},
                    {
                        "model": "dac",
                        "doi": "0",
                        "baselabels": [
                            {"type": "kvm", "label": "+487:+486"},
                            {"type": "qemu", "label": "+487:+486"},
                        ],
                    },
                ],
            },
            "guests": [
                {
                    "os_type": "hvm",
                    "arch": {
                        "name": "i686",
                        "wordsize": 32,
                        "emulator": "/usr/bin/qemu-system-i386",
                        "machines": {
                            "pc-i440fx-2.6": {
                                "maxcpus": 255,
                                "alternate_names": ["pc"],
                            },
                            "pc-0.12": {"maxcpus": 255, "alternate_names": []},
                        },
                        "domains": {
                            "qemu": {"emulator": None, "machines": {}},
                            "kvm": {
                                "emulator": "/usr/bin/qemu-kvm",
                                "machines": {
                                    "pc-i440fx-2.6": {
                                        "maxcpus": 255,
                                        "alternate_names": ["pc"],
                                    },
                                    "pc-0.12": {"maxcpus": 255, "alternate_names": []},
                                },
                            },
                        },
                    },
                    "features": {
                        "cpuselection": {"default": True, "toggle": False},
                        "deviceboot": {"default": True, "toggle": False},
                        "disksnapshot": {"default": True, "toggle": False},
                        "acpi": {"default": False, "toggle": True},
                        "apic": {"default": True, "toggle": False},
                        "pae": {"default": True, "toggle": False},
                        "nonpae": {"default": True, "toggle": False},
                    },
                },
                {
                    "os_type": "hvm",
                    "arch": {
                        "name": "x86_64",
                        "wordsize": 64,
                        "emulator": "/usr/bin/qemu-system-x86_64",
                        "machines": {
                            "pc-i440fx-2.6": {
                                "maxcpus": 255,
                                "alternate_names": ["pc"],
                            },
                            "pc-0.12": {"maxcpus": 255, "alternate_names": []},
                        },
                        "domains": {
                            "qemu": {"emulator": None, "machines": {}},
                            "kvm": {
                                "emulator": "/usr/bin/qemu-kvm",
                                "machines": {
                                    "pc-i440fx-2.6": {
                                        "maxcpus": 255,
                                        "alternate_names": ["pc"],
                                    },
                                    "pc-0.12": {"maxcpus": 255, "alternate_names": []},
                                },
                            },
                        },
                    },
                    "features": {
                        "cpuselection": {"default": True, "toggle": False},
                        "deviceboot": {"default": True, "toggle": False},
                        "disksnapshot": {"default": True, "toggle": False},
                        "acpi": {"default": True, "toggle": True},
                        "apic": {"default": False, "toggle": False},
                    },
                },
                {
                    "os_type": "xen",
                    "arch": {
                        "name": "x86_64",
                        "wordsize": 64,
                        "emulator": "/usr/bin/qemu-system-x86_64",
                        "machines": {"xenpv": {"alternate_names": []}},
                        "domains": {"xen": {"emulator": None, "machines": {}}},
                    },
                },
            ],
        }
        self.assertEqual(expected, caps)

    def test_network(self):
        """
        Test virt._get_net_xml()
        """
        xml_data = virt._gen_net_xml("network", "main", "bridge", "openvswitch")
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("name").text, "network")
        self.assertEqual(root.find("bridge").attrib["name"], "main")
        self.assertEqual(root.find("forward").attrib["mode"], "bridge")
        self.assertEqual(root.find("virtualport").attrib["type"], "openvswitch")

    def test_network_nat(self):
        """
        Test virt._get_net_xml() in a nat setup
        """
        xml_data = virt._gen_net_xml(
            "network",
            "main",
            "nat",
            None,
            ip_configs=[
                {
                    "cidr": "192.168.2.0/24",
                    "dhcp_ranges": [
                        {"start": "192.168.2.10", "end": "192.168.2.25"},
                        {"start": "192.168.2.110", "end": "192.168.2.125"},
                    ],
                }
            ],
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("name").text, "network")
        self.assertEqual(root.find("bridge").attrib["name"], "main")
        self.assertEqual(root.find("forward").attrib["mode"], "nat")
        self.assertEqual(
            root.find("./ip[@address='192.168.2.0']").attrib["prefix"], "24"
        )
        self.assertEqual(
            root.find("./ip[@address='192.168.2.0']").attrib["family"], "ipv4"
        )
        self.assertEqual(
            root.find(
                "./ip[@address='192.168.2.0']/dhcp/range[@start='192.168.2.10']"
            ).attrib["end"],
            "192.168.2.25",
        )
        self.assertEqual(
            root.find(
                "./ip[@address='192.168.2.0']/dhcp/range[@start='192.168.2.110']"
            ).attrib["end"],
            "192.168.2.125",
        )

    def test_domain_capabilities(self):
        """
        Test the virt.domain_capabilities parsing
        """
        xml = """
<domainCapabilities>
  <path>/usr/bin/qemu-system-aarch64</path>
  <domain>kvm</domain>
  <machine>virt-2.12</machine>
  <arch>aarch64</arch>
  <vcpu max='255'/>
  <iothreads supported='yes'/>
  <os supported='yes'>
    <loader supported='yes'>
      <value>/usr/share/AAVMF/AAVMF_CODE.fd</value>
      <value>/usr/share/AAVMF/AAVMF32_CODE.fd</value>
      <value>/usr/share/OVMF/OVMF_CODE.fd</value>
      <enum name='type'>
        <value>rom</value>
        <value>pflash</value>
      </enum>
      <enum name='readonly'>
        <value>yes</value>
        <value>no</value>
      </enum>
    </loader>
  </os>
  <cpu>
    <mode name='host-passthrough' supported='yes'/>
    <mode name='host-model' supported='yes'>
      <model fallback='forbid'>sample-cpu</model>
      <vendor>ACME</vendor>
      <feature policy='require' name='vme'/>
      <feature policy='require' name='ss'/>
    </mode>
    <mode name='custom' supported='yes'>
      <model usable='unknown'>pxa262</model>
      <model usable='yes'>pxa270-a0</model>
      <model usable='no'>arm1136</model>
    </mode>
  </cpu>
  <devices>
    <disk supported='yes'>
      <enum name='diskDevice'>
        <value>disk</value>
        <value>cdrom</value>
        <value>floppy</value>
        <value>lun</value>
      </enum>
      <enum name='bus'>
        <value>fdc</value>
        <value>scsi</value>
        <value>virtio</value>
        <value>usb</value>
        <value>sata</value>
      </enum>
    </disk>
    <graphics supported='yes'>
      <enum name='type'>
        <value>sdl</value>
        <value>vnc</value>
      </enum>
    </graphics>
    <video supported='yes'>
      <enum name='modelType'>
        <value>vga</value>
        <value>virtio</value>
      </enum>
    </video>
    <hostdev supported='yes'>
      <enum name='mode'>
        <value>subsystem</value>
      </enum>
      <enum name='startupPolicy'>
        <value>default</value>
        <value>mandatory</value>
        <value>requisite</value>
        <value>optional</value>
      </enum>
      <enum name='subsysType'>
        <value>usb</value>
        <value>pci</value>
        <value>scsi</value>
      </enum>
      <enum name='capsType'/>
      <enum name='pciBackend'>
        <value>default</value>
        <value>kvm</value>
        <value>vfio</value>
      </enum>
    </hostdev>
  </devices>
  <features>
    <gic supported='yes'>
      <enum name='version'>
        <value>3</value>
      </enum>
    </gic>
    <vmcoreinfo supported='yes'/>
  </features>
</domainCapabilities>
        """

        self.mock_conn.getDomainCapabilities.return_value = (
            xml  # pylint: disable=no-member
        )
        caps = virt.domain_capabilities()

        expected = {
            "emulator": "/usr/bin/qemu-system-aarch64",
            "domain": "kvm",
            "machine": "virt-2.12",
            "arch": "aarch64",
            "max_vcpus": 255,
            "iothreads": True,
            "os": {
                "loader": {
                    "type": ["rom", "pflash"],
                    "readonly": ["yes", "no"],
                    "values": [
                        "/usr/share/AAVMF/AAVMF_CODE.fd",
                        "/usr/share/AAVMF/AAVMF32_CODE.fd",
                        "/usr/share/OVMF/OVMF_CODE.fd",
                    ],
                }
            },
            "cpu": {
                "host-passthrough": True,
                "host-model": {
                    "model": {"name": "sample-cpu", "fallback": "forbid"},
                    "vendor": "ACME",
                    "features": {"vme": "require", "ss": "require"},
                },
                "custom": {
                    "models": {"pxa262": "unknown", "pxa270-a0": "yes", "arm1136": "no"}
                },
            },
            "devices": {
                "disk": {
                    "diskDevice": ["disk", "cdrom", "floppy", "lun"],
                    "bus": ["fdc", "scsi", "virtio", "usb", "sata"],
                },
                "graphics": {"type": ["sdl", "vnc"]},
                "video": {"modelType": ["vga", "virtio"]},
                "hostdev": {
                    "mode": ["subsystem"],
                    "startupPolicy": ["default", "mandatory", "requisite", "optional"],
                    "subsysType": ["usb", "pci", "scsi"],
                    "capsType": [],
                    "pciBackend": ["default", "kvm", "vfio"],
                },
            },
            "features": {"gic": {"version": ["3"]}, "vmcoreinfo": {}},
        }

        self.assertEqual(expected, caps)

    def test_all_capabilities(self):
        """
        Test the virt.domain_capabilities default output
        """
        domainXml = """
<domainCapabilities>
  <path>/usr/bin/qemu-system-x86_64</path>
  <domain>kvm</domain>
  <machine>virt-2.12</machine>
  <arch>x86_64</arch>
  <vcpu max='255'/>
  <iothreads supported='yes'/>
</domainCapabilities>
        """
        hostXml = """
<capabilities>
  <host>
    <uuid>44454c4c-3400-105a-8033-b3c04f4b344a</uuid>
    <cpu>
      <arch>x86_64</arch>
      <model>Nehalem</model>
      <vendor>Intel</vendor>
      <microcode version='25'/>
      <topology sockets='1' cores='4' threads='2'/>
    </cpu>
  </host>
  <guest>
    <os_type>hvm</os_type>
    <arch name='x86_64'>
      <wordsize>64</wordsize>
      <emulator>/usr/bin/qemu-system-x86_64</emulator>
      <machine maxCpus='255'>pc-i440fx-2.6</machine>
      <machine canonical='pc-i440fx-2.6' maxCpus='255'>pc</machine>
      <machine maxCpus='255'>pc-0.12</machine>
      <domain type='qemu'/>
      <domain type='kvm'>
        <emulator>/usr/bin/qemu-kvm</emulator>
        <machine maxCpus='255'>pc-i440fx-2.6</machine>
        <machine canonical='pc-i440fx-2.6' maxCpus='255'>pc</machine>
        <machine maxCpus='255'>pc-0.12</machine>
      </domain>
    </arch>
  </guest>
</capabilities>
        """

        # pylint: disable=no-member
        self.mock_conn.getCapabilities.return_value = hostXml
        self.mock_conn.getDomainCapabilities.side_effect = [
            domainXml,
            domainXml.replace("<domain>kvm", "<domain>qemu"),
        ]
        # pylint: enable=no-member

        caps = virt.all_capabilities()
        self.assertEqual(
            "44454c4c-3400-105a-8033-b3c04f4b344a", caps["host"]["host"]["uuid"]
        )
        self.assertEqual(
            {"qemu", "kvm"}, {domainCaps["domain"] for domainCaps in caps["domains"]},
        )

    def test_network_tag(self):
        """
        Test virt._get_net_xml() with VLAN tag
        """
        xml_data = virt._gen_net_xml("network", "main", "bridge", "openvswitch", 1001)
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("name").text, "network")
        self.assertEqual(root.find("bridge").attrib["name"], "main")
        self.assertEqual(root.find("forward").attrib["mode"], "bridge")
        self.assertEqual(root.find("virtualport").attrib["type"], "openvswitch")
        self.assertEqual(root.find("vlan/tag").attrib["id"], "1001")

    def test_list_networks(self):
        """
        Test virt.list_networks()
        """
        names = ["net1", "default", "net2"]
        net_mocks = [MagicMock(), MagicMock(), MagicMock()]
        for i, value in enumerate(names):
            net_mocks[i].name.return_value = value

        self.mock_conn.listAllNetworks.return_value = (
            net_mocks  # pylint: disable=no-member
        )
        actual = virt.list_networks()
        self.assertEqual(names, actual)

    def test_network_info(self):
        """
        Test virt.network_info()
        """
        self.mock_libvirt.VIR_IP_ADDR_TYPE_IPV4 = 0
        self.mock_libvirt.VIR_IP_ADDR_TYPE_IPV6 = 1

        net_mock = MagicMock()

        # pylint: disable=no-member
        net_mock.name.return_value = "foo"
        net_mock.UUIDString.return_value = "some-uuid"
        net_mock.bridgeName.return_value = "br0"
        net_mock.autostart.return_value = True
        net_mock.isActive.return_value = False
        net_mock.isPersistent.return_value = True
        net_mock.DHCPLeases.return_value = [
            {
                "iface": "virbr0",
                "expirytime": 1527757552,
                "type": 0,
                "mac": "52:54:00:01:71:bd",
                "ipaddr": "192.168.122.45",
                "prefix": 24,
                "hostname": "py3-test",
                "clientid": "01:52:54:00:01:71:bd",
                "iaid": None,
            }
        ]
        self.mock_conn.listAllNetworks.return_value = [net_mock]
        # pylint: enable=no-member

        net = virt.network_info("foo")
        self.assertEqual(
            {
                "foo": {
                    "uuid": "some-uuid",
                    "bridge": "br0",
                    "autostart": True,
                    "active": False,
                    "persistent": True,
                    "leases": [
                        {
                            "iface": "virbr0",
                            "expirytime": 1527757552,
                            "type": "ipv4",
                            "mac": "52:54:00:01:71:bd",
                            "ipaddr": "192.168.122.45",
                            "prefix": 24,
                            "hostname": "py3-test",
                            "clientid": "01:52:54:00:01:71:bd",
                            "iaid": None,
                        }
                    ],
                }
            },
            net,
        )

    def test_network_info_all(self):
        """
        Test virt.network_info()
        """
        self.mock_libvirt.VIR_IP_ADDR_TYPE_IPV4 = 0
        self.mock_libvirt.VIR_IP_ADDR_TYPE_IPV6 = 1

        net_mocks = []
        # pylint: disable=no-member
        for i in range(2):
            net_mock = MagicMock()

            net_mock.name.return_value = "net{}".format(i)
            net_mock.UUIDString.return_value = "some-uuid"
            net_mock.bridgeName.return_value = "br{}".format(i)
            net_mock.autostart.return_value = True
            net_mock.isActive.return_value = False
            net_mock.isPersistent.return_value = True
            net_mock.DHCPLeases.return_value = []
            net_mocks.append(net_mock)
        self.mock_conn.listAllNetworks.return_value = net_mocks
        # pylint: enable=no-member

        net = virt.network_info()
        self.assertEqual(
            {
                "net0": {
                    "uuid": "some-uuid",
                    "bridge": "br0",
                    "autostart": True,
                    "active": False,
                    "persistent": True,
                    "leases": [],
                },
                "net1": {
                    "uuid": "some-uuid",
                    "bridge": "br1",
                    "autostart": True,
                    "active": False,
                    "persistent": True,
                    "leases": [],
                },
            },
            net,
        )

    def test_network_info_notfound(self):
        """
        Test virt.network_info() when the network can't be found
        """
        # pylint: disable=no-member
        self.mock_conn.listAllNetworks.return_value = []
        # pylint: enable=no-member
        net = virt.network_info("foo")
        self.assertEqual({}, net)

    def test_network_get_xml(self):
        """
        Test virt.network_get_xml
        """
        network_mock = MagicMock()
        network_mock.XMLDesc.return_value = "<net>Raw XML</net>"
        self.mock_conn.networkLookupByName.return_value = network_mock

        self.assertEqual("<net>Raw XML</net>", virt.network_get_xml("default"))

    def test_pool(self):
        """
        Test virt._gen_pool_xml()
        """
        xml_data = virt._gen_pool_xml("pool", "logical", "/dev/base")
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("name").text, "pool")
        self.assertEqual(root.attrib["type"], "logical")
        self.assertEqual(root.find("target/path").text, "/dev/base")

    def test_pool_with_source(self):
        """
        Test virt._gen_pool_xml() with a source device
        """
        xml_data = virt._gen_pool_xml(
            "pool", "logical", "/dev/base", source_devices=[{"path": "/dev/sda"}]
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("name").text, "pool")
        self.assertEqual(root.attrib["type"], "logical")
        self.assertEqual(root.find("target/path").text, "/dev/base")
        self.assertEqual(root.find("source/device").attrib["path"], "/dev/sda")

    def test_pool_with_scsi(self):
        """
        Test virt._gen_pool_xml() with a SCSI source
        """
        xml_data = virt._gen_pool_xml(
            "pool",
            "scsi",
            "/dev/disk/by-path",
            source_devices=[{"path": "/dev/sda"}],
            source_adapter={
                "type": "scsi_host",
                "parent_address": {
                    "unique_id": 5,
                    "address": {
                        "domain": "0x0000",
                        "bus": "0x00",
                        "slot": "0x1f",
                        "function": "0x2",
                    },
                },
            },
            source_name="srcname",
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("name").text, "pool")
        self.assertEqual(root.attrib["type"], "scsi")
        self.assertEqual(root.find("target/path").text, "/dev/disk/by-path")
        self.assertEqual(root.find("source/device"), None)
        self.assertEqual(root.find("source/name"), None)
        self.assertEqual(root.find("source/adapter").attrib["type"], "scsi_host")
        self.assertEqual(
            root.find("source/adapter/parentaddr").attrib["unique_id"], "5"
        )
        self.assertEqual(
            root.find("source/adapter/parentaddr/address").attrib["domain"], "0x0000"
        )
        self.assertEqual(
            root.find("source/adapter/parentaddr/address").attrib["bus"], "0x00"
        )
        self.assertEqual(
            root.find("source/adapter/parentaddr/address").attrib["slot"], "0x1f"
        )
        self.assertEqual(
            root.find("source/adapter/parentaddr/address").attrib["function"], "0x2"
        )

    def test_pool_with_rbd(self):
        """
        Test virt._gen_pool_xml() with an RBD source
        """
        xml_data = virt._gen_pool_xml(
            "pool",
            "rbd",
            source_devices=[{"path": "/dev/sda"}],
            source_hosts=["1.2.3.4", "my.ceph.monitor:69"],
            source_auth={
                "type": "ceph",
                "username": "admin",
                "secret": {"type": "uuid", "value": "someuuid"},
            },
            source_name="srcname",
            source_adapter={"type": "scsi_host", "name": "host0"},
            source_dir="/some/dir",
            source_format="fmt",
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("name").text, "pool")
        self.assertEqual(root.attrib["type"], "rbd")
        self.assertEqual(root.find("target"), None)
        self.assertEqual(root.find("source/device"), None)
        self.assertEqual(root.find("source/name").text, "srcname")
        self.assertEqual(root.find("source/adapter"), None)
        self.assertEqual(root.find("source/dir"), None)
        self.assertEqual(root.find("source/format"), None)
        self.assertEqual(root.findall("source/host")[0].attrib["name"], "1.2.3.4")
        self.assertTrue("port" not in root.findall("source/host")[0].attrib)
        self.assertEqual(
            root.findall("source/host")[1].attrib["name"], "my.ceph.monitor"
        )
        self.assertEqual(root.findall("source/host")[1].attrib["port"], "69")
        self.assertEqual(root.find("source/auth").attrib["type"], "ceph")
        self.assertEqual(root.find("source/auth").attrib["username"], "admin")
        self.assertEqual(root.find("source/auth/secret").attrib["uuid"], "someuuid")

    def test_pool_with_netfs(self):
        """
        Test virt._gen_pool_xml() with a netfs source
        """
        xml_data = virt._gen_pool_xml(
            "pool",
            "netfs",
            target="/path/to/target",
            permissions={
                "mode": "0770",
                "owner": 1000,
                "group": 100,
                "label": "seclabel",
            },
            source_devices=[{"path": "/dev/sda"}],
            source_hosts=["nfs.host"],
            source_name="srcname",
            source_adapter={"type": "scsi_host", "name": "host0"},
            source_dir="/some/dir",
            source_format="nfs",
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("name").text, "pool")
        self.assertEqual(root.attrib["type"], "netfs")
        self.assertEqual(root.find("target/path").text, "/path/to/target")
        self.assertEqual(root.find("target/permissions/mode").text, "0770")
        self.assertEqual(root.find("target/permissions/owner").text, "1000")
        self.assertEqual(root.find("target/permissions/group").text, "100")
        self.assertEqual(root.find("target/permissions/label").text, "seclabel")
        self.assertEqual(root.find("source/device"), None)
        self.assertEqual(root.find("source/name"), None)
        self.assertEqual(root.find("source/adapter"), None)
        self.assertEqual(root.find("source/dir").attrib["path"], "/some/dir")
        self.assertEqual(root.find("source/format").attrib["type"], "nfs")
        self.assertEqual(root.find("source/host").attrib["name"], "nfs.host")
        self.assertEqual(root.find("source/auth"), None)

    def test_pool_with_iscsi_direct(self):
        """
        Test virt._gen_pool_xml() with a iscsi-direct source
        """
        xml_data = virt._gen_pool_xml(
            "pool",
            "iscsi-direct",
            source_hosts=["iscsi.example.com"],
            source_devices=[{"path": "iqn.2013-06.com.example:iscsi-pool"}],
            source_initiator="iqn.2013-06.com.example:iscsi-initiator",
        )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find("name").text, "pool")
        self.assertEqual(root.attrib["type"], "iscsi-direct")
        self.assertEqual(root.find("target"), None)
        self.assertEqual(
            root.find("source/device").attrib["path"],
            "iqn.2013-06.com.example:iscsi-pool",
        )
        self.assertEqual(
            root.findall("source/host")[0].attrib["name"], "iscsi.example.com"
        )
        self.assertEqual(
            root.find("source/initiator/iqn").attrib["name"],
            "iqn.2013-06.com.example:iscsi-initiator",
        )

    def test_pool_define(self):
        """
        Test virt.pool_define()
        """
        mock_pool = MagicMock()
        mock_secret = MagicMock()
        mock_secret_define = MagicMock(return_value=mock_secret)
        self.mock_conn.secretDefineXML = mock_secret_define
        self.mock_conn.storagePoolCreateXML = MagicMock(return_value=mock_pool)
        self.mock_conn.storagePoolDefineXML = MagicMock(return_value=mock_pool)

        mocks = [
            mock_pool,
            mock_secret,
            mock_secret_define,
            self.mock_conn.storagePoolCreateXML,
            self.mock_conn.secretDefineXML,
            self.mock_conn.storagePoolDefineXML,
        ]

        # Test case with already defined secret and permanent pool
        self.assertTrue(
            virt.pool_define(
                "default",
                "rbd",
                source_hosts=["one.example.com", "two.example.com"],
                source_name="rbdvol",
                source_auth={
                    "type": "ceph",
                    "username": "admin",
                    "secret": {"type": "uuid", "value": "someuuid"},
                },
            )
        )
        self.mock_conn.storagePoolDefineXML.assert_called_once()
        self.mock_conn.storagePoolCreateXML.assert_not_called()
        mock_pool.create.assert_called_once()
        mock_secret_define.assert_not_called()

        # Test case with Ceph secret to be defined and transient pool
        for mock in mocks:
            mock.reset_mock()
        self.assertTrue(
            virt.pool_define(
                "default",
                "rbd",
                transient=True,
                source_hosts=["one.example.com", "two.example.com"],
                source_name="rbdvol",
                source_auth={"username": "admin", "password": "c2VjcmV0"},
            )
        )
        self.mock_conn.storagePoolDefineXML.assert_not_called()

        pool_xml = self.mock_conn.storagePoolCreateXML.call_args[0][0]
        root = ET.fromstring(pool_xml)
        self.assertEqual(root.find("source/auth").attrib["type"], "ceph")
        self.assertEqual(root.find("source/auth").attrib["username"], "admin")
        self.assertEqual(
            root.find("source/auth/secret").attrib["usage"], "pool_default"
        )
        mock_pool.create.assert_not_called()
        mock_secret.setValue.assert_called_once_with(b"secret")

        secret_xml = mock_secret_define.call_args[0][0]
        root = ET.fromstring(secret_xml)
        self.assertEqual(root.find("usage/name").text, "pool_default")
        self.assertEqual(root.find("usage").attrib["type"], "ceph")
        self.assertEqual(root.attrib["private"], "yes")
        self.assertEqual(
            root.find("description").text, "Passphrase for default pool created by Salt"
        )

        # Test case with iscsi secret not starting
        for mock in mocks:
            mock.reset_mock()
        self.assertTrue(
            virt.pool_define(
                "default",
                "iscsi",
                target="/dev/disk/by-path",
                source_hosts=["iscsi.example.com"],
                source_devices=[{"path": "iqn.2013-06.com.example:iscsi-pool"}],
                source_auth={"username": "admin", "password": "secret"},
                start=False,
            )
        )
        self.mock_conn.storagePoolCreateXML.assert_not_called()

        pool_xml = self.mock_conn.storagePoolDefineXML.call_args[0][0]
        root = ET.fromstring(pool_xml)
        self.assertEqual(root.find("source/auth").attrib["type"], "chap")
        self.assertEqual(root.find("source/auth").attrib["username"], "admin")
        self.assertEqual(
            root.find("source/auth/secret").attrib["usage"], "pool_default"
        )
        mock_pool.create.assert_not_called()
        mock_secret.setValue.assert_called_once_with("secret")

        secret_xml = mock_secret_define.call_args[0][0]
        root = ET.fromstring(secret_xml)
        self.assertEqual(root.find("usage/target").text, "pool_default")
        self.assertEqual(root.find("usage").attrib["type"], "iscsi")
        self.assertEqual(root.attrib["private"], "yes")
        self.assertEqual(
            root.find("description").text, "Passphrase for default pool created by Salt"
        )

    def test_list_pools(self):
        """
        Test virt.list_pools()
        """
        names = ["pool1", "default", "pool2"]
        pool_mocks = [MagicMock(), MagicMock(), MagicMock()]
        for i, value in enumerate(names):
            pool_mocks[i].name.return_value = value

        self.mock_conn.listAllStoragePools.return_value = (
            pool_mocks  # pylint: disable=no-member
        )
        actual = virt.list_pools()
        self.assertEqual(names, actual)

    def test_pool_info(self):
        """
        Test virt.pool_info()
        """
        # pylint: disable=no-member
        pool_mock = MagicMock()
        pool_mock.name.return_value = "foo"
        pool_mock.UUIDString.return_value = "some-uuid"
        pool_mock.info.return_value = [0, 1234, 5678, 123]
        pool_mock.autostart.return_value = True
        pool_mock.isPersistent.return_value = True
        pool_mock.XMLDesc.return_value = """<pool type='dir'>
  <name>default</name>
  <uuid>d92682d0-33cf-4e10-9837-a216c463e158</uuid>
  <capacity unit='bytes'>854374301696</capacity>
  <allocation unit='bytes'>596275986432</allocation>
  <available unit='bytes'>258098315264</available>
  <source>
  </source>
  <target>
    <path>/srv/vms</path>
    <permissions>
      <mode>0755</mode>
      <owner>0</owner>
      <group>0</group>
    </permissions>
  </target>
</pool>"""
        self.mock_conn.listAllStoragePools.return_value = [pool_mock]
        # pylint: enable=no-member

        pool = virt.pool_info("foo")
        self.assertEqual(
            {
                "foo": {
                    "uuid": "some-uuid",
                    "state": "inactive",
                    "capacity": 1234,
                    "allocation": 5678,
                    "free": 123,
                    "autostart": True,
                    "persistent": True,
                    "type": "dir",
                    "target_path": "/srv/vms",
                }
            },
            pool,
        )

    def test_pool_info_notarget(self):
        """
        Test virt.pool_info()
        """
        # pylint: disable=no-member
        pool_mock = MagicMock()
        pool_mock.name.return_value = "ceph"
        pool_mock.UUIDString.return_value = "some-uuid"
        pool_mock.info.return_value = [0, 0, 0, 0]
        pool_mock.autostart.return_value = True
        pool_mock.isPersistent.return_value = True
        pool_mock.XMLDesc.return_value = """<pool type='rbd'>
  <name>ceph</name>
  <uuid>some-uuid</uuid>
  <capacity unit='bytes'>0</capacity>
  <allocation unit='bytes'>0</allocation>
  <available unit='bytes'>0</available>
  <source>
    <host name='localhost' port='6789'/>
    <host name='localhost' port='6790'/>
    <name>rbd</name>
    <auth type='ceph' username='admin'>
      <secret uuid='2ec115d7-3a88-3ceb-bc12-0ac909a6fd87'/>
    </auth>
  </source>
</pool>"""
        self.mock_conn.listAllStoragePools.return_value = [pool_mock]
        # pylint: enable=no-member

        pool = virt.pool_info("ceph")
        self.assertEqual(
            {
                "ceph": {
                    "uuid": "some-uuid",
                    "state": "inactive",
                    "capacity": 0,
                    "allocation": 0,
                    "free": 0,
                    "autostart": True,
                    "persistent": True,
                    "type": "rbd",
                    "target_path": None,
                }
            },
            pool,
        )

    def test_pool_info_notfound(self):
        """
        Test virt.pool_info() when the pool can't be found
        """
        # pylint: disable=no-member
        self.mock_conn.listAllStoragePools.return_value = []
        # pylint: enable=no-member
        pool = virt.pool_info("foo")
        self.assertEqual({}, pool)

    def test_pool_info_all(self):
        """
        Test virt.pool_info()
        """
        # pylint: disable=no-member
        pool_mocks = []
        for i in range(2):
            pool_mock = MagicMock()
            pool_mock.name.return_value = "pool{}".format(i)
            pool_mock.UUIDString.return_value = "some-uuid-{}".format(i)
            pool_mock.info.return_value = [0, 1234, 5678, 123]
            pool_mock.autostart.return_value = True
            pool_mock.isPersistent.return_value = True
            pool_mock.XMLDesc.return_value = """<pool type='dir'>
  <name>default</name>
  <uuid>d92682d0-33cf-4e10-9837-a216c463e158</uuid>
  <capacity unit='bytes'>854374301696</capacity>
  <allocation unit='bytes'>596275986432</allocation>
  <available unit='bytes'>258098315264</available>
  <source>
  </source>
  <target>
    <path>/srv/vms</path>
    <permissions>
      <mode>0755</mode>
      <owner>0</owner>
      <group>0</group>
    </permissions>
  </target>
</pool>"""
            pool_mocks.append(pool_mock)
        self.mock_conn.listAllStoragePools.return_value = pool_mocks
        # pylint: enable=no-member

        pool = virt.pool_info()
        self.assertEqual(
            {
                "pool0": {
                    "uuid": "some-uuid-0",
                    "state": "inactive",
                    "capacity": 1234,
                    "allocation": 5678,
                    "free": 123,
                    "autostart": True,
                    "persistent": True,
                    "type": "dir",
                    "target_path": "/srv/vms",
                },
                "pool1": {
                    "uuid": "some-uuid-1",
                    "state": "inactive",
                    "capacity": 1234,
                    "allocation": 5678,
                    "free": 123,
                    "autostart": True,
                    "persistent": True,
                    "type": "dir",
                    "target_path": "/srv/vms",
                },
            },
            pool,
        )

    def test_pool_get_xml(self):
        """
        Test virt.pool_get_xml
        """
        pool_mock = MagicMock()
        pool_mock.XMLDesc.return_value = "<pool>Raw XML</pool>"
        self.mock_conn.storagePoolLookupByName.return_value = pool_mock

        self.assertEqual("<pool>Raw XML</pool>", virt.pool_get_xml("default"))

    def test_pool_list_volumes(self):
        """
        Test virt.pool_list_volumes
        """
        names = ["volume1", "volume2"]
        mock_pool = MagicMock()
        # pylint: disable=no-member
        mock_pool.listVolumes.return_value = names
        self.mock_conn.storagePoolLookupByName.return_value = mock_pool
        # pylint: enable=no-member
        self.assertEqual(names, virt.pool_list_volumes("default"))

    @patch("salt.modules.virt._is_bhyve_hyper", return_value=False)
    @patch("salt.modules.virt._is_kvm_hyper", return_value=True)
    @patch("salt.modules.virt._is_xen_hyper", return_value=False)
    def test_get_hypervisor(self, isxen_mock, iskvm_mock, is_bhyve_mock):
        """
        test the virt.get_hypervisor() function
        """
        self.assertEqual("kvm", virt.get_hypervisor())

        iskvm_mock.return_value = False
        self.assertIsNone(virt.get_hypervisor())

        is_bhyve_mock.return_value = False
        self.assertIsNone(virt.get_hypervisor())

        isxen_mock.return_value = True
        self.assertEqual("xen", virt.get_hypervisor())

    def test_pool_delete(self):
        """
        Test virt.pool_delete function
        """
        mock_pool = MagicMock()
        mock_pool.delete = MagicMock(return_value=0)
        self.mock_conn.storagePoolLookupByName = MagicMock(return_value=mock_pool)

        res = virt.pool_delete("test-pool")
        self.assertTrue(res)

        self.mock_conn.storagePoolLookupByName.assert_called_once_with("test-pool")

        # Shouldn't be called with another parameter so far since those are not implemented
        # and thus throwing exceptions.
        mock_pool.delete.assert_called_once_with(
            self.mock_libvirt.VIR_STORAGE_POOL_DELETE_NORMAL
        )

    def test_pool_undefine_secret(self):
        """
        Test virt.pool_undefine function where the pool has a secret
        """
        mock_pool = MagicMock()
        mock_pool.undefine = MagicMock(return_value=0)
        mock_pool.XMLDesc.return_value = """
            <pool type='rbd'>
              <name>test-ses</name>
              <source>
                <host name='myhost'/>
                <name>libvirt-pool</name>
                <auth type='ceph' username='libvirt'>
                  <secret usage='pool_test-ses'/>
                </auth>
              </source>
            </pool>
        """
        self.mock_conn.storagePoolLookupByName = MagicMock(return_value=mock_pool)
        mock_undefine = MagicMock(return_value=0)
        self.mock_conn.secretLookupByUsage.return_value.undefine = mock_undefine

        res = virt.pool_undefine("test-ses")
        self.assertTrue(res)

        self.mock_conn.storagePoolLookupByName.assert_called_once_with("test-ses")
        mock_pool.undefine.assert_called_once_with()

        self.mock_conn.secretLookupByUsage.assert_called_once_with(
            self.mock_libvirt.VIR_SECRET_USAGE_TYPE_CEPH, "pool_test-ses"
        )
        mock_undefine.assert_called_once()

    def test_full_info(self):
        """
        Test virt.full_info
        """
        xml = """<domain type='kvm' id='7'>
              <uuid>28deee33-4859-4f23-891c-ee239cffec94</uuid>
              <name>test-vm</name>
              <on_poweroff>destroy</on_poweroff>
              <on_reboot>restart</on_reboot>
              <on_crash>destroy</on_crash>
              <devices>
                <disk type='file' device='disk'>
                <driver name='qemu' type='qcow2'/>
                <source file='/disks/test.qcow2'/>
                <target dev='vda' bus='virtio'/>
              </disk>
              <disk type='file' device='cdrom'>
                <driver name='qemu' type='raw'/>
                <source file='/disks/test-cdrom.iso'/>
                <target dev='hda' bus='ide'/>
                <readonly/>
              </disk>
              <interface type='bridge'>
                <mac address='ac:de:48:b6:8b:59'/>
                <source bridge='br0'/>
                <model type='virtio'/>
                <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
              </interface>
              <graphics type='vnc' port='5900' autoport='yes' listen='0.0.0.0'>
                <listen type='address' address='0.0.0.0'/>
              </graphics>
              </devices>
            </domain>
        """
        self.set_mock_vm("test-vm", xml)

        qemu_infos = """[{
            "virtual-size": 25769803776,
            "filename": "/disks/test.qcow2",
            "cluster-size": 65536,
            "format": "qcow2",
            "actual-size": 217088,
            "format-specific": {
                "type": "qcow2",
                "data": {
                    "compat": "1.1",
                    "lazy-refcounts": false,
                    "refcount-bits": 16,
                    "corrupt": false
                }
            },
            "full-backing-filename": "/disks/mybacking.qcow2",
            "backing-filename": "mybacking.qcow2",
            "dirty-flag": false
        },
        {
            "virtual-size": 25769803776,
            "filename": "/disks/mybacking.qcow2",
            "cluster-size": 65536,
            "format": "qcow2",
            "actual-size": 393744384,
            "format-specific": {
                "type": "qcow2",
                "data": {
                    "compat": "1.1",
                    "lazy-refcounts": false,
                    "refcount-bits": 16,
                    "corrupt": false
                }
            },
            "dirty-flag": false
        }]"""

        self.mock_popen.communicate.return_value = [
            qemu_infos
        ]  # pylint: disable=no-member

        self.mock_conn.getInfo = MagicMock(
            return_value=["x86_64", 4096, 8, 2712, 1, 2, 4, 2]
        )

        actual = virt.full_info()

        # Check that qemu-img was called with the proper parameters
        qemu_img_call = [
            call
            for call in self.mock_subprocess.Popen.call_args_list
            if "qemu-img" in call[0][0]
        ][0]
        self.assertIn("info", qemu_img_call[0][0])
        self.assertIn("-U", qemu_img_call[0][0])

        # Test the hypervisor infos
        self.assertEqual(2816, actual["freemem"])
        self.assertEqual(6, actual["freecpu"])
        self.assertEqual(4, actual["node_info"]["cpucores"])
        self.assertEqual(2712, actual["node_info"]["cpumhz"])
        self.assertEqual("x86_64", actual["node_info"]["cpumodel"])
        self.assertEqual(8, actual["node_info"]["cpus"])
        self.assertEqual(2, actual["node_info"]["cputhreads"])
        self.assertEqual(1, actual["node_info"]["numanodes"])
        self.assertEqual(4096, actual["node_info"]["phymemory"])
        self.assertEqual(2, actual["node_info"]["sockets"])

        # Test the vm_info output:
        self.assertEqual(2, actual["vm_info"]["test-vm"]["cpu"])
        self.assertEqual(1234, actual["vm_info"]["test-vm"]["cputime"])
        self.assertEqual(1024 * 1024, actual["vm_info"]["test-vm"]["mem"])
        self.assertEqual(2048 * 1024, actual["vm_info"]["test-vm"]["maxMem"])
        self.assertEqual("shutdown", actual["vm_info"]["test-vm"]["state"])
        self.assertEqual(
            "28deee33-4859-4f23-891c-ee239cffec94", actual["vm_info"]["test-vm"]["uuid"]
        )
        self.assertEqual("destroy", actual["vm_info"]["test-vm"]["on_crash"])
        self.assertEqual("restart", actual["vm_info"]["test-vm"]["on_reboot"])
        self.assertEqual("destroy", actual["vm_info"]["test-vm"]["on_poweroff"])

        # Test the nics
        nic = actual["vm_info"]["test-vm"]["nics"]["ac:de:48:b6:8b:59"]
        self.assertEqual("bridge", nic["type"])
        self.assertEqual("ac:de:48:b6:8b:59", nic["mac"])

        # Test the disks
        disks = actual["vm_info"]["test-vm"]["disks"]
        disk = disks.get("vda")
        self.assertEqual("/disks/test.qcow2", disk["file"])
        self.assertEqual("disk", disk["type"])
        self.assertEqual("/disks/mybacking.qcow2", disk["backing file"]["file"])
        cdrom = disks.get("hda")
        self.assertEqual("/disks/test-cdrom.iso", cdrom["file"])
        self.assertEqual("cdrom", cdrom["type"])
        self.assertFalse("backing file" in cdrom.keys())

        # Test the graphics
        graphics = actual["vm_info"]["test-vm"]["graphics"]
        self.assertEqual("vnc", graphics["type"])
        self.assertEqual("5900", graphics["port"])
        self.assertEqual("0.0.0.0", graphics["listen"])

    def test_pool_update(self):
        """
        Test the pool_update function
        """
        current_xml = """<pool type='dir'>
          <name>default</name>
          <uuid>20fbe05c-ab40-418a-9afa-136d512f0ede</uuid>
          <capacity unit='bytes'>1999421108224</capacity>
          <allocation unit='bytes'>713207042048</allocation>
          <available unit='bytes'>1286214066176</available>
          <source>
          </source>
          <target>
            <path>/path/to/pool</path>
            <permissions>
              <mode>0775</mode>
              <owner>0</owner>
              <group>100</group>
            </permissions>
          </target>
        </pool>"""

        expected_xml = (
            '<pool type="netfs">'
            "<name>default</name>"
            "<uuid>20fbe05c-ab40-418a-9afa-136d512f0ede</uuid>"
            '<capacity unit="bytes">1999421108224</capacity>'
            '<allocation unit="bytes">713207042048</allocation>'
            '<available unit="bytes">1286214066176</available>'
            "<target>"
            "<path>/mnt/cifs</path>"
            "<permissions>"
            "<mode>0774</mode>"
            "<owner>1234</owner>"
            "<group>123</group>"
            "</permissions>"
            "</target>"
            "<source>"
            '<dir path="samba_share" />'
            '<host name="one.example.com" />'
            '<host name="two.example.com" />'
            '<format type="cifs" />'
            "</source>"
            "</pool>"
        )

        mocked_pool = MagicMock()
        mocked_pool.XMLDesc = MagicMock(return_value=current_xml)
        self.mock_conn.storagePoolLookupByName = MagicMock(return_value=mocked_pool)
        self.mock_conn.storagePoolDefineXML = MagicMock()

        self.assertTrue(
            virt.pool_update(
                "default",
                "netfs",
                target="/mnt/cifs",
                permissions={"mode": "0774", "owner": "1234", "group": "123"},
                source_format="cifs",
                source_dir="samba_share",
                source_hosts=["one.example.com", "two.example.com"],
            )
        )
        self.mock_conn.storagePoolDefineXML.assert_called_once_with(expected_xml)

    def test_pool_update_nochange(self):
        """
        Test the pool_update function when no change is needed
        """

        current_xml = """<pool type='dir'>
          <name>default</name>
          <uuid>20fbe05c-ab40-418a-9afa-136d512f0ede</uuid>
          <capacity unit='bytes'>1999421108224</capacity>
          <allocation unit='bytes'>713207042048</allocation>
          <available unit='bytes'>1286214066176</available>
          <source>
          </source>
          <target>
            <path>/path/to/pool</path>
            <permissions>
              <mode>0775</mode>
              <owner>0</owner>
              <group>100</group>
            </permissions>
          </target>
        </pool>"""

        mocked_pool = MagicMock()
        mocked_pool.XMLDesc = MagicMock(return_value=current_xml)
        self.mock_conn.storagePoolLookupByName = MagicMock(return_value=mocked_pool)
        self.mock_conn.storagePoolDefineXML = MagicMock()

        self.assertFalse(
            virt.pool_update(
                "default",
                "dir",
                target="/path/to/pool",
                permissions={"mode": "0775", "owner": "0", "group": "100"},
                test=True,
            )
        )
        self.mock_conn.storagePoolDefineXML.assert_not_called()

    def test_pool_update_password(self):
        """
        Test the pool_update function, where the password only is changed
        """
        current_xml = """<pool type='rbd'>
          <name>default</name>
          <uuid>20fbe05c-ab40-418a-9afa-136d512f0ede</uuid>
          <capacity unit='bytes'>1999421108224</capacity>
          <allocation unit='bytes'>713207042048</allocation>
          <available unit='bytes'>1286214066176</available>
          <source>
            <name>iscsi-images</name>
            <host name='ses4.tf.local'/>
            <host name='ses5.tf.local'/>
            <auth username='libvirt' type='ceph'>
              <secret uuid='14e9a0f1-8fbf-4097-b816-5b094c182212'/>
            </auth>
          </source>
        </pool>"""

        mock_secret = MagicMock()
        self.mock_conn.secretLookupByUUIDString = MagicMock(return_value=mock_secret)

        mocked_pool = MagicMock()
        mocked_pool.XMLDesc = MagicMock(return_value=current_xml)
        self.mock_conn.storagePoolLookupByName = MagicMock(return_value=mocked_pool)
        self.mock_conn.storagePoolDefineXML = MagicMock()

        self.assertFalse(
            virt.pool_update(
                "default",
                "rbd",
                source_name="iscsi-images",
                source_hosts=["ses4.tf.local", "ses5.tf.local"],
                source_auth={"username": "libvirt", "password": "c2VjcmV0"},
            )
        )
        self.mock_conn.storagePoolDefineXML.assert_not_called()
        mock_secret.setValue.assert_called_once_with(b"secret")

        # Case where the secret can't be found
        self.mock_conn.secretLookupByUUIDString = MagicMock(
            side_effect=self.mock_libvirt.libvirtError("secret not found")
        )
        self.assertFalse(
            virt.pool_update(
                "default",
                "rbd",
                source_name="iscsi-images",
                source_hosts=["ses4.tf.local", "ses5.tf.local"],
                source_auth={"username": "libvirt", "password": "c2VjcmV0"},
            )
        )
        self.mock_conn.storagePoolDefineXML.assert_not_called()
        self.mock_conn.secretDefineXML.assert_called_once()
        mock_secret.setValue.assert_called_once_with(b"secret")

    def test_pool_update_password_create(self):
        """
        Test the pool_update function, where the password only is changed
        """
        current_xml = """<pool type='rbd'>
          <name>default</name>
          <uuid>20fbe05c-ab40-418a-9afa-136d512f0ede</uuid>
          <capacity unit='bytes'>1999421108224</capacity>
          <allocation unit='bytes'>713207042048</allocation>
          <available unit='bytes'>1286214066176</available>
          <source>
            <name>iscsi-images</name>
            <host name='ses4.tf.local'/>
            <host name='ses5.tf.local'/>
          </source>
        </pool>"""

        expected_xml = (
            '<pool type="rbd">'
            "<name>default</name>"
            "<uuid>20fbe05c-ab40-418a-9afa-136d512f0ede</uuid>"
            '<capacity unit="bytes">1999421108224</capacity>'
            '<allocation unit="bytes">713207042048</allocation>'
            '<available unit="bytes">1286214066176</available>'
            "<source>"
            '<host name="ses4.tf.local" />'
            '<host name="ses5.tf.local" />'
            '<auth type="ceph" username="libvirt">'
            '<secret usage="pool_default" />'
            "</auth>"
            "<name>iscsi-images</name>"
            "</source>"
            "</pool>"
        )

        mock_secret = MagicMock()
        self.mock_conn.secretDefineXML = MagicMock(return_value=mock_secret)

        mocked_pool = MagicMock()
        mocked_pool.XMLDesc = MagicMock(return_value=current_xml)
        self.mock_conn.storagePoolLookupByName = MagicMock(return_value=mocked_pool)
        self.mock_conn.storagePoolDefineXML = MagicMock()

        self.assertTrue(
            virt.pool_update(
                "default",
                "rbd",
                source_name="iscsi-images",
                source_hosts=["ses4.tf.local", "ses5.tf.local"],
                source_auth={"username": "libvirt", "password": "c2VjcmV0"},
            )
        )
        self.mock_conn.storagePoolDefineXML.assert_called_once_with(expected_xml)
        mock_secret.setValue.assert_called_once_with(b"secret")

    def test_volume_infos(self):
        """
        Test virt.volume_infos
        """
        vms_disks = [
            """
                <disk type='file' device='disk'>
                  <driver name='qemu' type='qcow2'/>
                  <source file='/path/to/vol0.qcow2'/>
                  <target dev='vda' bus='virtio'/>
                </disk>
            """,
            """
                <disk type='file' device='disk'>
                  <driver name='qemu' type='qcow2'/>
                  <source file='/path/to/vol3.qcow2'/>
                  <target dev='vda' bus='virtio'/>
                </disk>
            """,
            """
                <disk type='file' device='disk'>
                  <driver name='qemu' type='qcow2'/>
                  <source file='/path/to/vol2.qcow2'/>
                  <target dev='vda' bus='virtio'/>
                </disk>
            """,
        ]
        mock_vms = []
        for idx, disk in enumerate(vms_disks):
            vm = MagicMock()
            # pylint: disable=no-member
            vm.name.return_value = "vm{}".format(idx)
            vm.XMLDesc.return_value = """
                    <domain type='kvm' id='1'>
                      <name>vm{}</name>
                      <devices>{}</devices>
                    </domain>
                """.format(
                idx, disk
            )
            # pylint: enable=no-member
            mock_vms.append(vm)

        mock_pool_data = [
            {
                "name": "pool0",
                "state": self.mock_libvirt.VIR_STORAGE_POOL_RUNNING,
                "volumes": [
                    {
                        "key": "/key/of/vol0",
                        "name": "vol0",
                        "path": "/path/to/vol0.qcow2",
                        "info": [0, 123456789, 123456],
                        "backingStore": None,
                    }
                ],
            },
            {
                "name": "pool1",
                "state": self.mock_libvirt.VIR_STORAGE_POOL_RUNNING,
                "volumes": [
                    {
                        "key": "/key/of/vol0bad",
                        "name": "vol0bad",
                        "path": "/path/to/vol0bad.qcow2",
                        "info": None,
                        "backingStore": None,
                    },
                    {
                        "key": "/key/of/vol1",
                        "name": "vol1",
                        "path": "/path/to/vol1.qcow2",
                        "info": [0, 12345, 1234],
                        "backingStore": None,
                    },
                    {
                        "key": "/key/of/vol2",
                        "name": "vol2",
                        "path": "/path/to/vol2.qcow2",
                        "info": [0, 12345, 1234],
                        "backingStore": "/path/to/vol0.qcow2",
                    },
                ],
            },
        ]
        mock_pools = []
        for pool_data in mock_pool_data:
            mock_pool = MagicMock()
            mock_pool.name.return_value = pool_data["name"]  # pylint: disable=no-member
            mock_pool.info.return_value = [pool_data["state"]]
            mock_volumes = []
            for vol_data in pool_data["volumes"]:
                mock_volume = MagicMock()
                # pylint: disable=no-member
                mock_volume.name.return_value = vol_data["name"]
                mock_volume.key.return_value = vol_data["key"]
                mock_volume.path.return_value = "/path/to/{}.qcow2".format(
                    vol_data["name"]
                )
                if vol_data["info"]:
                    mock_volume.info.return_value = vol_data["info"]
                    backing_store = (
                        """
                        <backingStore>
                          <format type="qcow2"/>
                          <path>{}</path>
                        </backingStore>
                    """.format(
                            vol_data["backingStore"]
                        )
                        if vol_data["backingStore"]
                        else "<backingStore/>"
                    )
                    mock_volume.XMLDesc.return_value = """
                        <volume type='file'>
                          <name>{0}</name>
                          <target>
                            <format type="qcow2"/>
                            <path>/path/to/{0}.qcow2</path>
                          </target>
                          {1}
                        </volume>
                    """.format(
                        vol_data["name"], backing_store
                    )
                else:
                    mock_volume.info.side_effect = self.mock_libvirt.libvirtError(
                        "No such volume"
                    )
                    mock_volume.XMLDesc.side_effect = self.mock_libvirt.libvirtError(
                        "No such volume"
                    )
                mock_volumes.append(mock_volume)
                # pylint: enable=no-member
            mock_pool.listAllVolumes.return_value = (
                mock_volumes  # pylint: disable=no-member
            )
            mock_pools.append(mock_pool)

        inactive_pool = MagicMock()
        inactive_pool.name.return_value = "pool2"
        inactive_pool.info.return_value = [self.mock_libvirt.VIR_STORAGE_POOL_INACTIVE]
        inactive_pool.listAllVolumes.side_effect = self.mock_libvirt.libvirtError(
            "pool is inactive"
        )
        mock_pools.append(inactive_pool)

        self.mock_conn.listAllStoragePools.return_value = (
            mock_pools  # pylint: disable=no-member
        )

        with patch("salt.modules.virt._get_domain", MagicMock(return_value=mock_vms)):
            actual = virt.volume_infos("pool0", "vol0")
            self.assertEqual(1, len(actual.keys()))
            self.assertEqual(1, len(actual["pool0"].keys()))
            self.assertEqual(["vm0", "vm2"], sorted(actual["pool0"]["vol0"]["used_by"]))
            self.assertEqual("/path/to/vol0.qcow2", actual["pool0"]["vol0"]["path"])
            self.assertEqual("file", actual["pool0"]["vol0"]["type"])
            self.assertEqual("/key/of/vol0", actual["pool0"]["vol0"]["key"])
            self.assertEqual(123456789, actual["pool0"]["vol0"]["capacity"])
            self.assertEqual(123456, actual["pool0"]["vol0"]["allocation"])

            self.assertEqual(
                virt.volume_infos("pool1", None),
                {
                    "pool1": {
                        "vol1": {
                            "type": "file",
                            "key": "/key/of/vol1",
                            "path": "/path/to/vol1.qcow2",
                            "capacity": 12345,
                            "allocation": 1234,
                            "used_by": [],
                            "backing_store": None,
                            "format": "qcow2",
                        },
                        "vol2": {
                            "type": "file",
                            "key": "/key/of/vol2",
                            "path": "/path/to/vol2.qcow2",
                            "capacity": 12345,
                            "allocation": 1234,
                            "used_by": ["vm2"],
                            "backing_store": {
                                "path": "/path/to/vol0.qcow2",
                                "format": "qcow2",
                            },
                            "format": "qcow2",
                        },
                    }
                },
            )

            self.assertEqual(
                virt.volume_infos(None, "vol2"),
                {
                    "pool1": {
                        "vol2": {
                            "type": "file",
                            "key": "/key/of/vol2",
                            "path": "/path/to/vol2.qcow2",
                            "capacity": 12345,
                            "allocation": 1234,
                            "used_by": ["vm2"],
                            "backing_store": {
                                "path": "/path/to/vol0.qcow2",
                                "format": "qcow2",
                            },
                            "format": "qcow2",
                        }
                    }
                },
            )

        # Single VM test
        with patch(
            "salt.modules.virt._get_domain", MagicMock(return_value=mock_vms[0])
        ):
            actual = virt.volume_infos("pool0", "vol0")
            self.assertEqual(1, len(actual.keys()))
            self.assertEqual(1, len(actual["pool0"].keys()))
            self.assertEqual(["vm0"], sorted(actual["pool0"]["vol0"]["used_by"]))
            self.assertEqual("/path/to/vol0.qcow2", actual["pool0"]["vol0"]["path"])
            self.assertEqual("file", actual["pool0"]["vol0"]["type"])
            self.assertEqual("/key/of/vol0", actual["pool0"]["vol0"]["key"])
            self.assertEqual(123456789, actual["pool0"]["vol0"]["capacity"])
            self.assertEqual(123456, actual["pool0"]["vol0"]["allocation"])

            self.assertEqual(
                virt.volume_infos("pool1", None),
                {
                    "pool1": {
                        "vol1": {
                            "type": "file",
                            "key": "/key/of/vol1",
                            "path": "/path/to/vol1.qcow2",
                            "capacity": 12345,
                            "allocation": 1234,
                            "used_by": [],
                            "backing_store": None,
                            "format": "qcow2",
                        },
                        "vol2": {
                            "type": "file",
                            "key": "/key/of/vol2",
                            "path": "/path/to/vol2.qcow2",
                            "capacity": 12345,
                            "allocation": 1234,
                            "used_by": [],
                            "backing_store": {
                                "path": "/path/to/vol0.qcow2",
                                "format": "qcow2",
                            },
                            "format": "qcow2",
                        },
                    }
                },
            )

            self.assertEqual(
                virt.volume_infos(None, "vol2"),
                {
                    "pool1": {
                        "vol2": {
                            "type": "file",
                            "key": "/key/of/vol2",
                            "path": "/path/to/vol2.qcow2",
                            "capacity": 12345,
                            "allocation": 1234,
                            "used_by": [],
                            "backing_store": {
                                "path": "/path/to/vol0.qcow2",
                                "format": "qcow2",
                            },
                            "format": "qcow2",
                        }
                    }
                },
            )

        # No VM test
        with patch(
            "salt.modules.virt._get_domain",
            MagicMock(side_effect=CommandExecutionError("no VM")),
        ):
            actual = virt.volume_infos("pool0", "vol0")
            self.assertEqual(1, len(actual.keys()))
            self.assertEqual(1, len(actual["pool0"].keys()))
            self.assertEqual([], sorted(actual["pool0"]["vol0"]["used_by"]))
            self.assertEqual("/path/to/vol0.qcow2", actual["pool0"]["vol0"]["path"])
            self.assertEqual("file", actual["pool0"]["vol0"]["type"])
            self.assertEqual("/key/of/vol0", actual["pool0"]["vol0"]["key"])
            self.assertEqual(123456789, actual["pool0"]["vol0"]["capacity"])
            self.assertEqual(123456, actual["pool0"]["vol0"]["allocation"])

            self.assertEqual(
                virt.volume_infos("pool1", None),
                {
                    "pool1": {
                        "vol1": {
                            "type": "file",
                            "key": "/key/of/vol1",
                            "path": "/path/to/vol1.qcow2",
                            "capacity": 12345,
                            "allocation": 1234,
                            "used_by": [],
                            "backing_store": None,
                            "format": "qcow2",
                        },
                        "vol2": {
                            "type": "file",
                            "key": "/key/of/vol2",
                            "path": "/path/to/vol2.qcow2",
                            "capacity": 12345,
                            "allocation": 1234,
                            "used_by": [],
                            "backing_store": {
                                "path": "/path/to/vol0.qcow2",
                                "format": "qcow2",
                            },
                            "format": "qcow2",
                        },
                    }
                },
            )

            self.assertEqual(
                virt.volume_infos(None, "vol2"),
                {
                    "pool1": {
                        "vol2": {
                            "type": "file",
                            "key": "/key/of/vol2",
                            "path": "/path/to/vol2.qcow2",
                            "capacity": 12345,
                            "allocation": 1234,
                            "used_by": [],
                            "backing_store": {
                                "path": "/path/to/vol0.qcow2",
                                "format": "qcow2",
                            },
                            "format": "qcow2",
                        }
                    }
                },
            )

    def test_volume_delete(self):
        """
        Test virt.volume_delete
        """
        mock_delete = MagicMock(side_effect=[0, 1])
        mock_volume = MagicMock()
        mock_volume.delete = mock_delete  # pylint: disable=no-member
        mock_pool = MagicMock()
        # pylint: disable=no-member
        mock_pool.storageVolLookupByName.side_effect = [
            mock_volume,
            mock_volume,
            self.mock_libvirt.libvirtError("Missing volume"),
            mock_volume,
        ]
        self.mock_conn.storagePoolLookupByName.side_effect = [
            mock_pool,
            mock_pool,
            mock_pool,
            self.mock_libvirt.libvirtError("Missing pool"),
        ]

        # pylint: enable=no-member
        self.assertTrue(virt.volume_delete("default", "test_volume"))
        self.assertFalse(virt.volume_delete("default", "test_volume"))
        with self.assertRaises(self.mock_libvirt.libvirtError):
            virt.volume_delete("default", "missing")
            virt.volume_delete("missing", "test_volume")
        self.assertEqual(mock_delete.call_count, 2)

    def test_pool_capabilities(self):
        """
        Test virt.pool_capabilities where libvirt has the pool-capabilities feature
        """
        xml_caps = """
<storagepoolCapabilities>
  <pool type='disk' supported='yes'>
    <poolOptions>
      <defaultFormat type='unknown'/>
      <enum name='sourceFormatType'>
        <value>unknown</value>
        <value>dos</value>
        <value>dvh</value>
      </enum>
    </poolOptions>
    <volOptions>
      <defaultFormat type='none'/>
      <enum name='targetFormatType'>
        <value>none</value>
        <value>linux</value>
      </enum>
    </volOptions>
  </pool>
  <pool type='iscsi' supported='yes'>
  </pool>
  <pool type='rbd' supported='yes'>
    <volOptions>
      <defaultFormat type='raw'/>
      <enum name='targetFormatType'>
      </enum>
    </volOptions>
  </pool>
  <pool type='sheepdog' supported='no'>
  </pool>
</storagepoolCapabilities>
        """
        self.mock_conn.getStoragePoolCapabilities = MagicMock(return_value=xml_caps)

        actual = virt.pool_capabilities()
        self.assertEqual(
            {
                "computed": False,
                "pool_types": [
                    {
                        "name": "disk",
                        "supported": True,
                        "options": {
                            "pool": {
                                "default_format": "unknown",
                                "sourceFormatType": ["unknown", "dos", "dvh"],
                            },
                            "volume": {
                                "default_format": "none",
                                "targetFormatType": ["none", "linux"],
                            },
                        },
                    },
                    {"name": "iscsi", "supported": True},
                    {
                        "name": "rbd",
                        "supported": True,
                        "options": {
                            "volume": {"default_format": "raw", "targetFormatType": []}
                        },
                    },
                    {"name": "sheepdog", "supported": False},
                ],
            },
            actual,
        )

    @patch("salt.modules.virt.get_hypervisor", return_value="kvm")
    def test_pool_capabilities_computed(self, mock_get_hypervisor):
        """
        Test virt.pool_capabilities where libvirt doesn't have the pool-capabilities feature
        """
        self.mock_conn.getLibVersion = MagicMock(return_value=4006000)
        del self.mock_conn.getStoragePoolCapabilities

        actual = virt.pool_capabilities()

        self.assertTrue(actual["computed"])
        backends = actual["pool_types"]

        # libvirt version matching check
        self.assertFalse(
            [backend for backend in backends if backend["name"] == "iscsi-direct"][0][
                "supported"
            ]
        )
        self.assertTrue(
            [backend for backend in backends if backend["name"] == "gluster"][0][
                "supported"
            ]
        )
        self.assertFalse(
            [backend for backend in backends if backend["name"] == "zfs"][0][
                "supported"
            ]
        )

        # test case matching other hypervisors
        mock_get_hypervisor.return_value = "xen"
        backends = virt.pool_capabilities()["pool_types"]
        self.assertFalse(
            [backend for backend in backends if backend["name"] == "gluster"][0][
                "supported"
            ]
        )

        mock_get_hypervisor.return_value = "bhyve"
        backends = virt.pool_capabilities()["pool_types"]
        self.assertFalse(
            [backend for backend in backends if backend["name"] == "gluster"][0][
                "supported"
            ]
        )
        self.assertTrue(
            [backend for backend in backends if backend["name"] == "zfs"][0][
                "supported"
            ]
        )

        # Test options output
        self.assertNotIn(
            "options",
            [backend for backend in backends if backend["name"] == "iscsi"][0],
        )
        self.assertNotIn(
            "pool",
            [backend for backend in backends if backend["name"] == "dir"][0]["options"],
        )
        self.assertNotIn(
            "volume",
            [backend for backend in backends if backend["name"] == "logical"][0][
                "options"
            ],
        )
        self.assertEqual(
            {
                "pool": {
                    "default_format": "auto",
                    "sourceFormatType": ["auto", "nfs", "glusterfs", "cifs"],
                },
                "volume": {
                    "default_format": "raw",
                    "targetFormatType": [
                        "none",
                        "raw",
                        "dir",
                        "bochs",
                        "cloop",
                        "dmg",
                        "iso",
                        "vpc",
                        "vdi",
                        "fat",
                        "vhd",
                        "ploop",
                        "cow",
                        "qcow",
                        "qcow2",
                        "qed",
                        "vmdk",
                    ],
                },
            },
            [backend for backend in backends if backend["name"] == "netfs"][0][
                "options"
            ],
        )

    def test_get_domain(self):
        """
        Test the virt._get_domain function
        """
        # Tests with no VM
        self.mock_conn.listDomainsID.return_value = []
        self.mock_conn.listDefinedDomains.return_value = []
        self.assertEqual([], virt._get_domain(self.mock_conn))
        self.assertRaisesRegex(
            CommandExecutionError,
            "No virtual machines found.",
            virt._get_domain,
            self.mock_conn,
            "vm2",
        )

        # Test with active and inactive VMs
        self.mock_conn.listDomainsID.return_value = [1]

        def create_mock_vm(idx):
            mock_vm = MagicMock()
            mock_vm.name.return_value = "vm{}".format(idx)
            return mock_vm

        mock_vms = [create_mock_vm(idx) for idx in range(3)]
        self.mock_conn.lookupByID.return_value = mock_vms[0]
        self.mock_conn.listDefinedDomains.return_value = ["vm1", "vm2"]

        self.mock_conn.lookupByName.side_effect = mock_vms
        self.assertEqual(mock_vms, virt._get_domain(self.mock_conn))

        self.mock_conn.lookupByName.side_effect = None
        self.mock_conn.lookupByName.return_value = mock_vms[0]
        self.assertEqual(mock_vms[0], virt._get_domain(self.mock_conn, inactive=False))

        self.mock_conn.lookupByName.return_value = None
        self.mock_conn.lookupByName.side_effect = [mock_vms[1], mock_vms[2]]
        self.assertEqual(
            [mock_vms[1], mock_vms[2]], virt._get_domain(self.mock_conn, active=False)
        )

        self.mock_conn.reset_mock()
        self.mock_conn.lookupByName.return_value = None
        self.mock_conn.lookupByName.side_effect = [mock_vms[1], mock_vms[2]]
        self.assertEqual(
            [mock_vms[1], mock_vms[2]], virt._get_domain(self.mock_conn, "vm1", "vm2")
        )
        self.assertRaisesRegex(
            CommandExecutionError,
            'The VM "vm2" is not present',
            virt._get_domain,
            self.mock_conn,
            "vm2",
            inactive=False,
        )

    def test_volume_define(self):
        """
        Test virt.volume_define function
        """
        # Normal test case
        pool_mock = MagicMock()
        pool_mock.XMLDesc.return_value = "<pool type='dir'></pool>"
        self.mock_conn.storagePoolLookupByName.return_value = pool_mock

        self.assertTrue(
            virt.volume_define(
                "testpool",
                "myvm_system.qcow2",
                8192,
                allocation=4096,
                format="qcow2",
                type="file",
            )
        )

        expected_xml = (
            "<volume type='file'>\n"
            "  <name>myvm_system.qcow2</name>\n"
            "  <source>\n"
            "  </source>\n"
            "  <capacity unit='KiB'>8388608</capacity>\n"
            "  <allocation unit='KiB'>4194304</allocation>\n"
            "  <target>\n"
            "    <format type='qcow2'/>\n"
            "  </target>\n"
            "</volume>"
        )

        pool_mock.createXML.assert_called_once_with(expected_xml, 0)

        # backing store test case
        pool_mock.reset_mock()
        self.assertTrue(
            virt.volume_define(
                "testpool",
                "myvm_system.qcow2",
                8192,
                allocation=4096,
                format="qcow2",
                type="file",
                backing_store={"path": "/path/to/base.raw", "format": "raw"},
            )
        )

        expected_xml = (
            "<volume type='file'>\n"
            "  <name>myvm_system.qcow2</name>\n"
            "  <source>\n"
            "  </source>\n"
            "  <capacity unit='KiB'>8388608</capacity>\n"
            "  <allocation unit='KiB'>4194304</allocation>\n"
            "  <target>\n"
            "    <format type='qcow2'/>\n"
            "  </target>\n"
            "  <backingStore>\n"
            "    <path>/path/to/base.raw</path>\n"
            "    <format type='raw'/>\n"
            "  </backingStore>\n"
            "</volume>"
        )

        pool_mock.createXML.assert_called_once_with(expected_xml, 0)

        # logical pool test case
        pool_mock.reset_mock()
        pool_mock.XMLDesc.return_value = "<pool type='logical'></pool>"
        self.mock_conn.storagePoolLookupByName.return_value = pool_mock

        self.assertTrue(
            virt.volume_define(
                "testVG",
                "myvm_system",
                8192,
                backing_store={"path": "/dev/testVG/base"},
            )
        )

        expected_xml = (
            "<volume>\n"
            "  <name>myvm_system</name>\n"
            "  <source>\n"
            "  </source>\n"
            "  <capacity unit='KiB'>8388608</capacity>\n"
            "  <allocation unit='KiB'>8388608</allocation>\n"
            "  <target>\n"
            "  </target>\n"
            "  <backingStore>\n"
            "    <path>/dev/testVG/base</path>\n"
            "  </backingStore>\n"
            "</volume>"
        )

        pool_mock.createXML.assert_called_once_with(expected_xml, 0)

    def test_volume_upload(self):
        """
        Test virt.volume_upload function
        """
        pool_mock = MagicMock()
        vol_mock = MagicMock()
        pool_mock.storageVolLookupByName.return_value = vol_mock
        self.mock_conn.storagePoolLookupByName.return_value = pool_mock
        stream_mock = MagicMock()
        self.mock_conn.newStream.return_value = stream_mock

        open_mock = MagicMock()
        close_mock = MagicMock()
        with patch.dict(
            os.__dict__, {"open": open_mock, "close": close_mock}
        ):  # pylint: disable=no-member
            # Normal case
            self.assertTrue(virt.volume_upload("pool0", "vol1.qcow2", "/path/to/file"))
            stream_mock.sendAll.assert_called_once()
            stream_mock.finish.assert_called_once()
            self.mock_conn.close.assert_called_once()
            vol_mock.upload.assert_called_once_with(stream_mock, 0, 0, 0)

            # Sparse upload case
            stream_mock.sendAll.reset_mock()
            vol_mock.upload.reset_mock()
            self.assertTrue(
                virt.volume_upload(
                    "pool0",
                    "vol1.qcow2",
                    "/path/to/file",
                    offset=123,
                    length=456,
                    sparse=True,
                )
            )
            stream_mock.sendAll.assert_not_called()
            stream_mock.sparseSendAll.assert_called_once()
            vol_mock.upload.assert_called_once_with(
                stream_mock,
                123,
                456,
                self.mock_libvirt.VIR_STORAGE_VOL_UPLOAD_SPARSE_STREAM,
            )

            # Upload unsupported case
            vol_mock.upload.side_effect = self.mock_libvirt.libvirtError("Unsupported")
            self.assertRaisesRegex(
                CommandExecutionError,
                "Unsupported",
                virt.volume_upload,
                "pool0",
                "vol1.qcow2",
                "/path/to/file",
            )
