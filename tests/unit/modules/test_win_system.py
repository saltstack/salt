# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import types
from datetime import datetime

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.win_system as win_system


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinSystemTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Test cases for salt.modules.win_system
    '''
    def setup_loader_modules(self):
        modules_globals = {}
        if win_system.HAS_WIN32NET_MODS is False:
            win32api = types.ModuleType('win32api')
            now = datetime.now()
            win32api.GetLocalTime = MagicMock(return_value=[now.year, now.month, now.weekday(),
                                                            now.day, now.hour, now.minute,
                                                            now.second, now.microsecond])
            modules_globals['win32api'] = win32api
        return {win_system: modules_globals}

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

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_poweroff(self):
        '''
            Test to poweroff a running system
        '''
        mock = MagicMock(return_value='salt')
        with patch.object(win_system, 'shutdown', mock):
            self.assertEqual(win_system.poweroff(), 'salt')

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_reboot(self):
        '''
            Test to reboot the system
        '''
        mock = MagicMock(return_value='salt')
        with patch.dict(win_system.__salt__, {'cmd.run': mock}):
            self.assertEqual(win_system.reboot(), 'salt')
            mock.assert_called_once_with(['shutdown', '/r', '/t', '300'], python_shell=False)

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_reboot_with_timeout_in_minutes(self):
        '''
            Test to reboot the system with a timeout
        '''
        mock = MagicMock(return_value='salt')
        with patch.dict(win_system.__salt__, {'cmd.run': mock}):
            self.assertEqual(win_system.reboot(5, in_seconds=False), 'salt')
            mock.assert_called_once_with(['shutdown', '/r', '/t', '300'], python_shell=False)

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_reboot_with_timeout_in_seconds(self):
        '''
            Test to reboot the system with a timeout
        '''
        mock = MagicMock(return_value='salt')
        with patch.dict(win_system.__salt__, {'cmd.run': mock}):
            self.assertEqual(win_system.reboot(5, in_seconds=True), 'salt')
            mock.assert_called_once_with(['shutdown', '/r', '/t', '5'], python_shell=False)

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_reboot_with_wait(self):
        '''
            Test to reboot the system with a timeout and
            wait for it to finish
        '''
        mock = MagicMock(return_value='salt')
        sleep_mock = MagicMock(return_value='salt')
        with patch.dict(win_system.__salt__, {'cmd.run': mock}):
            with patch('time.sleep', sleep_mock):
                self.assertEqual(win_system.reboot(wait_for_reboot=True), 'salt')
                mock.assert_called_once_with(['shutdown', '/r', '/t', '300'], python_shell=False)
                sleep_mock.assert_called_once_with(330)

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_shutdown(self):
        '''
            Test to shutdown a running system
        '''
        mock = MagicMock(return_value='salt')
        with patch.dict(win_system.__salt__, {'cmd.run': mock}):
            self.assertEqual(win_system.shutdown(), 'salt')

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_shutdown_hard(self):
        '''
            Test to shutdown a running system with no timeout or warning
        '''
        mock = MagicMock(return_value='salt')
        with patch.dict(win_system.__salt__, {'cmd.run': mock}):
            self.assertEqual(win_system.shutdown_hard(), 'salt')

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'this test needs the w32net library')
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

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'this test needs the w32net library')
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

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_get_computer_name(self):
        '''
            Test to get the Windows computer name
        '''
        mock = MagicMock(side_effect=['Server Name Salt', 'Salt'])
        with patch.dict(win_system.__salt__, {'cmd.run': mock}):
            self.assertEqual(win_system.get_computer_name(), 'Salt')

            self.assertFalse(win_system.get_computer_name())

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'this test needs the w32net library')
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

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'this test needs the w32net library')
    def test_get_computer_desc(self):
        '''
            Test to get the Windows computer description
        '''
        mock = MagicMock(side_effect=['Server Comment Salt', 'Salt'])
        with patch.dict(win_system.__salt__, {'cmd.run': mock}):
            self.assertEqual(win_system.get_computer_desc(), 'Salt')

            self.assertFalse(win_system.get_computer_desc())

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'this test needs w32net and other windows libraries')
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
        tm = datetime.strftime(datetime.now(), "%I:%M:%S %p")
        win_tm = win_system.get_system_time()
        try:
            self.assertEqual(win_tm, tm)
        except AssertionError:
            # handle race condition
            import re
            self.assertTrue(re.search(r'^\d{2}:\d{2} \w{2}$', win_tm))

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'this test needs the w32net library')
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
        date = datetime.strftime(datetime.now(), "%m/%d/%Y")
        self.assertEqual(win_system.get_system_date(), date)

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'this test needs the w32net library')
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

    def test_set_hostname(self):
        '''
            Test setting a new hostname
        '''
        cmd_run_mock = MagicMock(return_value="Method execution successful.")
        get_hostname = MagicMock(return_value="MINION")
        with patch.dict(win_system.__salt__, {'cmd.run': cmd_run_mock}):
            with patch.object(win_system, 'get_hostname', get_hostname):
                win_system.set_hostname("NEW")

        cmd_run_mock.assert_called_once_with(cmd="wmic computersystem where name='MINION' call rename name='NEW'")

    def test_get_hostname(self):
        '''
            Test setting a new hostname
        '''
        cmd_run_mock = MagicMock(return_value="MINION")
        with patch.dict(win_system.__salt__, {'cmd.run': cmd_run_mock}):
            ret = win_system.get_hostname()
            self.assertEqual(ret, "MINION")
        cmd_run_mock.assert_called_once_with(cmd="hostname")
