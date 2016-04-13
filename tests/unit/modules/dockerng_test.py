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
from salt.exceptions import CommandExecutionError, SaltInvocationError

dockerng_mod.__context__ = {'docker.docker_version': ''}
dockerng_mod.__salt__ = {}


def _docker_py_version():
    return dockerng_mod.docker.version_info if dockerng_mod.HAS_DOCKER_PY else None


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

    def test_ps_with_filters(self):
        '''
        Check that dockerng.ps accept filters parameter.
        '''
        client = MagicMock()
        with patch.dict(dockerng_mod.__context__,
                        {'docker.client': client}):
            dockerng_mod.ps_(filters={'label': 'KEY'})
            client.containers.assert_called_once_with(
                all=True,
                filters={'label': 'KEY'})

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

    @skipIf(_docker_py_version() < (1, 4, 0),
            'docker module must be installed to run this test or is too old. >=1.4.0')
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

    @skipIf(_docker_py_version() < (1, 4, 0),
            'docker module must be installed to run this test or is too old. >=1.4.0')
    @patch.object(dockerng_mod, 'images', MagicMock())
    @patch.object(dockerng_mod, 'inspect_image')
    @patch.object(dockerng_mod, 'version', Mock(return_value={'ApiVersion': '1.19'}))
    def test_create_send_host_config(self, *args):
        '''
        Check host_config object is passed to create_container.
        '''
        __salt__ = {
            'config.get': Mock(),
            'mine.send': Mock(),
        }
        host_config = {'PublishAllPorts': True}
        client = Mock()
        client.api_version = '1.19'
        client.create_host_config.return_value = host_config
        client.create_container.return_value = {}
        with patch.dict(dockerng_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.dict(dockerng_mod.__context__,
                            {'docker.client': client}):
                dockerng_mod.create('image', name='ctn', publish_all_ports=True)
        client.create_container.assert_called_once_with(
            host_config=host_config,
            image='image',
            name='ctn')

    @skipIf(_docker_py_version() < (1, 4, 0),
            'docker module must be installed to run this test or is too old. >=1.4.0')
    @patch.object(dockerng_mod, 'images', MagicMock())
    @patch.object(dockerng_mod, 'inspect_image')
    @patch.object(dockerng_mod, 'version', Mock(return_value={'ApiVersion': '1.19'}))
    def test_create_with_labels_dict(self, *args):
        '''
        Create container with labels dictionary.
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
                dockerng_mod.create(
                    'image',
                    name='ctn',
                    labels={'KEY': 'VALUE'},
                    validate_input=True,
                )
        client.create_container.assert_called_once_with(
            labels={'KEY': 'VALUE'},
            host_config=host_config,
            image='image',
            name='ctn',
        )

    @skipIf(_docker_py_version() < (1, 4, 0),
            'docker module must be installed to run this test or is too old. >=1.4.0')
    @patch.object(dockerng_mod, 'images', MagicMock())
    @patch.object(dockerng_mod, 'inspect_image')
    @patch.object(dockerng_mod, 'version', Mock(return_value={'ApiVersion': '1.19'}))
    def test_create_with_labels_list(self, *args):
        '''
        Create container with labels list.
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
                dockerng_mod.create(
                    'image',
                    name='ctn',
                    labels=['KEY1', 'KEY2'],
                    validate_input=True,
                )
        client.create_container.assert_called_once_with(
            labels=['KEY1', 'KEY2'],
            host_config=host_config,
            image='image',
            name='ctn',
        )

    @skipIf(_docker_py_version() < (1, 4, 0),
            'docker module must be installed to run this test or is too old. >=1.4.0')
    @patch.object(dockerng_mod, 'images', MagicMock())
    @patch.object(dockerng_mod, 'inspect_image')
    @patch.object(dockerng_mod, 'version', Mock(return_value={'ApiVersion': '1.19'}))
    def test_create_with_labels_error(self, *args):
        '''
        Create container with invalid labels.
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
                self.assertRaises(SaltInvocationError,
                                  dockerng_mod.create,
                                  'image',
                                  name='ctn',
                                  labels=22,
                                  validate_input=True,
                                  )

    @skipIf(_docker_py_version() < (1, 4, 0),
            'docker module must be installed to run this test or is too old. >=1.4.0')
    @patch.object(dockerng_mod, 'images', MagicMock())
    @patch.object(dockerng_mod, 'inspect_image')
    @patch.object(dockerng_mod, 'version', Mock(return_value={'ApiVersion': '1.19'}))
    def test_create_with_labels_dictlist(self, *args):
        '''
        Create container with labels dictlist.
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
                dockerng_mod.create(
                    'image',
                    name='ctn',
                    labels=[{'KEY1': 'VALUE1'}, {'KEY2': 'VALUE2'}],
                    validate_input=True,
                )
        client.create_container.assert_called_once_with(
            labels={'KEY1': 'VALUE1', 'KEY2': 'VALUE2'},
            host_config=host_config,
            image='image',
            name='ctn',
        )

    @skipIf(_docker_py_version() < (1, 5, 0),
            'docker module must be installed to run this test or is too old. >=1.5.0')
    def test_list_networks(self, *args):
        '''
        test list networks.
        '''
        __salt__ = {
            'config.get': Mock(),
            'mine.send': Mock(),
        }
        host_config = {}
        client = Mock()
        client.api_version = '1.21'
        with patch.dict(dockerng_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.dict(dockerng_mod.__context__,
                            {'docker.client': client}):
                dockerng_mod.networks(
                    names=['foo'],
                    ids=['01234'],
                )
        client.networks.assert_called_once_with(
                    names=['foo'],
                    ids=['01234'],
        )

    @skipIf(_docker_py_version() < (1, 5, 0),
            'docker module must be installed to run this test or is too old. >=1.5.0')
    def test_create_network(self, *args):
        '''
        test create network.
        '''
        __salt__ = {
            'config.get': Mock(),
            'mine.send': Mock(),
        }
        host_config = {}
        client = Mock()
        client.api_version = '1.21'
        with patch.dict(dockerng_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.dict(dockerng_mod.__context__,
                            {'docker.client': client}):
                dockerng_mod.create_network(
                    'foo',
                    driver='bridge',
                )
        client.create_network.assert_called_once_with(
                    'foo',
                    driver='bridge',
        )

    @skipIf(_docker_py_version() < (1, 5, 0),
            'docker module must be installed to run this test or is too old. >=1.5.0')
    def test_remove_network(self, *args):
        '''
        test remove network.
        '''
        __salt__ = {
            'config.get': Mock(),
            'mine.send': Mock(),
        }
        host_config = {}
        client = Mock()
        client.api_version = '1.21'
        with patch.dict(dockerng_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.dict(dockerng_mod.__context__,
                            {'docker.client': client}):
                dockerng_mod.remove_network('foo')
        client.remove_network.assert_called_once_with('foo')

    @skipIf(_docker_py_version() < (1, 5, 0),
            'docker module must be installed to run this test or is too old. >=1.5.0')
    def test_inspect_network(self, *args):
        '''
        test inspect network.
        '''
        __salt__ = {
            'config.get': Mock(),
            'mine.send': Mock(),
        }
        host_config = {}
        client = Mock()
        client.api_version = '1.21'
        with patch.dict(dockerng_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.dict(dockerng_mod.__context__,
                            {'docker.client': client}):
                dockerng_mod.inspect_network('foo')
        client.inspect_network.assert_called_once_with('foo')

    @skipIf(_docker_py_version() < (1, 5, 0),
            'docker module must be installed to run this test or is too old. >=1.5.0')
    def test_connect_container_to_network(self, *args):
        '''
        test inspect network.
        '''
        __salt__ = {
            'config.get': Mock(),
            'mine.send': Mock(),
        }
        host_config = {}
        client = Mock()
        client.api_version = '1.21'
        with patch.dict(dockerng_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.dict(dockerng_mod.__context__,
                            {'docker.client': client}):
                dockerng_mod.connect_container_to_network('container', 'foo')
        client.connect_container_to_network.assert_called_once_with(
            'container', 'foo')

    @skipIf(_docker_py_version() < (1, 5, 0),
            'docker module must be installed to run this test or is too old. >=1.5.0')
    def test_disconnect_container_from_network(self, *args):
        '''
        test inspect network.
        '''
        __salt__ = {
            'config.get': Mock(),
            'mine.send': Mock(),
        }
        host_config = {}
        client = Mock()
        client.api_version = '1.21'
        with patch.dict(dockerng_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.dict(dockerng_mod.__context__,
                            {'docker.client': client}):
                dockerng_mod.disconnect_container_from_network('container', 'foo')
        client.disconnect_container_from_network.assert_called_once_with(
            'container', 'foo')

    @skipIf(_docker_py_version() < (1, 5, 0),
            'docker module must be installed to run this test or is too old. >=1.5.0')
    def test_list_volumes(self, *args):
        '''
        test list volumes.
        '''
        __salt__ = {
            'config.get': Mock(),
            'mine.send': Mock(),
        }
        client = Mock()
        client.api_version = '1.21'
        with patch.dict(dockerng_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.dict(dockerng_mod.__context__,
                            {'docker.client': client}):
                dockerng_mod.volumes(
                    filters={'dangling': [True]},
                )
        client.volumes.assert_called_once_with(
            filters={'dangling': [True]},
        )

    @skipIf(_docker_py_version() < (1, 5, 0),
            'docker module must be installed to run this test or is too old. >=1.5.0')
    def test_create_volume(self, *args):
        '''
        test create volume.
        '''
        __salt__ = {
            'config.get': Mock(),
            'mine.send': Mock(),
        }
        client = Mock()
        client.api_version = '1.21'
        with patch.dict(dockerng_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.dict(dockerng_mod.__context__,
                            {'docker.client': client}):
                dockerng_mod.create_volume(
                    'foo',
                    driver='bridge',
                    driver_opts={},
                )
        client.create_volume.assert_called_once_with(
                    'foo',
                    driver='bridge',
                    driver_opts={},
        )

    @skipIf(_docker_py_version() < (1, 5, 0),
            'docker module must be installed to run this test or is too old. >=1.5.0')
    def test_remove_volume(self, *args):
        '''
        test remove volume.
        '''
        __salt__ = {
            'config.get': Mock(),
            'mine.send': Mock(),
        }
        client = Mock()
        client.api_version = '1.21'
        with patch.dict(dockerng_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.dict(dockerng_mod.__context__,
                            {'docker.client': client}):
                dockerng_mod.remove_volume('foo')
        client.remove_volume.assert_called_once_with('foo')

    @skipIf(_docker_py_version() < (1, 5, 0),
            'docker module must be installed to run this test or is too old. >=1.5.0')
    def test_inspect_volume(self, *args):
        '''
        test inspect volume.
        '''
        __salt__ = {
            'config.get': Mock(),
            'mine.send': Mock(),
        }
        client = Mock()
        client.api_version = '1.21'
        with patch.dict(dockerng_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.dict(dockerng_mod.__context__,
                            {'docker.client': client}):
                dockerng_mod.inspect_volume('foo')
        client.inspect_volume.assert_called_once_with('foo')

    def test_wait_success(self):
        client = Mock()
        client.api_version = '1.21'
        client.wait = Mock(return_value=0)
        dockerng_inspect_container = Mock(side_effect=[
            {'State': {'Running': True}},
            {'State': {'Stopped': True}}])
        with patch.object(dockerng_mod, 'inspect_container',
                          dockerng_inspect_container):
            with patch.dict(dockerng_mod.__context__,
                            {'docker.client': client}):
                dockerng_mod._clear_context()
                result = dockerng_mod.wait('foo')
        self.assertEqual(result, {'result': True,
                                  'exit_status': 0,
                                  'state': {'new': 'stopped',
                                            'old': 'running'}})

    def test_wait_fails_already_stopped(self):
        client = Mock()
        client.api_version = '1.21'
        client.wait = Mock(return_value=0)
        dockerng_inspect_container = Mock(side_effect=[
            {'State': {'Stopped': True}},
            {'State': {'Stopped': True}},
        ])
        with patch.object(dockerng_mod, 'inspect_container',
                          dockerng_inspect_container):
            with patch.dict(dockerng_mod.__context__,
                            {'docker.client': client}):
                dockerng_mod._clear_context()
                result = dockerng_mod.wait('foo')
        self.assertEqual(result, {'result': False,
                                  'comment': "Container 'foo' already stopped",
                                  'exit_status': 0,
                                  'state': {'new': 'stopped',
                                            'old': 'stopped'}})

    def test_wait_success_already_stopped(self):
        client = Mock()
        client.api_version = '1.21'
        client.wait = Mock(return_value=0)
        dockerng_inspect_container = Mock(side_effect=[
            {'State': {'Stopped': True}},
            {'State': {'Stopped': True}},
        ])
        with patch.object(dockerng_mod, 'inspect_container',
                          dockerng_inspect_container):
            with patch.dict(dockerng_mod.__context__,
                            {'docker.client': client}):
                dockerng_mod._clear_context()
                result = dockerng_mod.wait('foo', ignore_already_stopped=True)
        self.assertEqual(result, {'result': True,
                                  'comment': "Container 'foo' already stopped",
                                  'exit_status': 0,
                                  'state': {'new': 'stopped',
                                            'old': 'stopped'}})

    def test_wait_success_absent_container(self):
        client = Mock()
        client.api_version = '1.21'
        dockerng_inspect_container = Mock(side_effect=CommandExecutionError)
        with patch.object(dockerng_mod, 'inspect_container',
                          dockerng_inspect_container):
            with patch.dict(dockerng_mod.__context__,
                            {'docker.client': client}):
                dockerng_mod._clear_context()
                result = dockerng_mod.wait('foo', ignore_already_stopped=True)
        self.assertEqual(result, {'result': True,
                                  'comment': "Container 'foo' absent"})

    def test_wait_fails_on_exit_status(self):
        client = Mock()
        client.api_version = '1.21'
        client.wait = Mock(return_value=1)
        dockerng_inspect_container = Mock(side_effect=[
            {'State': {'Running': True}},
            {'State': {'Stopped': True}}])
        with patch.object(dockerng_mod, 'inspect_container',
                          dockerng_inspect_container):
            with patch.dict(dockerng_mod.__context__,
                            {'docker.client': client}):
                dockerng_mod._clear_context()
                result = dockerng_mod.wait('foo', fail_on_exit_status=True)
        self.assertEqual(result, {'result': False,
                                  'exit_status': 1,
                                  'state': {'new': 'stopped',
                                            'old': 'running'}})

    def test_wait_fails_on_exit_status_and_already_stopped(self):
        client = Mock()
        client.api_version = '1.21'
        client.wait = Mock(return_value=1)
        dockerng_inspect_container = Mock(side_effect=[
            {'State': {'Stopped': True}},
            {'State': {'Stopped': True}}])
        with patch.object(dockerng_mod, 'inspect_container',
                          dockerng_inspect_container):
            with patch.dict(dockerng_mod.__context__,
                            {'docker.client': client}):
                dockerng_mod._clear_context()
                result = dockerng_mod.wait('foo',
                                           ignore_already_stopped=True,
                                           fail_on_exit_status=True)
        self.assertEqual(result, {'result': False,
                                  'comment': "Container 'foo' already stopped",
                                  'exit_status': 1,
                                  'state': {'new': 'stopped',
                                            'old': 'stopped'}})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DockerngTestCase, needs_daemon=False)
