# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    call
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import win_firewall

# Globals
win_firewall.__salt__ = {}

# Make sure this module runs on Windows system
IS_WIN = win_firewall.__virtual__()


@skipIf(not IS_WIN, "This test case runs only on Windows system")
class WinFirewallTestCase(TestCase):
    '''
    Test cases for salt.modules.win_firewall
    '''
    # 'get_config' function tests: 1

    def test_get_config(self):
        '''
        Test if it get the status of all the firewall profiles
        '''
        mock_cmd = MagicMock(return_value='')
        with patch.dict(win_firewall.__salt__, {'cmd.run': mock_cmd}):
            self.assertDictEqual(win_firewall.get_config(), {})
            mock_cmd.assert_called_once_with(['netsh', 'advfirewall', 'show', 'allprofiles'], python_shell=False)

    # 'disable' function tests: 1

    def test_disable(self):
        '''
        Test if it disable firewall profile :(default: allprofiles)
        '''
        mock_cmd = MagicMock(return_value='Ok.')
        with patch.dict(win_firewall.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(win_firewall.disable())
            mock_cmd.assert_called_once_with(['netsh', 'advfirewall', 'set', 'allprofiles', 'state', 'off'],
                                             python_shell=False)

    # 'enable' function tests: 1

    def test_enable(self):
        '''
        Test if it enable firewall profile :(default: allprofiles)
        '''
        mock_cmd = MagicMock(return_value='Ok.')
        with patch.dict(win_firewall.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(win_firewall.enable())
            mock_cmd.assert_called_once_with(['netsh', 'advfirewall', 'set', 'allprofiles', 'state', 'on'],
                                             python_shell=False)

    # 'get_rule' function tests: 1

    def test_get_rule(self):
        '''
        Test if it get firewall rule(s) info
        '''
        val = 'No rules match the specified criteria.'
        mock_cmd = MagicMock(side_effect=['salt', val])
        with patch.dict(win_firewall.__salt__, {'cmd.run': mock_cmd}):
            self.assertDictEqual(win_firewall.get_rule(), {'all': 'salt'})

            self.assertFalse(win_firewall.get_rule())

            calls = [
                call(['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=all'], python_shell=False),
                call(['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=all'], python_shell=False)
            ]
            mock_cmd.assert_has_calls(calls)

    # 'add_rule' function tests: 1

    def test_add_rule(self):
        '''
        Test if it add a new firewall rule
        '''
        mock_cmd = MagicMock(return_value='Ok.')
        with patch.dict(win_firewall.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(win_firewall.add_rule("test", "8080"))
            mock_cmd.assert_called_once_with(['netsh', 'advfirewall', 'firewall', 'add', 'rule', 'name=test',
                                              'protocol=tcp', 'dir=in', 'action=allow', 'localport=8080'],
                                             python_shell=False)

    def test_add_rule_icmp4(self):
        '''
        Test if it add a new firewall rule
        '''
        mock_cmd = MagicMock(return_value='Ok.')
        with patch.dict(win_firewall.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(win_firewall.add_rule("test", "1", protocol='icmpv4'))
            mock_cmd.assert_called_once_with(['netsh', 'advfirewall', 'firewall', 'add', 'rule', 'name=test',
                                              'protocol=icmpv4', 'dir=in', 'action=allow'],
                                             python_shell=False)

    def test_add_rule_icmp6(self):
        '''
        Test if it add a new firewall rule
        '''
        mock_cmd = MagicMock(return_value='Ok.')
        with patch.dict(win_firewall.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(win_firewall.add_rule("test", "1", protocol='icmpv6'))
            mock_cmd.assert_called_once_with(['netsh', 'advfirewall', 'firewall', 'add', 'rule', 'name=test',
                                              'protocol=icmpv6', 'dir=in', 'action=allow'],
                                             python_shell=False)

    def test_add_rule_icmp4_any(self):
        '''
        Test if it add a new firewall rule
        '''
        mock_cmd = MagicMock(return_value='Ok.')
        with patch.dict(win_firewall.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(win_firewall.add_rule("test", "1", protocol='icmpv4:any,any'))
            mock_cmd.assert_called_once_with(['netsh', 'advfirewall', 'firewall', 'add', 'rule', 'name=test',
                                              'protocol=icmpv4:any,any', 'dir=in', 'action=allow'],
                                             python_shell=False)

    # 'delete_rule' function tests: 1

    def test_delete_rule(self):
        '''
        Test if it delete an existing firewall rule
        '''
        mock_cmd = MagicMock(return_value='Ok.')
        with patch.dict(win_firewall.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(win_firewall.delete_rule("test", "8080", "tcp",
                                                     "in"))
            mock_cmd.assert_called_once_with(['netsh', 'advfirewall', 'firewall', 'delete', 'rule', 'name=test',
                                              'protocol=tcp', 'dir=in', 'localport=8080'], python_shell=False)

    def test_delete_rule_icmp4(self):
        '''
        Test if it deletes a new firewall rule
        '''
        mock_cmd = MagicMock(return_value='Ok.')
        with patch.dict(win_firewall.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(win_firewall.delete_rule("test", "1", protocol='icmpv4'))
            mock_cmd.assert_called_once_with(['netsh', 'advfirewall', 'firewall', 'delete', 'rule', 'name=test',
                                              'protocol=icmpv4', 'dir=in'],
                                             python_shell=False)

    def test_delete_rule_icmp6(self):
        '''
        Test if it deletes a new firewall rule
        '''
        mock_cmd = MagicMock(return_value='Ok.')
        with patch.dict(win_firewall.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(win_firewall.delete_rule("test", "1", protocol='icmpv6'))
            mock_cmd.assert_called_once_with(['netsh', 'advfirewall', 'firewall', 'delete', 'rule', 'name=test',
                                              'protocol=icmpv6', 'dir=in'],
                                             python_shell=False)

    def test_delete_rule_icmp4_any(self):
        '''
        Test if it deletes a new firewall rule
        '''
        mock_cmd = MagicMock(return_value='Ok.')
        with patch.dict(win_firewall.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(win_firewall.delete_rule("test", "1", protocol='icmpv4:any,any'))
            mock_cmd.assert_called_once_with(['netsh', 'advfirewall', 'firewall', 'delete', 'rule', 'name=test',
                                              'protocol=icmpv4:any,any', 'dir=in'],
                                             python_shell=False)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinFirewallTestCase, needs_daemon=False)
