# -*- coding: utf-8 -*-
'''
    :codeauthor: Bo Maryniuk <bo@suse.de>
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.unit import TestCase
from tests.support.mock import MagicMock, patch
from tests.unit.cloud.clouds import _preferred_ip

# Import Salt libs
from salt.cloud.clouds import nova


class NovaTestCase(TestCase):
    '''
    Test case for openstack
    '''
    PRIVATE_IPS = ['0.0.0.0', '1.1.1.1', '2.2.2.2']

    @patch('salt.cloud.clouds.nova.show_instance',
           MagicMock(return_value={'state': 'ACTIVE',
                                   'public_ips': [],
                                   'addresses': [],
                                   'private_ips': PRIVATE_IPS}))
    @patch('salt.cloud.clouds.nova.rackconnect', MagicMock(return_value=False))
    @patch('salt.cloud.clouds.nova.rackconnectv3', MagicMock(return_value={'mynet': ['1.1.1.1']}))
    @patch('salt.cloud.clouds.nova.cloudnetwork', MagicMock(return_value=False))
    @patch('salt.cloud.clouds.nova.managedcloud', MagicMock(return_value=False))
    @patch('salt.cloud.clouds.nova.preferred_ip', _preferred_ip(PRIVATE_IPS, ['0.0.0.0']))
    @patch('salt.cloud.clouds.nova.ssh_interface', MagicMock(return_value='public_ips'))
    def test_query_node_data_filter_preferred_ip_addresses(self):
        '''
        Test if query node data is filtering out unpreferred IP addresses.
        '''
        vm = {'name': None}
        data = MagicMock()
        data.public_ips = []

        assert nova._query_node_data(vm, data, MagicMock()).public_ips == ['0.0.0.0']
