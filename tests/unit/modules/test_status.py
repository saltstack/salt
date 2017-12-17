# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Libs
import salt.utils.platform
import salt.modules.status as status
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch,
    mock_open,
)


class StatusTestCase(TestCase, LoaderModuleMockMixin):
    '''
    test modules.status functions
    '''
    def setup_loader_modules(self):
        return {status: {}}

    def _set_up_test_uptime(self):
        '''
        Define common mock data for status.uptime tests
        '''
        class MockData(object):
            '''
            Store mock data
            '''

        m = MockData()
        m.now = 1477004312
        m.ut = 1540154.00
        m.idle = 3047777.32
        m.ret = {
            'users': 3,
            'seconds': 1540154,
            'since_t': 1475464158,
            'days': 17,
            'since_iso': '2016-10-03T03:09:18',
            'time': '19:49',
        }

        return m

    def _set_up_test_uptime_sunos(self):
        '''
        Define common mock data for cmd.run_all for status.uptime on SunOS
        '''
        class MockData(object):
            '''
            Store mock data
            '''

        m = MockData()
        m.ret = {
            'retcode': 0,
            'stdout': 'unix:0:system_misc:boot_time    1475464158',
        }

        return m

    def test_uptime_linux(self):
        '''
        Test modules.status.uptime function for Linux
        '''
        m = self._set_up_test_uptime()

        with patch.multiple(salt.utils.platform,
                            is_linux=MagicMock(return_value=True),
                            is_sunos=MagicMock(return_value=False),
                            is_darwin=MagicMock(return_value=False),
                            is_freebsd=MagicMock(return_value=False),
                            is_openbsd=MagicMock(return_value=False),
                            is_netbsd=MagicMock(return_value=False)), \
                patch('salt.utils.path.which', MagicMock(return_value=True)), \
                patch.dict(status.__salt__, {'cmd.run': MagicMock(return_value=os.linesep.join(['1', '2', '3']))}), \
                patch('time.time', MagicMock(return_value=m.now)), \
                patch('os.path.exists', MagicMock(return_value=True)):
            proc_uptime = '{0} {1}'.format(m.ut, m.idle)

            with patch('salt.utils.files.fopen', mock_open(read_data=proc_uptime)):
                ret = status.uptime()
                self.assertDictEqual(ret, m.ret)
            with patch('os.path.exists', MagicMock(return_value=False)):
                with self.assertRaises(CommandExecutionError):
                    status.uptime()

    def test_uptime_sunos(self):
        '''
        Test modules.status.uptime function for SunOS
        '''
        m = self._set_up_test_uptime()
        m2 = self._set_up_test_uptime_sunos()
        with patch.multiple(salt.utils.platform,
                            is_linux=MagicMock(return_value=False),
                            is_sunos=MagicMock(return_value=True),
                            is_darwin=MagicMock(return_value=False),
                            is_freebsd=MagicMock(return_value=False),
                            is_openbsd=MagicMock(return_value=False),
                            is_netbsd=MagicMock(return_value=False)), \
                patch('salt.utils.path.which', MagicMock(return_value=True)), \
                patch.dict(status.__salt__, {'cmd.run': MagicMock(return_value=os.linesep.join(['1', '2', '3'])),
                                             'cmd.run_all': MagicMock(return_value=m2.ret)}), \
                patch('time.time', MagicMock(return_value=m.now)):
            ret = status.uptime()
            self.assertDictEqual(ret, m.ret)

    def test_uptime_macos(self):
        '''
        Test modules.status.uptime function for macOS
        '''
        m = self._set_up_test_uptime()

        kern_boottime = ('{{ sec = {0}, usec = {1:0<6} }} Mon Oct 03 03:09:18.23 2016'
                         ''.format(*str(m.now - m.ut).split('.')))
        with patch.multiple(salt.utils.platform,
                            is_linux=MagicMock(return_value=False),
                            is_sunos=MagicMock(return_value=False),
                            is_darwin=MagicMock(return_value=True),
                            is_freebsd=MagicMock(return_value=False),
                            is_openbsd=MagicMock(return_value=False),
                            is_netbsd=MagicMock(return_value=False)), \
                patch('salt.utils.path.which', MagicMock(return_value=True)), \
                patch.dict(status.__salt__, {'cmd.run': MagicMock(return_value=os.linesep.join(['1', '2', '3'])),
                                             'sysctl.get': MagicMock(return_value=kern_boottime)}), \
                patch('time.time', MagicMock(return_value=m.now)):

            ret = status.uptime()
            self.assertDictEqual(ret, m.ret)

            with patch.dict(status.__salt__, {'sysctl.get': MagicMock(return_value='')}):
                with self.assertRaises(CommandExecutionError):
                    status.uptime()

    def test_uptime_return_success_not_supported(self):
        '''
        Test modules.status.uptime function for other platforms
        '''
        with patch.multiple(salt.utils.platform,
                            is_linux=MagicMock(return_value=False),
                            is_sunos=MagicMock(return_value=False),
                            is_darwin=MagicMock(return_value=False),
                            is_freebsd=MagicMock(return_value=False),
                            is_openbsd=MagicMock(return_value=False),
                            is_netbsd=MagicMock(return_value=False)):
            exc_mock = MagicMock(side_effect=CommandExecutionError)
            with self.assertRaises(CommandExecutionError):
                with patch.dict(status.__salt__, {'cmd.run': exc_mock}):
                    status.uptime()

    def _set_up_test_w_linux(self):
        '''
        Define mock data for status.w on Linux
        '''
        class MockData(object):
            '''
            Store mock data
            '''

        m = MockData()
        m.ret = [{
            'idle': '0s',
            'jcpu': '0.24s',
            'login': '13:42',
            'pcpu': '0.16s',
            'tty': 'pts/1',
            'user': 'root',
            'what': 'nmap -sV 10.2.2.2',
        }]

        return m

    def _set_up_test_w_bsd(self):
        '''
        Define mock data for status.w on Linux
        '''
        class MockData(object):
            '''
            Store mock data
            '''

        m = MockData()
        m.ret = [{
            'idle': '0',
            'from': '10.2.2.1',
            'login': '1:42PM',
            'tty': 'p1',
            'user': 'root',
            'what': 'nmap -sV 10.2.2.2',
        }]

        return m

    def test_w_linux(self):
        m = self._set_up_test_w_linux()
        w_output = 'root   pts/1  13:42    0s  0.24s  0.16s nmap -sV 10.2.2.2'

        with patch.dict(status.__grains__, {'kernel': 'Linux'}):
            with patch.dict(status.__salt__, {'cmd.run': MagicMock(return_value=w_output)}):
                ret = status.w()
                self.assertListEqual(ret, m.ret)

    def test_w_bsd(self):
        m = self._set_up_test_w_bsd()
        w_output = 'root   p1 10.2.2.1    1:42PM  0 nmap -sV 10.2.2.2'

        for bsd in ['Darwin', 'FreeBSD', 'OpenBSD']:
            with patch.dict(status.__grains__, {'kernel': bsd}):
                with patch.dict(status.__salt__, {'cmd.run': MagicMock(return_value=w_output)}):
                    ret = status.w()
                    self.assertListEqual(ret, m.ret)
