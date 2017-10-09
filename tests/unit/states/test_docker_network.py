# -*- coding: utf-8 -*-
'''
Unit tests for the docker state
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    Mock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

# Import Salt Libs
import salt.modules.dockermod as docker_mod
import salt.states.docker_network as docker_state


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DockerNetworkTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test docker_network states
    '''
    def setup_loader_modules(self):
        return {
            docker_mod: {
                '__context__': {'docker.docker_version': ''}
            },
            docker_state: {
                '__opts__': {'test': False}
            }
        }

    def test_present(self):
        '''
        Test docker_network.present
        '''
        docker_create_network = Mock(return_value='created')
        docker_connect_container_to_network = Mock(return_value='connected')
        docker_inspect_container = Mock(return_value={'Id': 'abcd', 'Name': 'container_bar'})
        # Get docker.networks to return a network with a name which is a superset of the name of
        # the network which is to be created, despite this network existing we should still expect
        # that the new network will be created.
        # Regression test for #41982.
        docker_networks = Mock(return_value=[{
            'Name': 'network_foobar',
            'Containers': {'container': {}}
        }])
        __salt__ = {'docker.create_network': docker_create_network,
                    'docker.inspect_container': docker_inspect_container,
                    'docker.connect_container_to_network': docker_connect_container_to_network,
                    'docker.networks': docker_networks,
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            ret = docker_state.present(
                'network_foo',
                containers=['container'],
                gateway='192.168.0.1',
                ip_range='192.168.0.128/25',
                subnet='192.168.0.0/24'
                )
        docker_create_network.assert_called_with('network_foo',
                                                 driver=None,
                                                 driver_opts=None,
                                                 gateway='192.168.0.1',
                                                 ip_range='192.168.0.128/25',
                                                 subnet='192.168.0.0/24')
        docker_connect_container_to_network.assert_called_with('abcd',
                                                                 'network_foo')
        self.assertEqual(ret, {'name': 'network_foo',
                               'comment': '',
                               'changes': {'connected': ['container_bar'],
                                           'created': 'created'},
                               'result': True})

    def test_present_with_change(self):
        '''
        Test docker_network.present when the specified network has properties differing from the already present network
        '''
        network_details = {
            'Id': 'abcd',
            'Name': 'network_foo',
            'Driver': 'macvlan',
            'Containers': {
                'abcd': {}
            },
            'Options': {
                'parent': 'eth0'
            },
            'IPAM': {
                'Config': [
                    {
                        'Subnet': '192.168.0.0/24',
                        'Gateway': '192.168.0.1'
                    }
                ]
            }
        }
        docker_networks = Mock(return_value=[network_details])
        network_details['Containers'] = {'abcd': {'Id': 'abcd', 'Name': 'container_bar'}}
        docker_inspect_network = Mock(return_value=network_details)
        docker_inspect_container = Mock(return_value={'Id': 'abcd', 'Name': 'container_bar'})
        docker_disconnect_container_from_network = Mock(return_value='disconnected')
        docker_remove_network = Mock(return_value='removed')
        docker_create_network = Mock(return_value='created')
        docker_connect_container_to_network = Mock(return_value='connected')

        __salt__ = {'docker.networks': docker_networks,
                    'docker.inspect_network': docker_inspect_network,
                    'docker.inspect_container': docker_inspect_container,
                    'docker.disconnect_container_from_network': docker_disconnect_container_from_network,
                    'docker.remove_network': docker_remove_network,
                    'docker.create_network': docker_create_network,
                    'docker.connect_container_to_network': docker_connect_container_to_network,
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            ret = docker_state.present(
                'network_foo',
                driver='macvlan',
                gateway='192.168.1.1',
                subnet='192.168.1.0/24',
                driver_opts={'parent': 'eth1'},
                containers=['abcd']
            )

        docker_disconnect_container_from_network.assert_called_with('abcd', 'network_foo')
        docker_remove_network.assert_called_with('network_foo')
        docker_create_network.assert_called_with('network_foo',
                                                 driver='macvlan',
                                                 driver_opts={'parent': 'eth1'},
                                                 gateway='192.168.1.1',
                                                 ip_range=None,
                                                 subnet='192.168.1.0/24')
        docker_connect_container_to_network.assert_called_with('abcd', 'network_foo')

        self.assertEqual(ret, {'name': 'network_foo',
                               'comment': 'Network \'network_foo\' was replaced with updated config',
                               'changes': {
                                   'updated': {'network_foo': {
                                       'old': {
                                           'driver_opts': {'parent': 'eth0'},
                                           'gateway': '192.168.0.1',
                                           'subnet': '192.168.0.0/24'
                                       },
                                       'new': {
                                           'driver_opts': {'parent': 'eth1'},
                                           'gateway': '192.168.1.1',
                                           'subnet': '192.168.1.0/24'
                                       }
                                   }},
                                   'reconnected': ['container_bar']
                               },
                               'result': True})

    def test_absent(self):
        '''
        Test docker_network.absent
        '''
        docker_remove_network = Mock(return_value='removed')
        docker_disconnect_container_from_network = Mock(return_value='disconnected')
        docker_networks = Mock(return_value=[{
            'Name': 'network_foo',
            'Containers': {'container': {}}
        }])
        __salt__ = {
            'docker.remove_network': docker_remove_network,
            'docker.disconnect_container_from_network': docker_disconnect_container_from_network,
            'docker.networks': docker_networks,
        }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            ret = docker_state.absent('network_foo')
        docker_disconnect_container_from_network.assert_called_with('container',
                                                                      'network_foo')
        docker_remove_network.assert_called_with('network_foo')
        self.assertEqual(ret, {'name': 'network_foo',
                               'comment': '',
                               'changes': {'disconnected': 'disconnected',
                                           'removed': 'removed'},
                               'result': True})

    def test_absent_with_matching_network(self):
        '''
        Test docker_network.absent when the specified network does not exist,
        but another network with a name which is a superset of the specified
        name does exist.  In this case we expect there to be no attempt to remove
        any network.
        Regression test for #41982.
        '''
        docker_remove_network = Mock(return_value='removed')
        docker_disconnect_container_from_network = Mock(return_value='disconnected')
        docker_networks = Mock(return_value=[{
            'Name': 'network_foobar',
            'Containers': {'container': {}}
        }])
        __salt__ = {
            'docker.remove_network': docker_remove_network,
            'docker.disconnect_container_from_network': docker_disconnect_container_from_network,
            'docker.networks': docker_networks,
        }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            ret = docker_state.absent('network_foo')
        docker_disconnect_container_from_network.assert_not_called()
        docker_remove_network.assert_not_called()
        self.assertEqual(ret, {'name': 'network_foo',
                               'comment': 'Network \'network_foo\' already absent',
                               'changes': {},
                               'result': True})
