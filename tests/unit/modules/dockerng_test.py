# -*- coding: utf-8 -*-
'''
Unit tests for the dockerng module
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

dockerng_mod.__context__ = {'docker.docker_version': ''}
dockerng_mod.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DockerngTestCase(TestCase):
    '''
    Validate dockerng module
    '''

    def test_ps_with_host_true(self):
        '''
        Check that dockerng.ps called with host is ``True``,
        include resutlt of ``network.interfaces`` command in returned result.
        '''
        network_interfaces = Mock(return_value={'mocked': None})
        with patch.dict(dockerng_mod.__salt__,
                        {'network.interfaces': network_interfaces}):
            with patch.dict(dockerng_mod.__context__,
                            {'docker.client': MagicMock()}):
                ret = dockerng_mod.ps_(host=True)
                self.assertEqual(ret,
                                 {'host': {'interfaces': {'mocked': None}}})

    @patch.object(dockerng_mod, '_get_exec_driver')
    def test_check_mine_cache_is_refreshed_on_container_change_event(self, _):
        '''
        Every command that might modify docker containers state.
        Should trig an update on ``mine.send``
        '''

        for command_name, args in (('create', ()),
                                   ('rm_', ()),
                                   ('kill', ()),
                                   ('pause', ()),
                                   ('signal_', ('KILL',)),
                                   ('start', ()),
                                   ('stop', ()),
                                   ('unpause', ()),
                                   ('_run', ('command',)),
                                   ('_script', ('command',)),
                                   ):
            mine_send = Mock()
            command = getattr(dockerng_mod, command_name)
            docker_client = MagicMock()
            docker_client.api_version = '1.12'
            with patch.dict(dockerng_mod.__salt__,
                            {'mine.send': mine_send,
                             'container_resource.run': MagicMock(),
                             'cp.cache_file': MagicMock(return_value=False)}):
                with patch.dict(dockerng_mod.__context__,
                                {'docker.client': docker_client}):
                    command('container', *args)
            mine_send.assert_called_with('dockerng.ps', verbose=True, all=True,
                                         host=True)

    @patch.object(dockerng_mod, 'images', MagicMock())
    @patch.object(dockerng_mod, 'inspect_image')
    @patch.object(dockerng_mod, 'version', Mock(return_value={'ApiVersion': '1.19'}))
    def test_create_with_arg_cmd(self, *args):
        '''
        When cmd argument is passed check it is renamed to command.
        '''
        __salt__ = {
            'config.get': Mock(),
            'mine.send': Mock(),
        }
        host_config = {}
        client = Mock()
        client.api_version = '1.19'
        client.create_host_config.return_value = host_config
        client.create_container.return_value = {}
        with patch.dict(dockerng_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.dict(dockerng_mod.__context__,
                            {'docker.client': client}):
                dockerng_mod.create('image', cmd='ls', name='ctn')
        client.create_container.assert_called_once_with(
            command='ls',
            host_config=host_config,
            image='image',
            name='ctn')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DockerngTestCase, needs_daemon=False)
