# -*- coding: utf-8 -*-
'''
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import os

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    Mock,
    MagicMock,
    patch,
)

# Import Salt Libs
import salt.modules.systemd_service as systemd
import salt.utils.systemd
from salt.exceptions import CommandExecutionError

_SYSTEMCTL_STATUS = {
    'sshd.service': {
        'stdout': '''\
* sshd.service - OpenSSH Daemon
   Loaded: loaded (/usr/lib/systemd/system/sshd.service; disabled; vendor preset: disabled)
   Active: inactive (dead)''',
        'stderr': '',
        'retcode': 3,
        'pid': 12345,
    },

    'foo.service': {
        'stdout': '''\
* foo.service
   Loaded: not-found (Reason: No such file or directory)
   Active: inactive (dead)''',
        'stderr': '',
        'retcode': 3,
        'pid': 12345,
    },
}

# This reflects systemd >= 231 behavior
_SYSTEMCTL_STATUS_GTE_231 = {
    'bar.service': {
        'stdout': 'Unit bar.service could not be found.',
        'stderr': '',
        'retcode': 4,
        'pid': 12345,
    },
}

_LIST_UNIT_FILES = '''\
service1.service                           enabled
service2.service                           disabled
service3.service                           static
timer1.timer                               enabled
timer2.timer                               disabled
timer3.timer                               static'''


class SystemdTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test case for salt.modules.systemd
    '''
    def setup_loader_modules(self):
        return {systemd: {}}

    def test_systemctl_reload(self):
        '''
            Test to Reloads systemctl
        '''
        mock = MagicMock(side_effect=[
            {'stdout': 'Who knows why?',
             'stderr': '',
             'retcode': 1,
             'pid': 12345},
            {'stdout': '',
             'stderr': '',
             'retcode': 0,
             'pid': 54321},
        ])
        with patch.dict(systemd.__salt__, {'cmd.run_all': mock}):
            self.assertRaisesRegex(
                CommandExecutionError,
                'Problem performing systemctl daemon-reload: Who knows why?',
                systemd.systemctl_reload
            )
            self.assertTrue(systemd.systemctl_reload())

    def test_get_enabled(self):
        '''
        Test to return a list of all enabled services
        '''
        cmd_mock = MagicMock(return_value=_LIST_UNIT_FILES)
        listdir_mock = MagicMock(return_value=['foo', 'bar', 'baz', 'README'])
        sd_mock = MagicMock(
            return_value=set(
                [x.replace('.service', '') for x in _SYSTEMCTL_STATUS]
            )
        )
        access_mock = MagicMock(
            side_effect=lambda x, y: x != os.path.join(
                systemd.INITSCRIPT_PATH,
                'README'
            )
        )
        sysv_enabled_mock = MagicMock(side_effect=lambda x, _: x == 'baz')

        with patch.dict(systemd.__salt__, {'cmd.run': cmd_mock}):
            with patch.object(os, 'listdir', listdir_mock):
                with patch.object(systemd, '_get_systemd_services', sd_mock):
                    with patch.object(os, 'access', side_effect=access_mock):
                        with patch.object(systemd, '_sysv_enabled',
                                          sysv_enabled_mock):
                            self.assertListEqual(
                                systemd.get_enabled(),
                                ['baz', 'service1', 'timer1.timer']
                            )

    def test_get_disabled(self):
        '''
        Test to return a list of all disabled services
        '''
        cmd_mock = MagicMock(return_value=_LIST_UNIT_FILES)
        # 'foo' should collide with the systemd services (as returned by
        # sd_mock) and thus not be returned by _get_sysv_services(). It doesn't
        # matter that it's not part of the _LIST_UNIT_FILES output, we just
        # want to ensure that 'foo' isn't identified as a disabled initscript
        # even though below we are mocking it to show as not enabled (since
        # only 'baz' will be considered an enabled sysv service).
        listdir_mock = MagicMock(return_value=['foo', 'bar', 'baz', 'README'])
        sd_mock = MagicMock(
            return_value=set(
                [x.replace('.service', '') for x in _SYSTEMCTL_STATUS]
            )
        )
        access_mock = MagicMock(
            side_effect=lambda x, y: x != os.path.join(
                systemd.INITSCRIPT_PATH,
                'README'
            )
        )
        sysv_enabled_mock = MagicMock(side_effect=lambda x, _: x == 'baz')

        with patch.dict(systemd.__salt__, {'cmd.run': cmd_mock}):
            with patch.object(os, 'listdir', listdir_mock):
                with patch.object(systemd, '_get_systemd_services', sd_mock):
                    with patch.object(os, 'access', side_effect=access_mock):
                        with patch.object(systemd, '_sysv_enabled',
                                          sysv_enabled_mock):
                            self.assertListEqual(
                                systemd.get_disabled(),
                                ['bar', 'service2', 'timer2.timer']
                            )

    def test_get_all(self):
        '''
        Test to return a list of all available services
        '''
        listdir_mock = MagicMock(side_effect=[
            ['foo.service', 'multi-user.target.wants', 'mytimer.timer'],
            [],
            ['foo.service', 'multi-user.target.wants', 'bar.service'],
            ['mysql', 'nginx', 'README']
        ])
        access_mock = MagicMock(
            side_effect=lambda x, y: x != os.path.join(
                systemd.INITSCRIPT_PATH,
                'README'
            )
        )
        with patch.object(os, 'listdir', listdir_mock):
            with patch.object(os, 'access', side_effect=access_mock):
                self.assertListEqual(
                    systemd.get_all(),
                    ['bar', 'foo', 'mysql', 'mytimer.timer', 'nginx']
                )

    def test_available(self):
        '''
        Test to check that the given service is available
        '''
        mock = MagicMock(side_effect=lambda x: _SYSTEMCTL_STATUS[x])

        # systemd < 231
        with patch.dict(systemd.__context__, {'salt.utils.systemd.version': 230}):
            with patch.object(systemd, '_systemctl_status', mock):
                self.assertTrue(systemd.available('sshd.service'))
                self.assertFalse(systemd.available('foo.service'))

        # systemd >= 231
        with patch.dict(systemd.__context__, {'salt.utils.systemd.version': 231}):
            with patch.dict(_SYSTEMCTL_STATUS, _SYSTEMCTL_STATUS_GTE_231):
                with patch.object(systemd, '_systemctl_status', mock):
                    self.assertTrue(systemd.available('sshd.service'))
                    self.assertFalse(systemd.available('bar.service'))

        # systemd < 231 with retcode/output changes backported (e.g. RHEL 7.3)
        with patch.dict(systemd.__context__, {'salt.utils.systemd.version': 219}):
            with patch.dict(_SYSTEMCTL_STATUS, _SYSTEMCTL_STATUS_GTE_231):
                with patch.object(systemd, '_systemctl_status', mock):
                    self.assertTrue(systemd.available('sshd.service'))
                    self.assertFalse(systemd.available('bar.service'))

    def test_missing(self):
        '''
            Test to the inverse of service.available.
        '''
        mock = MagicMock(side_effect=lambda x: _SYSTEMCTL_STATUS[x])

        # systemd < 231
        with patch.dict(systemd.__context__, {'salt.utils.systemd.version': 230}):
            with patch.object(systemd, '_systemctl_status', mock):
                self.assertFalse(systemd.missing('sshd.service'))
                self.assertTrue(systemd.missing('foo.service'))

        # systemd >= 231
        with patch.dict(systemd.__context__, {'salt.utils.systemd.version': 231}):
            with patch.dict(_SYSTEMCTL_STATUS, _SYSTEMCTL_STATUS_GTE_231):
                with patch.object(systemd, '_systemctl_status', mock):
                    self.assertFalse(systemd.missing('sshd.service'))
                    self.assertTrue(systemd.missing('bar.service'))

        # systemd < 231 with retcode/output changes backported (e.g. RHEL 7.3)
        with patch.dict(systemd.__context__, {'salt.utils.systemd.version': 219}):
            with patch.dict(_SYSTEMCTL_STATUS, _SYSTEMCTL_STATUS_GTE_231):
                with patch.object(systemd, '_systemctl_status', mock):
                    self.assertFalse(systemd.missing('sshd.service'))
                    self.assertTrue(systemd.missing('bar.service'))

    def test_show(self):
        '''
        Test to show properties of one or more units/jobs or the manager
        '''
        show_output = 'a=b\nc=d\ne={ f=g ; h=i }\nWants=foo.service bar.service\n'
        mock = MagicMock(return_value=show_output)
        with patch.dict(systemd.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(
                systemd.show('sshd'),
                {'a': 'b',
                 'c': 'd',
                 'e': {'f': 'g', 'h': 'i'},
                 'Wants': ['foo.service', 'bar.service']}
            )

    def test_execs(self):
        '''
        Test to return a list of all files specified as ``ExecStart`` for all
        services
        '''
        mock = MagicMock(return_value=['a', 'b'])
        with patch.object(systemd, 'get_all', mock):
            mock = MagicMock(return_value={'ExecStart': {'path': 'c'}})
            with patch.object(systemd, 'show', mock):
                self.assertDictEqual(systemd.execs(), {'a': 'c', 'b': 'c'})

    def test_status(self):
        '''
        Test to confirm that the function retries when the service is in the
        activating/deactivating state.
        '''
        active = {
            'stdout': 'active',
            'stderr': '',
            'retcode': 0,
            'pid': 12345}
        inactive = {
            'stdout': 'inactive',
            'stderr': '',
            'retcode': 3,
            'pid': 12345}
        activating = {
            'stdout': 'activating',
            'stderr': '',
            'retcode': 3,
            'pid': 12345}
        deactivating = {
            'stdout': 'deactivating',
            'stderr': '',
            'retcode': 3,
            'pid': 12345}

        check_mock = Mock()

        cmd_mock = MagicMock(side_effect=[activating, activating, active, inactive])
        with patch.dict(systemd.__salt__, {'cmd.run_all': cmd_mock}), \
                patch.object(systemd, '_check_for_unit_changes', check_mock):
            ret = systemd.status('foo')
            assert ret is True
            # We should only have had three calls, since the third was not
            # either in the activating or deactivating state and we should not
            # have retried after.
            assert cmd_mock.call_count == 3

        cmd_mock = MagicMock(side_effect=[deactivating, deactivating, inactive, active])
        with patch.dict(systemd.__salt__, {'cmd.run_all': cmd_mock}), \
                patch.object(systemd, '_check_for_unit_changes', check_mock):
            ret = systemd.status('foo')
            assert ret is False
            # We should only have had three calls, since the third was not
            # either in the activating or deactivating state and we should not
            # have retried after.
            assert cmd_mock.call_count == 3

        cmd_mock = MagicMock(side_effect=[activating, activating, active, inactive])
        with patch.dict(systemd.__salt__, {'cmd.run_all': cmd_mock}), \
                patch.object(systemd, '_check_for_unit_changes', check_mock):
            ret = systemd.status('foo', wait=0.25)
            assert ret is False
            # We should only have had two calls, because "wait" was set too low
            # to allow for more than one retry.
            assert cmd_mock.call_count == 2

        cmd_mock = MagicMock(side_effect=[active, inactive])
        with patch.dict(systemd.__salt__, {'cmd.run_all': cmd_mock}), \
                patch.object(systemd, '_check_for_unit_changes', check_mock):
            ret = systemd.status('foo')
            assert ret is True
            # We should only have a single call, because the first call was in
            # the active state.
            assert cmd_mock.call_count == 1

        cmd_mock = MagicMock(side_effect=[inactive, active])
        with patch.dict(systemd.__salt__, {'cmd.run_all': cmd_mock}), \
                patch.object(systemd, '_check_for_unit_changes', check_mock):
            ret = systemd.status('foo')
            assert ret is False
            # We should only have a single call, because the first call was in
            # the inactive state.
            assert cmd_mock.call_count == 1


class SystemdScopeTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Test case for salt.modules.systemd, for functions which use systemd
        scopes
    '''
    def setup_loader_modules(self):
        return {systemd: {}}

    unit_name = 'foo'
    mock_none = MagicMock(return_value=None)
    mock_success = MagicMock(return_value=0)
    mock_failure = MagicMock(return_value=1)
    mock_true = MagicMock(return_value=True)
    mock_false = MagicMock(return_value=False)
    mock_empty_list = MagicMock(return_value=[])
    mock_run_all_success = MagicMock(return_value={'retcode': 0,
                                                   'stdout': '',
                                                   'stderr': '',
                                                   'pid': 12345})
    mock_run_all_failure = MagicMock(return_value={'retcode': 1,
                                                   'stdout': '',
                                                   'stderr': '',
                                                   'pid': 12345})

    def _change_state(self, action, no_block=False):
        '''
        Common code for start/stop/restart/reload/force_reload tests
        '''
        # We want the traceback if the function name can't be found in the
        # systemd execution module.
        func = getattr(systemd, action)
        # Remove trailing _ in "reload_"
        action = action.rstrip('_').replace('_', '-')
        systemctl_command = ['systemctl']
        if no_block:
            systemctl_command.append('--no-block')
        systemctl_command.extend([action, self.unit_name + '.service'])
        scope_prefix = ['systemd-run', '--scope']

        assert_kwargs = {'python_shell': False}
        if action in ('enable', 'disable'):
            assert_kwargs['ignore_retcode'] = True

        with patch.object(systemd, '_check_for_unit_changes', self.mock_none):
            with patch.object(systemd, '_unit_file_changed', self.mock_none):
                with patch.object(systemd, '_check_unmask', self.mock_none):
                    with patch.object(systemd, '_get_sysv_services', self.mock_empty_list):

                        # Has scopes available
                        with patch.object(salt.utils.systemd, 'has_scope', self.mock_true):

                            # Scope enabled, successful
                            with patch.dict(
                                    systemd.__salt__,
                                    {'config.get': self.mock_true,
                                     'cmd.run_all': self.mock_run_all_success}):
                                ret = func(self.unit_name, no_block=no_block)
                                self.assertTrue(ret)
                                self.mock_run_all_success.assert_called_with(
                                    scope_prefix + systemctl_command,
                                    **assert_kwargs)

                            # Scope enabled, failed
                            with patch.dict(
                                    systemd.__salt__,
                                    {'config.get': self.mock_true,
                                     'cmd.run_all': self.mock_run_all_failure}):
                                if action in ('stop', 'disable'):
                                    ret = func(self.unit_name, no_block=no_block)
                                    self.assertFalse(ret)
                                else:
                                    self.assertRaises(
                                        CommandExecutionError,
                                        func,
                                        self.unit_name,
                                        no_block=no_block)
                                self.mock_run_all_failure.assert_called_with(
                                    scope_prefix + systemctl_command,
                                    **assert_kwargs)

                            # Scope disabled, successful
                            with patch.dict(
                                    systemd.__salt__,
                                    {'config.get': self.mock_false,
                                     'cmd.run_all': self.mock_run_all_success}):
                                ret = func(self.unit_name, no_block=no_block)
                                self.assertTrue(ret)
                                self.mock_run_all_success.assert_called_with(
                                    systemctl_command,
                                    **assert_kwargs)

                            # Scope disabled, failed
                            with patch.dict(
                                    systemd.__salt__,
                                    {'config.get': self.mock_false,
                                     'cmd.run_all': self.mock_run_all_failure}):
                                if action in ('stop', 'disable'):
                                    ret = func(self.unit_name, no_block=no_block)
                                    self.assertFalse(ret)
                                else:
                                    self.assertRaises(
                                        CommandExecutionError,
                                        func,
                                        self.unit_name,
                                        no_block=no_block)
                                self.mock_run_all_failure.assert_called_with(
                                    systemctl_command,
                                    **assert_kwargs)

                        # Does not have scopes available
                        with patch.object(salt.utils.systemd, 'has_scope', self.mock_false):

                            # The results should be the same irrespective of
                            # whether or not scope is enabled, since scope is not
                            # available, so we repeat the below tests with it both
                            # enabled and disabled.
                            for scope_mock in (self.mock_true, self.mock_false):

                                # Successful
                                with patch.dict(
                                        systemd.__salt__,
                                        {'config.get': scope_mock,
                                         'cmd.run_all': self.mock_run_all_success}):
                                    ret = func(self.unit_name, no_block=no_block)
                                    self.assertTrue(ret)
                                    self.mock_run_all_success.assert_called_with(
                                        systemctl_command,
                                        **assert_kwargs)

                                # Failed
                                with patch.dict(
                                        systemd.__salt__,
                                        {'config.get': scope_mock,
                                         'cmd.run_all': self.mock_run_all_failure}):
                                    if action in ('stop', 'disable'):
                                        ret = func(self.unit_name,
                                                   no_block=no_block)
                                        self.assertFalse(ret)
                                    else:
                                        self.assertRaises(
                                            CommandExecutionError,
                                            func,
                                            self.unit_name,
                                            no_block=no_block)
                                    self.mock_run_all_failure.assert_called_with(
                                        systemctl_command,
                                        **assert_kwargs)

    def _mask_unmask(self, action, runtime):
        '''
        Common code for mask/unmask tests
        '''
        # We want the traceback if the function name can't be found in the
        # systemd execution module, so don't provide a fallback value for the
        # call to getattr() here.
        func = getattr(systemd, action)
        # Remove trailing _ in "unmask_"
        action = action.rstrip('_').replace('_', '-')
        systemctl_command = ['systemctl', action]
        if runtime:
            systemctl_command.append('--runtime')
        systemctl_command.append(self.unit_name + '.service')
        scope_prefix = ['systemd-run', '--scope']

        args = [self.unit_name, runtime]

        masked_mock = self.mock_true if action == 'unmask' else self.mock_false

        with patch.object(systemd, '_check_for_unit_changes', self.mock_none):
            if action == 'unmask':
                mock_not_run = MagicMock(return_value={'retcode': 0,
                                                       'stdout': '',
                                                       'stderr': '',
                                                       'pid': 12345})
                with patch.dict(systemd.__salt__, {'cmd.run_all': mock_not_run}):
                    with patch.object(systemd, 'masked', self.mock_false):
                        # Test not masked (should take no action and return True)
                        self.assertTrue(systemd.unmask_(self.unit_name))
                        # Also should not have called cmd.run_all
                        self.assertTrue(mock_not_run.call_count == 0)

            with patch.object(systemd, 'masked', masked_mock):

                # Has scopes available
                with patch.object(salt.utils.systemd, 'has_scope', self.mock_true):

                    # Scope enabled, successful
                    with patch.dict(
                            systemd.__salt__,
                            {'config.get': self.mock_true,
                             'cmd.run_all': self.mock_run_all_success}):
                        ret = func(*args)
                        self.assertTrue(ret)
                        self.mock_run_all_success.assert_called_with(
                            scope_prefix + systemctl_command,
                            python_shell=False,
                            redirect_stderr=True)

                    # Scope enabled, failed
                    with patch.dict(
                            systemd.__salt__,
                            {'config.get': self.mock_true,
                             'cmd.run_all': self.mock_run_all_failure}):
                        self.assertRaises(
                            CommandExecutionError,
                            func, *args)
                        self.mock_run_all_failure.assert_called_with(
                            scope_prefix + systemctl_command,
                            python_shell=False,
                            redirect_stderr=True)

                    # Scope disabled, successful
                    with patch.dict(
                            systemd.__salt__,
                            {'config.get': self.mock_false,
                             'cmd.run_all': self.mock_run_all_success}):
                        ret = func(*args)
                        self.assertTrue(ret)
                        self.mock_run_all_success.assert_called_with(
                            systemctl_command,
                            python_shell=False,
                            redirect_stderr=True)

                    # Scope disabled, failed
                    with patch.dict(
                            systemd.__salt__,
                            {'config.get': self.mock_false,
                             'cmd.run_all': self.mock_run_all_failure}):
                        self.assertRaises(
                            CommandExecutionError,
                            func, *args)
                        self.mock_run_all_failure.assert_called_with(
                            systemctl_command,
                            python_shell=False,
                            redirect_stderr=True)

                # Does not have scopes available
                with patch.object(salt.utils.systemd, 'has_scope', self.mock_false):

                    # The results should be the same irrespective of
                    # whether or not scope is enabled, since scope is not
                    # available, so we repeat the below tests with it both
                    # enabled and disabled.
                    for scope_mock in (self.mock_true, self.mock_false):

                        # Successful
                        with patch.dict(
                                systemd.__salt__,
                                {'config.get': scope_mock,
                                 'cmd.run_all': self.mock_run_all_success}):
                            ret = func(*args)
                            self.assertTrue(ret)
                            self.mock_run_all_success.assert_called_with(
                                systemctl_command,
                                python_shell=False,
                                redirect_stderr=True)

                        # Failed
                        with patch.dict(
                                systemd.__salt__,
                                {'config.get': scope_mock,
                                 'cmd.run_all': self.mock_run_all_failure}):
                            self.assertRaises(
                                CommandExecutionError,
                                func, *args)
                            self.mock_run_all_failure.assert_called_with(
                                systemctl_command,
                                python_shell=False,
                                redirect_stderr=True)

    def test_start(self):
        self._change_state('start', no_block=False)
        self._change_state('start', no_block=True)

    def test_stop(self):
        self._change_state('stop', no_block=False)
        self._change_state('stop', no_block=True)

    def test_restart(self):
        self._change_state('restart', no_block=False)
        self._change_state('restart', no_block=True)

    def test_reload(self):
        self._change_state('reload_', no_block=False)
        self._change_state('reload_', no_block=True)

    def test_force_reload(self):
        self._change_state('force_reload', no_block=False)
        self._change_state('force_reload', no_block=True)

    def test_enable(self):
        self._change_state('enable', no_block=False)
        self._change_state('enable', no_block=True)

    def test_disable(self):
        self._change_state('disable', no_block=False)
        self._change_state('disable', no_block=True)

    def test_mask(self):
        self._mask_unmask('mask', False)

    def test_mask_runtime(self):
        self._mask_unmask('mask', True)

    def test_unmask(self):
        self._mask_unmask('unmask_', False)

    def test_unmask_runtime(self):
        self._mask_unmask('unmask_', True)
