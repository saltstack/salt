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
        docker_inspect_container = Mock(return_value={'Id': 'abcd'})
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
                )
        docker_create_network.assert_called_with('network_foo', driver=None)
        docker_connect_container_to_network.assert_called_with('abcd',
                                                                 'network_foo')
        self.assertEqual(ret, {'name': 'network_foo',
                               'comment': '',
                               'changes': {'connected': 'connected',
                                           'created': 'created'},
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
