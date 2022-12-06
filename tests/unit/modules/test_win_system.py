"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import types
from datetime import datetime

import pytest

import salt.modules.win_system as win_system
import salt.utils.platform
import salt.utils.stringutils
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, Mock, patch
from tests.support.unit import TestCase

try:
    import wmi

    HAS_WMI = True
except ImportError:
    HAS_WMI = False


class MockWMI_ComputerSystem:
    """
    Mock WMI Win32_ComputerSystem Class
    """

    BootupState = "Normal boot"
    Caption = "SALT SERVER"
    ChassisBootupState = 3
    ChassisSKUNumber = "3.14159"
    DNSHostname = "SALT SERVER"
    Domain = "WORKGROUP"
    DomainRole = 2
    Manufacturer = "Dell Inc."
    Model = "Dell 2980"
    NetworkServerModeEnabled = True
    PartOfDomain = False
    PCSystemType = 4
    PowerState = 0
    Status = "OK"
    SystemType = "x64-based PC"
    TotalPhysicalMemory = 17078214656
    ThermalState = 3
    Workgroup = "WORKGROUP"

    def __init__(self):
        pass

    @staticmethod
    def Rename(Name):
        return Name == Name

    @staticmethod
    def JoinDomainOrWorkgroup(Name):
        return [0]

    @staticmethod
    def UnjoinDomainOrWorkgroup(Password, UserName, FUnjoinOptions):
        return [0]


class MockWMI_OperatingSystem:
    """
    Mock WMI Win32_OperatingSystem Class
    """

    Description = "Because salt goes EVERYWHERE"
    InstallDate = "20110211131800"
    LastBootUpTime = "19620612120000"
    Manufacturer = "Python"
    Caption = "Salty"
    NumberOfUsers = 7530000000
    Organization = "SaltStack"
    OSArchitecture = "Windows"
    Primary = True
    ProductType = 3
    RegisteredUser = "thatch@saltstack.com"
    SystemDirectory = "C:\\Windows\\System32"
    SystemDrive = "C:\\"
    Version = "10.0.17763"
    WindowsDirectory = "C:\\Windows"

    def __init__(self):
        pass


class MockWMI_ComputerSystemProduct:
    def __init__(self):
        self.SKUNumber = None


class MockWMI_Processor:
    """
    Mock WMI Win32_Processor Class
    """

    Manufacturer = "Intel"
    MaxClockSpeed = 2301
    NumberOfLogicalProcessors = 8
    NumberOfCores = 4
    NumberOfEnabledCore = 4

    def __init__(self):
        pass


class MockWMI_BIOS:
    """
    Mock WMI Win32_BIOS Class
    """

    SerialNumber = "SALTY2011"
    Manufacturer = "Dell Inc."
    Version = "DELL - 10283849"
    Caption = "A12"
    BIOSVersion = [Version, Caption, "ASUS - 3948D"]
    Description = Caption

    def __init__(self):
        pass


