# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import sys
import re

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
ensure_in_syspath('../../')

# Import salt libs
from salt.modules import virt
from salt.modules import config
from salt._compat import ElementTree as ET
import salt.utils

# Import third party libs
import yaml
import salt.ext.six as six

config.__grains__ = {}
config.__opts__ = {}
config.__pillar__ = {}
virt.__salt__ = {
    'config.get': config.get,
    'config.option': config.option,
}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class VirtTestCase(TestCase):

    @skipIf(sys.version_info < (2, 7), 'ElementTree version 1.3 required'
            ' which comes with Python 2.7')
    def test_boot_default_dev(self):
        diskp = virt._disk_profile('default', 'kvm')
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

    @skipIf(sys.version_info < (2, 7), 'ElementTree version 1.3 required'
            ' which comes with Python 2.7')
    def test_boot_custom_dev(self):
        diskp = virt._disk_profile('default', 'kvm')
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

    @skipIf(sys.version_info < (2, 7), 'ElementTree version 1.3 required'
            ' which comes with Python 2.7')
    def test_boot_multiple_devs(self):
        diskp = virt._disk_profile('default', 'kvm')
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

    @skipIf(sys.version_info < (2, 7), 'ElementTree version 1.3 required'
            ' which comes with Python 2.7')
    def test_gen_xml_for_serial_console(self):
        diskp = virt._disk_profile('default', 'kvm')
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

    @skipIf(sys.version_info < (2, 7), 'ElementTree version 1.3 required'
            ' which comes with Python 2.7')
    def test_gen_xml_for_telnet_console(self):
        diskp = virt._disk_profile('default', 'kvm')
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

    @skipIf(sys.version_info < (2, 7), 'ElementTree version 1.3 required'
            ' which comes with Python 2.7')
    def test_gen_xml_for_telnet_console_unspecified_port(self):
        diskp = virt._disk_profile('default', 'kvm')
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

    @skipIf(sys.version_info < (2, 7), 'ElementTree version 1.3 required'
            ' which comes with Python 2.7')
    def test_gen_xml_for_serial_no_console(self):
        diskp = virt._disk_profile('default', 'kvm')
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

    @skipIf(sys.version_info < (2, 7), 'ElementTree version 1.3 required'
            ' which comes with Python 2.7')
    def test_gen_xml_for_telnet_no_console(self):
        diskp = virt._disk_profile('default', 'kvm')
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

    def test_default_disk_profile_hypervisor_esxi(self):
        mock = MagicMock(return_value={})
        with patch.dict(virt.__salt__, {'config.get': mock}):
            ret = virt._disk_profile('nonexistent', 'esxi')
            self.assertTrue(len(ret) == 1)
            self.assertIn('system', ret[0])
            system = ret[0]['system']
            self.assertEqual(system['format'], 'vmdk')
            self.assertEqual(system['model'], 'scsi')
            self.assertTrue(int(system['size']) >= 1)

    def test_default_disk_profile_hypervisor_kvm(self):
        mock = MagicMock(return_value={})
        with patch.dict(virt.__salt__, {'config.get': mock}):
            ret = virt._disk_profile('nonexistent', 'kvm')
            self.assertTrue(len(ret) == 1)
            self.assertIn('system', ret[0])
            system = ret[0]['system']
            self.assertEqual(system['format'], 'qcow2')
            self.assertEqual(system['model'], 'virtio')
            self.assertTrue(int(system['size']) >= 1)

    def test_default_nic_profile_hypervisor_esxi(self):
        mock = MagicMock(return_value={})
        with patch.dict(virt.__salt__, {'config.get': mock}):
            ret = virt._nic_profile('nonexistent', 'esxi')
            self.assertTrue(len(ret) == 1)
            eth0 = ret[0]
            self.assertEqual(eth0['name'], 'eth0')
            self.assertEqual(eth0['type'], 'bridge')
            self.assertEqual(eth0['source'], 'DEFAULT')
            self.assertEqual(eth0['model'], 'e1000')

    def test_default_nic_profile_hypervisor_kvm(self):
        mock = MagicMock(return_value={})
        with patch.dict(virt.__salt__, {'config.get': mock}):
            ret = virt._nic_profile('nonexistent', 'kvm')
            self.assertTrue(len(ret) == 1)
            eth0 = ret[0]
            self.assertEqual(eth0['name'], 'eth0')
            self.assertEqual(eth0['type'], 'bridge')
            self.assertEqual(eth0['source'], 'br0')
            self.assertEqual(eth0['model'], 'virtio')

    @skipIf(sys.version_info < (2, 7), 'ElementTree version 1.3 required'
            ' which comes with Python 2.7')
    def test_gen_vol_xml_for_kvm(self):
        xml_data = virt._gen_vol_xml('vmname', 'system', 8192, 'kvm')
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('name').text, 'vmname/system.qcow2')
        self.assertEqual(root.find('key').text, 'vmname/system')
        self.assertEqual(root.find('capacity').attrib['unit'], 'KiB')
        self.assertEqual(root.find('capacity').text, str(8192 * 1024))

    @skipIf(sys.version_info < (2, 7), 'ElementTree version 1.3 required'
            ' which comes with Python 2.7')
    def test_gen_vol_xml_for_esxi(self):
        xml_data = virt._gen_vol_xml('vmname', 'system', 8192, 'esxi')
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('name').text, 'vmname/system.vmdk')
        self.assertEqual(root.find('key').text, 'vmname/system')
        self.assertEqual(root.find('capacity').attrib['unit'], 'KiB')
        self.assertEqual(root.find('capacity').text, str(8192 * 1024))

    @skipIf(sys.version_info < (2, 7), 'ElementTree version 1.3 required'
            ' which comes with Python 2.7')
    def test_gen_xml_for_kvm_default_profile(self):
        diskp = virt._disk_profile('default', 'kvm')
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
        self.assertEqual(root.find('memory').text, str(512 * 1024))
        self.assertEqual(root.find('memory').attrib['unit'], 'KiB')

        disks = root.findall('.//disk')
        self.assertEqual(len(disks), 1)
        disk = disks[0]
        self.assertTrue(disk.find('source').attrib['file'].startswith('/'))
        self.assertTrue('hello/system' in disk.find('source').attrib['file'])
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

    @skipIf(sys.version_info < (2, 7), 'ElementTree version 1.3 required'
            ' which comes with Python 2.7')
    def test_gen_xml_for_esxi_default_profile(self):
        diskp = virt._disk_profile('default', 'esxi')
        nicp = virt._nic_profile('default', 'esxi')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'esxi',
            )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.attrib['type'], 'vmware')
        self.assertEqual(root.find('vcpu').text, '1')
        self.assertEqual(root.find('memory').text, str(512 * 1024))
        self.assertEqual(root.find('memory').attrib['unit'], 'KiB')

        disks = root.findall('.//disk')
        self.assertEqual(len(disks), 1)
        disk = disks[0]
        self.assertTrue('[0]' in disk.find('source').attrib['file'])
        self.assertTrue('hello/system' in disk.find('source').attrib['file'])
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

    @skipIf(sys.version_info < (2, 7), 'ElementTree version 1.3 required'
            ' which comes with Python 2.7')
    @patch('salt.modules.virt._nic_profile')
    @patch('salt.modules.virt._disk_profile')
    def test_gen_xml_for_esxi_custom_profile(self, disk_profile, nic_profile):
        diskp_yaml = '''
- first:
    size: 8192
    format: vmdk
    model: scsi
    pool: datastore1
- second:
    size: 4096
    format: vmdk  # FIX remove line, currently test fails
    model: scsi   # FIX remove line, currently test fails
    pool: datastore2
'''
        nicp_yaml = '''
- type: bridge
  name: eth1
  source: ONENET
  model: e1000
  mac: '00:00:00:00:00:00'
- name: eth2
  type: bridge
  source: TWONET
  model: e1000
  mac: '00:00:00:00:00:00'
'''
        disk_profile.return_value = yaml.load(diskp_yaml)
        nic_profile.return_value = yaml.load(nicp_yaml)
        diskp = virt._disk_profile('noeffect', 'esxi')
        nicp = virt._nic_profile('noeffect', 'esxi')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'esxi',
            )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.attrib['type'], 'vmware')
        self.assertEqual(root.find('vcpu').text, '1')
        self.assertEqual(root.find('memory').text, str(512 * 1024))
        self.assertEqual(root.find('memory').attrib['unit'], 'KiB')
        self.assertTrue(len(root.findall('.//disk')) == 2)
        self.assertTrue(len(root.findall('.//interface')) == 2)

    @skipIf(sys.version_info < (2, 7), 'ElementTree version 1.3 required'
            ' which comes with Python 2.7')
    @patch('salt.modules.virt._nic_profile')
    @patch('salt.modules.virt._disk_profile')
    def test_gen_xml_for_kvm_custom_profile(self, disk_profile, nic_profile):
        diskp_yaml = '''
- first:
    size: 8192
    format: qcow2
    model: virtio
    pool: /var/lib/images
- second:
    size: 4096
    format: qcow2   # FIX remove line, currently test fails
    model: virtio   # FIX remove line, currently test fails
    pool: /var/lib/images
'''
        nicp_yaml = '''
- type: bridge
  name: eth1
  source: b2
  model: virtio
  mac: '00:00:00:00:00:00'
- name: eth2
  type: bridge
  source: b2
  model: virtio
  mac: '00:00:00:00:00:00'
'''
        disk_profile.return_value = yaml.load(diskp_yaml)
        nic_profile.return_value = yaml.load(nicp_yaml)
        diskp = virt._disk_profile('noeffect', 'kvm')
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
        self.assertEqual(root.find('memory').text, str(512 * 1024))
        self.assertEqual(root.find('memory').attrib['unit'], 'KiB')
        self.assertTrue(len(root.findall('.//disk')) == 2)
        self.assertTrue(len(root.findall('.//interface')) == 2)

    @skipIf(sys.version_info < (2, 7), 'ElementTree version 1.3 required'
            ' which comes with Python 2.7')
    def test_controller_for_esxi(self):
        diskp = virt._disk_profile('default', 'esxi')
        nicp = virt._nic_profile('default', 'esxi')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'esxi'
            )
        root = ET.fromstring(xml_data)
        controllers = root.findall('.//devices/controller')
        self.assertTrue(len(controllers) == 1)
        controller = controllers[0]
        self.assertEqual(controller.attrib['model'], 'lsilogic')

    @skipIf(sys.version_info < (2, 7), 'ElementTree version 1.3 required'
            ' which comes with Python 2.7')
    def test_controller_for_kvm(self):
        diskp = virt._disk_profile('default', 'kvm')
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

    def test_mixed_dict_and_list_as_profile_objects(self):

        yaml_config = '''
          virt.nic:
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
        mock_config = yaml.load(yaml_config)
        salt.modules.config.__opts__ = mock_config

        for name in six.iterkeys(mock_config['virt.nic']):
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

    @skipIf(sys.version_info < (2, 7), 'ElementTree version 1.3 required'
            ' which comes with Python 2.7')
    def test_get_graphics(self):
        virt.get_xml = MagicMock(return_value='''<domain type='kvm' id='7'>
              <name>test-vm</name>
              <devices>
                <graphics type='vnc' port='5900' autoport='yes' listen='0.0.0.0'>
                  <listen type='address' address='0.0.0.0'/>
                </graphics>
              </devices>
            </domain>
        ''')
        graphics = virt.get_graphics('test-vm')
        self.assertEqual('vnc', graphics['type'])
        self.assertEqual('5900', graphics['port'])
        self.assertEqual('0.0.0.0', graphics['listen'])

    @skipIf(sys.version_info < (2, 7), 'ElementTree version 1.3 required'
            ' which comes with Python 2.7')
    def test_get_nics(self):
        virt.get_xml = MagicMock(return_value='''<domain type='kvm' id='7'>
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
        ''')
        nics = virt.get_nics('test-vm')
        nic = nics[list(nics)[0]]
        self.assertEqual('bridge', nic['type'])
        self.assertEqual('ac:de:48:b6:8b:59', nic['mac'])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(VirtTestCase, needs_daemon=False)
