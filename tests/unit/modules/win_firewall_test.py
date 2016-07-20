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
    patch
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

    # 'disable' function tests: 1

    def test_disable(self):
        '''
        Test if it disable firewall profile :(default: allprofiles)
        '''
        mock_cmd = MagicMock(return_value='Ok.')
        with patch.dict(win_firewall.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(win_firewall.disable())

    # 'enable' function tests: 1

    def test_enable(self):
        '''
        Test if it enable firewall profile :(default: allprofiles)
        '''
        mock_cmd = MagicMock(return_value='Ok.')
        with patch.dict(win_firewall.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(win_firewall.enable())

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

    # 'add_rule' function tests: 1

    def test_add_rule(self):
        '''
        Test if it add a new firewall rule
        '''
        mock_cmd = MagicMock(return_value='Ok.')
        with patch.dict(win_firewall.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(win_firewall.add_rule("test", "8080"))

    # 'delete_rule' function tests: 1

    def test_delete_rule(self):
        '''
        Test if it delete an existing firewall rule
        '''
        mock_cmd = MagicMock(return_value='Ok.')
        with patch.dict(win_firewall.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(win_firewall.delete_rule("test", "8080", "tcp",
                                                     "in"))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinFirewallTestCase, needs_daemon=False)
