# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase
from salt.cloud.clouds import openstack
from salttesting.mock import MagicMock, patch
from tests.unit.cloud.clouds import _preferred_ip


class OpenstackTestCase(TestCase):
    '''
    Test case for openstack
    '''
    PRIVATE_IPS = ['0.0.0.0', '1.1.1.1', '2.2.2.2']

    @patch('salt.cloud.clouds.openstack.show_instance',
           MagicMock(return_value={'state': True,
                                   'public_ips': [],
                                   'private_ips': PRIVATE_IPS}))
    @patch('salt.cloud.clouds.openstack.rackconnect', MagicMock(return_value=False))
    @patch('salt.cloud.clouds.openstack.managedcloud', MagicMock(return_value=False))
    @patch('salt.cloud.clouds.openstack.preferred_ip', _preferred_ip(PRIVATE_IPS, ['0.0.0.0']))
    @patch('salt.cloud.clouds.openstack.ssh_interface', MagicMock(return_value=False))
    def test_query_node_data_filter_preferred_ip_addresses(self):
        '''
        Test if query node data is filtering out unpreferred IP addresses.
        '''
        openstack.NodeState = MagicMock()
        openstack.NodeState.RUNNING = True
        openstack.__opts__ = {}

        vm = {'name': None}
        data = MagicMock()
        data.public_ips = []

        with patch('salt.utils.cloud.is_public_ip', MagicMock(return_value=True)):
            assert openstack._query_node_data(vm, data, False, MagicMock()).public_ips == ['0.0.0.0']
