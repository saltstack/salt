# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.modules import status
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    mock_open,
)

ensure_in_syspath('../../')

# Globals
status.__salt__ = {}
status.__grains__ = {}


class StatusTestCase(TestCase):
    '''
    test modules.status functions
    '''
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

    @patch('salt.utils.is_linux', MagicMock(return_value=True))
    @patch('salt.utils.is_sunos', MagicMock(return_value=False))
    @patch('salt.utils.is_darwin', MagicMock(return_value=False))
    @patch('salt.utils.is_freebsd', MagicMock(return_value=False))
    @patch('salt.utils.is_openbsd', MagicMock(return_value=False))
    @patch('salt.utils.is_netbsd', MagicMock(return_value=False))
    def test_uptime_linux(self):
        '''
        Test modules.status.uptime function for Linux
        '''
        m = self._set_up_test_uptime()

        with patch.dict(status.__salt__, {'cmd.run': MagicMock(return_value="1\n2\n3")}):
            with patch('time.time', MagicMock(return_value=m.now)):
                with patch('os.path.exists', MagicMock(return_value=True)):
                    proc_uptime = '{0} {1}'.format(m.ut, m.idle)
                    with patch('salt.utils.fopen', mock_open(read_data=proc_uptime)):
                        ret = status.uptime()
                        self.assertDictEqual(ret, m.ret)

                with patch('os.path.exists', MagicMock(return_value=False)):
                    with self.assertRaises(CommandExecutionError):
                        status.uptime()

    @patch('salt.utils.is_linux', MagicMock(return_value=False))
    @patch('salt.utils.is_sunos', MagicMock(return_value=True))
    @patch('salt.utils.is_darwin', MagicMock(return_value=False))
    @patch('salt.utils.is_freebsd', MagicMock(return_value=False))
    @patch('salt.utils.is_openbsd', MagicMock(return_value=False))
    @patch('salt.utils.is_netbsd', MagicMock(return_value=False))
    def test_uptime_sunos(self):
        '''
        Test modules.status.uptime function for SunOS
        '''
        m = self._set_up_test_uptime()
        m2 = self._set_up_test_uptime_sunos()

        with patch.dict(status.__salt__, {'cmd.run': MagicMock(return_value="1\n2\n3"),
                                          'cmd.run_all': MagicMock(return_value=m2.ret)}):
            with patch('time.time', MagicMock(return_value=m.now)):
                ret = status.uptime()
                self.assertDictEqual(ret, m.ret)

    @patch('salt.utils.is_linux', MagicMock(return_value=False))
    @patch('salt.utils.is_sunos', MagicMock(return_value=False))
    @patch('salt.utils.is_darwin', MagicMock(return_value=True))
    @patch('salt.utils.is_freebsd', MagicMock(return_value=False))
    @patch('salt.utils.is_openbsd', MagicMock(return_value=False))
    @patch('salt.utils.is_netbsd', MagicMock(return_value=False))
    def test_uptime_macos(self):
        '''
        Test modules.status.uptime function for macOS
        '''
        m = self._set_up_test_uptime()

        kern_boottime = ('{{ sec = {0}, usec = {1:0<6} }} Mon Oct 03 03:09:18.23 2016'
                         ''.format(*str(m.now - m.ut).split('.')))
        with patch.dict(status.__salt__, {'cmd.run': MagicMock(return_value="1\n2\n3"),
                                          'sysctl.get': MagicMock(return_value=kern_boottime)}):
            with patch('time.time', MagicMock(return_value=m.now)):
                ret = status.uptime()
                self.assertDictEqual(ret, m.ret)

        with patch.dict(status.__salt__, {'sysctl.get': MagicMock(return_value='')}):
            with self.assertRaises(CommandExecutionError):
                status.uptime()

    @patch('salt.utils.is_linux', MagicMock(return_value=False))
    @patch('salt.utils.is_sunos', MagicMock(return_value=False))
    @patch('salt.utils.is_darwin', MagicMock(return_value=False))
    @patch('salt.utils.is_freebsd', MagicMock(return_value=False))
    @patch('salt.utils.is_openbsd', MagicMock(return_value=False))
    @patch('salt.utils.is_netbsd', MagicMock(return_value=False))
    def test_uptime_return_success_not_supported(self):
        '''
        Test modules.status.uptime function for other platforms
        '''
        with self.assertRaises(CommandExecutionError):
            status.uptime()


if __name__ == '__main__':
    from integration import run_tests
    run_tests(StatusTestCase, needs_daemon=False)