@pytest.mark.skipif(not HAS_WMI, reason="WMI only available on Windows")
@pytest.mark.skip_unless_on_windows
class WinSystemTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.win_system
    """

    def setup_loader_modules(self):
        modules_globals = {}
        # wmi and pythoncom modules are platform specific...
        mock_pythoncom = types.ModuleType(salt.utils.stringutils.to_str("pythoncom"))
        sys_modules_patcher = patch.dict("sys.modules", {"pythoncom": mock_pythoncom})
        sys_modules_patcher.start()
        self.addCleanup(sys_modules_patcher.stop)
        self.WMI = Mock()
        self.addCleanup(delattr, self, "WMI")
        modules_globals["wmi"] = wmi

        if win_system.HAS_WIN32NET_MODS is False:
            win32api = types.ModuleType("win32api")
            now = datetime.now()
            win32api.GetLocalTime = MagicMock(
                return_value=[
                    now.year,
                    now.month,
                    now.weekday(),
                    now.day,
                    now.hour,
                    now.minute,
                    now.second,
                    now.microsecond,
                ]
            )
            modules_globals["win32api"] = win32api
            win32net = types.ModuleType("win32net")
            win32net.NetServerGetInfo = MagicMock()
            win32net.NetServerSetInfo = MagicMock()
            modules_globals["win32net"] = win32net

        return {win_system: modules_globals}

    def test_halt(self):
        """
        Test to halt a running system
        """
        mock = MagicMock(return_value="salt")
        with patch.object(win_system, "shutdown", mock):
            self.assertEqual(win_system.halt(), "salt")

    def test_init(self):
        """
        Test to change the system runlevel on sysV compatible systems
        """
        self.assertEqual(win_system.init(3), "Not implemented on Windows at this time.")

    @pytest.mark.skipif(
        not win_system.HAS_WIN32NET_MODS, reason="Missing win32 libraries"
    )
    def test_poweroff(self):
        """
        Test to poweroff a running system
        """
        mock = MagicMock(return_value="salt")
        with patch.object(win_system, "shutdown", mock):
            self.assertEqual(win_system.poweroff(), "salt")

    @pytest.mark.skipif(
        not win_system.HAS_WIN32NET_MODS, reason="Missing win32 libraries"
    )
    def test_reboot(self):
        """
        Test to reboot the system
        """
        with patch("salt.modules.win_system.shutdown", MagicMock(return_value=True)):
            self.assertEqual(win_system.reboot(), True)

    @pytest.mark.skipif(
        not win_system.HAS_WIN32NET_MODS, reason="Missing win32 libraries"
    )
    def test_reboot_with_timeout_in_minutes(self):
        """
        Test to reboot the system with a timeout
        """
        with patch(
            "salt.modules.win_system.shutdown", MagicMock(return_value=True)
        ) as shutdown:
            self.assertEqual(win_system.reboot(5, in_seconds=False), True)
            shutdown.assert_called_with(
                timeout=5, in_seconds=False, reboot=True, only_on_pending_reboot=False
            )

    @pytest.mark.skipif(
        not win_system.HAS_WIN32NET_MODS, reason="Missing win32 libraries"
    )
    def test_reboot_with_timeout_in_seconds(self):
        """
        Test to reboot the system with a timeout
        """
        with patch(
            "salt.modules.win_system.shutdown", MagicMock(return_value=True)
        ) as shutdown:
            self.assertEqual(win_system.reboot(5, in_seconds=True), True)
            shutdown.assert_called_with(
                timeout=5, in_seconds=True, reboot=True, only_on_pending_reboot=False
            )

    @pytest.mark.skipif(
        not win_system.HAS_WIN32NET_MODS, reason="Missing win32 libraries"
    )
    def test_reboot_with_wait(self):
        """
        Test to reboot the system with a timeout and
        wait for it to finish
        """
        with patch(
            "salt.modules.win_system.shutdown", MagicMock(return_value=True)
        ), patch("salt.modules.win_system.time.sleep", MagicMock()) as time:
            self.assertEqual(win_system.reboot(wait_for_reboot=True), True)
            time.assert_called_with(330)

    @pytest.mark.skipif(
        not win_system.HAS_WIN32NET_MODS, reason="Missing win32 libraries"
    )
    def test_shutdown(self):
        """
        Test to shutdown a running system
        """
        with patch(
            "salt.modules.win_system.win32api.InitiateSystemShutdown", MagicMock()
        ):
            self.assertEqual(win_system.shutdown(), True)

    @pytest.mark.skipif(
        not win_system.HAS_WIN32NET_MODS, reason="Missing win32 libraries"
    )
    def test_shutdown_hard(self):
        """
        Test to shutdown a running system with no timeout or warning
        """
        with patch(
            "salt.modules.win_system.shutdown", MagicMock(return_value=True)
        ) as shutdown:
            self.assertEqual(win_system.shutdown_hard(), True)
            shutdown.assert_called_with(timeout=0)

    @pytest.mark.skipif(
        not win_system.HAS_WIN32NET_MODS, reason="Missing win32 libraries"
    )
    def test_set_computer_name(self):
        """
        Test to set the Windows computer name
        """
        with patch(
            "salt.modules.win_system.windll.kernel32.SetComputerNameExW",
            MagicMock(return_value=True),
        ), patch.object(
            win_system, "get_computer_name", MagicMock(return_value="salt")
        ), patch.object(
            win_system,
            "get_pending_computer_name",
            MagicMock(return_value="salt_new"),
        ):
            self.assertDictEqual(
                win_system.set_computer_name("salt_new"),
                {"Computer Name": {"Current": "salt", "Pending": "salt_new"}},
            )
        # Test set_computer_name failure
        with patch(
            "salt.modules.win_system.windll.kernel32.SetComputerNameExW",
            MagicMock(return_value=False),
        ):
            self.assertFalse(win_system.set_computer_name("salt"))

    @pytest.mark.skipif(
        not win_system.HAS_WIN32NET_MODS, reason="Missing win32 libraries"
    )
    def test_set_computer_desc(self):
        """
        Test to set the Windows computer description
        """
        mock = MagicMock()
        mock_get_info = MagicMock(return_value={"comment": ""})
        mock_get_desc = MagicMock(return_value="Salt's comp")
        with patch(
            "salt.modules.win_system.win32net.NetServerGetInfo", mock_get_info
        ), patch(
            "salt.modules.win_system.win32net.NetServerSetInfo", mock
        ), patch.object(
            win_system, "get_computer_desc", mock_get_desc
        ):
            self.assertDictEqual(
                win_system.set_computer_desc("Salt's comp"),
                {"Computer Description": "Salt's comp"},
            )

    @pytest.mark.skipif(
        not win_system.HAS_WIN32NET_MODS, reason="Missing win32 libraries"
    )
    def test_get_computer_desc(self):
        """
        Test to get the Windows computer description
        """
        with patch(
            "salt.modules.win_system.get_system_info",
            MagicMock(
                side_effect=[{"description": "salt description"}, {"description": None}]
            ),
        ):
            self.assertEqual(win_system.get_computer_desc(), "salt description")
            self.assertFalse(win_system.get_computer_desc())

    @pytest.mark.skipif(
        not win_system.HAS_WIN32NET_MODS, reason="Missing win32 libraries"
    )
    def test_join_domain(self):
        """
        Test to join a computer to an Active Directory domain
        """
        with patch(
            "salt.modules.win_system._join_domain", MagicMock(return_value=0)
        ), patch(
            "salt.modules.win_system.get_domain_workgroup",
            MagicMock(return_value={"Workgroup": "Workgroup"}),
        ):
            self.assertDictEqual(
                win_system.join_domain("saltstack", "salt", "salt@123"),
                {"Domain": "saltstack", "Restart": False},
            )

    @pytest.mark.skipif(
        not win_system.HAS_WIN32NET_MODS, reason="Missing win32 libraries"
    )
    def test_join_domain_already_joined(self):
        """
        Test to join a computer to an Active Directory domain when it is
        already joined
        """
        with patch(
            "salt.modules.win_system._join_domain", MagicMock(return_value=0)
        ), patch(
            "salt.modules.win_system.get_domain_workgroup",
            MagicMock(return_value={"Domain": "saltstack"}),
        ):
            self.assertEqual(
                win_system.join_domain("saltstack", "salt", "salt@123"),
                "Already joined to saltstack",
            )

    @pytest.mark.skipif(
        not win_system.HAS_WIN32NET_MODS, reason="Missing win32 libraries"
    )
    def test_unjoin_domain(self):
        """
        Test unjoining a computer from an Active Directory domain
        """
        with patch("salt.utils.winapi.Com", MagicMock()), patch.object(
            self.WMI, "Win32_ComputerSystem", return_value=[MockWMI_ComputerSystem()]
        ), patch.object(wmi, "WMI", Mock(return_value=self.WMI)), patch(
            "salt.modules.win_system.get_domain_workgroup",
            MagicMock(return_value={"Domain": "contoso.com"}),
        ):
            self.assertDictEqual(
                win_system.unjoin_domain(),
                {"Workgroup": "WORKGROUP", "Restart": False},
            )

    @pytest.mark.skipif(
        not win_system.HAS_WIN32NET_MODS, reason="Missing win32 libraries"
    )
    def test_unjoin_domain_already_unjoined(self):
        """
        Test unjoining a computer from an Active Directory domain
        """
        with patch("salt.utils.winapi.Com", MagicMock()), patch.object(
            self.WMI, "Win32_ComputerSystem", return_value=[MockWMI_ComputerSystem()]
        ), patch.object(wmi, "WMI", Mock(return_value=self.WMI)), patch(
            "salt.modules.win_system.get_domain_workgroup",
            MagicMock(return_value={"Workgroup": "WORKGROUP"}),
        ):
            self.assertEqual(win_system.unjoin_domain(), "Already joined to WORKGROUP")

    def test_get_system_time(self):
        """
        Test to get system time
        """
        tm = datetime.strftime(datetime.now(), "%I:%M:%S %p")
        win_tm = win_system.get_system_time()
        try:
            self.assertEqual(win_tm, tm)
        except AssertionError:
            # handle race condition
            import re

            self.assertTrue(re.search(r"^\d{2}:\d{2} \w{2}$", win_tm))

    @pytest.mark.skipif(
        not win_system.HAS_WIN32NET_MODS, reason="Missing win32 libraries"
    )
    def test_set_system_time(self):
        """
        Test to set system time
        """
        with patch(
            "salt.modules.win_system.set_system_date_time",
            MagicMock(side_effect=[False, True]),
        ):
            self.assertFalse(win_system.set_system_time("11:31:15 AM"))
            self.assertTrue(win_system.set_system_time("11:31:15 AM"))

    def test_get_system_date(self):
        """
        Test to get system date
        """
        date = datetime.strftime(datetime.now(), "%m/%d/%Y")
        self.assertEqual(win_system.get_system_date(), date)

    @pytest.mark.skipif(
        not win_system.HAS_WIN32NET_MODS, reason="Missing win32 libraries"
    )
    def test_set_system_date(self):
        """
        Test to set system date
        """
        with patch(
            "salt.modules.win_system.set_system_date_time",
            MagicMock(side_effect=[False, True]),
        ):
            self.assertFalse(win_system.set_system_date("03-28-13"))
            self.assertTrue(win_system.set_system_date("03-28-13"))

    def test_start_time_service(self):
        """
        Test to start the Windows time service
        """
        mock = MagicMock(return_value=True)
        with patch.dict(win_system.__salt__, {"service.start": mock}):
            self.assertTrue(win_system.start_time_service())

    def test_stop_time_service(self):
        """
        Test to stop the windows time service
        """
        mock = MagicMock(return_value=True)
        with patch.dict(win_system.__salt__, {"service.stop": mock}):
            self.assertTrue(win_system.stop_time_service())

    def test_set_hostname(self):
        """
        Test setting a new hostname
        """
        with patch("salt.utils.winapi.Com", MagicMock()), patch.object(
            self.WMI, "Win32_ComputerSystem", return_value=[MockWMI_ComputerSystem()]
        ), patch.object(wmi, "WMI", Mock(return_value=self.WMI)):
            self.assertTrue(win_system.set_hostname("NEW"))

    def test_get_domain_workgroup(self):
        """
        Test get_domain_workgroup
        """
        with patch.object(wmi, "WMI", Mock(return_value=self.WMI)), patch(
            "salt.utils.winapi.Com", MagicMock()
        ), patch.object(
            self.WMI, "Win32_ComputerSystem", return_value=[MockWMI_ComputerSystem()]
        ):
            self.assertDictEqual(
                win_system.get_domain_workgroup(), {"Workgroup": "WORKGROUP"}
            )

    def test_set_domain_workgroup(self):
        """
        Test set_domain_workgroup
        """
        with patch.object(wmi, "WMI", Mock(return_value=self.WMI)), patch(
            "salt.utils.winapi.Com", MagicMock()
        ), patch.object(
            self.WMI, "Win32_ComputerSystem", return_value=[MockWMI_ComputerSystem()]
        ):
            self.assertTrue(win_system.set_domain_workgroup("test"))

    def test_get_hostname(self):
        """
        Test getting a new hostname
        """
        cmd_run_mock = MagicMock(return_value="MINION")
        with patch.dict(win_system.__salt__, {"cmd.run": cmd_run_mock}):
            ret = win_system.get_hostname()
            self.assertEqual(ret, "MINION")
        cmd_run_mock.assert_called_once_with(cmd="hostname")

    @pytest.mark.skipif(
        not win_system.HAS_WIN32NET_MODS, reason="Missing win32 libraries"
    )
    def test_get_system_info(self):
        fields = [
            "bios_caption",
            "bios_description",
            "bios_details",
            "bios_manufacturer",
            "bios_version",
            "bootup_state",
            "caption",
            "chassis_bootup_state",
            "chassis_sku_number",
            "description",
            "dns_hostname",
            "domain",
            "domain_role",
            "hardware_manufacturer",
            "hardware_model",
            "hardware_serial",
            "install_date",
            "last_boot",
            "name",
            "network_server_mode_enabled",
            "organization",
            "os_architecture",
            "os_manufacturer",
            "os_name",
            "os_type",
            "os_version",
            "part_of_domain",
            "pc_system_type",
            "power_state",
            "primary",
            "processor_cores",
            "processor_cores_enabled",
            "processor_manufacturer",
            "processor_max_clock_speed",
            "processors",
            "processors_logical",
            "registered_user",
            "status",
            "system_directory",
            "system_drive",
            "system_type",
            "thermal_state",
            "total_physical_memory",
            "total_physical_memory_raw",
            "users",
            "windows_directory",
            "workgroup",
        ]
        with patch("salt.utils.win_system.get_computer_name", MagicMock()), patch(
            "salt.utils.winapi.Com", MagicMock()
        ), patch.object(
            self.WMI, "Win32_OperatingSystem", return_value=[MockWMI_OperatingSystem()]
        ), patch.object(
            self.WMI, "Win32_ComputerSystem", return_value=[MockWMI_ComputerSystem()]
        ), patch.object(
            self.WMI,
            "Win32_ComputerSystemProduct",
            return_value=[MockWMI_ComputerSystemProduct()],
        ), patch.object(
            self.WMI,
            "Win32_Processor",
            return_value=[MockWMI_Processor(), MockWMI_Processor()],
        ), patch.object(
            self.WMI, "Win32_BIOS", return_value=[MockWMI_BIOS()]
        ), patch.object(
            wmi, "WMI", Mock(return_value=self.WMI)
        ):
            ret = win_system.get_system_info()
        # Make sure all the fields are in the return
        for field in fields:
            self.assertIn(field, ret)
        # os_type
        os_types = ["Work Station", "Domain Controller", "Server"]
        self.assertIn(ret["os_type"], os_types)
        domain_roles = [
            "Standalone Workstation",
            "Member Workstation",
            "Standalone Server",
            "Member Server",
            "Backup Domain Controller",
            "Primary Domain Controller",
        ]
        self.assertIn(ret["domain_role"], domain_roles)
        system_types = [
            "Unspecified",
            "Desktop",
            "Mobile",
            "Workstation",
            "Enterprise Server",
            "SOHO Server",
            "Appliance PC",
            "Performance Server",
            "Slate",
            "Maximum",
        ]
        self.assertIn(ret["pc_system_type"], system_types)
        warning_states = [
            "Other",
            "Unknown",
            "Safe",
            "Warning",
            "Critical",
            "Non-recoverable",
        ]
        self.assertIn(ret["chassis_bootup_state"], warning_states)
        self.assertIn(ret["thermal_state"], warning_states)

    @pytest.mark.skipif(
        not win_system.HAS_WIN32NET_MODS, reason="Missing win32 libraries"
    )
    def test_get_system_info_no_number_of_enabled_core(self):
        """
        Tests get_system_info when there is no `NumberOfEnabledCore` property in
        the WMI Class Win32_Processor. Older versions of Windows are missing
        this property
        """
        # Create a mock processor class that does not have the
        # NumberOfCoresEnabled property
        class MockWMIProcessor:
            """
            Mock WMI Win32_Processor Class
            """

            def __init__(self):
                self.Manufacturer = "Intel"
                self.MaxClockSpeed = 2301
                self.NumberOfLogicalProcessors = 8
                self.NumberOfCores = 4

        with patch("salt.utils.win_system.get_computer_name", MagicMock()), patch(
            "salt.utils.winapi.Com", MagicMock()
        ), patch.object(
            self.WMI, "Win32_OperatingSystem", return_value=[MockWMI_OperatingSystem()]
        ), patch.object(
            self.WMI, "Win32_ComputerSystem", return_value=[MockWMI_ComputerSystem()]
        ), patch.object(
            self.WMI,
            "Win32_ComputerSystemProduct",
            return_value=[MockWMI_ComputerSystemProduct()],
        ), patch.object(
            self.WMI,
            "Win32_Processor",
            return_value=[MockWMIProcessor(), MockWMIProcessor()],
        ), patch.object(
            self.WMI, "Win32_BIOS", return_value=[MockWMI_BIOS()]
        ), patch.object(
            wmi, "WMI", Mock(return_value=self.WMI)
        ):
            ret = win_system.get_system_info()
            self.assertIn("processors", ret)
            self.assertIn("processors_logical", ret)
            self.assertIn("processor_cores", ret)
            self.assertIn("processor_manufacturer", ret)
            self.assertIn("processor_max_clock_speed", ret)
            self.assertNotIn("processor_cores_enabled", ret)
