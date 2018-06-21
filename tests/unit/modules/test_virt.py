# -*- coding: utf-8 -*-
'''
virt execution module unit tests
'''

# pylint: disable=3rd-party-module-not-gated

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
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

# Import third party libs
from salt.ext import six


# pylint: disable=invalid-name,protected-access,attribute-defined-outside-init,too-many-public-methods,unused-argument


class LibvirtMock(MagicMock):  # pylint: disable=too-many-ancestors
    '''
    Libvirt library mock
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
        mock_domain = MagicMock()
        self.mock_conn.lookupByName.return_value = mock_domain  # pylint: disable=no-member
        mock_domain.XMLDesc.return_value = xml  # pylint: disable=no-member

        # Return state as shutdown
        mock_domain.info.return_value = [4, 0, 0, 0]  # pylint: disable=no-member

    def test_disk_profile_merge(self):
        '''
        Test virt._disk_profile() when merging with user-defined disks
        '''
        userdisks = [{'name': 'data', 'size': 16384, 'format': 'raw'}]

        disks = virt._disk_profile('default', 'kvm', userdisks, 'myvm', image='/path/to/image')
        self.assertEqual(
            [{'name': 'system',
              'size': 8192,
              'format': 'qcow2',
              'model': 'virtio',
              'pool': '/srv/salt-images',
              'filename': 'myvm_system.qcow2',
              'image': '/path/to/image',
              'source_file': '/srv/salt-images/myvm_system.qcow2'},
             {'name': 'data',
              'size': 16384,
              'format': 'raw',
              'model': 'virtio',
              'pool': '/srv/salt-images',
              'filename': 'myvm_data.raw',
              'source_file': '/srv/salt-images/myvm_data.raw'}],
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
            'kvm'
            )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('os/boot').attrib['dev'], 'hd')

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
            boot_dev='cdrom network'
            )
        root = ET.fromstring(xml_data)
        devs = root.findall('.//boot')
        self.assertTrue(len(devs) == 2)

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
            'kvm'
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
                "/srv/salt-images", disks, nics])}):
            diskp = virt._disk_profile('noeffect', 'kvm', [], 'hello')
            nicp = virt._nic_profile('noeffect', 'kvm')
            xml_data = virt._gen_xml(
                'hello',
                1,
                512,
                diskp,
                nicp,
                'kvm',
                )
            root = ET.fromstring(xml_data)
            self.assertEqual(root.attrib['type'], 'kvm')
            self.assertEqual(root.find('vcpu').text, '1')
            self.assertEqual(root.find('memory').text, six.text_type(512 * 1024))
            self.assertEqual(root.find('memory').attrib['unit'], 'KiB')
            self.assertTrue(len(root.findall('.//disk')) == 2)
            self.assertTrue(len(root.findall('.//interface')) == 2)

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
            'vmware'
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
            'kvm'
            )
        root = ET.fromstring(xml_data)
        controllers = root.findall('.//devices/controller')
        # There should be no controller
        self.assertTrue(len(controllers) == 0)
        # kvm mac address shoud start with 52:54:00
        self.assertTrue("mac address='52:54:00" in xml_data)

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
        self.mock_conn.networkLookupByName.return_value = net_mock
        # pylint: enable=no-member

        net = virt.network_info('foo')
        self.assertEqual({
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
            ]}, net)

    def test_network_info_notfound(self):
        '''
        Test virt.network_info() when the network can't be found
        '''
        # pylint: disable=no-member
        self.mock_conn.networkLookupByName.side_effect = \
            self.mock_libvirt.libvirtError("Network not found")
        # pylint: enable=no-member
        net = virt.network_info('foo')
        self.assertEqual({}, net)

    def test_pool(self):
        '''
        Test virt._gen_pool_xml()
        '''
        xml_data = virt._gen_pool_xml('pool', 'logical', 'base')
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('name').text, 'pool')
        self.assertEqual(root.attrib['type'], 'logical')
        self.assertEqual(root.find('target/path').text, '/dev/base')

    def test_pool_with_source(self):
        '''
        Test virt._gen_pool_xml() with a source device
        '''
        xml_data = virt._gen_pool_xml('pool', 'logical', 'base', 'sda')
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('name').text, 'pool')
        self.assertEqual(root.attrib['type'], 'logical')
        self.assertEqual(root.find('target/path').text, '/dev/base')
        self.assertEqual(root.find('source/device').attrib['path'], '/dev/sda')

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
        pool_mock.UUIDString.return_value = 'some-uuid'
        pool_mock.info.return_value = [0, 1234, 5678, 123]
        pool_mock.autostart.return_value = True
        pool_mock.isPersistent.return_value = True
        self.mock_conn.storagePoolLookupByName.return_value = pool_mock
        # pylint: enable=no-member

        pool = virt.pool_info('foo')
        self.assertEqual({
            'uuid': 'some-uuid',
            'state': 'inactive',
            'capacity': 1234,
            'allocation': 5678,
            'free': 123,
            'autostart': True,
            'persistent': True}, pool)

    def test_pool_info_notfound(self):
        '''
        Test virt.pool_info() when the pool can't be found
        '''
        # pylint: disable=no-member
        self.mock_conn.storagePoolLookupByName.side_effect = \
            self.mock_libvirt.libvirtError("Pool not found")
        # pylint: enable=no-member
        pool = virt.pool_info('foo')
        self.assertEqual({}, pool)

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
