# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import system

# Globals
system.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SystemTestCase(TestCase):
    '''
    Test cases for salt.modules.system
    '''
    def test_halt(self):
        '''
        Test to halt a running system
        '''
        with patch.dict(system.__salt__,
                        {'cmd.run': MagicMock(return_value='A')}):
            self.assertEqual(system.halt(), 'A')

    def test_init(self):
        '''
        Test to change the system runlevel on sysV compatible systems
        '''
        with patch.dict(system.__salt__,
                        {'cmd.run': MagicMock(return_value='A')}):
            self.assertEqual(system.init('r'), 'A')

    def test_poweroff(self):
        '''
        Test to poweroff a running system
        '''
        with patch.dict(system.__salt__,
                        {'cmd.run': MagicMock(return_value='A')}):
            self.assertEqual(system.poweroff(), 'A')

    @patch.dict(system.__salt__, {'cmd.run': MagicMock(return_value='A')})
    def test_reboot(self):
        '''
        Test to reboot the system with shutdown -r
        '''
        self.assertEqual(system.reboot(), 'A')
        system.__salt__['cmd.run'].assert_called_with(
            ['shutdown', '-r', 'now'], python_shell=False)

    @patch.dict(system.__salt__, {'cmd.run': MagicMock(return_value='A')})
    def test_reboot_with_delay(self):
        '''
        Test to reboot the system using shutdown -r with a delay
        '''
        self.assertEqual(system.reboot(at_time=5), 'A')
        system.__salt__['cmd.run'].assert_called_with(
            ['shutdown', '-r', '5'], python_shell=False)

    def test_shutdown(self):
        '''
        Test to shutdown a running system
        '''
        with patch.dict(system.__salt__,
                        {'cmd.run': MagicMock(return_value='A')}):
            self.assertEqual(system.shutdown(), 'A')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SystemTestCase, needs_daemon=False)
