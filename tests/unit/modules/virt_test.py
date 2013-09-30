# -*- coding: utf-8 -*-

# Import python libs
import sys
from xml.etree import ElementTree as ElementTree

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
ensure_in_syspath('../../')

# Import salt libs
from salt.modules import virt
from salt.modules import config
from salt._compat import StringIO as _StringIO, ElementTree as _ElementTree

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
            self.assertIn('eth0', ret)
            eth0 = ret['eth0']
            self.assertEqual(eth0['bridge'], 'DEFAULT')
            self.assertEqual(eth0['model'], 'e1000')

    def test_default_nic_profile_hypervisor_kvm(self):
        mock = MagicMock(return_value={})
        with patch.dict(virt.__salt__, {'config.get': mock}):
            ret = virt._nic_profile('nonexistant', 'kvm')
            self.assertTrue(len(ret) == 1)
            self.assertIn('eth0', ret)
            eth0 = ret['eth0']
            self.assertEqual(eth0['bridge'], 'br0')
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
        tree = _ElementTree.parse(_StringIO(xml_data))
        self.assertTrue(tree.getroot().attrib['type'] == 'kvm')
        self.assertTrue(tree.find('vcpu').text == '1')
        self.assertTrue(tree.find('memory').text == '524288')
        self.assertTrue(tree.find('memory').attrib['unit'] == 'KiB')
        self.assertTrue(len(tree.findall('.//disk')) == 1)
        self.assertTrue(len(tree.findall('.//interface')) == 1)

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
        tree = _ElementTree.parse(_StringIO(xml_data))
        self.assertTrue(tree.getroot().attrib['type'] == 'vmware')
        self.assertTrue(tree.find('vcpu').text == '1')
        self.assertTrue(tree.find('memory').text == '524288')
        self.assertTrue(tree.find('memory').attrib['unit'] == 'KiB')
        self.assertTrue(len(tree.findall('.//disk')) == 1)
        self.assertTrue(len(tree.findall('.//interface')) == 1)

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
- second:
    size: 4096
    format: vmdk  # FIX remove line, currently test fails
    model: scsi   # FIX remove line, currently test fails
'''
        nicp_yaml = '''
eth1:
  bridge: ONENET
  model: e1000
eth2:
  bridge: TWONET
  model: e1000    # FIX remove line, currently test fails
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
            eth1_mac='00:00:00:00:00:00',  # FIX test for this
            )
        tree = _ElementTree.parse(_StringIO(xml_data))
        self.assertTrue(tree.getroot().attrib['type'] == 'vmware')
        self.assertTrue(tree.find('vcpu').text == '1')
        self.assertTrue(tree.find('memory').text == '524288')
        self.assertTrue(tree.find('memory').attrib['unit'] == 'KiB')
        self.assertTrue(len(tree.findall('.//disk')) == 2)
        self.assertTrue(len(tree.findall('.//interface')) == 2)

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
- second:
    size: 4096
    format: qcow2   # FIX remove line, currently test fails
    model: virtio   # FIX remove line, currently test fails
'''
        nicp_yaml = '''
eth1:
  bridge: br1
  model: virtio
eth2:
  bridge: b2
  model: virtio     # FIX remove line, currently test fails
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
            eth1_mac='00:00:00:00:00:00',  # FIX test for this
            )
        tree = _ElementTree.parse(_StringIO(xml_data))
        self.assertTrue(tree.getroot().attrib['type'] == 'kvm')
        self.assertTrue(tree.find('vcpu').text == '1')
        self.assertTrue(tree.find('memory').text == '524288')
        self.assertTrue(tree.find('memory').attrib['unit'] == 'KiB')
        self.assertTrue(len(tree.findall('.//disk')) == 2)
        self.assertTrue(len(tree.findall('.//interface')) == 2)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(VirtTestCase, needs_daemon=False)
