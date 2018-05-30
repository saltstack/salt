# -*- coding: utf-8 -*-
'''
virt execution module unit tests
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import re
import os

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
        self.addCleanup(delattr, self, 'mock_libvirt')
        self.addCleanup(delattr, self, 'mock_conn')
        loader_globals = {
            '__salt__': {
                'config.get': config.get,
                'config.option': config.option,
            },
            'libvirt': self.mock_libvirt
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

    def test_boot_default_dev(self):
        '''
        Test virt_gen_xml() default boot device
        '''
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

    def test_boot_custom_dev(self):
        '''
        Test virt_gen_xml() custom boot device
        '''
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

    def test_boot_multiple_devs(self):
        '''
        Test virt_gen_xml() multiple boot devices
        '''
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

    def test_gen_xml_for_serial_console(self):
        '''
        Test virt_gen_xml() serial console
        '''
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

    def test_gen_xml_for_telnet_console(self):
        '''
        Test virt_gen_xml() telnet console
        '''
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

    def test_gen_xml_for_telnet_console_unspecified_port(self):
        '''
        Test virt_gen_xml() telnet console without any specified port
        '''
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

    def test_gen_xml_for_serial_no_console(self):
        '''
        Test virt_gen_xml() with no serial console
        '''
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

    def test_gen_xml_for_telnet_no_console(self):
        '''
        Test virt_gen_xml() with no telnet console
        '''
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
        '''
        Test virt._disk_profile() default ESXi profile
        '''
        mock = MagicMock(return_value={})
        with patch.dict(virt.__salt__, {'config.get': mock}):  # pylint: disable=no-member
            ret = virt._disk_profile('nonexistent', 'esxi')
            self.assertTrue(len(ret) == 1)
            self.assertIn('system', ret[0])
            system = ret[0]['system']
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
            self.assertIn('system', ret[0])
            system = ret[0]['system']
            self.assertEqual(system['format'], 'qcow2')
            self.assertEqual(system['model'], 'virtio')
            self.assertTrue(int(system['size']) >= 1)

    def test_default_nic_profile_hypervisor_esxi(self):
        '''
        Test virt._nic_profile() default ESXi profile
        '''
        mock = MagicMock(return_value={})
        with patch.dict(virt.__salt__, {'config.get': mock}):  # pylint: disable=no-member
            ret = virt._nic_profile('nonexistent', 'esxi')
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

    def test_gen_vol_xml_for_kvm(self):
        '''
        Test virt._get_vol_xml(), KVM case
        '''
        xml_data = virt._gen_vol_xml('vmname', 'system', 8192, 'kvm')
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('name').text, 'vmname/system.qcow2')
        self.assertEqual(root.find('key').text, 'vmname/system')
        self.assertEqual(root.find('capacity').attrib['unit'], 'KiB')
        self.assertEqual(root.find('capacity').text, six.text_type(8192 * 1024))

    def test_gen_vol_xml_for_esxi(self):
        '''
        Test virt._get_vol_xml(), ESXi case
        '''
        xml_data = virt._gen_vol_xml('vmname', 'system', 8192, 'esxi')
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('name').text, 'vmname/system.vmdk')
        self.assertEqual(root.find('key').text, 'vmname/system')
        self.assertEqual(root.find('capacity').attrib['unit'], 'KiB')
        self.assertEqual(root.find('capacity').text, six.text_type(8192 * 1024))

    def test_gen_xml_for_kvm_default_profile(self):
        '''
        Test virt._gen_xml(), KVM default profile case
        '''
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
        self.assertEqual(root.find('memory').text, six.text_type(512 * 1024))
        self.assertEqual(root.find('memory').attrib['unit'], 'KiB')

        disks = root.findall('.//disk')
        self.assertEqual(len(disks), 1)
        disk = disks[0]
        root_dir = salt.config.DEFAULT_MINION_OPTS.get('root_dir')
        self.assertTrue(disk.find('source').attrib['file'].startswith(root_dir))
        self.assertTrue(os.path.join('hello', 'system') in disk.find('source').attrib['file'])
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
        Test virt._gen_xml(), ESXi default profile case
        '''
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
        self.assertEqual(root.find('memory').text, six.text_type(512 * 1024))
        self.assertEqual(root.find('memory').attrib['unit'], 'KiB')

        disks = root.findall('.//disk')
        self.assertEqual(len(disks), 1)
        disk = disks[0]
        self.assertTrue('[0]' in disk.find('source').attrib['file'])
        self.assertTrue(os.path.join('hello', 'system') in disk.find('source').attrib['file'])
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
        Test virt._gen_xml(), ESXi custom profile case
        '''
        diskp_yaml = '''
