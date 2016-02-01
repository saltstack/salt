# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from salt.exceptions import CommandExecutionError
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import systemd

# Globals
systemd.__salt__ = {}
systemd.__context__ = {}

_SYSTEMCTL_STATUS = {
    'sshd.service': '''\
* sshd.service - OpenSSH Daemon
   Loaded: loaded (/usr/lib/systemd/system/sshd.service; disabled; vendor preset: disabled)
   Active: inactive (dead)''',

    'foo.service': '''\
* foo.service
   Loaded: not-found (Reason: No such file or directory)
   Active: inactive (dead)'''
}

_LIST_UNIT_FILES = '''\
service1.service                           enabled
service2.service                           disabled
service3.service                           static
timer1.timer                               enabled
timer2.timer                               disabled
timer3.timer                               static'''


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SystemdTestCase(TestCase):
    '''
        Test case for salt.modules.systemd
    '''
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
            self.assertRaisesRegexp(
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
        sysv_enabled_mock = MagicMock(side_effect=lambda x: x == 'baz')

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
        sysv_enabled_mock = MagicMock(side_effect=lambda x: x == 'baz')

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
        with patch.object(systemd, '_systemctl_status', mock):
            self.assertTrue(systemd.available('sshd.service'))
            self.assertFalse(systemd.available('foo.service'))

    def test_missing(self):
        '''
            Test to the inverse of service.available.
        '''
        mock = MagicMock(side_effect=lambda x: _SYSTEMCTL_STATUS[x])
        with patch.object(systemd, '_systemctl_status', mock):
            self.assertFalse(systemd.missing('sshd.service'))
            self.assertTrue(systemd.missing('foo.service'))

    def test_show(self):
        '''
            Test to show properties of one or more units/jobs or the manager
        '''
        mock = MagicMock(return_value="a = b , c = d")
        with patch.dict(systemd.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(systemd.show("sshd"), {'a ': ' b , c = d'})

    def test_execs(self):
        '''
            Test to return a list of all files specified as ``ExecStart``
            for all services
        '''
        mock = MagicMock(return_value=["a", "b"])
        with patch.object(systemd, 'get_all', mock):
            mock = MagicMock(return_value={"ExecStart": {"path": "c"}})
            with patch.object(systemd, 'show', mock):
                self.assertDictEqual(systemd.execs(), {'a': 'c', 'b': 'c'})

if __name__ == '__main__':
    from integration import run_tests
    run_tests(SystemdTestCase, needs_daemon=False)
