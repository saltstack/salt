# -*- coding: utf-8 -*-
'''
virt execution module unit tests
'''

# pylint: disable=3rd-party-module-not-gated

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import re
import datetime

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import salt libs
import salt.utils.yaml
import salt.modules.virt as virt
import salt.modules.config as config
from salt._compat import ElementTree as ET
import salt.config
import salt.syspaths
from salt.exceptions import CommandExecutionError

# Import third party libs
from salt.ext import six
# pylint: disable=import-error
from salt.ext.six.moves import range  # pylint: disable=redefined-builtin


# pylint: disable=invalid-name,protected-access,attribute-defined-outside-init,too-many-public-methods,unused-argument


class LibvirtMock(MagicMock):  # pylint: disable=too-many-ancestors
    '''
    Libvirt library mock
    '''
    class virDomain(MagicMock):
        '''
        virDomain mock
        '''

    class libvirtError(Exception):
        '''
        libvirtError mock
        '''


@skipIf(NO_MOCK, NO_MOCK_REASON)
class VirtTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.module.virt
    '''

    def setup_loader_modules(self):
        self.mock_libvirt = LibvirtMock()
        self.mock_conn = MagicMock()
        self.mock_libvirt.openAuth.return_value = self.mock_conn
        self.mock_popen = MagicMock()
        self.addCleanup(delattr, self, 'mock_libvirt')
        self.addCleanup(delattr, self, 'mock_conn')
        self.addCleanup(delattr, self, 'mock_popen')
        mock_subprocess = MagicMock()
        mock_subprocess.Popen.return_value = self.mock_popen  # pylint: disable=no-member
        loader_globals = {
            '__salt__': {
                'config.get': config.get,
                'config.option': config.option,
            },
            'libvirt': self.mock_libvirt,
            'subprocess': mock_subprocess
        }
        return {virt: loader_globals, config: loader_globals}

    def set_mock_vm(self, name, xml):
        '''
        Define VM to use in tests
        '''
        self.mock_conn.listDefinedDomains.return_value = [name]  # pylint: disable=no-member
        mock_domain = self.mock_libvirt.virDomain()
        self.mock_conn.lookupByName.return_value = mock_domain  # pylint: disable=no-member
        mock_domain.XMLDesc.return_value = xml  # pylint: disable=no-member

        # Return state as shutdown
        mock_domain.info.return_value = [4, 0, 0, 0]  # pylint: disable=no-member
        return mock_domain

    def test_disk_profile_merge(self):
        '''
        Test virt._disk_profile() when merging with user-defined disks
        '''
        root_dir = os.path.join(salt.syspaths.ROOT_DIR, 'srv', 'salt-images')
        userdisks = [{'name': 'data', 'size': 16384, 'format': 'raw'}]

        disks = virt._disk_profile('default', 'kvm', userdisks, 'myvm', image='/path/to/image')
        self.assertEqual(
            [{'name': 'system',
              'device': 'disk',
              'size': 8192,
              'format': 'qcow2',
              'model': 'virtio',
              'filename': 'myvm_system.qcow2',
              'image': '/path/to/image',
              'source_file': '{0}{1}myvm_system.qcow2'.format(root_dir, os.sep)},
             {'name': 'data',
              'device': 'disk',
              'size': 16384,
              'format': 'raw',
              'model': 'virtio',
              'filename': 'myvm_data.raw',
              'source_file': '{0}{1}myvm_data.raw'.format(root_dir, os.sep)}],
            disks
        )

    def test_boot_default_dev(self):
        '''
        Test virt._gen_xml() default boot device
        '''
        diskp = virt._disk_profile('default', 'kvm', [], 'hello')
        nicp = virt._nic_profile('default', 'kvm')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'kvm',
            'hvm',
            'x86_64'
            )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('os/boot').attrib['dev'], 'hd')
        self.assertEqual(root.find('os/type').attrib['arch'], 'x86_64')
        self.assertEqual(root.find('os/type').text, 'hvm')

    def test_boot_custom_dev(self):
        '''
        Test virt._gen_xml() custom boot device
        '''
        diskp = virt._disk_profile('default', 'kvm', [], 'hello')
        nicp = virt._nic_profile('default', 'kvm')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'kvm',
            'hvm',
            'x86_64',
            boot_dev='cdrom'
            )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('os/boot').attrib['dev'], 'cdrom')

    def test_boot_multiple_devs(self):
        '''
        Test virt._gen_xml() multiple boot devices
        '''
        diskp = virt._disk_profile('default', 'kvm', [], 'hello')
        nicp = virt._nic_profile('default', 'kvm')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'kvm',
            'hvm',
            'x86_64',
            boot_dev='cdrom network'
            )
        root = ET.fromstring(xml_data)
        devs = root.findall('.//boot')
        self.assertTrue(len(devs) == 2)

    def test_gen_xml_no_nic(self):
        '''
        Test virt._gen_xml() serial console
        '''
        diskp = virt._disk_profile('default', 'kvm', [], 'hello')
        nicp = virt._nic_profile('default', 'kvm')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'kvm',
            'hvm',
            'x86_64',
            serial_type='pty',
            console=True
            )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('devices/serial').attrib['type'], 'pty')
        self.assertEqual(root.find('devices/console').attrib['type'], 'pty')

    def test_gen_xml_for_serial_console(self):
        '''
        Test virt._gen_xml() serial console
        '''
        diskp = virt._disk_profile('default', 'kvm', [], 'hello')
        nicp = virt._nic_profile('default', 'kvm')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'kvm',
            'hvm',
            'x86_64',
            serial_type='pty',
            console=True
            )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('devices/serial').attrib['type'], 'pty')
        self.assertEqual(root.find('devices/console').attrib['type'], 'pty')

    def test_gen_xml_for_telnet_console(self):
        '''
        Test virt._gen_xml() telnet console
        '''
        diskp = virt._disk_profile('default', 'kvm', [], 'hello')
        nicp = virt._nic_profile('default', 'kvm')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'kvm',
            'hvm',
            'x86_64',
            serial_type='tcp',
            console=True,
            telnet_port=22223
            )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('devices/serial').attrib['type'], 'tcp')
        self.assertEqual(root.find('devices/console').attrib['type'], 'tcp')
        self.assertEqual(root.find('devices/console/source').attrib['service'], '22223')

    def test_gen_xml_for_telnet_console_unspecified_port(self):
        '''
        Test virt._gen_xml() telnet console without any specified port
        '''
        diskp = virt._disk_profile('default', 'kvm', [], 'hello')
        nicp = virt._nic_profile('default', 'kvm')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'kvm',
            'hvm',
            'x86_64',
            serial_type='tcp',
            console=True
            )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('devices/serial').attrib['type'], 'tcp')
        self.assertEqual(root.find('devices/console').attrib['type'], 'tcp')
        self.assertIsInstance(int(root.find('devices/console/source').attrib['service']), int)

    def test_gen_xml_for_serial_no_console(self):
        '''
        Test virt._gen_xml() with no serial console
        '''
        diskp = virt._disk_profile('default', 'kvm', [], 'hello')
        nicp = virt._nic_profile('default', 'kvm')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'kvm',
            'hvm',
            'x86_64',
            serial_type='pty',
            console=False
            )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('devices/serial').attrib['type'], 'pty')
        self.assertEqual(root.find('devices/console'), None)

    def test_gen_xml_for_telnet_no_console(self):
        '''
        Test virt._gen_xml() with no telnet console
        '''
        diskp = virt._disk_profile('default', 'kvm', [], 'hello')
        nicp = virt._nic_profile('default', 'kvm')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'kvm',
            'hvm',
            'x86_64',
            serial_type='tcp',
            console=False,
            )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('devices/serial').attrib['type'], 'tcp')
        self.assertEqual(root.find('devices/console'), None)

    def test_gen_xml_nographics_default(self):
        '''
        Test virt._gen_xml() with default no graphics device
        '''
        diskp = virt._disk_profile('default', 'kvm', [], 'hello')
        nicp = virt._nic_profile('default', 'kvm')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'kvm',
            'hvm',
            'x86_64'
            )
        root = ET.fromstring(xml_data)
        self.assertIsNone(root.find('devices/graphics'))

    def test_gen_xml_vnc_default(self):
        '''
        Test virt._gen_xml() with default vnc graphics device
        '''
        diskp = virt._disk_profile('default', 'kvm', [], 'hello')
        nicp = virt._nic_profile('default', 'kvm')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'kvm',
            'hvm',
            'x86_64',
            graphics={'type': 'vnc', 'port': 1234, 'tlsPort': 5678,
                      'listen': {'type': 'address', 'address': 'myhost'}},
            )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('devices/graphics').attrib['type'], 'vnc')
        self.assertEqual(root.find('devices/graphics').attrib['autoport'], 'no')
        self.assertEqual(root.find('devices/graphics').attrib['port'], '1234')
        self.assertFalse('tlsPort' in root.find('devices/graphics').attrib)
        self.assertEqual(root.find('devices/graphics').attrib['listen'], 'myhost')
        self.assertEqual(root.find('devices/graphics/listen').attrib['type'], 'address')
        self.assertEqual(root.find('devices/graphics/listen').attrib['address'], 'myhost')

    def test_gen_xml_spice_default(self):
        '''
        Test virt._gen_xml() with default spice graphics device
        '''
        diskp = virt._disk_profile('default', 'kvm', [], 'hello')
        nicp = virt._nic_profile('default', 'kvm')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'kvm',
            'hvm',
            'x86_64',
            graphics={'type': 'spice'},
            )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('devices/graphics').attrib['type'], 'spice')
        self.assertEqual(root.find('devices/graphics').attrib['autoport'], 'yes')
        self.assertEqual(root.find('devices/graphics').attrib['listen'], '0.0.0.0')
        self.assertEqual(root.find('devices/graphics/listen').attrib['type'], 'address')
        self.assertEqual(root.find('devices/graphics/listen').attrib['address'], '0.0.0.0')

    def test_gen_xml_spice(self):
        '''
        Test virt._gen_xml() with spice graphics device
        '''
        diskp = virt._disk_profile('default', 'kvm', [], 'hello')
        nicp = virt._nic_profile('default', 'kvm')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'kvm',
            'hvm',
            'x86_64',
            graphics={'type': 'spice', 'port': 1234, 'tls_port': 5678, 'listen': {'type': 'none'}},
            )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('devices/graphics').attrib['type'], 'spice')
        self.assertEqual(root.find('devices/graphics').attrib['autoport'], 'no')
        self.assertEqual(root.find('devices/graphics').attrib['port'], '1234')
        self.assertEqual(root.find('devices/graphics').attrib['tlsPort'], '5678')
        self.assertFalse('listen' in root.find('devices/graphics').attrib)
        self.assertEqual(root.find('devices/graphics/listen').attrib['type'], 'none')
        self.assertFalse('address' in root.find('devices/graphics/listen').attrib)

    def test_default_disk_profile_hypervisor_esxi(self):
        '''
        Test virt._disk_profile() default ESXi profile
        '''
        mock = MagicMock(return_value={})
        with patch.dict(virt.__salt__, {'config.get': mock}):  # pylint: disable=no-member
            ret = virt._disk_profile('nonexistent', 'vmware')
            self.assertTrue(len(ret) == 1)
            found = [disk for disk in ret if disk['name'] == 'system']
            self.assertTrue(bool(found))
            system = found[0]
            self.assertEqual(system['format'], 'vmdk')
            self.assertEqual(system['model'], 'scsi')
            self.assertTrue(int(system['size']) >= 1)

    def test_default_disk_profile_hypervisor_kvm(self):
        '''
        Test virt._disk_profile() default KVM profile
        '''
        mock = MagicMock(return_value={})
        with patch.dict(virt.__salt__, {'config.get': mock}):  # pylint: disable=no-member
            ret = virt._disk_profile('nonexistent', 'kvm')
            self.assertTrue(len(ret) == 1)
            found = [disk for disk in ret if disk['name'] == 'system']
            self.assertTrue(bool(found))
            system = found[0]
            self.assertEqual(system['format'], 'qcow2')
            self.assertEqual(system['model'], 'virtio')
            self.assertTrue(int(system['size']) >= 1)

    def test_default_disk_profile_hypervisor_xen(self):
        '''
        Test virt._disk_profile() default XEN profile
        '''
        mock = MagicMock(return_value={})
        with patch.dict(virt.__salt__, {'config.get': mock}):  # pylint: disable=no-member
            ret = virt._disk_profile('nonexistent', 'xen')
            self.assertTrue(len(ret) == 1)
            found = [disk for disk in ret if disk['name'] == 'system']
            self.assertTrue(bool(found))
            system = found[0]
            self.assertEqual(system['format'], 'qcow2')
            self.assertEqual(system['model'], 'xen')
            self.assertTrue(int(system['size']) >= 1)

    def test_default_nic_profile_hypervisor_esxi(self):
        '''
        Test virt._nic_profile() default ESXi profile
        '''
        mock = MagicMock(return_value={})
        with patch.dict(virt.__salt__, {'config.get': mock}):  # pylint: disable=no-member
            ret = virt._nic_profile('nonexistent', 'vmware')
            self.assertTrue(len(ret) == 1)
            eth0 = ret[0]
            self.assertEqual(eth0['name'], 'eth0')
            self.assertEqual(eth0['type'], 'bridge')
            self.assertEqual(eth0['source'], 'DEFAULT')
            self.assertEqual(eth0['model'], 'e1000')

    def test_default_nic_profile_hypervisor_kvm(self):
        '''
        Test virt._nic_profile() default KVM profile
        '''
        mock = MagicMock(return_value={})
        with patch.dict(virt.__salt__, {'config.get': mock}):  # pylint: disable=no-member
            ret = virt._nic_profile('nonexistent', 'kvm')
            self.assertTrue(len(ret) == 1)
            eth0 = ret[0]
            self.assertEqual(eth0['name'], 'eth0')
            self.assertEqual(eth0['type'], 'bridge')
            self.assertEqual(eth0['source'], 'br0')
            self.assertEqual(eth0['model'], 'virtio')

    def test_default_nic_profile_hypervisor_xen(self):
        '''
        Test virt._nic_profile() default XEN profile
        '''
        mock = MagicMock(return_value={})
        with patch.dict(virt.__salt__, {'config.get': mock}):  # pylint: disable=no-member
            ret = virt._nic_profile('nonexistent', 'xen')
            self.assertTrue(len(ret) == 1)
            eth0 = ret[0]
            self.assertEqual(eth0['name'], 'eth0')
            self.assertEqual(eth0['type'], 'bridge')
            self.assertEqual(eth0['source'], 'br0')
            self.assertFalse(eth0['model'])

    def test_gen_vol_xml(self):
        '''
        Test virt._get_vol_xml()
        '''
        xml_data = virt._gen_vol_xml('vmname', 'system', 'qcow2', 8192, '/path/to/image/')
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('name').text, 'vmname/system.qcow2')
        self.assertEqual(root.find('key').text, 'vmname/system')
        self.assertEqual(root.find('capacity').attrib['unit'], 'KiB')
        self.assertEqual(root.find('capacity').text, six.text_type(8192 * 1024))

    def test_gen_xml_for_kvm_default_profile(self):
        '''
        Test virt._gen_xml(), KVM default profile case
        '''
        diskp = virt._disk_profile('default', 'kvm', [], 'hello')
        nicp = virt._nic_profile('default', 'kvm')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'kvm',
            'hvm',
            'x86_64',
            )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.attrib['type'], 'kvm')
        self.assertEqual(root.find('vcpu').text, '1')
        self.assertEqual(root.find('memory').text, six.text_type(512 * 1024))
        self.assertEqual(root.find('memory').attrib['unit'], 'KiB')

        disks = root.findall('.//disk')
        self.assertEqual(len(disks), 1)
        disk = disks[0]
        root_dir = salt.config.DEFAULT_MINION_OPTS.get('root_dir')
        self.assertTrue(disk.find('source').attrib['file'].startswith(root_dir))
        self.assertTrue('hello_system' in disk.find('source').attrib['file'])
        self.assertEqual(disk.find('target').attrib['dev'], 'vda')
        self.assertEqual(disk.find('target').attrib['bus'], 'virtio')
        self.assertEqual(disk.find('driver').attrib['name'], 'qemu')
        self.assertEqual(disk.find('driver').attrib['type'], 'qcow2')

        interfaces = root.findall('.//interface')
        self.assertEqual(len(interfaces), 1)
        iface = interfaces[0]
        self.assertEqual(iface.attrib['type'], 'bridge')
        self.assertEqual(iface.find('source').attrib['bridge'], 'br0')
        self.assertEqual(iface.find('model').attrib['type'], 'virtio')

        mac = iface.find('mac').attrib['address']
        self.assertTrue(
              re.match('^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$', mac, re.I))

    def test_gen_xml_for_esxi_default_profile(self):
        '''
        Test virt._gen_xml(), ESXi/vmware default profile case
        '''
        diskp = virt._disk_profile('default', 'vmware', [], 'hello')
        nicp = virt._nic_profile('default', 'vmware')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'vmware',
            'hvm',
            'x86_64',
            )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.attrib['type'], 'vmware')
        self.assertEqual(root.find('vcpu').text, '1')
        self.assertEqual(root.find('memory').text, six.text_type(512 * 1024))
        self.assertEqual(root.find('memory').attrib['unit'], 'KiB')

        disks = root.findall('.//disk')
        self.assertEqual(len(disks), 1)
        disk = disks[0]
        self.assertTrue('[0]' in disk.find('source').attrib['file'])
        self.assertTrue('hello_system' in disk.find('source').attrib['file'])
        self.assertEqual(disk.find('target').attrib['dev'], 'sda')
        self.assertEqual(disk.find('target').attrib['bus'], 'scsi')
        self.assertEqual(disk.find('address').attrib['unit'], '0')

        interfaces = root.findall('.//interface')
        self.assertEqual(len(interfaces), 1)
        iface = interfaces[0]
        self.assertEqual(iface.attrib['type'], 'bridge')
        self.assertEqual(iface.find('source').attrib['bridge'], 'DEFAULT')
        self.assertEqual(iface.find('model').attrib['type'], 'e1000')

        mac = iface.find('mac').attrib['address']
        self.assertTrue(
              re.match('^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$', mac, re.I))

    def test_gen_xml_for_xen_default_profile(self):
        '''
        Test virt._gen_xml(), XEN PV default profile case
        '''
        diskp = virt._disk_profile('default', 'xen', [], 'hello')
        nicp = virt._nic_profile('default', 'xen')
        with patch.dict(virt.__grains__, {'os_family': 'Suse'}):
            xml_data = virt._gen_xml(
                'hello',
                1,
                512,
                diskp,
                nicp,
                'xen',
                'xen',
                'x86_64',
                )
            root = ET.fromstring(xml_data)
            self.assertEqual(root.attrib['type'], 'xen')
            self.assertEqual(root.find('vcpu').text, '1')
            self.assertEqual(root.find('memory').text, six.text_type(512 * 1024))
            self.assertEqual(root.find('memory').attrib['unit'], 'KiB')
            self.assertEqual(root.find('.//kernel').text, '/usr/lib/grub2/x86_64-xen/grub.xen')

            disks = root.findall('.//disk')
            self.assertEqual(len(disks), 1)
            disk = disks[0]
            root_dir = salt.config.DEFAULT_MINION_OPTS.get('root_dir')
            self.assertTrue(disk.find('source').attrib['file'].startswith(root_dir))
            self.assertTrue('hello_system' in disk.find('source').attrib['file'])
            self.assertEqual(disk.find('target').attrib['dev'], 'xvda')
            self.assertEqual(disk.find('target').attrib['bus'], 'xen')
            self.assertEqual(disk.find('driver').attrib['name'], 'qemu')
            self.assertEqual(disk.find('driver').attrib['type'], 'qcow2')

            interfaces = root.findall('.//interface')
            self.assertEqual(len(interfaces), 1)
            iface = interfaces[0]
            self.assertEqual(iface.attrib['type'], 'bridge')
            self.assertEqual(iface.find('source').attrib['bridge'], 'br0')
            self.assertIsNone(iface.find('model'))

    def test_gen_xml_for_esxi_custom_profile(self):
        '''
        Test virt._gen_xml(), ESXi/vmware custom profile case
        '''
        disks = {
            'noeffect': [
                {'first': {'size': 8192, 'pool': 'datastore1'}},
                {'second': {'size': 4096, 'pool': 'datastore2'}}
            ]
        }
        nics = {
            'noeffect': [
                {'name': 'eth1', 'source': 'ONENET'},
                {'name': 'eth2', 'source': 'TWONET'}
            ]
        }
        with patch.dict(virt.__salt__,  # pylint: disable=no-member
                        {'config.get': MagicMock(side_effect=[disks, nics])}):
            diskp = virt._disk_profile('noeffect', 'vmware', [], 'hello')
            nicp = virt._nic_profile('noeffect', 'vmware')
            xml_data = virt._gen_xml(
                'hello',
                1,
                512,
                diskp,
                nicp,
                'vmware',
                'hvm',
                'x86_64',
                )
            root = ET.fromstring(xml_data)
            self.assertEqual(root.attrib['type'], 'vmware')
            self.assertEqual(root.find('vcpu').text, '1')
            self.assertEqual(root.find('memory').text, six.text_type(512 * 1024))
            self.assertEqual(root.find('memory').attrib['unit'], 'KiB')
            self.assertTrue(len(root.findall('.//disk')) == 2)
            self.assertTrue(len(root.findall('.//interface')) == 2)

    def test_gen_xml_for_kvm_custom_profile(self):
        '''
        Test virt._gen_xml(), KVM custom profile case
        '''
        disks = {
            'noeffect': [
                {'first': {'size': 8192, 'pool': '/var/lib/images'}},
                {'second': {'size': 4096, 'pool': '/var/lib/images'}}
            ]
        }
        nics = {
            'noeffect': [
                {'name': 'eth1', 'source': 'b2'},
                {'name': 'eth2', 'source': 'b2'}
            ]
        }
        with patch.dict(virt.__salt__, {'config.get': MagicMock(side_effect=[  # pylint: disable=no-member
                disks, nics])}):
            diskp = virt._disk_profile('noeffect', 'kvm', [], 'hello')
            nicp = virt._nic_profile('noeffect', 'kvm')
            xml_data = virt._gen_xml(
                'hello',
                1,
                512,
                diskp,
                nicp,
                'kvm',
                'hvm',
                'x86_64',
                )
            root = ET.fromstring(xml_data)
            self.assertEqual(root.attrib['type'], 'kvm')
            self.assertEqual(root.find('vcpu').text, '1')
            self.assertEqual(root.find('memory').text, six.text_type(512 * 1024))
            self.assertEqual(root.find('memory').attrib['unit'], 'KiB')
            self.assertTrue(len(root.findall('.//disk')) == 2)
            self.assertTrue(len(root.findall('.//interface')) == 2)

    @patch('salt.modules.virt.pool_info',
           return_value={'mypool': {'target_path': os.path.join(salt.syspaths.ROOT_DIR, 'pools', 'mypool')}})
    def test_disk_profile_kvm_disk_pool(self, mock_poolinfo):
        '''
        Test virt._gen_xml(), KVM case with pools defined.
        '''
        disks = {
            'noeffect': [
                {'first': {'size': 8192, 'pool': 'mypool'}},
                {'second': {'size': 4096}}
            ]
        }

        # pylint: disable=no-member
        with patch.dict(virt.__salt__, {'config.get': MagicMock(side_effect=[
                disks,
                os.path.join(salt.syspaths.ROOT_DIR, 'default', 'path')])}):

            diskp = virt._disk_profile('noeffect', 'kvm', [], 'hello')

            pools_path = os.path.join(salt.syspaths.ROOT_DIR, 'pools', 'mypool') + os.sep
            default_path = os.path.join(salt.syspaths.ROOT_DIR, 'default', 'path') + os.sep

            self.assertEqual(len(diskp), 2)
            self.assertTrue(diskp[0]['source_file'].startswith(pools_path))
            self.assertTrue(diskp[1]['source_file'].startswith(default_path))
        # pylint: enable=no-member

    def test_disk_profile_kvm_disk_external_image(self):
        '''
        Test virt._gen_xml(), KVM case with an external image.
        '''
        diskp = virt._disk_profile(None, 'kvm', [
            {
                'name': 'mydisk',
                'source_file': '/path/to/my/image.qcow2'
            }], 'hello')

        self.assertEqual(len(diskp), 1)
        self.assertEqual(diskp[0]['source_file'], ('/path/to/my/image.qcow2'))

    @patch('salt.modules.virt.pool_info', return_value={})
    def test_disk_profile_kvm_disk_pool_notfound(self, mock_poolinfo):
        '''
        Test virt._gen_xml(), KVM case with pools defined.
        '''
        disks = {
            'noeffect': [
                {'first': {'size': 8192, 'pool': 'default'}},
            ]
        }
        with patch.dict(virt.__salt__, {'config.get': MagicMock(side_effect=[  # pylint: disable=no-member
                disks, "/default/path/"])}):
            with self.assertRaises(CommandExecutionError):
                virt._disk_profile('noeffect', 'kvm', [], 'hello')

    @patch('salt.modules.virt.pool_info', return_value={'target_path': '/dev/disk/by-path'})
    def test_disk_profile_kvm_disk_pool_invalid(self, mock_poolinfo):
        '''
        Test virt._gen_xml(), KVM case with pools defined.
        '''
        disks = {
            'noeffect': [
                {'first': {'size': 8192, 'pool': 'default'}},
            ]
        }
        with patch.dict(virt.__salt__, {'config.get': MagicMock(side_effect=[  # pylint: disable=no-member
                disks, "/default/path/"])}):
            with self.assertRaises(CommandExecutionError):
                virt._disk_profile('noeffect', 'kvm', [], 'hello')

    def test_gen_xml_cdrom(self):
        '''
        Test virt._gen_xml(), generating a cdrom device (different disk type, no source)
        '''
        diskp = virt._disk_profile(None, 'kvm', [{
            'name': 'tested',
            'device': 'cdrom',
            'source_file': None,
            'model': 'ide'}], 'hello')
        nicp = virt._nic_profile(None, 'kvm')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'kvm',
            'hvm',
            'x86_64',
            )
        root = ET.fromstring(xml_data)
        disk = root.findall('.//disk')[0]
        self.assertEqual(disk.attrib['device'], 'cdrom')
        self.assertIsNone(disk.find('source'))

    def test_controller_for_esxi(self):
        '''
        Test virt._gen_xml() generated device controller for ESXi/vmware
        '''
        diskp = virt._disk_profile('default', 'vmware', [], 'hello')
        nicp = virt._nic_profile('default', 'vmware')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'vmware',
            'hvm',
            'x86_64',
            )
        root = ET.fromstring(xml_data)
        controllers = root.findall('.//devices/controller')
        self.assertTrue(len(controllers) == 1)
        controller = controllers[0]
        self.assertEqual(controller.attrib['model'], 'lsilogic')

    def test_controller_for_kvm(self):
        '''
        Test virt._gen_xml() generated device controller for KVM
        '''
        diskp = virt._disk_profile('default', 'kvm', [], 'hello')
        nicp = virt._nic_profile('default', 'kvm')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'kvm',
            'hvm',
            'x86_64',
            )
        root = ET.fromstring(xml_data)
        controllers = root.findall('.//devices/controller')
        # There should be no controller
        self.assertTrue(len(controllers) == 0)
        # kvm mac address shoud start with 52:54:00
        self.assertTrue("mac address='52:54:00" in xml_data)

    def test_diff_disks(self):
        '''
        Test virt._diff_disks()
        '''
        old_disks = ET.fromstring('''
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
        ''').findall('disk')

        new_disks = ET.fromstring('''
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
        ''').findall('disk')
        ret = virt._diff_disk_lists(old_disks, new_disks)
        self.assertEqual([disk.find('source').get('file') if disk.find('source') is not None else None
                          for disk in ret['unchanged']], [])
        self.assertEqual([disk.find('source').get('file') if disk.find('source') is not None else None
                          for disk in ret['new']],
                         ['/path/to/img3.qcow2', '/path/to/img0.qcow2', '/path/to/img4.qcow2', None])
        self.assertEqual([disk.find('target').get('dev') for disk in ret['sorted']],
                         ['vda', 'vdb', 'vdc', 'hda'])
        self.assertEqual([disk.find('source').get('file') if disk.find('source') is not None else None
                          for disk in ret['sorted']],
                         ['/path/to/img3.qcow2',
                          '/path/to/img0.qcow2',
                          '/path/to/img4.qcow2',
                          None])
        self.assertEqual(ret['new'][1].find('target').get('bus'), 'virtio')
        self.assertEqual([disk.find('source').get('file') if disk.find('source') is not None else None
                          for disk in ret['deleted']],
                         ['/path/to/img0.qcow2',
                          '/path/to/img1.qcow2',
                          '/path/to/img2.qcow2',
                          '/path/to/img4.qcow2',
                          None])

    def test_diff_nics(self):
        '''
        Test virt._diff_nics()
        '''
        old_nics = ET.fromstring('''
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
        ''').findall('interface')

        new_nics = ET.fromstring('''
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
        ''').findall('interface')
        ret = virt._diff_interface_lists(old_nics, new_nics)
        self.assertEqual([nic.find('mac').get('address') for nic in ret['unchanged']],
                         ['52:54:00:39:02:b1'])
        self.assertEqual([nic.find('mac').get('address') for nic in ret['new']],
                         ['52:54:00:39:02:b2', '52:54:00:39:02:b4'])
        self.assertEqual([nic.find('mac').get('address') for nic in ret['deleted']],
                         ['52:54:00:39:02:b2', '52:54:00:39:02:b3'])

    def test_init(self):
        '''
        Test init() function
        '''
        xml = '''
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
        '''
        self.mock_conn.getCapabilities.return_value = xml  # pylint: disable=no-member

        root_dir = os.path.join(salt.syspaths.ROOT_DIR, 'srv', 'salt-images')

        defineMock = MagicMock(return_value=1)
        self.mock_conn.defineXML = defineMock
        mock_chmod = MagicMock()
        mock_run = MagicMock()
        with patch.dict(os.__dict__, {'chmod': mock_chmod, 'makedirs': MagicMock()}):  # pylint: disable=no-member
            with patch.dict(virt.__salt__, {'cmd.run': mock_run}):  # pylint: disable=no-member

                # Ensure the init() function allows creating VM without NIC and disk
                virt.init('test vm',
                          2,
                          1234,
                          nic=None,
                          disk=None,
                          seed=False,
                          start=False)
                definition = defineMock.call_args_list[0][0][0]
                self.assertFalse('<interface' in definition)
                self.assertFalse('<disk' in definition)

                # Test case creating disks
                defineMock.reset_mock()
                mock_run.reset_mock()
                virt.init('test vm',
                          2,
                          1234,
                          nic=None,
                          disk=None,
                          disks=[
                              {'name': 'system', 'size': 10240},
                              {'name': 'cddrive', 'device': 'cdrom', 'source_file': None, 'model': 'ide'}
                          ],
                          seed=False,
                          start=False)
                definition = ET.fromstring(defineMock.call_args_list[0][0][0])
                disk_sources = [disk.find('source').get('file') if disk.find('source') is not None else None
                                for disk in definition.findall('./devices/disk')]
                expected_disk_path = os.path.join(root_dir, 'test vm_system.qcow2')
                self.assertEqual(disk_sources, [expected_disk_path, None])
                self.assertEqual(mock_run.call_args[0][0],
                                 'qemu-img create -f qcow2 "{0}" 10240M'.format(expected_disk_path))
                self.assertEqual(mock_chmod.call_args[0][0], expected_disk_path)

    def test_update(self):
        '''
        Test virt.update()
        '''
        root_dir = os.path.join(salt.syspaths.ROOT_DIR, 'srv', 'salt-images')
        xml = '''
            <domain type='kvm' id='7'>
              <name>my vm</name>
              <memory unit='KiB'>1048576</memory>
              <currentMemory unit='KiB'>1048576</currentMemory>
              <vcpu placement='auto'>1</vcpu>
              <os>
                <type arch='x86_64' machine='pc-i440fx-2.6'>hvm</type>
              </os>
              <devices>
                <disk type='file' device='disk'>
                  <driver name='qemu' type='qcow2'/>
                  <source file='{0}{1}my vm_system.qcow2'/>
                  <backingStore/>
                  <target dev='vda' bus='virtio'/>
                  <alias name='virtio-disk0'/>
                  <address type='pci' domain='0x0000' bus='0x00' slot='0x07' function='0x0'/>
                </disk>
                <disk type='file' device='disk'>
                  <driver name='qemu' type='qcow2'/>
                  <source file='{0}{1}my vm_data.qcow2'/>
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
        '''.format(root_dir, os.sep)
        domain_mock = self.set_mock_vm('my vm', xml)
        domain_mock.OSType = MagicMock(return_value='hvm')
        define_mock = MagicMock(return_value=True)
        self.mock_conn.defineXML = define_mock

        # Update vcpus case
        setvcpus_mock = MagicMock(return_value=0)
        domain_mock.setVcpusFlags = setvcpus_mock
        self.assertEqual({
                'definition': True,
                'cpu': True,
                'disk': {'attached': [], 'detached': []},
                'interface': {'attached': [], 'detached': []}
            }, virt.update('my vm', cpu=2))
        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual(setxml.find('vcpu').text, '2')
        self.assertEqual(setvcpus_mock.call_args[0][0], 2)

        # Update memory case
        setmem_mock = MagicMock(return_value=0)
        domain_mock.setMemoryFlags = setmem_mock

        self.assertEqual({
                'definition': True,
                'mem': True,
                'disk': {'attached': [], 'detached': []},
                'interface': {'attached': [], 'detached': []}
            }, virt.update('my vm', mem=2048))
        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual(setxml.find('memory').text, '2048')
        self.assertEqual(setxml.find('memory').get('unit'), 'MiB')
        self.assertEqual(setmem_mock.call_args[0][0], 2048 * 1024)

        # Update disks case
        devattach_mock = MagicMock(return_value=0)
        devdetach_mock = MagicMock(return_value=0)
        domain_mock.attachDevice = devattach_mock
        domain_mock.detachDevice = devdetach_mock
        mock_chmod = MagicMock()
        mock_run = MagicMock()
        with patch.dict(os.__dict__, {'chmod': mock_chmod, 'makedirs': MagicMock()}):  # pylint: disable=no-member
            with patch.dict(virt.__salt__, {'cmd.run': mock_run}):  # pylint: disable=no-member
                ret = virt.update('my vm', disk_profile='default', disks=[
                    {'name': 'cddrive', 'device': 'cdrom', 'source_file': None, 'model': 'ide'},
                    {'name': 'added', 'size': 2048}])
                added_disk_path = os.path.join(
                        virt.__salt__['config.get']('virt:images'), 'my vm_added.qcow2')  # pylint: disable=no-member
                self.assertEqual(mock_run.call_args[0][0],
                                 'qemu-img create -f qcow2 "{0}" 2048M'.format(added_disk_path))
                self.assertEqual(mock_chmod.call_args[0][0], added_disk_path)
                self.assertListEqual(
                    [None, os.path.join(root_dir, 'my vm_added.qcow2')],
                    [ET.fromstring(disk).find('source').get('file') if str(disk).find('<source') > -1 else None
                     for disk in ret['disk']['attached']])

                self.assertListEqual(
                    [os.path.join(root_dir, 'my vm_data.qcow2')],
                    [ET.fromstring(disk).find('source').get('file') for disk in ret['disk']['detached']])
                self.assertEqual(devattach_mock.call_count, 2)
                devdetach_mock.assert_called_once()

        # Update nics case
        yaml_config = '''
          virt:
             nic:
                myprofile:
                   - network: default
                     name: eth0
        '''
        mock_config = salt.utils.yaml.safe_load(yaml_config)
        devattach_mock.reset_mock()
        devdetach_mock.reset_mock()
        with patch.dict(salt.modules.config.__opts__, mock_config):  # pylint: disable=no-member
            ret = virt.update('my vm', nic_profile='myprofile',
                              interfaces=[{'name': 'eth0', 'type': 'network', 'source': 'default',
                                           'mac': '52:54:00:39:02:b1'},
                                          {'name': 'eth1', 'type': 'network', 'source': 'newnet'}])
            self.assertEqual(['newnet'],
                             [ET.fromstring(nic).find('source').get('network') for nic in ret['interface']['attached']])
            self.assertEqual(['oldnet'],
                             [ET.fromstring(nic).find('source').get('network') for nic in ret['interface']['detached']])
            devattach_mock.assert_called_once()
            devdetach_mock.assert_called_once()

        # Remove nics case
        devattach_mock.reset_mock()
        devdetach_mock.reset_mock()
        ret = virt.update('my vm', nic_profile=None, interfaces=[])
        self.assertEqual([], ret['interface']['attached'])
        self.assertEqual(2, len(ret['interface']['detached']))
        devattach_mock.assert_not_called()
        devdetach_mock.assert_called()

        # Remove disks case (yeah, it surely is silly)
        devattach_mock.reset_mock()
        devdetach_mock.reset_mock()
        ret = virt.update('my vm', disk_profile=None, disks=[])
        self.assertEqual([], ret['disk']['attached'])
        self.assertEqual(2, len(ret['disk']['detached']))
        devattach_mock.assert_not_called()
        devdetach_mock.assert_called()

        # Graphics change test case
        self.assertEqual({
                'definition': True,
                'disk': {'attached': [], 'detached': []},
                'interface': {'attached': [], 'detached': []}
            }, virt.update('my vm', graphics={'type': 'vnc'}))
        setxml = ET.fromstring(define_mock.call_args[0][0])
        self.assertEqual('vnc', setxml.find('devices/graphics').get('type'))

        # Update with no diff case
        self.assertEqual({
                'definition': False,
                'disk': {'attached': [], 'detached': []},
                'interface': {'attached': [], 'detached': []}
            }, virt.update('my vm', cpu=1, mem=1024,
                           disk_profile='default', disks=[{'name': 'data', 'size': 2048}],
                           nic_profile='myprofile',
                           interfaces=[{'name': 'eth0', 'type': 'network', 'source': 'default',
                                        'mac': '52:54:00:39:02:b1'},
                                       {'name': 'eth1', 'type': 'network', 'source': 'oldnet',
                                        'mac': '52:54:00:39:02:b2'}],
                           graphics={'type': 'spice',
                                     'listen': {'type': 'address', 'address': '127.0.0.1'}}))

        # Failed XML description update case
        self.mock_conn.defineXML.side_effect = self.mock_libvirt.libvirtError("Test error")
        setmem_mock.reset_mock()
        with self.assertRaises(self.mock_libvirt.libvirtError):
            virt.update('my vm', mem=2048)

        # Failed single update failure case
        self.mock_conn.defineXML = MagicMock(return_value=True)
        setmem_mock.side_effect = self.mock_libvirt.libvirtError("Failed to live change memory")
        self.assertEqual({
                'definition': True,
                'errors': ['Failed to live change memory'],
                'disk': {'attached': [], 'detached': []},
                'interface': {'attached': [], 'detached': []}
            }, virt.update('my vm', mem=2048))

        # Failed multiple updates failure case
        self.assertEqual({
                'definition': True,
                'errors': ['Failed to live change memory'],
                'cpu': True,
                'disk': {'attached': [], 'detached': []},
                'interface': {'attached': [], 'detached': []}
            }, virt.update('my vm', cpu=4, mem=2048))

    def test_mixed_dict_and_list_as_profile_objects(self):
        '''
        Test virt._nic_profile with mixed dictionaries and lists as input.
        '''
        yaml_config = '''
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
        '''
        mock_config = salt.utils.yaml.safe_load(yaml_config)
        with patch.dict(salt.modules.config.__opts__, mock_config):  # pylint: disable=no-member

            for name in six.iterkeys(mock_config['virt']['nic']):
                profile = salt.modules.virt._nic_profile(name, 'kvm')
                self.assertEqual(len(profile), 2)

                interface_attrs = profile[0]
                self.assertIn('source', interface_attrs)
                self.assertIn('type', interface_attrs)
                self.assertIn('name', interface_attrs)
                self.assertIn('model', interface_attrs)
                self.assertEqual(interface_attrs['model'], 'virtio')
                self.assertIn('mac', interface_attrs)
                self.assertTrue(
                    re.match('^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$',
                             interface_attrs['mac'], re.I))

    def test_get_graphics(self):
        '''
        Test virt.get_graphics()
        '''
        xml = '''<domain type='kvm' id='7'>
              <name>test-vm</name>
              <devices>
                <graphics type='vnc' port='5900' autoport='yes' listen='0.0.0.0'>
                  <listen type='address' address='0.0.0.0'/>
                </graphics>
              </devices>
            </domain>
        '''
        self.set_mock_vm("test-vm", xml)

        graphics = virt.get_graphics('test-vm')
        self.assertEqual('vnc', graphics['type'])
        self.assertEqual('5900', graphics['port'])
        self.assertEqual('0.0.0.0', graphics['listen'])

    def test_get_nics(self):
        '''
        Test virt.get_nics()
        '''
        xml = '''<domain type='kvm' id='7'>
              <name>test-vm</name>
              <devices>
                <interface type='bridge'>
                  <mac address='ac:de:48:b6:8b:59'/>
                  <source bridge='br0'/>
                  <model type='virtio'/>
                  <address type='pci' domain='0x0000' bus='0x00' slot='0x03' function='0x0'/>
                </interface>
              </devices>
            </domain>
        '''
        self.set_mock_vm("test-vm", xml)

        nics = virt.get_nics('test-vm')
        nic = nics[list(nics)[0]]
        self.assertEqual('bridge', nic['type'])
        self.assertEqual('ac:de:48:b6:8b:59', nic['mac'])

    def test_get_xml(self):
        '''
        Test virt.get_xml()
        '''
        xml = '''<domain type='kvm' id='7'>
              <name>test-vm</name>
              <devices>
                <graphics type='vnc' port='5900' autoport='yes' listen='0.0.0.0'>
                  <listen type='address' address='0.0.0.0'/>
                </graphics>
              </devices>
            </domain>
        '''
        domain = self.set_mock_vm("test-vm", xml)
        self.assertEqual(xml, virt.get_xml('test-vm'))
        self.assertEqual(xml, virt.get_xml(domain))

    def test_parse_qemu_img_info(self):
        '''
        Make sure that qemu-img info output is properly parsed
        '''
        qemu_infos = '''[{
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
        }]'''

        self.assertEqual(
            {
                'file': '/disks/test.qcow2',
                'file format': 'qcow2',
                'backing file': {
                    'file': '/disks/mybacking.qcow2',
                    'file format': 'qcow2',
                    'disk size': 393744384,
                    'virtual size': 25769803776,
                    'cluster size': 65536,
                    'backing file': {
                        'file': '/disks/root.qcow2',
                        'file format': 'qcow2',
                        'disk size': 196872192,
                        'virtual size': 25769803776,
                        'cluster size': 65536,
                    }
                },
                'disk size': 217088,
                'virtual size': 25769803776,
                'cluster size': 65536,
                'snapshots': [
                    {
                        'id': '1',
                        'tag': 'first-snap',
                        'vmsize': 1234,
                        'date': datetime.datetime.fromtimestamp(
                            float("{}.{}".format(1528877587, 380589000))).isoformat(),
                        'vmclock': '00:00:00'
                    },
                    {
                        'id': '2',
                        'tag': 'second snap',
                        'vmsize': 4567,
                        'date': datetime.datetime.fromtimestamp(
                            float("{}.{}".format(1528877592, 933509000))).isoformat(),
                        'vmclock': '00:00:00'
                    }
                ],
            }, virt._parse_qemu_img_info(qemu_infos))

    def test_get_disks(self):
        '''
        Test virt.get_disks()
        '''
        xml = '''<domain type='kvm' id='7'>
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
        '''
        self.set_mock_vm("test-vm", xml)

        qemu_infos = '''[{
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
        }]'''

        self.mock_popen.communicate.return_value = [qemu_infos]  # pylint: disable=no-member
        disks = virt.get_disks('test-vm')
        disk = disks.get('vda')
        self.assertEqual('/disks/test.qcow2', disk['file'])
        self.assertEqual('disk', disk['type'])
        self.assertEqual('/disks/mybacking.qcow2', disk['backing file']['file'])
        cdrom = disks.get('hda')
        self.assertEqual('/disks/test-cdrom.iso', cdrom['file'])
        self.assertEqual('cdrom', cdrom['type'])
        self.assertFalse('backing file' in cdrom.keys())

    @patch('salt.modules.virt.stop', return_value=True)
    @patch('salt.modules.virt.undefine')
    @patch('os.remove')
    def test_purge_default(self, mock_remove, mock_undefine, mock_stop):
        '''
        Test virt.purge() with default parameters
        '''
        xml = '''<domain type='kvm' id='7'>
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
        '''
        self.set_mock_vm("test-vm", xml)

        qemu_infos = '''[{
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
        }]'''

        self.mock_popen.communicate.return_value = [qemu_infos]  # pylint: disable=no-member

        res = virt.purge('test-vm')
        self.assertTrue(res)
        mock_remove.assert_any_call('/disks/test.qcow2')
        mock_remove.assert_any_call('/disks/test-cdrom.iso')

    @patch('salt.modules.virt.stop', return_value=True)
    @patch('salt.modules.virt.undefine')
    @patch('os.remove')
    def test_purge_noremovable(self, mock_remove, mock_undefine, mock_stop):
        '''
        Test virt.purge(removables=False)
        '''
        xml = '''<domain type='kvm' id='7'>
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
        '''
        self.set_mock_vm("test-vm", xml)

        qemu_infos = '''[{
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
        }]'''

        self.mock_popen.communicate.return_value = [qemu_infos]  # pylint: disable=no-member

        res = virt.purge('test-vm', removables=False)
        self.assertTrue(res)
        mock_remove.assert_called_once()
        mock_remove.assert_any_call('/disks/test.qcow2')

    def test_capabilities(self):
        '''
        Test the virt.capabilities parsing
        '''
        xml = '''
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
        '''
        self.mock_conn.getCapabilities.return_value = xml  # pylint: disable=no-member
        caps = virt.capabilities()

        expected = {
            'host': {
                'uuid': '44454c4c-3400-105a-8033-b3c04f4b344a',
                'cpu': {
                    'arch': 'x86_64',
                    'model': 'Nehalem',
                    'vendor': 'Intel',
                    'microcode': '25',
                    'sockets': 1,
                    'cores': 4,
                    'threads': 2,
                    'features': ['vme', 'ds', 'acpi'],
                    'pages': [{'size': '4 KiB'}, {'size': '2048 KiB'}]
                },
                'power_management': ['suspend_mem', 'suspend_disk', 'suspend_hybrid'],
                'migration': {
                    'live': True,
                    'transports': ['tcp', 'rdma']
                },
                'topology': {
                    'cells': [
                        {
                            'id': 0,
                            'memory': '12367120 KiB',
                            'pages': [
                                {'size': '4 KiB', 'available': 3091780},
                                {'size': '2048 KiB', 'available': 0}
                            ],
                            'distances': {
                                0: 10,
                            },
                            'cpus': [
                                {'id': 0, 'socket_id': 0, 'core_id': 0, 'siblings': '0,4'},
                                {'id': 1, 'socket_id': 0, 'core_id': 1, 'siblings': '1,5'},
                                {'id': 2, 'socket_id': 0, 'core_id': 2, 'siblings': '2,6'},
                                {'id': 3, 'socket_id': 0, 'core_id': 3, 'siblings': '3,7'},
                                {'id': 4, 'socket_id': 0, 'core_id': 0, 'siblings': '0,4'},
                                {'id': 5, 'socket_id': 0, 'core_id': 1, 'siblings': '1,5'},
                                {'id': 6, 'socket_id': 0, 'core_id': 2, 'siblings': '2,6'},
                                {'id': 7, 'socket_id': 0, 'core_id': 3, 'siblings': '3,7'}
                            ]
                        }
                    ]
                },
                'cache': {
                    'banks': [
                        {'id': 0, 'level': 3, 'type': 'both', 'size': '8 MiB', 'cpus': '0-7'}
                    ]
                },
                'security': [
                    {'model': 'apparmor', 'doi': '0', 'baselabels': []},
                    {'model': 'dac', 'doi': '0', 'baselabels': [
                        {'type': 'kvm', 'label': '+487:+486'},
                        {'type': 'qemu', 'label': '+487:+486'}
                    ]}
                ]
            },
            'guests': [
                {
                    'os_type': 'hvm',
                    'arch': {
                        'name': 'i686',
                        'wordsize': 32,
                        'emulator': '/usr/bin/qemu-system-i386',
                        'machines': {
                            'pc-i440fx-2.6': {'maxcpus': 255, 'alternate_names': ['pc']},
                            'pc-0.12': {'maxcpus': 255, 'alternate_names': []}
                        },
                        'domains': {
                            'qemu': {
                                'emulator': None,
                                'machines': {}
                            },
                            'kvm': {
                                'emulator': '/usr/bin/qemu-kvm',
                                'machines': {
                                    'pc-i440fx-2.6': {'maxcpus': 255, 'alternate_names': ['pc']},
                                    'pc-0.12': {'maxcpus': 255, 'alternate_names': []}
                                }
                            }
                        }
                    },
                    'features': {
                        'cpuselection': {'default': True, 'toggle': False},
                        'deviceboot': {'default': True, 'toggle': False},
                        'disksnapshot': {'default': True, 'toggle': False},
                        'acpi': {'default': True, 'toggle': True},
                        'apic': {'default': True, 'toggle': False},
                        'pae': {'default': True, 'toggle': False},
                        'nonpae': {'default': True, 'toggle': False}
                    }
                },
                {
                    'os_type': 'hvm',
                    'arch': {
                        'name': 'x86_64',
                        'wordsize': 64,
                        'emulator': '/usr/bin/qemu-system-x86_64',
                        'machines': {
                            'pc-i440fx-2.6': {'maxcpus': 255, 'alternate_names': ['pc']},
                            'pc-0.12': {'maxcpus': 255, 'alternate_names': []}
                        },
                        'domains': {
                            'qemu': {
                                'emulator': None,
                                'machines': {}
                            },
                            'kvm': {
                                'emulator': '/usr/bin/qemu-kvm',
                                'machines': {
                                    'pc-i440fx-2.6': {'maxcpus': 255, 'alternate_names': ['pc']},
                                    'pc-0.12': {'maxcpus': 255, 'alternate_names': []}
                                }
                            }
                        }
                    },
                    'features': {
                        'cpuselection': {'default': True, 'toggle': False},
                        'deviceboot': {'default': True, 'toggle': False},
                        'disksnapshot': {'default': True, 'toggle': False},
                        'acpi': {'default': True, 'toggle': True},
                        'apic': {'default': True, 'toggle': False}
                    }
                },
                {
                    'os_type': 'xen',
                    'arch': {
                        'name': 'x86_64',
                        'wordsize': 64,
                        'emulator': '/usr/bin/qemu-system-x86_64',
                        'machines': {
                            'xenpv': {'alternate_names': []}
                        },
                        'domains': {
                            'xen': {
                                'emulator': None,
                                'machines': {}
                            }
                        }
                    }
                }
            ]
        }

        self.assertEqual(expected, caps)

    def test_network(self):
        '''
        Test virt._get_net_xml()
        '''
        xml_data = virt._gen_net_xml('network', 'main', 'bridge', 'openvswitch')
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('name').text, 'network')
        self.assertEqual(root.find('bridge').attrib['name'], 'main')
        self.assertEqual(root.find('forward').attrib['mode'], 'bridge')
        self.assertEqual(root.find('virtualport').attrib['type'], 'openvswitch')

    def test_domain_capabilities(self):
        '''
        Test the virt.domain_capabilities parsing
        '''
        xml = '''
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
        '''

        self.mock_conn.getDomainCapabilities.return_value = xml  # pylint: disable=no-member
        caps = virt.domain_capabilities()

        expected = {
            'emulator': '/usr/bin/qemu-system-aarch64',
            'domain': 'kvm',
            'machine': 'virt-2.12',
            'arch': 'aarch64',
            'max_vcpus': 255,
            'iothreads': True,
            'os': {
                'loader': {
                    'type': ['rom', 'pflash'],
                    'readonly': ['yes', 'no'],
                    'values': [
                        '/usr/share/AAVMF/AAVMF_CODE.fd',
                        '/usr/share/AAVMF/AAVMF32_CODE.fd',
                        '/usr/share/OVMF/OVMF_CODE.fd'
                    ]
                }
            },
            'cpu': {
                'host-passthrough': True,
                'host-model': {
                    'model': {
                        'name': 'sample-cpu',
                        'fallback': 'forbid'
                    },
                    'vendor': 'ACME',
                    'features': {
                        'vme': 'require',
                        'ss': 'require'
                    }
                },
                'custom': {
                    'models': {
                        'pxa262': 'unknown',
                        'pxa270-a0': 'yes',
                        'arm1136': 'no'
                    }
                }
            },
            'devices': {
                'disk': {
                    'diskDevice': ['disk', 'cdrom', 'floppy', 'lun'],
                    'bus': ['fdc', 'scsi', 'virtio', 'usb', 'sata'],
                },
                'graphics': {
                    'type': ['sdl', 'vnc']
                },
                'video': {
                    'modelType': ['vga', 'virtio']
                },
                'hostdev': {
                    'mode': ['subsystem'],
                    'startupPolicy': ['default', 'mandatory', 'requisite', 'optional'],
                    'subsysType': ['usb', 'pci', 'scsi'],
                    'capsType': [],
                    'pciBackend': ['default', 'kvm', 'vfio']
                }
            },
            'features': {
                'gic': {
                    'version': ['3']
                },
                'vmcoreinfo': {}
            }
        }

        self.assertEqual(expected, caps)

    def test_network_tag(self):
        '''
        Test virt._get_net_xml() with VLAN tag
        '''
        xml_data = virt._gen_net_xml('network', 'main', 'bridge', 'openvswitch', 1001)
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('name').text, 'network')
        self.assertEqual(root.find('bridge').attrib['name'], 'main')
        self.assertEqual(root.find('forward').attrib['mode'], 'bridge')
        self.assertEqual(root.find('virtualport').attrib['type'], 'openvswitch')
        self.assertEqual(root.find('vlan/tag').attrib['id'], '1001')

    def test_list_networks(self):
        '''
        Test virt.list_networks()
        '''
        names = ['net1', 'default', 'net2']
        net_mocks = [MagicMock(), MagicMock(), MagicMock()]
        for i, value in enumerate(names):
            net_mocks[i].name.return_value = value

        self.mock_conn.listAllNetworks.return_value = net_mocks  # pylint: disable=no-member
        actual = virt.list_networks()
        self.assertEqual(names, actual)

    def test_network_info(self):
        '''
        Test virt.network_info()
        '''
        self.mock_libvirt.VIR_IP_ADDR_TYPE_IPV4 = 0
        self.mock_libvirt.VIR_IP_ADDR_TYPE_IPV6 = 1

        net_mock = MagicMock()

        # pylint: disable=no-member
        net_mock.name.return_value = 'foo'
        net_mock.UUIDString.return_value = 'some-uuid'
        net_mock.bridgeName.return_value = 'br0'
        net_mock.autostart.return_value = True
        net_mock.isActive.return_value = False
        net_mock.isPersistent.return_value = True
        net_mock.DHCPLeases.return_value = [
            {
                'iface': 'virbr0',
                'expirytime': 1527757552,
                'type': 0,
                'mac': '52:54:00:01:71:bd',
                'ipaddr': '192.168.122.45',
                'prefix': 24,
                'hostname': 'py3-test',
                'clientid': '01:52:54:00:01:71:bd',
                'iaid': None
            }
        ]
        self.mock_conn.listAllNetworks.return_value = [net_mock]
        # pylint: enable=no-member

        net = virt.network_info('foo')
        self.assertEqual({'foo': {
            'uuid': 'some-uuid',
            'bridge': 'br0',
            'autostart': True,
            'active': False,
            'persistent': True,
            'leases': [
                {
                    'iface': 'virbr0',
                    'expirytime': 1527757552,
                    'type': 'ipv4',
                    'mac': '52:54:00:01:71:bd',
                    'ipaddr': '192.168.122.45',
                    'prefix': 24,
                    'hostname': 'py3-test',
                    'clientid': '01:52:54:00:01:71:bd',
                    'iaid': None
                }
            ]}}, net)

    def test_network_info_all(self):
        '''
        Test virt.network_info()
        '''
        self.mock_libvirt.VIR_IP_ADDR_TYPE_IPV4 = 0
        self.mock_libvirt.VIR_IP_ADDR_TYPE_IPV6 = 1

        net_mocks = []
        # pylint: disable=no-member
        for i in range(2):
            net_mock = MagicMock()

            net_mock.name.return_value = 'net{0}'.format(i)
            net_mock.UUIDString.return_value = 'some-uuid'
            net_mock.bridgeName.return_value = 'br{0}'.format(i)
            net_mock.autostart.return_value = True
            net_mock.isActive.return_value = False
            net_mock.isPersistent.return_value = True
            net_mock.DHCPLeases.return_value = []
            net_mocks.append(net_mock)
        self.mock_conn.listAllNetworks.return_value = net_mocks
        # pylint: enable=no-member

        net = virt.network_info()
        self.assertEqual({
            'net0':
            {
                'uuid': 'some-uuid',
                'bridge': 'br0',
                'autostart': True,
                'active': False,
                'persistent': True,
                'leases': []
            }, 'net1':
            {
                'uuid': 'some-uuid',
                'bridge': 'br1',
                'autostart': True,
                'active': False,
                'persistent': True,
                'leases': []
            }
        }, net)

    def test_network_info_notfound(self):
        '''
        Test virt.network_info() when the network can't be found
        '''
        # pylint: disable=no-member
        self.mock_conn.listAllNetworks.return_value = []
        # pylint: enable=no-member
        net = virt.network_info('foo')
        self.assertEqual({}, net)

    def test_pool(self):
        '''
        Test virt._gen_pool_xml()
        '''
        xml_data = virt._gen_pool_xml('pool', 'logical', '/dev/base')
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('name').text, 'pool')
        self.assertEqual(root.attrib['type'], 'logical')
        self.assertEqual(root.find('target/path').text, '/dev/base')

    def test_pool_with_source(self):
        '''
        Test virt._gen_pool_xml() with a source device
        '''
        xml_data = virt._gen_pool_xml('pool', 'logical', '/dev/base', source_devices=[{'path': '/dev/sda'}])
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('name').text, 'pool')
        self.assertEqual(root.attrib['type'], 'logical')
        self.assertEqual(root.find('target/path').text, '/dev/base')
        self.assertEqual(root.find('source/device').attrib['path'], '/dev/sda')

    def test_pool_with_scsi(self):
        '''
        Test virt._gen_pool_xml() with a SCSI source
        '''
        xml_data = virt._gen_pool_xml('pool',
                                      'scsi',
                                      '/dev/disk/by-path',
                                      source_devices=[{'path': '/dev/sda'}],
                                      source_adapter={
                                          'type': 'scsi_host',
                                          'parent_address': {
                                              'unique_id': 5,
                                              'address': {
                                                  'domain': '0x0000',
                                                  'bus': '0x00',
                                                  'slot': '0x1f',
                                                  'function': '0x2'
                                              }
                                          }
                                      },
                                      source_name='srcname')
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('name').text, 'pool')
        self.assertEqual(root.attrib['type'], 'scsi')
        self.assertEqual(root.find('target/path').text, '/dev/disk/by-path')
        self.assertEqual(root.find('source/device'), None)
        self.assertEqual(root.find('source/name'), None)
        self.assertEqual(root.find('source/adapter').attrib['type'], 'scsi_host')
        self.assertEqual(root.find('source/adapter/parentaddr').attrib['unique_id'], '5')
        self.assertEqual(root.find('source/adapter/parentaddr/address').attrib['domain'], '0x0000')
        self.assertEqual(root.find('source/adapter/parentaddr/address').attrib['bus'], '0x00')
        self.assertEqual(root.find('source/adapter/parentaddr/address').attrib['slot'], '0x1f')
        self.assertEqual(root.find('source/adapter/parentaddr/address').attrib['function'], '0x2')

    def test_pool_with_rbd(self):
        '''
        Test virt._gen_pool_xml() with an RBD source
        '''
        xml_data = virt._gen_pool_xml('pool',
                                      'rbd',
                                      source_devices=[{'path': '/dev/sda'}],
                                      source_hosts=['1.2.3.4', 'my.ceph.monitor:69'],
                                      source_auth={
                                          'type': 'ceph',
                                          'username': 'admin',
                                          'secret': {
                                              'type': 'uuid',
                                              'value': 'someuuid'
                                          }
                                      },
                                      source_name='srcname',
                                      source_adapter={'type': 'scsi_host', 'name': 'host0'},
                                      source_dir='/some/dir',
                                      source_format='fmt')
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('name').text, 'pool')
        self.assertEqual(root.attrib['type'], 'rbd')
        self.assertEqual(root.find('target'), None)
        self.assertEqual(root.find('source/device'), None)
        self.assertEqual(root.find('source/name').text, 'srcname')
        self.assertEqual(root.find('source/adapter'), None)
        self.assertEqual(root.find('source/dir'), None)
        self.assertEqual(root.find('source/format'), None)
        self.assertEqual(root.findall('source/host')[0].attrib['name'], '1.2.3.4')
        self.assertTrue('port' not in root.findall('source/host')[0].attrib)
        self.assertEqual(root.findall('source/host')[1].attrib['name'], 'my.ceph.monitor')
        self.assertEqual(root.findall('source/host')[1].attrib['port'], '69')
        self.assertEqual(root.find('source/auth').attrib['type'], 'ceph')
        self.assertEqual(root.find('source/auth').attrib['username'], 'admin')
        self.assertEqual(root.find('source/auth/secret').attrib['type'], 'uuid')
        self.assertEqual(root.find('source/auth/secret').attrib['uuid'], 'someuuid')

    def test_pool_with_netfs(self):
        '''
        Test virt._gen_pool_xml() with a netfs source
        '''
        xml_data = virt._gen_pool_xml('pool',
                                      'netfs',
                                      target='/path/to/target',
                                      permissions={
                                        'mode': '0770',
                                        'owner': 1000,
                                        'group': 100,
                                        'label': 'seclabel'
                                      },
                                      source_devices=[{'path': '/dev/sda'}],
                                      source_hosts=['nfs.host'],
                                      source_name='srcname',
                                      source_adapter={'type': 'scsi_host', 'name': 'host0'},
                                      source_dir='/some/dir',
                                      source_format='nfs')
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('name').text, 'pool')
        self.assertEqual(root.attrib['type'], 'netfs')
        self.assertEqual(root.find('target/path').text, '/path/to/target')
        self.assertEqual(root.find('target/permissions/mode').text, '0770')
        self.assertEqual(root.find('target/permissions/owner').text, '1000')
        self.assertEqual(root.find('target/permissions/group').text, '100')
        self.assertEqual(root.find('target/permissions/label').text, 'seclabel')
        self.assertEqual(root.find('source/device'), None)
        self.assertEqual(root.find('source/name'), None)
        self.assertEqual(root.find('source/adapter'), None)
        self.assertEqual(root.find('source/dir').attrib['path'], '/some/dir')
        self.assertEqual(root.find('source/format').attrib['type'], 'nfs')
        self.assertEqual(root.find('source/host').attrib['name'], 'nfs.host')
        self.assertEqual(root.find('source/auth'), None)

    def test_list_pools(self):
        '''
        Test virt.list_pools()
        '''
        names = ['pool1', 'default', 'pool2']
        pool_mocks = [MagicMock(), MagicMock(), MagicMock()]
        for i, value in enumerate(names):
            pool_mocks[i].name.return_value = value

        self.mock_conn.listAllStoragePools.return_value = pool_mocks  # pylint: disable=no-member
        actual = virt.list_pools()
        self.assertEqual(names, actual)

    def test_pool_info(self):
        '''
        Test virt.pool_info()
        '''
        # pylint: disable=no-member
        pool_mock = MagicMock()
        pool_mock.name.return_value = 'foo'
        pool_mock.UUIDString.return_value = 'some-uuid'
        pool_mock.info.return_value = [0, 1234, 5678, 123]
        pool_mock.autostart.return_value = True
        pool_mock.isPersistent.return_value = True
        pool_mock.XMLDesc.return_value = '''<pool type='dir'>
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
</pool>'''
        self.mock_conn.listAllStoragePools.return_value = [pool_mock]
        # pylint: enable=no-member

        pool = virt.pool_info('foo')
        self.assertEqual({'foo': {
            'uuid': 'some-uuid',
            'state': 'inactive',
            'capacity': 1234,
            'allocation': 5678,
            'free': 123,
            'autostart': True,
            'persistent': True,
            'type': 'dir',
            'target_path': '/srv/vms'}}, pool)

    def test_pool_info_notarget(self):
        '''
        Test virt.pool_info()
        '''
        # pylint: disable=no-member
        pool_mock = MagicMock()
        pool_mock.name.return_value = 'ceph'
        pool_mock.UUIDString.return_value = 'some-uuid'
        pool_mock.info.return_value = [0, 0, 0, 0]
        pool_mock.autostart.return_value = True
        pool_mock.isPersistent.return_value = True
        pool_mock.XMLDesc.return_value = '''<pool type='rbd'>
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
</pool>'''
        self.mock_conn.listAllStoragePools.return_value = [pool_mock]
        # pylint: enable=no-member

        pool = virt.pool_info('ceph')
        self.assertEqual({'ceph': {
            'uuid': 'some-uuid',
            'state': 'inactive',
            'capacity': 0,
            'allocation': 0,
            'free': 0,
            'autostart': True,
            'persistent': True,
            'type': 'rbd',
            'target_path': None}}, pool)

    def test_pool_info_notfound(self):
        '''
        Test virt.pool_info() when the pool can't be found
        '''
        # pylint: disable=no-member
        self.mock_conn.listAllStoragePools.return_value = []
        # pylint: enable=no-member
        pool = virt.pool_info('foo')
        self.assertEqual({}, pool)

    def test_pool_info_all(self):
        '''
        Test virt.pool_info()
        '''
        # pylint: disable=no-member
        pool_mocks = []
        for i in range(2):
            pool_mock = MagicMock()
            pool_mock.name.return_value = 'pool{0}'.format(i)
            pool_mock.UUIDString.return_value = 'some-uuid-{0}'.format(i)
            pool_mock.info.return_value = [0, 1234, 5678, 123]
            pool_mock.autostart.return_value = True
            pool_mock.isPersistent.return_value = True
            pool_mock.XMLDesc.return_value = '''<pool type='dir'>
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
</pool>'''
            pool_mocks.append(pool_mock)
        self.mock_conn.listAllStoragePools.return_value = pool_mocks
        # pylint: enable=no-member

        pool = virt.pool_info()
        self.assertEqual({
            'pool0':
            {
                'uuid': 'some-uuid-0',
                'state': 'inactive',
                'capacity': 1234,
                'allocation': 5678,
                'free': 123,
                'autostart': True,
                'persistent': True,
                'type': 'dir',
                'target_path': '/srv/vms'
            }, 'pool1': {
                'uuid': 'some-uuid-1',
                'state': 'inactive',
                'capacity': 1234,
                'allocation': 5678,
                'free': 123,
                'autostart': True,
                'persistent': True,
                'type': 'dir',
                'target_path': '/srv/vms'
            }
        }, pool)

    def test_pool_list_volumes(self):
        '''
        Test virt.pool_list_volumes
        '''
        names = ['volume1', 'volume2']
        mock_pool = MagicMock()
        # pylint: disable=no-member
        mock_pool.listVolumes.return_value = names
        self.mock_conn.storagePoolLookupByName.return_value = mock_pool
        # pylint: enable=no-member
        self.assertEqual(names, virt.pool_list_volumes('default'))

    @patch('salt.modules.virt._is_kvm_hyper', return_value=True)
    @patch('salt.modules.virt._is_xen_hyper', return_value=False)
    def test_get_hypervisor(self, isxen_mock, iskvm_mock):
        '''
        test the virt.get_hypervisor() function
        '''
        self.assertEqual('kvm', virt.get_hypervisor())

        iskvm_mock.return_value = False
        self.assertIsNone(virt.get_hypervisor())

        isxen_mock.return_value = True
        self.assertEqual('xen', virt.get_hypervisor())
