# -*- coding: utf-8 -*-

# Import python libs
import sys
from xml.etree import ElementTree as ElementTree
import re

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
ensure_in_syspath('../../')

# Import salt libs
from salt.modules import virt
from salt.modules import config
from salt._compat import ElementTree as _ElementTree
import salt.utils

# Import third party libs
import yaml

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
    def test_gen_xml_for_serial(self):
        diskp = virt._disk_profile('default', 'kvm')
        nicp = virt._nic_profile('default', 'kvm')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'kvm',
            serial_type="pty",
            console=True
            )
        root = ElementTree.fromstring(xml_data)
        self.assertEquals(root.find('devices/serial').attrib['type'], 'pty')
        self.assertEquals(root.find('devices/console').attrib['type'], 'pty')

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
            serial_type="pty",
            console=False
            )
        root = ElementTree.fromstring(xml_data)
        self.assertEquals(root.find('devices/serial').attrib['type'], 'pty')
        self.assertEquals(root.find('devices/console'), None)

    def test_default_disk_profile_hypervisor_esxi(self):
        mock = MagicMock(return_value={})
        with patch.dict(virt.__salt__, {'config.get': mock}):
            ret = virt._disk_profile('nonexistant', 'esxi')
            self.assertTrue(len(ret) == 1)
            self.assertIn('system', ret[0])
            system = ret[0]['system']
            self.assertEqual(system['format'], 'vmdk')
            self.assertEqual(system['model'], 'scsi')
            self.assertTrue(system['size'] >= 1)

    def test_default_disk_profile_hypervisor_kvm(self):
        mock = MagicMock(return_value={})
        with patch.dict(virt.__salt__, {'config.get': mock}):
            ret = virt._disk_profile('nonexistant', 'kvm')
            self.assertTrue(len(ret) == 1)
            self.assertIn('system', ret[0])
            system = ret[0]['system']
            self.assertEqual(system['format'], 'qcow2')
            self.assertEqual(system['model'], 'virtio')
            self.assertTrue(system['size'] >= 1)

    def test_default_nic_profile_hypervisor_esxi(self):
        mock = MagicMock(return_value={})
        with patch.dict(virt.__salt__, {'config.get': mock}):
            ret = virt._nic_profile('nonexistant', 'esxi')
            self.assertTrue(len(ret) == 1)
            eth0 = ret[0]
            self.assertEqual(eth0['name'], 'eth0')
            self.assertEqual(eth0['type'], 'bridge')
            self.assertEqual(eth0['source'], 'DEFAULT')
            self.assertEqual(eth0['model'], 'e1000')

    def test_default_nic_profile_hypervisor_kvm(self):
        mock = MagicMock(return_value={})
        with patch.dict(virt.__salt__, {'config.get': mock}):
            ret = virt._nic_profile('nonexistant', 'kvm')
            self.assertTrue(len(ret) == 1)
            eth0 = ret[0]
            self.assertEqual(eth0['name'], 'eth0')
            self.assertEqual(eth0['type'], 'bridge')
            self.assertEqual(eth0['source'], 'br0')
            self.assertEqual(eth0['model'], 'virtio')

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
        root = ElementTree.fromstring(xml_data)
        self.assertTrue(root.attrib['type'] == 'kvm')
        self.assertTrue(root.find('vcpu').text == '1')
        self.assertTrue(root.find('memory').text == '524288')
        self.assertTrue(root.find('memory').attrib['unit'] == 'KiB')
        self.assertTrue(len(root.findall('.//disk')) == 1)

        interfaces = root.findall('.//interface')
        self.assertEquals(len(interfaces), 1)

        iface = interfaces[0]
        self.assertEquals(iface.attrib['type'], 'bridge')
        self.assertEquals(iface.find('source').attrib['bridge'], 'br0')
        self.assertEquals(iface.find('model').attrib['type'], 'virtio')

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
        root = _ElementTree.fromstring(xml_data)
        self.assertTrue(root.attrib['type'] == 'vmware')
        self.assertTrue(root.find('vcpu').text == '1')
        self.assertTrue(root.find('memory').text == '524288')
        self.assertTrue(root.find('memory').attrib['unit'] == 'KiB')
        self.assertTrue(len(root.findall('.//disk')) == 1)

        interfaces = root.findall('.//interface')
        self.assertEquals(len(interfaces), 1)

        iface = interfaces[0]
        self.assertEquals(iface.attrib['type'], 'bridge')
        self.assertEquals(iface.find('source').attrib['bridge'], 'DEFAULT')
        self.assertEquals(iface.find('model').attrib['type'], 'e1000')

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
        root = _ElementTree.fromstring(xml_data)
        self.assertTrue(root.attrib['type'] == 'vmware')
        self.assertTrue(root.find('vcpu').text == '1')
        self.assertTrue(root.find('memory').text == '524288')
        self.assertTrue(root.find('memory').attrib['unit'] == 'KiB')
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
        root = _ElementTree.fromstring(xml_data)
        self.assertTrue(root.attrib['type'] == 'kvm')
        self.assertTrue(root.find('vcpu').text == '1')
        self.assertTrue(root.find('memory').text == '524288')
        self.assertTrue(root.find('memory').attrib['unit'] == 'KiB')
        self.assertTrue(len(root.findall('.//disk')) == 2)
        self.assertTrue(len(root.findall('.//interface')) == 2)


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

        for name in mock_config['virt.nic'].keys():
            profile = salt.modules.virt._nic_profile(name, 'kvm')
            self.assertEquals(len(profile), 2)

            interface_attrs = profile[0]
            self.assertIn('source', interface_attrs)
            self.assertIn('type', interface_attrs)
            self.assertIn('name', interface_attrs)
            self.assertIn('model', interface_attrs)
            self.assertEquals(interface_attrs['model'], 'virtio')
            self.assertIn('mac', interface_attrs)
            self.assertTrue(
                re.match('^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$',
                interface_attrs['mac'] , re.I))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(VirtTestCase, needs_daemon=False)
