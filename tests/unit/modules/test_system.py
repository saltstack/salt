# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.modules.system as system


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SystemTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.system
    '''
    loader_module = system

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
        Test to reboot the system with shutdown -r
        '''
        cmd_mock = MagicMock(return_value='A')
        with patch.dict(system.__salt__, {'cmd.run': cmd_mock}):
            self.assertEqual(system.reboot(), 'A')
        cmd_mock.assert_called_with(['shutdown', '-r', 'now'], python_shell=False)

    def test_reboot_with_delay(self):
        '''
        Test to reboot the system using shutdown -r with a delay
        '''
        cmd_mock = MagicMock(return_value='A')
        with patch.dict(system.__salt__, {'cmd.run': cmd_mock}):
            self.assertEqual(system.reboot(at_time=5), 'A')
        cmd_mock.assert_called_with(['shutdown', '-r', '5'], python_shell=False)

    def test_shutdown(self):
        '''
        Test to shutdown a running system
        '''
        with patch.dict(system.__salt__,
                        {'cmd.run': MagicMock(return_value='A')}):
            self.assertEqual(system.shutdown(), 'A')
