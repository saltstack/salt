# -*- coding: utf-8 -*-
'''
mac_power tests
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import mac_power
from salt.utils import mac_utils
from salt.exceptions import SaltInvocationError

mac_utils.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MacPowerTestCase(TestCase):
    '''
    test mac_power execution module
    '''
    def test_set_sleep(self):
        '''
        test set_sleep function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_sleep(179)
            mock_cmd.assert_called_once_with('systemsetup -setsleep 179')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_sleep('never')
            mock_cmd.assert_called_once_with('systemsetup -setsleep never')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 1, 'stdout': 'plankton'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertRaises(SaltInvocationError, mac_power.set_sleep, 181)

    def test_get_computer_sleep(self):
        '''
        test get_computer_sleep function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob: squarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_computer_sleep()
            mock_cmd.assert_called_once_with('systemsetup -getcomputersleep')
            self.assertEqual(ret, 'squarepants')

        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob:\nsquarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_computer_sleep()
            mock_cmd.assert_called_once_with('systemsetup -getcomputersleep')
            self.assertEqual(ret, 'squarepants')

        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'squarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_computer_sleep()
            mock_cmd.assert_called_once_with('systemsetup -getcomputersleep')
            self.assertEqual(ret, 'squarepants')

    def test_set_computer_sleep(self):
        '''
        test set_computer_sleep function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_computer_sleep(179)
            mock_cmd.assert_called_once_with('systemsetup -setcomputersleep 179')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_computer_sleep('never')
            mock_cmd.assert_called_once_with('systemsetup -setcomputersleep never')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 1, 'stdout': 'plankton'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertRaises(SaltInvocationError, mac_power.set_computer_sleep, 181)

    def test_get_display_sleep(self):
        '''
        test get_display_sleep function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob: squarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_display_sleep()
            mock_cmd.assert_called_once_with('systemsetup -getdisplaysleep')
            self.assertEqual(ret, 'squarepants')

        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob:\nsquarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_display_sleep()
            mock_cmd.assert_called_once_with('systemsetup -getdisplaysleep')
            self.assertEqual(ret, 'squarepants')

        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'squarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_display_sleep()
            mock_cmd.assert_called_once_with('systemsetup -getdisplaysleep')
            self.assertEqual(ret, 'squarepants')

    def test_set_display_sleep(self):
        '''
        test set_display_sleep function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_display_sleep(179)
            mock_cmd.assert_called_once_with('systemsetup -setdisplaysleep 179')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_display_sleep('never')
            mock_cmd.assert_called_once_with('systemsetup -setdisplaysleep never')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 1, 'stdout': 'plankton'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertRaises(SaltInvocationError, mac_power.set_display_sleep, 181)

    def test_get_harddisk_sleep(self):
        '''
        test get_harddisk_sleep function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob: squarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_harddisk_sleep()
            mock_cmd.assert_called_once_with('systemsetup -getharddisksleep')
            self.assertEqual(ret, 'squarepants')

        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob:\nsquarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_harddisk_sleep()
            mock_cmd.assert_called_once_with('systemsetup -getharddisksleep')
            self.assertEqual(ret, 'squarepants')

        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'squarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_harddisk_sleep()
            mock_cmd.assert_called_once_with('systemsetup -getharddisksleep')
            self.assertEqual(ret, 'squarepants')

    def test_set_harddisk_sleep(self):
        '''
        test set_harddisk_sleep function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_harddisk_sleep(179)
            mock_cmd.assert_called_once_with('systemsetup -setharddisksleep 179')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_harddisk_sleep('never')
            mock_cmd.assert_called_once_with('systemsetup -setharddisksleep never')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 1, 'stdout': 'plankton'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertRaises(SaltInvocationError, mac_power.set_harddisk_sleep, 181)

    def test_get_wake_on_modem(self):
        '''
        test get_wake_on_modem function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob: squarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_wake_on_modem()
            mock_cmd.assert_called_once_with('systemsetup -getwakeonmodem')
            self.assertEqual(ret, 'squarepants')

        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob:\nsquarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_wake_on_modem()
            mock_cmd.assert_called_once_with('systemsetup -getwakeonmodem')
            self.assertEqual(ret, 'squarepants')

        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'squarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_wake_on_modem()
            mock_cmd.assert_called_once_with('systemsetup -getwakeonmodem')
            self.assertEqual(ret, 'squarepants')

    def test_set_wake_on_modem(self):
        '''
        test set_wake_on_modem function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_wake_on_modem('on')
            mock_cmd.assert_called_once_with('systemsetup -setwakeonmodem on')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_wake_on_modem(True)
            mock_cmd.assert_called_once_with('systemsetup -setwakeonmodem on')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_wake_on_modem('off')
            mock_cmd.assert_called_once_with('systemsetup -setwakeonmodem off')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_wake_on_modem(False)
            mock_cmd.assert_called_once_with('systemsetup -setwakeonmodem off')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 1, 'stdout': 'plankton'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertRaises(SaltInvocationError, mac_power.set_wake_on_modem, 'fail')

    def test_get_wake_on_network(self):
        '''
        test get_wake_on_network function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob: squarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_wake_on_network()
            mock_cmd.assert_called_once_with('systemsetup -getwakeonnetworkaccess')
            self.assertEqual(ret, 'squarepants')

        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob:\nsquarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_wake_on_network()
            mock_cmd.assert_called_once_with('systemsetup -getwakeonnetworkaccess')
            self.assertEqual(ret, 'squarepants')

        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'squarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_wake_on_network()
            mock_cmd.assert_called_once_with('systemsetup -getwakeonnetworkaccess')
            self.assertEqual(ret, 'squarepants')

    def test_set_wake_on_network(self):
        '''
        test set_wake_on_network function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_wake_on_network('on')
            mock_cmd.assert_called_once_with('systemsetup -setwakeonnetworkaccess on')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_wake_on_network(True)
            mock_cmd.assert_called_once_with('systemsetup -setwakeonnetworkaccess on')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_wake_on_network('off')
            mock_cmd.assert_called_once_with('systemsetup -setwakeonnetworkaccess off')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_wake_on_network(False)
            mock_cmd.assert_called_once_with('systemsetup -setwakeonnetworkaccess off')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 1, 'stdout': 'plankton'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertRaises(SaltInvocationError, mac_power.set_wake_on_network, 'fail')

    def test_get_restart_power_failure(self):
        '''
        test get_restart_power_failure function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob: squarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_restart_power_failure()
            mock_cmd.assert_called_once_with('systemsetup -getrestartpowerfailure')
            self.assertEqual(ret, 'squarepants')

        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob:\nsquarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_restart_power_failure()
            mock_cmd.assert_called_once_with('systemsetup -getrestartpowerfailure')
            self.assertEqual(ret, 'squarepants')

        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'squarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_restart_power_failure()
            mock_cmd.assert_called_once_with('systemsetup -getrestartpowerfailure')
            self.assertEqual(ret, 'squarepants')

    def test_set_restart_power_failure(self):
        '''
        test set_restart_power_failure function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_restart_power_failure('on')
            mock_cmd.assert_called_once_with('systemsetup -setrestartpowerfailure on')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_restart_power_failure(True)
            mock_cmd.assert_called_once_with('systemsetup -setrestartpowerfailure on')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_restart_power_failure('off')
            mock_cmd.assert_called_once_with('systemsetup -setrestartpowerfailure off')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_restart_power_failure(False)
            mock_cmd.assert_called_once_with('systemsetup -setrestartpowerfailure off')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 1, 'stdout': 'plankton'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertRaises(SaltInvocationError, mac_power.set_restart_power_failure, 'fail')

    def test_get_restart_freeze(self):
        '''
        test get_restart_freeze function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob: squarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_restart_freeze()
            mock_cmd.assert_called_once_with('systemsetup -getrestartfreeze')
            self.assertEqual(ret, 'squarepants')

        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob:\nsquarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_restart_freeze()
            mock_cmd.assert_called_once_with('systemsetup -getrestartfreeze')
            self.assertEqual(ret, 'squarepants')

        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'squarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_restart_freeze()
            mock_cmd.assert_called_once_with('systemsetup -getrestartfreeze')
            self.assertEqual(ret, 'squarepants')

    def test_set_restart_freeze(self):
        '''
        test set_restart_freeze function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_restart_freeze('on')
            mock_cmd.assert_called_once_with('systemsetup -setrestartfreeze on')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_restart_freeze(True)
            mock_cmd.assert_called_once_with('systemsetup -setrestartfreeze on')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_restart_freeze('off')
            mock_cmd.assert_called_once_with('systemsetup -setrestartfreeze off')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_restart_freeze(False)
            mock_cmd.assert_called_once_with('systemsetup -setrestartfreeze off')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 1, 'stdout': 'plankton'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertRaises(SaltInvocationError, mac_power.set_restart_freeze, 'fail')

    def test_get_sleep_on_power_button(self):
        '''
        test get_sleep_on_power_button function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob: squarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_sleep_on_power_button()
            mock_cmd.assert_called_once_with('systemsetup -getallowpowerbuttontosleepcomputer')
            self.assertEqual(ret, 'squarepants')

        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob:\nsquarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_sleep_on_power_button()
            mock_cmd.assert_called_once_with('systemsetup -getallowpowerbuttontosleepcomputer')
            self.assertEqual(ret, 'squarepants')

        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'squarepants',
                                           'stderr': 'patrick'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.get_sleep_on_power_button()
            mock_cmd.assert_called_once_with('systemsetup -getallowpowerbuttontosleepcomputer')
            self.assertEqual(ret, 'squarepants')

    def test_set_sleep_on_power_button(self):
        '''
        test set_sleep_on_power_button function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_sleep_on_power_button('on')
            mock_cmd.assert_called_once_with('systemsetup -setallowpowerbuttontosleepcomputer on')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_sleep_on_power_button(True)
            mock_cmd.assert_called_once_with('systemsetup -setallowpowerbuttontosleepcomputer on')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_sleep_on_power_button('off')
            mock_cmd.assert_called_once_with('systemsetup -setallowpowerbuttontosleepcomputer off')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 0, 'stdout': 'spongebob'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            ret = mac_power.set_sleep_on_power_button(False)
            mock_cmd.assert_called_once_with('systemsetup -setallowpowerbuttontosleepcomputer off')
            self.assertEqual(ret, True)

        mock_cmd = MagicMock(return_value={'retcode': 1, 'stdout': 'plankton'})
        with patch.dict(mac_utils.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertRaises(SaltInvocationError, mac_power.set_sleep_on_power_button, 'fail')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacPowerTestCase, needs_daemon=False)
