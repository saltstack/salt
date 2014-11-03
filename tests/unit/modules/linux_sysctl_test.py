# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`jmoney <justin@saltstack.com>`
'''

# Import Salt Libs
from salt.modules import linux_sysctl
from salt.modules import systemd
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    mock_open,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Globals
linux_sysctl.__salt__ = {}
systemd.__context__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LinuxSysctlTestCase(TestCase):
    '''
    TestCase for salt.modules.linux_sysctl module
    '''

    def test_get(self):
        '''
        Tests the return of get function
        '''
        mock_cmd = MagicMock(return_value=1)
        with patch.dict(linux_sysctl.__salt__, {'cmd.run': mock_cmd}):
            self.assertEqual(linux_sysctl.get('net.ipv4.ip_forward'), 1)

    @patch('os.path.exists', MagicMock(return_value=False))
    def test_assign_proc_sys_failed(self):
        '''
        Tests if /proc/sys/<kernel-subsystem> exists or not
        '''
        cmd = {'pid': 1337, 'retcode': 0, 'stderr': '',
               'stdout': 'net.ipv4.ip_forward = 1'}
        mock_cmd = MagicMock(return_value=cmd)
        with patch.dict(linux_sysctl.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertRaises(CommandExecutionError,
                              linux_sysctl.assign,
                              'net.ipv4.ip_forward', 1)

    @patch('os.path.exists', MagicMock(return_value=True))
    def test_assign_cmd_failed(self):
        '''
        Tests if the assignment was successful or not
        '''
        cmd = {'pid': 1337, 'retcode': 0, 'stderr':
               'sysctl: setting key "net.ipv4.ip_forward": Invalid argument',
               'stdout': 'net.ipv4.ip_forward = backward'}
        mock_cmd = MagicMock(return_value=cmd)
        with patch.dict(linux_sysctl.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertRaises(CommandExecutionError,
                              linux_sysctl.assign,
                              'net.ipv4.ip_forward', 'backward')

    @patch('os.path.exists', MagicMock(return_value=True))
    def test_assign_success(self):
        '''
        Tests the return of successful assign function
        '''
        cmd = {'pid': 1337, 'retcode': 0, 'stderr': '',
               'stdout': 'net.ipv4.ip_forward = 1'}
        ret = {'net.ipv4.ip_forward': '1'}
        mock_cmd = MagicMock(return_value=cmd)
        with patch.dict(linux_sysctl.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(linux_sysctl.assign(
                'net.ipv4.ip_forward', 1), ret)

    @patch('os.path.isfile', MagicMock(return_value=False))
    def test_persist_no_conf_failure(self):
        '''
        Tests adding of config file failure
        '''
        with patch('salt.utils.fopen', mock_open()) as m_open:
            helper_open = m_open()
            helper_open.write.assertRaises(CommandExecutionError,
                                           linux_sysctl.persist,
                                           'net.ipv4.ip_forward',
                                           1, config=None)

    @patch('os.path.isfile', MagicMock(return_value=False))
    def test_persist_no_conf_success(self):
        '''
        Tests successful add of config file when previously not one
        '''
        asn_cmd = {'pid': 1337, 'retcode': 0, 'stderr': '',
               'stdout': 'net.ipv4.ip_forward = 1'}
        mock_asn_cmd = MagicMock(return_value=asn_cmd)

        sys_cmd = 'systemd 208\n+PAM +LIBWRAP'
        mock_sys_cmd = MagicMock(return_value=sys_cmd)

        with patch('salt.utils.fopen', mock_open()) as m_open:
            with patch.dict(linux_sysctl.__salt__,
                            {'cmd.run_stdout': mock_sys_cmd,
                             'cmd.run_all': mock_asn_cmd}):
                with patch.dict(systemd.__context__,
                                {'systemd.sd_booted': True}):
                    linux_sysctl.persist('net.ipv4.ip_forward', 1)
                    helper_open = m_open()
                    helper_open.write.assert_called_once_with(
                        '#\n# Kernel sysctl configuration\n#\n')

    @patch('os.path.isfile', MagicMock(return_value=True))
    def test_persist_read_conf_success(self):
        '''
        Tests sysctl.conf read success
        '''
        asn_cmd = {'pid': 1337, 'retcode': 0, 'stderr': '',
               'stdout': 'net.ipv4.ip_forward = 1'}
        mock_asn_cmd = MagicMock(return_value=asn_cmd)

        sys_cmd = 'systemd 208\n+PAM +LIBWRAP'
        mock_sys_cmd = MagicMock(return_value=sys_cmd)

        with patch('salt.utils.fopen', mock_open()):
            with patch.dict(linux_sysctl.__salt__,
                            {'cmd.run_stdout': mock_sys_cmd,
                             'cmd.run_all': mock_asn_cmd}):
                with patch.dict(systemd.__context__,
                                {'systemd.sd_booted': True}):
                    self.assertEqual(linux_sysctl.persist(
                                     'net.ipv4.ip_forward', 1), 'Updated')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(LinuxSysctlTestCase, needs_daemon=False)
