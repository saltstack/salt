# -*- coding: utf-8 -*-
'''
Unit tests for the docker state
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    Mock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

# Import Salt Libs
import salt.modules.docker as docker_mod
import salt.states.docker_network as docker_state

docker_mod.__context__ = {'docker.docker_version': ''}
docker_mod.__salt__ = {}
docker_state.__context__ = {}
docker_state.__opts__ = {'test': False}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DockerNetworkTestCase(TestCase):
    '''
    Test docker_network states
    '''
    def test_present(self):
        '''
        Test docker_network.present
        '''
        docker_create_network = Mock(return_value='created')
        docker_connect_container_to_network = Mock(return_value='connected')
        docker_inspect_container = Mock(return_value={'Id': 'abcd'})
        __salt__ = {'docker.create_network': docker_create_network,
                    'docker.inspect_container': docker_inspect_container,
                    'docker.connect_container_to_network': docker_connect_container_to_network,
                    'docker.networks': Mock(return_value=[]),
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
        __salt__ = {
            'docker.remove_network': docker_remove_network,
            'docker.disconnect_container_from_network': docker_disconnect_container_from_network,
            'docker.networks': Mock(return_value=[{'Containers': {'container': {}}}]),
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
