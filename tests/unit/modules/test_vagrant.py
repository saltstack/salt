# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import re

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import salt libs
import salt.modules.vagrant as vagrant
import salt.modules.config as config
from salt._compat import ElementTree as ET
import salt.utils

# Import third party libs
import yaml
from salt.ext import six


@skipIf(NO_MOCK, NO_MOCK_REASON)
class VagrantTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Unit TestCase for the salt.modules.vagrant module.
    '''
    # def setup_loader_modules(self):
    #     return {vsphere: {'__virtual__': MagicMock(return_value='vsphere')}}

    def setup_loader_modules(self):
        loader_globals = {
            '__salt__': {
                'config.get': config.get,
                'config.option': config.option,
            }
        }
        return {vagrant: loader_globals, config: loader_globals}

    def test_boot_default_dev(self):
        diskp = vagrant._disk_profile('default', 'kvm')
        nicp = vagrant._nic_profile('default', 'kvm')
        xml_data = vagrant._gen_xml(
            'hello',
            1,
            512,
            diskp,
            nicp,
            'kvm'
            )
        root = ET.fromstring(xml_data)
        self.assertEqual(root.find('os/boot').attrib['dev'], 'hd')


    def test_gen_xml_for_telnet_console(self):
        diskp = vagrant._disk_profile('default', 'kvm')
        nicp = vagrant._nic_profile('default', 'kvm')
        xml_data = vagrant._gen_xml(
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


    def test_controller_for_kvm(self):
        diskp = vagrant._disk_profile('default', 'kvm')
        nicp = vagrant._nic_profile('default', 'kvm')
        xml_data = vagrant._gen_xml(
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
