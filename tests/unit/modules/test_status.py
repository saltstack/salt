# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Libs
import salt.utils.platform
import salt.modules.status as status
from salt.exceptions import CommandExecutionError
from salt.ext import six

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
            proc_uptime = salt.utils.stringutils.to_str('{0} {1}'.format(m.ut, m.idle))

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
                         ''.format(*six.text_type(m.now - m.ut).split('.')))
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

    def _set_up_test_cpustats_openbsd(self):
        '''
        Define mock data for status.cpustats on OpenBSD
        '''
        class MockData(object):
            '''
            Store mock data
            '''

        m = MockData()
        m.ret = {
           '0': {
                'User': '0.0%',
                'Nice': '0.0%',
                'System': '4.5%',
                'Interrupt': '0.5%',
                'Idle': '95.0%',
            }
        }

        return m

    def test_cpustats_openbsd(self):
        '''
        Test modules.status.cpustats function for OpenBSD
        '''
        m = self._set_up_test_cpustats_openbsd()

        systat = '\n' \
                 '\n' \
                 '   1 users Load 0.20 0.07 0.05                        salt.localdomain 09:42:42\n' \
                 'CPU                User           Nice        System     Interrupt          Idle\n' \
                 '0                  0.0%           0.0%          4.5%          0.5%         95.0%\n'

        with patch.multiple(salt.utils.platform,
                            is_linux=MagicMock(return_value=False),
                            is_sunos=MagicMock(return_value=False),
                            is_darwin=MagicMock(return_value=False),
                            is_freebsd=MagicMock(return_value=False),
                            is_openbsd=MagicMock(return_value=True),
                            is_netbsd=MagicMock(return_value=False)), \
                    patch('salt.utils.path.which', MagicMock(return_value=True)), \
                    patch.dict(status.__grains__, {'kernel': 'OpenBSD'}), \
                    patch.dict(status.__salt__, {'cmd.run': MagicMock(return_value=systat)}):
            ret = status.cpustats()
            self.assertDictEqual(ret, m.ret)

    def _set_up_test_cpuinfo_bsd(self):
        class MockData(object):
            '''
            Store mock data
            '''

        m = MockData()
        m.ret = {
          'hw.model': 'Intel(R) Core(TM) i5-7287U CPU @ 3.30GHz',
          'hw.ncpu': '4',
        }

        return m

    def test_cpuinfo_freebsd(self):
        m = self._set_up_test_cpuinfo_bsd()
        sysctl = 'hw.model:Intel(R) Core(TM) i5-7287U CPU @ 3.30GHz\nhw.ncpu:4'

        with patch.dict(status.__grains__, {'kernel': 'FreeBSD'}):
            with patch.dict(status.__salt__, {'cmd.run': MagicMock(return_value=sysctl)}):
                ret = status.cpuinfo()
                self.assertDictEqual(ret, m.ret)

    def test_cpuinfo_openbsd(self):
        m = self._set_up_test_cpuinfo_bsd()
        sysctl = 'hw.model=Intel(R) Core(TM) i5-7287U CPU @ 3.30GHz\nhw.ncpu=4'

        for bsd in ['NetBSD', 'OpenBSD']:
            with patch.dict(status.__grains__, {'kernel': bsd}):
                with patch.dict(status.__salt__, {'cmd.run': MagicMock(return_value=sysctl)}):
                    ret = status.cpuinfo()
                    self.assertDictEqual(ret, m.ret)

    def _set_up_test_meminfo_openbsd(self):
        class MockData(object):
            '''
            Store mock data
            '''

        m = MockData()
        m.ret = {
            'active virtual pages': '355M',
            'free list size': '305M',
            'page faults': '845',
            'pages reclaimed': '1',
            'pages paged in': '2',
            'pages paged out': '3',
            'pages freed': '4',
            'pages scanned': '5'
        }

        return m

    def test_meminfo_openbsd(self):
        m = self._set_up_test_meminfo_openbsd()
        vmstat = ' procs    memory       page                    disks    traps          cpu\n' \
                 ' r   s   avm     fre  flt  re  pi  po  fr  sr cd0 sd0  int   sys   cs us sy id\n' \
                 ' 2 103  355M    305M  845   1   2   3   4   5   0   1   21   682   86  1  1 98'

        with patch.dict(status.__grains__, {'kernel': 'OpenBSD'}):
            with patch.dict(status.__salt__, {'cmd.run': MagicMock(return_value=vmstat)}):
                ret = status.meminfo()
                self.assertDictEqual(ret, m.ret)
