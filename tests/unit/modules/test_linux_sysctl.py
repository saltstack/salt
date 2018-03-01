# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`jmoney <justin@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.linux_sysctl as linux_sysctl
import salt.modules.systemd as systemd
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    mock_open,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LinuxSysctlTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.modules.linux_sysctl module
    '''

    def setup_loader_modules(self):
        return {linux_sysctl: {}, systemd: {}}

    def test_get(self):
        '''
        Tests the return of get function
        '''
        mock_cmd = MagicMock(return_value=1)
        with patch.dict(linux_sysctl.__salt__, {'cmd.run': mock_cmd}):
            self.assertEqual(linux_sysctl.get('net.ipv4.ip_forward'), 1)

    def test_assign_proc_sys_failed(self):
        '''
        Tests if /proc/sys/<kernel-subsystem> exists or not
        '''
        with patch('os.path.exists', MagicMock(return_value=False)):
            cmd = {'pid': 1337, 'retcode': 0, 'stderr': '',
                   'stdout': 'net.ipv4.ip_forward = 1'}
            mock_cmd = MagicMock(return_value=cmd)
            with patch.dict(linux_sysctl.__salt__, {'cmd.run_all': mock_cmd}):
                self.assertRaises(CommandExecutionError,
                                  linux_sysctl.assign,
                                  'net.ipv4.ip_forward', 1)

    def test_assign_cmd_failed(self):
        '''
        Tests if the assignment was successful or not
        '''
        with patch('os.path.exists', MagicMock(return_value=True)):
            cmd = {'pid': 1337, 'retcode': 0, 'stderr':
                   'sysctl: setting key "net.ipv4.ip_forward": Invalid argument',
                   'stdout': 'net.ipv4.ip_forward = backward'}
            mock_cmd = MagicMock(return_value=cmd)
            with patch.dict(linux_sysctl.__salt__, {'cmd.run_all': mock_cmd}):
                self.assertRaises(CommandExecutionError,
                                  linux_sysctl.assign,
                                  'net.ipv4.ip_forward', 'backward')

    def test_assign_success(self):
        '''
        Tests the return of successful assign function
        '''
        with patch('os.path.exists', MagicMock(return_value=True)):
            cmd = {'pid': 1337, 'retcode': 0, 'stderr': '',
                   'stdout': 'net.ipv4.ip_forward = 1'}
            ret = {'net.ipv4.ip_forward': '1'}
            mock_cmd = MagicMock(return_value=cmd)
            with patch.dict(linux_sysctl.__salt__, {'cmd.run_all': mock_cmd}):
                self.assertEqual(linux_sysctl.assign(
                    'net.ipv4.ip_forward', 1), ret)

    def test_persist_no_conf_failure(self):
        '''
        Tests adding of config file failure
        '''
        asn_cmd = {'pid': 1337, 'retcode': 0,
            'stderr': "sysctl: permission denied", 'stdout': ''}
        mock_asn_cmd = MagicMock(return_value=asn_cmd)
        cmd = "sysctl -w net.ipv4.ip_forward=1"
        mock_cmd = MagicMock(return_value=cmd)
        with patch.dict(linux_sysctl.__salt__, {'cmd.run_stdout': mock_cmd,
                                                'cmd.run_all': mock_asn_cmd}):
            with patch('salt.utils.files.fopen', mock_open()) as m_open:
                self.assertRaises(CommandExecutionError,
                                  linux_sysctl.persist,
                                  'net.ipv4.ip_forward',
                                  1, config=None)

    def test_persist_no_conf_success(self):
        '''
        Tests successful add of config file when previously not one
        '''
        with patch('os.path.isfile', MagicMock(return_value=False)), \
                patch('os.path.exists', MagicMock(return_value=True)):
            asn_cmd = {'pid': 1337, 'retcode': 0, 'stderr': '',
                   'stdout': 'net.ipv4.ip_forward = 1'}
            mock_asn_cmd = MagicMock(return_value=asn_cmd)

            sys_cmd = 'systemd 208\n+PAM +LIBWRAP'
            mock_sys_cmd = MagicMock(return_value=sys_cmd)

            with patch('salt.utils.files.fopen', mock_open()) as m_open:
                with patch.dict(linux_sysctl.__context__, {'salt.utils.systemd.version': 232}):
                    with patch.dict(linux_sysctl.__salt__,
                                    {'cmd.run_stdout': mock_sys_cmd,
                                     'cmd.run_all': mock_asn_cmd}):
                        with patch.dict(systemd.__context__,
                                        {'salt.utils.systemd.booted': True,
                                         'salt.utils.systemd.version': 232}):
                            linux_sysctl.persist('net.ipv4.ip_forward', 1)
                            helper_open = m_open()
                            helper_open.write.assert_called_once_with(
                                '#\n# Kernel sysctl configuration\n#\n')

    def test_persist_read_conf_success(self):
        '''
        Tests sysctl.conf read success
        '''
        with patch('os.path.isfile', MagicMock(return_value=True)), \
                patch('os.path.exists', MagicMock(return_value=True)):
            asn_cmd = {'pid': 1337, 'retcode': 0, 'stderr': '',
                   'stdout': 'net.ipv4.ip_forward = 1'}
            mock_asn_cmd = MagicMock(return_value=asn_cmd)

            sys_cmd = 'systemd 208\n+PAM +LIBWRAP'
            mock_sys_cmd = MagicMock(return_value=sys_cmd)

            with patch('salt.utils.files.fopen', mock_open()):
                with patch.dict(linux_sysctl.__context__, {'salt.utils.systemd.version': 232}):
                    with patch.dict(linux_sysctl.__salt__,
                                    {'cmd.run_stdout': mock_sys_cmd,
                                     'cmd.run_all': mock_asn_cmd}):
                        with patch.dict(systemd.__context__,
                                        {'salt.utils.systemd.booted': True}):
                            self.assertEqual(linux_sysctl.persist(
                                             'net.ipv4.ip_forward', 1), 'Updated')
