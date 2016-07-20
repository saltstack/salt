# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

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
from salt.modules import win_service

win_service.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinServiceTestCase(TestCase):
    '''
        Test cases for salt.modules.win_service
    '''
    def test_get_enabled(self):
        '''
            Test to return the enabled services
        '''
        mock = MagicMock(return_value=['c', 'a', 'b'])
        with patch.object(win_service, 'get_all', mock):
            mock = MagicMock(side_effect=[True, False, True])
            with patch.object(win_service, 'enabled', mock):
                self.assertListEqual(win_service.get_enabled(), ['b', 'c'])

    def test_get_disabled(self):
        '''
            Test to return the disabled services
        '''
        mock = MagicMock(return_value=['c', 'a', 'b'])
        with patch.object(win_service, 'get_all', mock):
            mock = MagicMock(side_effect=[True, False, True])
            with patch.object(win_service, 'disabled', mock):
                self.assertListEqual(win_service.get_disabled(), ['b', 'c'])

    def test_available(self):
        '''
            Test to Returns ``True`` if the specified service
            is available, otherwise returns ``False``
        '''
        mock = MagicMock(return_value=['c', 'a', 'b'])
        with patch.object(win_service, 'get_all', mock):
            self.assertTrue(win_service.available("a"))

    def test_missing(self):
        '''
            Test to the inverse of service.available
        '''
        mock = MagicMock(return_value=['c', 'a', 'b'])
        with patch.object(win_service, 'get_all', mock):
            self.assertTrue(win_service.missing("d"))

    def test_get_all(self):
        '''
            Test to return all installed services
        '''
        mock = MagicMock(return_value="")
        with patch.dict(win_service.__salt__, {'cmd.run': mock}):
            self.assertListEqual(win_service.get_all(), [])

    def test_get_service_name(self):
        '''
            Test to the Display Name is what is displayed
            in Windows when services.msc is executed.
        '''
        ret = ['Service Names and Display Names mismatch',
               {'salt DISPLAY_NAME:salt': 'salt DISPLAY_NAME:salt'}]
        mock = MagicMock(side_effect=['SERVICE_NAME:salt',
                                      'SERVICE_NAME:salt DISPLAY_NAME:salt',
                                      'SERVICE_NAME:salt DISPLAY_NAME:salt'])
        with patch.dict(win_service.__salt__, {'cmd.run': mock}):
            self.assertEqual(win_service.get_service_name(), ret[0])

            self.assertDictEqual(win_service.get_service_name(), ret[1])

            self.assertDictEqual(win_service.get_service_name("salt"), {})

    def test_start(self):
        '''
            Test to start the specified service
        '''
        mock = MagicMock(return_value=False)
        with patch.dict(win_service.__salt__, {'cmd.retcode': mock}):
            self.assertTrue(win_service.start("salt"))

    def test_stop(self):
        '''
            Test to stop the specified service
        '''
        win_service.SERVICE_STOP_POLL_MAX_ATTEMPTS = 1
        win_service.SERVICE_STOP_DELAY_SECONDS = 1
        mock = MagicMock(side_effect=[['service was stopped'], ["salt"],
                                      ["salt"]])
        with patch.dict(win_service.__salt__, {'cmd.run': mock}):
            self.assertTrue(win_service.stop("salt"))

            mock = MagicMock(side_effect=[False, True])
            with patch.object(win_service, 'status', mock):
                self.assertTrue(win_service.stop("salt"))

                self.assertFalse(win_service.stop("salt"))

    def test_restart(self):
        '''
            Test to restart the named service
        '''
        mock_true = MagicMock(return_value=True)
        with patch.object(win_service, 'create_win_salt_restart_task',
                          mock_true):
            with patch.object(win_service, 'execute_salt_restart_task',
                              mock_true):
                self.assertTrue(win_service.restart("salt-minion"))

        with patch.object(win_service, 'stop', mock_true):
            with patch.object(win_service, 'start', mock_true):
                self.assertTrue(win_service.restart("salt"))

    def test_createwin_saltrestart_task(self):
        '''
            Test to create a task in Windows task
            scheduler to enable restarting the salt-minion
        '''
        mock_true = MagicMock(return_value=True)
        with patch.dict(win_service.__salt__, {'task.create_task': mock_true}):
            self.assertTrue(win_service.create_win_salt_restart_task())

    def test_execute_salt_restart_task(self):
        '''
            Test to run the Windows Salt restart task
        '''
        mock_true = MagicMock(return_value=True)
        with patch.dict(win_service.__salt__, {'task.run': mock_true}):
            self.assertTrue(win_service.execute_salt_restart_task())

    def test_status(self):
        '''
            Test to return the status for a service
        '''
        mock = MagicMock(side_effect=["RUNNING", "STOP_PENDING", ""])
        with patch.dict(win_service.__salt__, {'cmd.run': mock}):
            self.assertTrue(win_service.status("salt"))

            self.assertTrue(win_service.status("salt"))

            self.assertFalse(win_service.status("salt"))

    def test_getsid(self):
        '''
            Test to return the sid for this windows service
        '''
        mock = MagicMock(side_effect=["SERVICE SID:S-1-5-80-1956725871-603941828-2318551034-3950094706-3826225633", "SERVICE SID"])
        with patch.dict(win_service.__salt__, {'cmd.run': mock}):
            self.assertEqual(win_service.getsid("salt"), 'S-1-5-80-1956725871-603941828-2318551034-3950094706-3826225633')

            self.assertEqual(win_service.getsid("salt"), None)

    def test_enable(self):
        '''
            Test to enable the named service to start at boot
        '''
        mock = MagicMock(return_value=False)
        with patch.dict(win_service.__salt__, {'cmd.retcode': mock}):
            self.assertTrue(win_service.enable("salt"))

    def test_disable(self):
        '''
            Test to disable the named service to start at boot
        '''
        mock = MagicMock(return_value=False)
        with patch.dict(win_service.__salt__, {'cmd.retcode': mock}):
            self.assertTrue(win_service.disable("salt"))

    def test_enabled(self):
        '''
            Test to check to see if the named
            service is enabled to start on boot
        '''
        mock = MagicMock(side_effect=["AUTO_START", ""])
        with patch.dict(win_service.__salt__, {'cmd.run': mock}):
            self.assertTrue(win_service.enabled("salt"))

            self.assertFalse(win_service.enabled("salt"))

    def test_disabled(self):
        '''
            Test to check to see if the named
            service is disabled to start on boot
        '''
        mock = MagicMock(side_effect=["DEMAND_START", "DISABLED", ""])
        with patch.dict(win_service.__salt__, {'cmd.run': mock}):
            self.assertTrue(win_service.disabled("salt"))

            self.assertTrue(win_service.disabled("salt"))

            self.assertFalse(win_service.disabled("salt"))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinServiceTestCase, needs_daemon=False)
