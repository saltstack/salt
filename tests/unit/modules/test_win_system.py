# -*- coding: utf-8 -*-
'''
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function
import types
from datetime import datetime

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
)

# Import Salt Libs
import salt.modules.win_system as win_system
import salt.utils.platform


@skipIf(not salt.utils.platform.is_windows(), 'System is not Windows')
class WinSystemTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Test cases for salt.modules.win_system
    '''
    def setup_loader_modules(self):
        modules_globals = {}
        if win_system.HAS_WIN32NET_MODS is False:
            win32api = types.ModuleType(
                str('win32api')  # future lint: disable=blacklisted-function
            )
            now = datetime.now()
            win32api.GetLocalTime = MagicMock(return_value=[now.year, now.month, now.weekday(),
                                                            now.day, now.hour, now.minute,
                                                            now.second, now.microsecond])
            modules_globals['win32api'] = win32api
            win32net = types.ModuleType(str('win32net'))  # future lint: disable=blacklisted-function
            win32net.NetServerGetInfo = MagicMock()
            win32net.NetServerSetInfo = MagicMock()
            modules_globals['win32net'] = win32net

        return {win_system: modules_globals}

    def test_halt(self):
        '''
            Test to halt a running system
        '''
        mock = MagicMock(return_value='salt')
        with patch.object(win_system, 'shutdown', mock):
            assert win_system.halt() == 'salt'

    def test_init(self):
        '''
            Test to change the system runlevel on sysV compatible systems
        '''
        assert win_system.init(3) == \
                         'Not implemented on Windows at this time.'

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'Missing win32 libraries')
    def test_poweroff(self):
        '''
            Test to poweroff a running system
        '''
        mock = MagicMock(return_value='salt')
        with patch.object(win_system, 'shutdown', mock):
            assert win_system.poweroff() == 'salt'

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'Missing win32 libraries')
    def test_reboot(self):
        '''
            Test to reboot the system
        '''
        with patch('salt.modules.win_system.shutdown',
                   MagicMock(return_value=True)) as shutdown:
            assert win_system.reboot() is True

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'Missing win32 libraries')
    def test_reboot_with_timeout_in_minutes(self):
        '''
            Test to reboot the system with a timeout
        '''
        with patch('salt.modules.win_system.shutdown',
                   MagicMock(return_value=True)) as shutdown:
            assert win_system.reboot(5, in_seconds=False) is True
            shutdown.assert_called_with(timeout=5, in_seconds=False, reboot=True,
                                        only_on_pending_reboot=False)

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'Missing win32 libraries')
    def test_reboot_with_timeout_in_seconds(self):
        '''
            Test to reboot the system with a timeout
        '''
        with patch('salt.modules.win_system.shutdown',
                   MagicMock(return_value=True)) as shutdown:
            assert win_system.reboot(5, in_seconds=True) is True
            shutdown.assert_called_with(timeout=5, in_seconds=True, reboot=True,
                                        only_on_pending_reboot=False)

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'Missing win32 libraries')
    def test_reboot_with_wait(self):
        '''
            Test to reboot the system with a timeout and
            wait for it to finish
        '''
        with patch('salt.modules.win_system.shutdown',
                   MagicMock(return_value=True)), \
                patch('salt.modules.win_system.time.sleep',
                      MagicMock()) as time:
            assert win_system.reboot(wait_for_reboot=True) is True
            time.assert_called_with(330)

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'Missing win32 libraries')
    def test_shutdown(self):
        '''
            Test to shutdown a running system
        '''
        with patch('salt.modules.win_system.win32api.InitiateSystemShutdown',
                   MagicMock()):
            assert win_system.shutdown() is True

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'Missing win32 libraries')
    def test_shutdown_hard(self):
        '''
            Test to shutdown a running system with no timeout or warning
        '''
        with patch('salt.modules.win_system.shutdown',
                   MagicMock(return_value=True)) as shutdown:
            assert win_system.shutdown_hard() is True
            shutdown.assert_called_with(timeout=0)

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'Missing win32 libraries')
    def test_set_computer_name(self):
        '''
            Test to set the Windows computer name
        '''
        with patch('salt.modules.win_system.windll.kernel32.SetComputerNameExW',
                   MagicMock(return_value=True)):
            with patch.object(win_system, 'get_computer_name',
                              MagicMock(return_value='salt')):
                with patch.object(win_system, 'get_pending_computer_name',
                                  MagicMock(return_value='salt_new')):
                    assert win_system.set_computer_name("salt_new") == \
                                         {'Computer Name': {'Current': 'salt',
                                                            'Pending': 'salt_new'}}
        # Test set_computer_name failure
        with patch('salt.modules.win_system.windll.kernel32.SetComputerNameExW',
                   MagicMock(return_value=False)):
            assert not win_system.set_computer_name("salt")

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'Missing win32 libraries')
    def test_get_pending_computer_name(self):
        '''
            Test to get a pending computer name.
        '''
        with patch.object(win_system, 'get_computer_name',
                          MagicMock(return_value='salt')):
            reg_mock = MagicMock(return_value={'vdata': 'salt'})
            with patch.dict(win_system.__salt__, {'reg.read_value': reg_mock}):
                assert not win_system.get_pending_computer_name()

            reg_mock = MagicMock(return_value={'vdata': 'salt_pending'})
            with patch.dict(win_system.__salt__, {'reg.read_value': reg_mock}):
                assert win_system.get_pending_computer_name() == \
                                 'salt_pending'

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'Missing win32 libraries')
    def test_get_computer_name(self):
        '''
            Test to get the Windows computer name
        '''
        with patch('salt.modules.win_system.win32api.GetComputerNameEx',
                   MagicMock(side_effect=['computer name', ''])):
            assert win_system.get_computer_name() == 'computer name'
            assert not win_system.get_computer_name()

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'Missing win32 libraries')
    def test_set_computer_desc(self):
        '''
            Test to set the Windows computer description
        '''
        mock = MagicMock()
        mock_get_info = MagicMock(return_value={'comment': ''})
        mock_get_desc = MagicMock(return_value="Salt's comp")
        with patch('salt.modules.win_system.win32net.NetServerGetInfo', mock_get_info), \
                patch('salt.modules.win_system.win32net.NetServerSetInfo', mock), \
                patch.object(win_system, 'get_computer_desc', mock_get_desc):
            assert win_system.set_computer_desc("Salt's comp") == \
                {'Computer Description': "Salt's comp"}

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'Missing win32 libraries')
    def test_get_computer_desc(self):
        '''
            Test to get the Windows computer description
        '''
        with patch('salt.modules.win_system.get_system_info',
                   MagicMock(side_effect=[{'description': 'salt description'},
                                          {'description': None}])):
            assert win_system.get_computer_desc() == 'salt description'
            assert not win_system.get_computer_desc()

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'Missing win32 libraries')
    def test_join_domain(self):
        '''
            Test to join a computer to an Active Directory domain
        '''
        with patch('salt.modules.win_system._join_domain',
                   MagicMock(return_value=0)):
            with patch('salt.modules.win_system.get_domain_workgroup',
                       MagicMock(return_value={'Workgroup': 'Workgroup'})):
                assert win_system.join_domain(
                        "saltstack", "salt", "salt@123") == \
                        {'Domain': 'saltstack', 'Restart': False}

            with patch('salt.modules.win_system.get_domain_workgroup',
                       MagicMock(return_value={'Domain': 'saltstack'})):
                assert win_system.join_domain("saltstack", "salt", "salt@123") == \
                    'Already joined to saltstack'

    def test_get_system_time(self):
        '''
            Test to get system time
        '''
        tm = datetime.strftime(datetime.now(), "%I:%M:%S %p")
        win_tm = win_system.get_system_time()
        try:
            assert win_tm == tm
        except AssertionError:
            # handle race condition
            import re
            assert re.search(r'^\d{2}:\d{2} \w{2}$', win_tm)

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'Missing win32 libraries')
    def test_set_system_time(self):
        '''
            Test to set system time
        '''
        with patch('salt.modules.win_system.set_system_date_time',
                   MagicMock(side_effect=[False, True])):
            assert not win_system.set_system_time("11:31:15 AM")
            assert win_system.set_system_time("11:31:15 AM")

    def test_get_system_date(self):
        '''
            Test to get system date
        '''
        date = datetime.strftime(datetime.now(), "%m/%d/%Y")
        assert win_system.get_system_date() == date

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'Missing win32 libraries')
    def test_set_system_date(self):
        '''
            Test to set system date
        '''
        with patch('salt.modules.win_system.set_system_date_time',
                   MagicMock(side_effect=[False, True])):
            assert not win_system.set_system_date("03-28-13")
            assert win_system.set_system_date("03-28-13")

    def test_start_time_service(self):
        '''
            Test to start the Windows time service
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(win_system.__salt__, {'service.start': mock}):
            assert win_system.start_time_service()

    def test_stop_time_service(self):
        '''
            Test to stop the windows time service
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(win_system.__salt__, {'service.stop': mock}):
            assert win_system.stop_time_service()

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
            assert ret == "MINION"
        cmd_run_mock.assert_called_once_with(cmd="hostname")

    @skipIf(not win_system.HAS_WIN32NET_MODS, 'Missing win32 libraries')
    def test_get_system_info(self):
        fields = ['bios_caption', 'bios_description', 'bios_details',
                  'bios_manufacturer', 'bios_version', 'bootup_state',
                  'caption', 'chassis_bootup_state', 'chassis_sku_number',
                  'description', 'dns_hostname', 'domain', 'domain_role',
                  'hardware_manufacturer', 'hardware_model', 'hardware_serial',
                  'install_date', 'last_boot', 'name',
                  'network_server_mode_enabled', 'organization',
                  'os_architecture', 'os_manufacturer', 'os_name', 'os_type',
                  'os_version', 'part_of_domain', 'pc_system_type',
                  'power_state', 'primary', 'processor_cores',
                  'processor_cores_enabled', 'processor_manufacturer',
                  'processor_max_clock_speed', 'processors',
                  'processors_logical', 'registered_user', 'status',
                  'system_directory', 'system_drive', 'system_type',
                  'thermal_state', 'total_physical_memory',
                  'total_physical_memory_raw', 'users', 'windows_directory',
                  'workgroup']
        ret = win_system.get_system_info()
        # Make sure all the fields are in the return
        for field in fields:
            assert field in ret
        # os_type
        os_types = ['Work Station', 'Domain Controller', 'Server']
        assert ret['os_type'] in os_types
        domain_roles = ['Standalone Workstation', 'Member Workstation',
                        'Standalone Server', 'Member Server',
                        'Backup Domain Controller', 'Primary Domain Controller']
        assert ret['domain_role'] in domain_roles
        system_types = ['Unspecified', 'Desktop', 'Mobile', 'Workstation',
                        'Enterprise Server', 'SOHO Server', 'Appliance PC',
                        'Performance Server', 'Slate', 'Maximum']
        assert ret['pc_system_type'] in system_types
        warning_states = ['Other', 'Unknown', 'Safe', 'Warning', 'Critical',
                          'Non-recoverable']
        assert ret['chassis_bootup_state'] in warning_states
        assert ret['thermal_state'] in warning_states
