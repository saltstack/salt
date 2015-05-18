from salttesting import TestCase
from salttesting.mock import MagicMock, Mock, patch

import salt.states.dockerng


class DockerngTestCase(TestCase):

    @patch.dict(salt.modules.dockerng.__dict__, {'__context__': {}})
    @patch.dict(salt.modules.dockerng.__dict__, {'__salt__': MagicMock()})
    @patch.dict(salt.states.dockerng.__dict__, {'__context__': {}})
    @patch.dict(salt.states.dockerng.__dict__, {'__context__': {}})
    @patch.dict(salt.states.dockerng.__dict__, {'__opts__': {'test': False}})
    def test_running(self):
        dockerng_create = Mock()
        dockerng_start = Mock()
        __salt__ = {'dockerng.list_containers': MagicMock(),
                    'dockerng.list_tags': MagicMock(),
                    'dockerng.pull': MagicMock(),
                    'dockerng.state': MagicMock(),
                    'dockerng.create': dockerng_create,
                    'dockerng.start': dockerng_start,
                    }
        with patch.dict(salt.states.dockerng.__dict__,
                        {'__salt__': __salt__}):
            result = salt.states.dockerng.running(
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
