# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Eric Radman <ericshane@eradman.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON,
)

# Import Salt libs
import salt.cloud

EXAMPLE_PROVIDERS = {
 'nyc_vcenter': {'vmware': {'driver': 'vmware',
                            'password': '123456',
                            'profiles': {'nyc-vm': {'cluster': 'nycvirt',
                                                    'datastore': 'datastore1',
                                                    'devices': {'disk': {'Hard disk 1': {'controller': 'SCSI controller 1',
                                                                                         'size': 20}},
                                                                 'network': {'Network Adapter 1': {'mac': '44:44:44:44:44:42',
                                                                                                   'name': 'vlan50',
                                                                                                   'switch_type': 'standard'}},
                                                                 'scsi': {'SCSI controller 1': {'type': 'paravirtual'}}},
                                                    'extra_config': {'mem.hotadd': 'yes'},
                                                    'folder': 'coreinfra',
                                                    'image': 'rhel6_64Guest',
                                                    'memory': '8GB',
                                                    'num_cpus': 2,
                                                    'power_on': True,
                                                    'profile': 'nyc-vm',
                                                    'provider': 'nyc_vcenter:vmware',
                                                    'resourcepool': 'Resources'}},
                            'url': 'vca1.saltstack.com',
                            'user': 'root'}}
}

EXAMPLE_PROFILES = {
 'nyc-vm': {'cluster': 'nycvirt',
            'datastore': 'datastore1',
            'devices': {'disk': {'Hard disk 1': {'controller': 'SCSI controller 1',
                                                 'size': 20}},
                        'network': {'Network Adapter 1': {'mac': '44:44:44:44:44:42',
                                                          'name': 'vlan50',
                                                          'switch_type': 'standard'}},
                        'scsi': {'SCSI controller 1': {'type': 'paravirtual'}}},
            'extra_config': {'mem.hotadd': 'yes'},
            'folder': 'coreinfra',
            'image': 'rhel6_64Guest',
            'memory': '8GB',
            'num_cpus': 2,
            'power_on': True,
            'profile': 'nyc-vm',
            'provider': 'nyc_vcenter:vmware',
            'resourcepool': 'Resources'}
}

EXAMPLE_MAP = {
 'nyc-vm': {'db1': {'cpus': 4,
                    'devices': {'disk': {'Hard disk 1': {'size': 40}},
                                'network': {'Network Adapter 1': {'mac': '22:4a:b2:92:b3:eb'}}},
                    'memory': '16GB',
                    'name': 'db1'}}
}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MapConfTest(TestCase):
    '''
    Validate evaluation of salt-cloud map configuration
    '''

    @patch('salt.config.check_driver_dependencies', MagicMock(return_value=True))
    @patch('salt.cloud.Map.read', MagicMock(return_value=EXAMPLE_MAP))
    def test_cloud_map_merge_conf(self):
        '''
        Ensure that nested values can be selectivly overridden in a map file
        '''
        self.maxDiff = None
        opts = {'extension_modules': '/var/cache/salt/master/extmods',
                'providers': EXAMPLE_PROVIDERS, 'profiles': EXAMPLE_PROFILES}
        cloud_map = salt.cloud.Map(opts)
        merged_profile = {
         'create': {'db1': {'cluster': 'nycvirt',
                            'cpus': 4,
                            'datastore': 'datastore1',
                            'devices': {'disk': {'Hard disk 1': {'controller': 'SCSI controller 1',
                                                                 'size': 40}},
                                        'network': {'Network Adapter 1': {'mac': '22:4a:b2:92:b3:eb',
                                                                          'name': 'vlan50',
                                                                          'switch_type': 'standard'}},
                                        'scsi': {'SCSI controller 1': {'type': 'paravirtual'}}},
                            'driver': 'vmware',
                            'extra_config': {'mem.hotadd': 'yes'},
                            'folder': 'coreinfra',
                            'image': 'rhel6_64Guest',
                            'memory': '16GB',
                            'name': 'db1',
                            'num_cpus': 2,
                            'password': '123456',
                            'power_on': True,
                            'profile': 'nyc-vm',
                            'provider': 'nyc_vcenter:vmware',
                            'resourcepool': 'Resources',
                            'url': 'vca1.saltstack.com',
                            'user': 'root'}}
        }
        self.assertEqual(cloud_map.map_data(), merged_profile)
