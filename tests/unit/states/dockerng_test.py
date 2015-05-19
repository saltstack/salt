# -*- coding: utf-8 -*-
'''
Unit tests for the dockerng state
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    Mock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import dockerng as dockerng_mod
from salt.states import dockerng as dockerng_state

dockerng_mod.__context__ = {'docker.docker_version': ''}
dockerng_mod.__salt__ = {}
dockerng_state.__context__ = {}
dockerng_state.__opts__ = {'test': False}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DockerngTestCase(TestCase):
    '''
    Validate dockerng state
    '''

    def test_running(self):
        '''
        Test dockerng.running function
        '''
        dockerng_create = Mock()
        dockerng_start = Mock()
        __salt__ = {'dockerng.list_containers': MagicMock(),
                    'dockerng.list_tags': MagicMock(),
                    'dockerng.pull': MagicMock(),
                    'dockerng.state': MagicMock(),
                    'dockerng.create': dockerng_create,
                    'dockerng.start': dockerng_start,
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            result = dockerng_state.running(
                'cont',
                image='image:latest',
                binds=['/host-0:/container-0:ro'])
        dockerng_create.assert_called_with(
            'image:latest',
            validate_input=False,
            name='cont',
            volumes=['/container-0'],
            client_timeout=60)
        dockerng_start.assert_called_with(
            'cont',
            binds={'/host-0': {'bind': '/container-0', 'ro': True}},
            validate_ip_addrs=False,
            validate_input=False)

    def test_compare_volumes_no_diff(self):
        '''
        test dockerng._compare function with binds volumes.

        Make sure that volumes that are not managed by user doens't interfere
        with comparison.

        Here the volume ``/container-0`` is not bind by the user.
        So it shouldn't appear in the diff.
        '''
        actual = {'Config':
                  {'Volumes':
                   {'/container-0': '/var/lib/docker/vfs/dir/abcdef',
                    '/container-1': '/host-1'}},
                  'HostConfig': {'Binds': ['/host-1:/container-1:rw']},
                  }
        create_kwargs = {'volumes': ['/container-1']}
        runtime_kwargs = {'binds':
                          {'/host-1':
                           {'bind': '/container-1',
                            'ro': False}
                           }
                          }
        ret = dockerng_state._compare(actual, create_kwargs, runtime_kwargs)
        self.assertEqual(ret, {})

    def test_compare_volumes_diff(self):
        '''
        test dockerng._compare function with binds volumes.

        Make sure that volumes that are not managed by user doens't interfere
        with comparison.

        Here the volume ``/container-1`` is bind by the user but not
        by the container. So it should appear in the diff.
        '''
        actual = {'Config':
                  {'Volumes':
                   {'/container-0': '/var/lib/docker/vfs/dir/abcdef',
                    '/container-1': '/var/lib/docker/vfs/dir/12345'}},
                  'HostConfig': {'Binds': []},
                  }
        create_kwargs = {'volumes': ['/container-1']}
        runtime_kwargs = {'binds':
                          {'/host-1':
                           {'bind': '/container-1',
                            'ro': False}
                           }
                          }
        ret = dockerng_state._compare(actual, create_kwargs, runtime_kwargs)
        self.assertEqual(ret, {'binds':
                               {'old': [],
                                'new': ['/host-1:/container-1:rw']},
                               })

    def test_compare_ports_no_diff(self):
        '''
        test dockerng._compare function with port binding.

        Make sure that ports that are not managed by user doens't interfere
        with comparison.

        Here the port ``9090`` is not bind by the user.
        So it shouldn't appear in the diff.
        '''
        actual = {'Config': {'ExposedPorts': {'9090/tcp': {},
                                              '9797/tcp': {}}},
                  'HostConfig': {'PortBindings':
                                 {'9797/tcp': [{'HostIp': '',
                                                'HostPort': '9797'}]}},
                  }
        create_kwargs = {'ports': [9797]}
        runtime_kwargs = {'port_bindings': {9797: [9797]}}
        ret = dockerng_state._compare(actual, create_kwargs, runtime_kwargs)
        self.assertEqual(ret, {})

    def test_compare_ports_diff(self):
        '''
        test dockerng._compare function with port binding.

        Here the port ``9797`` is bind by the user but not by the container,
        So it should appear in the diff.
        '''
        actual = {'Config': {'ExposedPorts': {'9090/tcp': {},
                                              '9797/tcp': {}}},
                  'HostConfig': {'PortBindings': {}},
                  }
        create_kwargs = {'ports': [9797]}
        runtime_kwargs = {'port_bindings': {9797: [9797]}}
        ret = dockerng_state._compare(actual, create_kwargs, runtime_kwargs)
        self.assertEqual(ret, {'port_bindings':
                               {'old': [], 'new': ['9797:9797']}})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DockerngTestCase, needs_daemon=False)