- first:
    size: 8192
    format: vmdk
    model: scsi
    pool: datastore1
- second:
    size: 4096
    format: vmdk
    model: scsi
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
        with patch('salt.modules.virt._nic_profile') as nic_profile, \
                patch('salt.modules.virt._disk_profile') as disk_profile:
            disk_profile.return_value = salt.utils.yaml.safe_load(diskp_yaml)
            nic_profile.return_value = salt.utils.yaml.safe_load(nicp_yaml)
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
            self.assertEqual(root.find('memory').text, six.text_type(512 * 1024))
            self.assertEqual(root.find('memory').attrib['unit'], 'KiB')
            self.assertTrue(len(root.findall('.//disk')) == 2)
            self.assertTrue(len(root.findall('.//interface')) == 2)

    def test_gen_xml_for_kvm_custom_profile(self):
        '''
        Test virt._gen_xml(), KVM custom profile case
        '''
        diskp_yaml = '''
- first:
    size: 8192
    format: qcow2
    model: virtio
    pool: /var/lib/images
- second:
    size: 4096
    format: qcow2
    model: virtio
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
        with patch('salt.modules.virt._nic_profile') as nic_profile, \
                patch('salt.modules.virt._disk_profile') as disk_profile:
            disk_profile.return_value = salt.utils.yaml.safe_load(diskp_yaml)
            nic_profile.return_value = salt.utils.yaml.safe_load(nicp_yaml)
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
            self.assertEqual(root.find('memory').text, six.text_type(512 * 1024))
            self.assertEqual(root.find('memory').attrib['unit'], 'KiB')
            self.assertTrue(len(root.findall('.//disk')) == 2)
            self.assertTrue(len(root.findall('.//interface')) == 2)

    def test_controller_for_esxi(self):
        '''
        Test virt._gen_xml() generated device controller for ESXi
        '''
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

    def test_controller_for_kvm(self):
        '''
        Test virt._gen_xml() generated device controller for KVM
        '''
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

    @patch('subprocess.Popen')
    @patch('subprocess.Popen.communicate', return_value="")
    def test_get_disks(self, mock_communicate, mock_popen):
        '''
        Test virt.get_discs()
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

        disks = virt.get_disks('test-vm')
        disk = disks[list(disks)[0]]
        self.assertEqual('/disks/test.qcow2', disk['file'])
        self.assertEqual('disk', disk['type'])
        cdrom = disks[list(disks)[1]]
        self.assertEqual('/disks/test-cdrom.iso', cdrom['file'])
        self.assertEqual('cdrom', cdrom['type'])

    @patch('subprocess.Popen')
    @patch('subprocess.Popen.communicate', return_value="")
    @patch('salt.modules.virt.stop', return_value=True)
    @patch('salt.modules.virt.undefine')
    @patch('os.remove')
    def test_purge_default(self, mock_remove, mock_undefine, mock_stop, mock_communicate, mock_popen):
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

        res = virt.purge('test-vm')
        self.assertTrue(res)
        mock_remove.assert_any_call('/disks/test.qcow2')
        mock_remove.assert_any_call('/disks/test-cdrom.iso')

    @patch('subprocess.Popen')
    @patch('subprocess.Popen.communicate', return_value="")
    @patch('salt.modules.virt.stop', return_value=True)
    @patch('salt.modules.virt.undefine')
    @patch('os.remove')
    def test_purge_noremovable(self, mock_remove, mock_undefine, mock_stop, mock_communicate, mock_popen):
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

        res = virt.purge('test-vm', removables=False)
        self.assertTrue(res)
        mock_remove.assert_called_once()
        mock_remove.assert_any_call('/disks/test.qcow2')

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
        self.mock_conn.networkLookupByName.side_effect = \
            self.mock_libvirt.libvirtError("Network not found")  # pylint: disable=no-member
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
        self.mock_conn.storagePoolLookupByName.side_effect = \
            self.mock_libvirt.libvirtError("Pool not found")  # pylint: disable=no-member
        pool = virt.pool_info('foo')
        self.assertEqual({}, pool)
