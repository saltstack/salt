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

    def test_running_with_no_predifined_volume(self):
        '''
        Test dockerng.running function with an image
        that doens't have VOLUME defined.

        The ``binds`` argument, should create a container
        with respective volumes extracted from ``binds``.
        '''
        dockerng_create = Mock()
        dockerng_start = Mock()
        dockerng_history = MagicMock(return_value=[])
        __salt__ = {'dockerng.list_containers': MagicMock(),
                    'dockerng.list_tags': MagicMock(),
                    'dockerng.pull': MagicMock(),
                    'dockerng.state': MagicMock(),
                    'dockerng.create': dockerng_create,
                    'dockerng.start': dockerng_start,
                    'dockerng.history': dockerng_history,
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            dockerng_state.running(
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

    def test_running_with_predifined_volume(self):
        '''
        Test dockerng.running function with an image
        that already have VOLUME defined.

        The ``binds`` argument, shouldn't have side effects on
        container creation.
        '''
        dockerng_create = Mock()
        dockerng_start = Mock()
        dockerng_history = MagicMock(return_value=['VOLUME /container-0'])
        __salt__ = {'dockerng.list_containers': MagicMock(),
                    'dockerng.list_tags': MagicMock(),
                    'dockerng.pull': MagicMock(),
                    'dockerng.state': MagicMock(),
                    'dockerng.create': dockerng_create,
                    'dockerng.start': dockerng_start,
                    'dockerng.history': dockerng_history,
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            dockerng_state.running(
                'cont',
                image='image:latest',
                binds=['/host-0:/container-0:ro'])
        dockerng_create.assert_called_with(
            'image:latest',
            validate_input=False,
            name='cont',
            client_timeout=60)
        dockerng_start.assert_called_with(
            'cont',
            binds={'/host-0': {'bind': '/container-0', 'ro': True}},
            validate_ip_addrs=False,
            validate_input=False)

    def test_running_with_no_predifined_ports(self):
        '''
        Test dockerng.running function with an image
        that doens't have EXPOSE defined.

        The ``port_bindings`` argument, should create a container
        with respective ``ports`` extracted from ``port_bindings``.
        '''
        dockerng_create = Mock()
        dockerng_start = Mock()
        dockerng_history = MagicMock(return_value=[])
        __salt__ = {'dockerng.list_containers': MagicMock(),
                    'dockerng.list_tags': MagicMock(),
                    'dockerng.pull': MagicMock(),
                    'dockerng.state': MagicMock(),
                    'dockerng.create': dockerng_create,
                    'dockerng.start': dockerng_start,
                    'dockerng.history': dockerng_history,
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            dockerng_state.running(
                'cont',
                image='image:latest',
                port_bindings=['9090:9797/tcp'])
        dockerng_create.assert_called_with(
            'image:latest',
            validate_input=False,
            name='cont',
            ports=[9797],
            client_timeout=60)
        dockerng_start.assert_called_with(
            'cont',
            port_bindings={9797: [9090]},
            validate_ip_addrs=False,
            validate_input=False)

    def test_running_with_predifined_ports(self):
        '''
        Test dockerng.running function with an image
        that contains EXPOSE statements.

        The ``port_bindings`` argument, shouldn't have side effect on container
        creation.
        '''
        dockerng_create = Mock()
        dockerng_start = Mock()
        dockerng_history = MagicMock(return_value=['EXPOSE 9797/tcp'])
        __salt__ = {'dockerng.list_containers': MagicMock(),
                    'dockerng.list_tags': MagicMock(),
                    'dockerng.pull': MagicMock(),
                    'dockerng.state': MagicMock(),
                    'dockerng.create': dockerng_create,
                    'dockerng.start': dockerng_start,
                    'dockerng.history': dockerng_history,
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            dockerng_state.running(
                'cont',
                image='image:latest',
                port_bindings=['9090:9797/tcp'])
        dockerng_create.assert_called_with(
            'image:latest',
            validate_input=False,
            name='cont',
            client_timeout=60)
        dockerng_start.assert_called_with(
            'cont',
            port_bindings={9797: [9090]},
            validate_ip_addrs=False,
            validate_input=False)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DockerngTestCase, needs_daemon=False)
