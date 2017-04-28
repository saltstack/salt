# -*- coding: utf-8 -*-
'''
Unit tests for the docker module
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    Mock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

# Import Salt Libs
from salt.ext.six.moves import range
from salt.exceptions import CommandExecutionError
import salt.modules.dockermod as docker_mod


def _docker_py_version():
    try:
        if docker_mod.HAS_DOCKER_PY:
            return docker_mod.docker.version_info
    except AttributeError:
        pass
    return (0,)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(docker_mod.HAS_DOCKER_PY is False, 'docker-py must be installed to run these tests. Skipping.')
class DockerTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Validate docker module
    '''
    def setup_loader_modules(self):
        return {docker_mod: {'__context__': {'docker.docker_version': ''}}}

    try:
        docker_version = docker_mod.docker.version_info
    except AttributeError:
        docker_version = 0,

    def setUp(self):
        '''
        Ensure we aren't persisting context dunders between tests
        '''
        docker_mod.__context__.pop('docker.client', None)

    def test_ps_with_host_true(self):
        '''
        Check that docker.ps called with host is ``True``,
        include resutlt of ``network.interfaces`` command in returned result.
        '''
        client = Mock()
        client.containers = MagicMock(return_value=[])
        get_client_mock = MagicMock(return_value=client)
        network_interfaces = Mock(return_value={'mocked': None})

        with patch.dict(docker_mod.__salt__,
                        {'network.interfaces': network_interfaces}):
            with patch.object(docker_mod, '_get_client', get_client_mock):
                ret = docker_mod.ps_(host=True)
                self.assertEqual(ret,
                                 {'host': {'interfaces': {'mocked': None}}})

    def test_ps_with_filters(self):
        '''
        Check that docker.ps accept filters parameter.
        '''
        client = Mock()
        client.containers = MagicMock(return_value=[])
        get_client_mock = MagicMock(return_value=client)

        with patch.object(docker_mod, '_get_client', get_client_mock):
            docker_mod.ps_(filters={'label': 'KEY'})
            client.containers.assert_called_once_with(
                all=True,
                filters={'label': 'KEY'})

    def test_check_mine_cache_is_refreshed_on_container_change_event(self):
        '''
        Every command that might modify docker containers state.
        Should trig an update on ``mine.send``
        '''
        with patch.object(docker_mod, '_get_exec_driver'):
            client_args_mock = MagicMock(return_value={
                'create_container': [
                    'image', 'command', 'hostname', 'user', 'detach', 'stdin_open',
                    'tty', 'ports', 'environment', 'volumes', 'network_disabled',
                    'name', 'entrypoint', 'working_dir', 'domainname', 'cpuset',
                    'host_config', 'mac_address', 'labels', 'volume_driver',
                    'stop_signal', 'networking_config', 'healthcheck',
                    'stop_timeout'],
               'host_config': [
                   'binds', 'port_bindings', 'lxc_conf', 'publish_all_ports',
                   'links', 'privileged', 'dns', 'dns_search', 'volumes_from',
                   'network_mode', 'restart_policy', 'cap_add', 'cap_drop',
                   'devices', 'extra_hosts', 'read_only', 'pid_mode', 'ipc_mode',
                   'security_opt', 'ulimits', 'log_config', 'mem_limit',
                   'memswap_limit', 'mem_reservation', 'kernel_memory',
                   'mem_swappiness', 'cgroup_parent', 'group_add', 'cpu_quota',
                   'cpu_period', 'blkio_weight', 'blkio_weight_device',
                   'device_read_bps', 'device_write_bps', 'device_read_iops',
                   'device_write_iops', 'oom_kill_disable', 'shm_size', 'sysctls',
                   'tmpfs', 'oom_score_adj', 'dns_opt', 'cpu_shares',
                   'cpuset_cpus', 'userns_mode', 'pids_limit', 'isolation',
                   'auto_remove', 'storage_opt'],
               'networking_config': [
                   'aliases', 'links', 'ipv4_address', 'ipv6_address',
                   'link_local_ips'],
               }

            )

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
                command = getattr(docker_mod, command_name)
                client = MagicMock()
                client.api_version = '1.12'
                with patch.dict(docker_mod.__salt__,
                                {'mine.send': mine_send,
                                 'container_resource.run': MagicMock(),
                                 'cp.cache_file': MagicMock(return_value=False),
                                 'docker.get_client_args': client_args_mock}):
                    with patch.object(docker_mod, '_get_client', client):
                        command('container', *args)
                mine_send.assert_called_with('docker.ps', verbose=True, all=True,
                                             host=True)

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
        get_client_mock = MagicMock(return_value=client)

        with patch.dict(docker_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.object(docker_mod, '_get_client', get_client_mock):
                docker_mod.networks(names=['foo'], ids=['01234'])
        client.networks.assert_called_once_with(names=['foo'], ids=['01234'])

    @skipIf(docker_version < (1, 5, 0),
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
        get_client_mock = MagicMock(return_value=client)

        with patch.dict(docker_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.object(docker_mod, '_get_client', get_client_mock):
                docker_mod.create_network('foo',
                                          driver='bridge',
                                          driver_opts={})
        client.create_network.assert_called_once_with('foo',
                                                      driver='bridge',
                                                      options={},
                                                      check_duplicate=True)

    @skipIf(docker_version < (1, 5, 0),
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
        get_client_mock = MagicMock(return_value=client)

        with patch.dict(docker_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.object(docker_mod, '_get_client', get_client_mock):
                docker_mod.remove_network('foo')
        client.remove_network.assert_called_once_with('foo')

    @skipIf(docker_version < (1, 5, 0),
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
        get_client_mock = MagicMock(return_value=client)

        with patch.dict(docker_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.object(docker_mod, '_get_client', get_client_mock):
                docker_mod.inspect_network('foo')
        client.inspect_network.assert_called_once_with('foo')

    @skipIf(docker_version < (1, 5, 0),
            'docker module must be installed to run this test or is too old. >=1.5.0')
    def test_connect_container_to_network(self, *args):
        '''
        test connect_container_to_network
        '''
        __salt__ = {
            'config.get': Mock(),
            'mine.send': Mock(),
        }
        host_config = {}
        client = Mock()
        client.api_version = '1.21'
        get_client_mock = MagicMock(return_value=client)

        context = {'docker.exec_driver': 'docker-exec'}

        with patch.dict(docker_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.dict(docker_mod.__context__, context):
                with patch.object(docker_mod, '_get_client', get_client_mock):
                    docker_mod.connect_container_to_network('container', 'foo')
        client.connect_container_to_network.assert_called_once_with(
            'container', 'foo', None)

    @skipIf(docker_version < (1, 5, 0),
            'docker module must be installed to run this test or is too old. >=1.5.0')
    def test_disconnect_container_from_network(self, *args):
        '''
        test disconnect_container_from_network
        '''
        __salt__ = {
            'config.get': Mock(),
            'mine.send': Mock(),
        }
        host_config = {}
        client = Mock()
        client.api_version = '1.21'
        get_client_mock = MagicMock(return_value=client)

        with patch.dict(docker_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.object(docker_mod, '_get_client', get_client_mock):
                docker_mod.disconnect_container_from_network('container', 'foo')
        client.disconnect_container_from_network.assert_called_once_with(
            'container', 'foo')

    @skipIf(docker_version < (1, 5, 0),
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
        get_client_mock = MagicMock(return_value=client)

        with patch.dict(docker_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.object(docker_mod, '_get_client', get_client_mock):
                docker_mod.volumes(
                    filters={'dangling': [True]},
                )
        client.volumes.assert_called_once_with(
            filters={'dangling': [True]},
        )

    @skipIf(docker_version < (1, 5, 0),
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
        get_client_mock = MagicMock(return_value=client)

        with patch.dict(docker_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.object(docker_mod, '_get_client', get_client_mock):
                docker_mod.create_volume(
                    'foo',
                    driver='bridge',
                    driver_opts={},
                )
        client.create_volume.assert_called_once_with(
                    'foo',
                    driver='bridge',
                    driver_opts={},
        )

    @skipIf(docker_version < (1, 5, 0),
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
        get_client_mock = MagicMock(return_value=client)

        with patch.dict(docker_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.object(docker_mod, '_get_client', get_client_mock):
                docker_mod.remove_volume('foo')
        client.remove_volume.assert_called_once_with('foo')

    @skipIf(docker_version < (1, 5, 0),
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
        get_client_mock = MagicMock(return_value=client)

        with patch.dict(docker_mod.__dict__,
                        {'__salt__': __salt__}):
            with patch.object(docker_mod, '_get_client', get_client_mock):
                docker_mod.inspect_volume('foo')
        client.inspect_volume.assert_called_once_with('foo')

    def test_wait_success(self):
        client = Mock()
        client.api_version = '1.21'
        client.wait = Mock(return_value=0)
        get_client_mock = MagicMock(return_value=client)

        docker_inspect_container = Mock(side_effect=[
            {'State': {'Running': True}},
            {'State': {'Stopped': True}}])
        with patch.object(docker_mod, 'inspect_container',
                          docker_inspect_container):
            with patch.object(docker_mod, '_get_client', get_client_mock):
                docker_mod._clear_context()
                result = docker_mod.wait('foo')
        self.assertEqual(result, {'result': True,
                                  'exit_status': 0,
                                  'state': {'new': 'stopped',
                                            'old': 'running'}})

    def test_wait_fails_already_stopped(self):
        client = Mock()
        client.api_version = '1.21'
        client.wait = Mock(return_value=0)
        get_client_mock = MagicMock(return_value=client)

        docker_inspect_container = Mock(side_effect=[
            {'State': {'Stopped': True}},
            {'State': {'Stopped': True}},
        ])
        with patch.object(docker_mod, 'inspect_container',
                          docker_inspect_container):
            with patch.object(docker_mod, '_get_client', get_client_mock):
                docker_mod._clear_context()
                result = docker_mod.wait('foo')
        self.assertEqual(result, {'result': False,
                                  'comment': "Container 'foo' already stopped",
                                  'exit_status': 0,
                                  'state': {'new': 'stopped',
                                            'old': 'stopped'}})

    def test_wait_success_already_stopped(self):
        client = Mock()
        client.api_version = '1.21'
        client.wait = Mock(return_value=0)
        get_client_mock = MagicMock(return_value=client)

        docker_inspect_container = Mock(side_effect=[
            {'State': {'Stopped': True}},
            {'State': {'Stopped': True}},
        ])
        with patch.object(docker_mod, 'inspect_container',
                          docker_inspect_container):
            with patch.object(docker_mod, '_get_client', get_client_mock):
                docker_mod._clear_context()
                result = docker_mod.wait('foo', ignore_already_stopped=True)
        self.assertEqual(result, {'result': True,
                                  'comment': "Container 'foo' already stopped",
                                  'exit_status': 0,
                                  'state': {'new': 'stopped',
                                            'old': 'stopped'}})

    def test_wait_success_absent_container(self):
        client = Mock()
        client.api_version = '1.21'
        get_client_mock = MagicMock(return_value=client)

        docker_inspect_container = Mock(side_effect=CommandExecutionError)
        with patch.object(docker_mod, 'inspect_container',
                          docker_inspect_container):
            with patch.object(docker_mod, '_get_client', get_client_mock):
                docker_mod._clear_context()
                result = docker_mod.wait('foo', ignore_already_stopped=True)
        self.assertEqual(result, {'result': True,
                                  'comment': "Container 'foo' absent"})

    def test_wait_fails_on_exit_status(self):
        client = Mock()
        client.api_version = '1.21'
        client.wait = Mock(return_value=1)
        get_client_mock = MagicMock(return_value=client)

        docker_inspect_container = Mock(side_effect=[
            {'State': {'Running': True}},
            {'State': {'Stopped': True}}])
        with patch.object(docker_mod, 'inspect_container',
                          docker_inspect_container):
            with patch.object(docker_mod, '_get_client', get_client_mock):
                docker_mod._clear_context()
                result = docker_mod.wait('foo', fail_on_exit_status=True)
        self.assertEqual(result, {'result': False,
                                  'exit_status': 1,
                                  'state': {'new': 'stopped',
                                            'old': 'running'}})

    def test_wait_fails_on_exit_status_and_already_stopped(self):
        client = Mock()
        client.api_version = '1.21'
        client.wait = Mock(return_value=1)
        get_client_mock = MagicMock(return_value=client)

        docker_inspect_container = Mock(side_effect=[
            {'State': {'Stopped': True}},
            {'State': {'Stopped': True}}])
        with patch.object(docker_mod, 'inspect_container',
                          docker_inspect_container):
            with patch.object(docker_mod, '_get_client', get_client_mock):
                docker_mod._clear_context()
                result = docker_mod.wait('foo',
                                           ignore_already_stopped=True,
                                           fail_on_exit_status=True)
        self.assertEqual(result, {'result': False,
                                  'comment': "Container 'foo' already stopped",
                                  'exit_status': 1,
                                  'state': {'new': 'stopped',
                                            'old': 'stopped'}})

    def test_sls_build(self, *args):
        '''
        test build sls image.
        '''
        docker_start_mock = MagicMock(
            return_value={})
        docker_create_mock = MagicMock(
            return_value={'Id': 'ID', 'Name': 'NAME'})
        docker_stop_mock = MagicMock(
            return_value={'state': {'old': 'running', 'new': 'stopped'},
                          'result': True})
        docker_rm_mock = MagicMock(return_value={})
        docker_commit_mock = MagicMock(
            return_value={'Id': 'ID2', 'Image': 'foo', 'Time_Elapsed': 42})

        docker_sls_mock = MagicMock(
            return_value={
                "file_|-/etc/test.sh_|-/etc/test.sh_|-managed": {
                    "comment": "File /etc/test.sh is in the correct state",
                    "name": "/etc/test.sh",
                    "start_time": "07:04:26.834792",
                    "result": True,
                    "duration": 13.492,
                    "__run_num__": 0,
                    "changes": {}
                },
                "test_|-always-passes_|-foo_|-succeed_without_changes": {
                    "comment": "Success!",
                    "name": "foo",
                    "start_time": "07:04:26.848915",
                    "result": True,
                    "duration": 0.363,
                    "__run_num__": 1,
                    "changes": {}
                }
            })

        ret = None
        with patch.object(docker_mod, 'start', docker_start_mock):
            with patch.object(docker_mod, 'create', docker_create_mock):
                with patch.object(docker_mod, 'stop', docker_stop_mock):
                    with patch.object(docker_mod, 'commit', docker_commit_mock):
                        with patch.object(docker_mod, 'sls', docker_sls_mock):
                            with patch.object(docker_mod, 'rm_', docker_rm_mock):
                                ret = docker_mod.sls_build(
                                    'foo',
                                    mods='foo',
                                )
        docker_create_mock.assert_called_once_with(
            cmd='sleep infinity',
            image='opensuse/python', interactive=True, tty=True)
        docker_start_mock.assert_called_once_with('ID')
        docker_sls_mock.assert_called_once_with('ID', 'foo', 'base')
        docker_stop_mock.assert_called_once_with('ID')
        docker_rm_mock.assert_called_once_with('ID')
        docker_commit_mock.assert_called_once_with('ID', 'foo')
        self.assertEqual(
            {'Id': 'ID2', 'Image': 'foo', 'Time_Elapsed': 42}, ret)

    def test_sls_build_dryrun(self, *args):
        '''
        test build sls image in dryrun mode.
        '''
        docker_start_mock = MagicMock(
            return_value={})
        docker_create_mock = MagicMock(
            return_value={'Id': 'ID', 'Name': 'NAME'})
        docker_stop_mock = MagicMock(
            return_value={'state': {'old': 'running', 'new': 'stopped'},
                          'result': True})
        docker_rm_mock = MagicMock(
            return_value={})

        docker_sls_mock = MagicMock(
            return_value={
                "file_|-/etc/test.sh_|-/etc/test.sh_|-managed": {
                    "comment": "File /etc/test.sh is in the correct state",
                    "name": "/etc/test.sh",
                    "start_time": "07:04:26.834792",
                    "result": True,
                    "duration": 13.492,
                    "__run_num__": 0,
                    "changes": {}
                },
                "test_|-always-passes_|-foo_|-succeed_without_changes": {
                    "comment": "Success!",
                    "name": "foo",
                    "start_time": "07:04:26.848915",
                    "result": True,
                    "duration": 0.363,
                    "__run_num__": 1,
                    "changes": {}
                }
            })

        ret = None
        with patch.object(docker_mod, 'start', docker_start_mock):
            with patch.object(docker_mod, 'create', docker_create_mock):
                with patch.object(docker_mod, 'stop', docker_stop_mock):
                    with patch.object(docker_mod, 'rm_', docker_rm_mock):
                        with patch.object(docker_mod, 'sls', docker_sls_mock):
                            ret = docker_mod.sls_build(
                                'foo',
                                mods='foo',
                                dryrun=True
                            )
        docker_create_mock.assert_called_once_with(
            cmd='sleep infinity',
            image='opensuse/python', interactive=True, tty=True)
        docker_start_mock.assert_called_once_with('ID')
        docker_sls_mock.assert_called_once_with('ID', 'foo', 'base')
        docker_stop_mock.assert_called_once_with('ID')
        docker_rm_mock.assert_called_once_with('ID')
        self.assertEqual(
                {
                "file_|-/etc/test.sh_|-/etc/test.sh_|-managed": {
                    "comment": "File /etc/test.sh is in the correct state",
                    "name": "/etc/test.sh",
                    "start_time": "07:04:26.834792",
                    "result": True,
                    "duration": 13.492,
                    "__run_num__": 0,
                    "changes": {}
                },
                "test_|-always-passes_|-foo_|-succeed_without_changes": {
                    "comment": "Success!",
                    "name": "foo",
                    "start_time": "07:04:26.848915",
                    "result": True,
                    "duration": 0.363,
                    "__run_num__": 1,
                    "changes": {}
                }
                },
                ret)

    def test_call_success(self):
        '''
        test module calling inside containers
        '''
        ret = None
        docker_run_all_mock = MagicMock(
            return_value={
                'retcode': 0,
                'stdout': '{"retcode": 0, "comment": "container cmd"}',
                'stderr': 'err',
            })
        docker_copy_to_mock = MagicMock(
            return_value={
                'retcode': 0
            })
        docker_config_mock = MagicMock(
            return_value=''
            )
        client = Mock()
        client.put_archive = Mock()
        get_client_mock = MagicMock(return_value=client)

        context = {'docker.exec_driver': 'docker-exec'}
        salt_dunder = {'config.option': docker_config_mock}

        with patch.object(docker_mod, 'run_all', docker_run_all_mock):
            with patch.object(docker_mod, 'copy_to', docker_copy_to_mock):
                with patch.object(docker_mod, '_get_client', get_client_mock):
                    with patch.dict(docker_mod.__opts__, {'cachedir': '/tmp'}):
                        with patch.dict(docker_mod.__salt__, salt_dunder):
                            with patch.dict(docker_mod.__context__, context):
                                # call twice to verify tmp path later
                                for i in range(2):
                                    ret = docker_mod.call(
                                        'ID',
                                        'test.arg',
                                        1, 2,
                                        arg1='val1')

        # Check that the directory is different each time
        # [ call(name, [args]), ...
        self.assertIn('mkdir', docker_run_all_mock.mock_calls[0][1][1])
        self.assertIn('mkdir', docker_run_all_mock.mock_calls[3][1][1])
        self.assertNotEqual(docker_run_all_mock.mock_calls[0][1][1],
                            docker_run_all_mock.mock_calls[3][1][1])

        self.assertIn('salt-call', docker_run_all_mock.mock_calls[1][1][1])
        self.assertIn('salt-call', docker_run_all_mock.mock_calls[4][1][1])
        self.assertNotEqual(docker_run_all_mock.mock_calls[1][1][1],
                            docker_run_all_mock.mock_calls[4][1][1])

        # check directory cleanup
        self.assertIn('rm -rf', docker_run_all_mock.mock_calls[2][1][1])
        self.assertIn('rm -rf', docker_run_all_mock.mock_calls[5][1][1])
        self.assertNotEqual(docker_run_all_mock.mock_calls[2][1][1],
                            docker_run_all_mock.mock_calls[5][1][1])

        self.assertEqual({"retcode": 0, "comment": "container cmd"}, ret)

    def test_images_with_empty_tags(self):
        """
        docker 1.12 reports also images without tags with `null`.
        """
        client = Mock()
        client.api_version = '1.24'
        client.images = Mock(
            return_value=[{'Id': 'sha256:abcde',
                           'RepoTags': None},
                          {'Id': 'sha256:abcdef'},
                          {'Id': 'sha256:abcdefg',
                           'RepoTags': ['image:latest']}])
        get_client_mock = MagicMock(return_value=client)

        with patch.object(docker_mod, '_get_client', get_client_mock):
            docker_mod._clear_context()
            result = docker_mod.images()
        self.assertEqual(result,
                         {'sha256:abcdefg': {'RepoTags': ['image:latest']}})
