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

    def test_reboot(self):
        '''
        Test to reboot the system using the 'reboot' command
        '''
        with patch.dict(system.__salt__,
                        {'cmd.run': MagicMock(return_value='A')}):
            self.assertEqual(system.reboot(), 'A')

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
