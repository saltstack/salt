# -*- coding: utf-8 -*-

# Import python libs
import sys
from xml.etree import ElementTree as ElementTree
from StringIO import StringIO

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
ensure_in_syspath('../../')

# Import salt libs
from salt.modules import virt

virt.__salt__ = {}


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

    @skipIf(sys.hexversion < 0x02070000, 'ElementTree version 1.3 required')
    @patch('salt.modules.virt._nic_profile')
    @patch('salt.modules.virt._disk_profile')
    def test_gen_xml_for_esxi(self, disk_profile, nic_profile):
        disk_profile.return_value = [{'first': {'size': '8192',
                                                'format': 'vmdk',
                                                'model': 'scsi'}},
                                     {'second': {'size': '4096',
                                                 'format': 'vmdk',
                                                 'model': 'scsi'}}]
        nic_profile.return_value = {'eth1': {'bridge': 'ONENET',
                                             'model': 'e1000'},
                                    'eth2': {'bridge': 'TWONET',
                                             'model': 'e1000'}}
        diskp = virt._disk_profile('noeffect', 'esxi')
        nicp = virt._nic_profile('noeffect', 'esxi')
        xml_data = virt._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'esxi',
            eth1_mac='00:00:00:00:00:00',
            )
        tree = ElementTree.parse(StringIO(xml_data))
        self.assertTrue(tree.getroot().attrib['type'] == 'vmware')
        self.assertTrue(tree.find('vcpu').text == '1')
        self.assertTrue(tree.find('memory').text == '524288')
        self.assertTrue(tree.find('memory').attrib['unit'] == 'KiB')
        self.assertTrue(len(tree.findall('.//disk')) == 2)
        self.assertTrue(len(tree.findall('.//interface')) == 2)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(VirtTestCase, needs_daemon=False)
