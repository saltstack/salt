# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
from datetime import datetime

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')
# Import Salt Libs
from salt.modules import win_system

# Import 3rd Party Libs
try:
    import win32net  # pylint: disable=W0611
    import win32api  # pylint: disable=W0611
    import pywintypes  # pylint: disable=W0611
    from ctypes import windll  # pylint: disable=W0611
    HAS_WIN32NET_MODS = True
except ImportError:
    HAS_WIN32NET_MODS = False

win_system.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinSystemTestCase(TestCase):
    '''
        Test cases for salt.modules.win_system
    '''
    def test_halt(self):
        '''
            Test to halt a running system
        '''
        mock = MagicMock(return_value='salt')
        with patch.object(win_system, 'shutdown', mock):
            self.assertEqual(win_system.halt(), 'salt')

    def test_init(self):
        '''
            Test to change the system runlevel on sysV compatible systems
        '''
        self.assertEqual(win_system.init(3),
                         'Not implemented on Windows at this time.')

    @skipIf(not HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_poweroff(self):
        '''
            Test to poweroff a running system
        '''
        mock = MagicMock(return_value='salt')
        with patch.object(win_system, 'shutdown', mock):
            self.assertEqual(win_system.poweroff(), 'salt')

    @skipIf(not HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_reboot(self):
        '''
            Test to reboot the system
        '''
        mock = MagicMock(return_value='salt')
        with patch.dict(win_system.__salt__, {'cmd.run': mock}):
            self.assertEqual(win_system.reboot(), 'salt')

    @skipIf(not HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_shutdown(self):
        '''
            Test to shutdown a running system
        '''
        mock = MagicMock(return_value='salt')
        with patch.dict(win_system.__salt__, {'cmd.run': mock}):
            self.assertEqual(win_system.shutdown(), 'salt')

    @skipIf(not HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_shutdown_hard(self):
        '''
            Test to shutdown a running system with no timeout or warning
        '''
        mock = MagicMock(return_value='salt')
        with patch.dict(win_system.__salt__, {'cmd.run': mock}):
            self.assertEqual(win_system.shutdown_hard(), 'salt')

    @skipIf(not HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_set_computer_name(self):
        '''
            Test to set the Windows computer name
        '''
        mock = MagicMock(side_effect=[{'Computer Name': {'Current': ""},
                                       'ReturnValue = 0;': True},
                                      {'Computer Name': {'Current': 'salt'}}])
        with patch.dict(win_system.__salt__, {'cmd.run': mock}):
            mock = MagicMock(return_value='salt')
            with patch.object(win_system, 'get_computer_name', mock):
                mock = MagicMock(return_value=True)
                with patch.object(win_system,
                                  'get_pending_computer_name', mock):
                    self.assertDictEqual(win_system.set_computer_name("salt"),
                                         {'Computer Name': {'Current': 'salt',
                                                            'Pending': True}})

            self.assertFalse(win_system.set_computer_name("salt"))

    @skipIf(not HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_get_pending_computer_name(self):
        '''
            Test to get a pending computer name.
        '''
        mock = MagicMock(return_value='salt')
        with patch.object(win_system, 'get_computer_name', mock):
            mock = MagicMock(side_effect=['salt0',
                                          'ComputerName REG_SZ (salt)'])
            with patch.dict(win_system.__salt__, {'cmd.run': mock}):
                self.assertFalse(win_system.get_pending_computer_name())

                self.assertEqual(win_system.get_pending_computer_name(),
                                 '(salt)')

    @skipIf(not HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_get_computer_name(self):
        '''
            Test to get the Windows computer name
        '''
        mock = MagicMock(side_effect=['Server Name Salt', 'Salt'])
        with patch.dict(win_system.__salt__, {'cmd.run': mock}):
            self.assertEqual(win_system.get_computer_name(), 'Salt')

            self.assertFalse(win_system.get_computer_name())

    @skipIf(not HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_set_computer_desc(self):
        '''
            Test to set the Windows computer description
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(win_system.__salt__, {'cmd.run': mock}):
            mock = MagicMock(return_value="Salt's comp")
            with patch.object(win_system, 'get_computer_desc', mock):
                self.assertDictEqual(win_system.set_computer_desc(
                                                                  "Salt's comp"
                                                                  ),
                                     {'Computer Description': "Salt's comp"})

    @skipIf(not HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_get_computer_desc(self):
        '''
            Test to get the Windows computer description
        '''
        mock = MagicMock(side_effect=['Server Comment Salt', 'Salt'])
        with patch.dict(win_system.__salt__, {'cmd.run': mock}):
            self.assertEqual(win_system.get_computer_desc(), 'Salt')

            self.assertFalse(win_system.get_computer_desc())

    @skipIf(not HAS_WIN32NET_MODS, 'this test needs w32net and other windows libraries')
    def test_join_domain(self):
        '''
            Test to join a computer to an Active Directory domain
        '''
        mock = MagicMock(side_effect=[{'ReturnValue = 0;': True},
                                      {'Salt': True}])
        with patch.dict(win_system.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(win_system.join_domain("saltstack",
                                                        "salt",
                                                        "salt@123"),
                                 {'Domain': 'saltstack'})

            self.assertFalse(win_system.join_domain("saltstack",
                                                    "salt",
                                                    "salt@123"))

    def test_get_system_time(self):
        '''
            Test to get system time
        '''
        tm = datetime.strftime(datetime.now(), "%I:%M %p")
        win_tm = win_system.get_system_time()
        try:
            self.assertEqual(win_tm, tm)
        except AssertionError:
            # handle race condition
            import re
            self.assertTrue(re.search(r'^\d{2}:\d{2} \w{2}$', win_tm))

    @skipIf(not HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_set_system_time(self):
        '''
            Test to set system time
        '''
        mock = MagicMock(side_effect=[False, True])
        with patch.object(win_system, '_validate_time', mock):
            self.assertFalse(win_system.set_system_time("11:31:15 AM"))

            mock = MagicMock(return_value=True)
            with patch.dict(win_system.__salt__, {'cmd.retcode': mock}):
                self.assertFalse(win_system.set_system_time("11:31:15 AM"))

    def test_get_system_date(self):
        '''
            Test to get system date
        '''
        date = datetime.strftime(datetime.now(), "%a %m/%d/%Y")
        self.assertEqual(win_system.get_system_date(), date)

    @skipIf(not HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_set_system_date(self):
        '''
            Test to set system date
        '''
        mock = MagicMock(side_effect=[False, True])
        with patch.object(win_system, '_validate_date', mock):
            self.assertFalse(win_system.set_system_date("03-28-13"))

            mock = MagicMock(return_value=True)
            with patch.dict(win_system.__salt__, {'cmd.retcode': mock}):
                self.assertFalse(win_system.set_system_date("03-28-13"))

    def test_start_time_service(self):
        '''
            Test to start the Windows time service
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(win_system.__salt__, {'service.start': mock}):
            self.assertTrue(win_system.start_time_service())

    def test_stop_time_service(self):
        '''
            Test to stop the windows time service
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(win_system.__salt__, {'service.stop': mock}):
            self.assertTrue(win_system.stop_time_service())


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinSystemTestCase, needs_daemon=False)
