# -*- coding: utf-8 -*-
'''
Validate the virt module
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import pytest

# Import Salt Testing libs
from tests.support.case import ModuleCase


@pytest.mark.requires_salt_modules('virt.get_profiles')
class VirtTest(ModuleCase):
    '''
    Test virt routines
    '''

    def test_default_kvm_profile(self):
        '''
        Test virt.get_profiles with the KVM profile
        '''
        profiles = self.run_function('virt.get_profiles', ['kvm'])
        nicp = profiles['nic']['default']
        assert nicp[0].get('model', '') == 'virtio'
        assert nicp[0].get('source', '') == 'br0'
        diskp = profiles['disk']['default']
        assert diskp[0]['system'].get('model', '') == 'virtio'
        assert diskp[0]['system'].get('format', '') == 'qcow2'
        assert diskp[0]['system'].get('size', '') == '8192'

    def test_default_esxi_profile(self):
        '''
        Test virt.get_profiles with the ESX profile
        '''
        profiles = self.run_function('virt.get_profiles', ['esxi'])
        nicp = profiles['nic']['default']
        assert nicp[0].get('model', '') == 'e1000'
        assert nicp[0].get('source', '') == 'DEFAULT'
        diskp = profiles['disk']['default']
        assert diskp[0]['system'].get('model', '') == 'scsi'
        assert diskp[0]['system'].get('format', '') == 'vmdk'
        assert diskp[0]['system'].get('size', '') == '8192'
