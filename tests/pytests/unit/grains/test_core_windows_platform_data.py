import pytest

import salt.grains.core as core
from tests.support.mock import MagicMock, Mock, patch

pytestmark = [
    pytest.mark.skip_unless_on_windows,
]

wmi = pytest.importorskip("wmi", reason="WMI only available on Windows")


def test__windows_platform_data_index_errors():
    # mock = [MagicMock(Manufacturer="Dell Inc.", Model="Precision 5820 Tower")]
    # mock = [MagicMock(
    #     Version="10.0.22631",
    #     Caption="Microsoft Windows 11 Enterprise",
    #     Manufacturer="Microsoft Corporation",
    #     ProductType=1,
    # )]

    WMI = Mock()
    platform_version = "1.2.3"
    os_version_info = {"Domain": "test", "DomainType": "test_type"}

    with patch("salt.utils.winapi.Com", MagicMock()), patch.object(
        wmi, "WMI", Mock(return_value=WMI)
    ), patch.object(WMI, "Win32_ComputerSystem", return_value=[]), patch.object(
        WMI, "Win32_OperatingSystem", return_value=[]
    ), patch.object(
        WMI, "Win32_BIOS", return_value=[]
    ), patch.object(
        WMI, "Win32_TimeZone", return_value=[]
    ), patch.object(
        WMI, "Win32_ComputerSystemProduct", return_value=[]
    ), patch.object(
        WMI, "Win32_BaseBoard", return_value=[]
    ), patch(
        "platform.version", return_value=platform_version
    ), patch(
        "salt.utils.win_osinfo.get_join_info", return_value=os_version_info
    ):
        result = core._windows_platform_data()
        expected = {
            "biosstring": None,
            "biosversion": None,
            "kernelrelease": None,
            "kernelversion": platform_version,
            "manufacturer": None,
            "motherboard": {"productname": None, "serialnumber": None},
            "osfullname": None,
            "osmanufacturer": None,
            "osrelease": None,
            "osservicepack": None,
            "osversion": None,
            "productname": None,
            "serialnumber": None,
            "timezone": None,
            "uuid": None,
            "windowsdomain": os_version_info["Domain"],
            "windowsdomaintype": os_version_info["DomainType"],
        }
        assert result == expected


def test__windows_platform_data_computer_system():
    mock = [MagicMock(Manufacturer="Dell Inc.", Model="Precision 5820 Tower")]
    WMI = Mock()
    platform_version = "1.2.3"
    os_version_info = {"Domain": "test", "DomainType": "test_type"}
    with patch("salt.utils.winapi.Com", MagicMock()), patch.object(
        wmi, "WMI", Mock(return_value=WMI)
    ), patch.object(WMI, "Win32_ComputerSystem", return_value=mock), patch.object(
        WMI, "Win32_OperatingSystem", return_value=[]
    ), patch.object(
        WMI, "Win32_BIOS", return_value=[]
    ), patch.object(
        WMI, "Win32_TimeZone", return_value=[]
    ), patch.object(
        WMI, "Win32_ComputerSystemProduct", return_value=[]
    ), patch.object(
        WMI, "Win32_BaseBoard", return_value=[]
    ), patch(
        "platform.version", return_value=platform_version
    ), patch(
        "salt.utils.win_osinfo.get_join_info", return_value=os_version_info
    ):
        result = core._windows_platform_data()
        assert result["manufacturer"] == "Dell Inc."
        assert result["productname"] == "Precision 5820 Tower"


def test__windows_platform_data_operating_system():
    mock = [
        MagicMock(
            Version="10.0.22631",
            Caption="Microsoft Windows 11 Enterprise",
            Manufacturer="Microsoft Corporation",
            ProductType=1,
        )
    ]

    WMI = Mock()
    platform_version = "1.2.3"
    os_version_info = {"Domain": "test", "DomainType": "test_type"}
    with patch("salt.utils.winapi.Com", MagicMock()), patch.object(
        wmi, "WMI", Mock(return_value=WMI)
    ), patch.object(WMI, "Win32_ComputerSystem", return_value=[]), patch.object(
        WMI, "Win32_OperatingSystem", return_value=mock
    ), patch.object(
        WMI, "Win32_BIOS", return_value=[]
    ), patch.object(
        WMI, "Win32_TimeZone", return_value=[]
    ), patch.object(
        WMI, "Win32_ComputerSystemProduct", return_value=[]
    ), patch.object(
        WMI, "Win32_BaseBoard", return_value=[]
    ), patch(
        "platform.version", return_value=platform_version
    ), patch(
        "salt.utils.win_osinfo.get_join_info", return_value=os_version_info
    ):
        result = core._windows_platform_data()
        assert result["kernelrelease"] == "10.0.22631"
        assert result["osfullname"] == "Microsoft Windows 11 Enterprise"
        assert result["osmanufacturer"] == "Microsoft Corporation"
        assert result["osrelease"] == "11"
        assert result["osversion"] == "10.0.22631"


def test__windows_platform_data_bios():
    mock = [
        MagicMock(
            Name="11.22.33",
            Version="DELL   - 1072009",
            SerialNumber="BCF3H13",
        )
    ]

    WMI = Mock()
    platform_version = "1.2.3"
    os_version_info = {"Domain": "test", "DomainType": "test_type"}
    with patch("salt.utils.winapi.Com", MagicMock()), patch.object(
        wmi, "WMI", Mock(return_value=WMI)
    ), patch.object(WMI, "Win32_ComputerSystem", return_value=[]), patch.object(
        WMI, "Win32_OperatingSystem", return_value=[]
    ), patch.object(
        WMI, "Win32_BIOS", return_value=mock
    ), patch.object(
        WMI, "Win32_TimeZone", return_value=[]
    ), patch.object(
        WMI, "Win32_ComputerSystemProduct", return_value=[]
    ), patch.object(
        WMI, "Win32_BaseBoard", return_value=[]
    ), patch(
        "platform.version", return_value=platform_version
    ), patch(
        "salt.utils.win_osinfo.get_join_info", return_value=os_version_info
    ):
        result = core._windows_platform_data()
        assert result["biosversion"] == "11.22.33"
        assert result["biosstring"] == "DELL   - 1072009"
        assert result["serialnumber"] == "BCF3H13"


def test__windows_platform_data_timezone():
    mock = [
        MagicMock(
            Description="(UTC-07:00) Mountain Time (US & Canada)",
        )
    ]

    WMI = Mock()
    platform_version = "1.2.3"
    os_version_info = {"Domain": "test", "DomainType": "test_type"}
    with patch("salt.utils.winapi.Com", MagicMock()), patch.object(
        wmi, "WMI", Mock(return_value=WMI)
    ), patch.object(WMI, "Win32_ComputerSystem", return_value=[]), patch.object(
        WMI, "Win32_OperatingSystem", return_value=[]
    ), patch.object(
        WMI, "Win32_BIOS", return_value=[]
    ), patch.object(
        WMI, "Win32_TimeZone", return_value=mock
    ), patch.object(
        WMI, "Win32_ComputerSystemProduct", return_value=[]
    ), patch.object(
        WMI, "Win32_BaseBoard", return_value=[]
    ), patch(
        "platform.version", return_value=platform_version
    ), patch(
        "salt.utils.win_osinfo.get_join_info", return_value=os_version_info
    ):
        result = core._windows_platform_data()
        assert result["timezone"] == "(UTC-07:00) Mountain Time (US & Canada)"


def test__windows_platform_data_computer_system_product():
    mock = [
        MagicMock(
            UUID="4C4C4544-0043-4610-8030-C2C04F483033",
        )
    ]

    WMI = Mock()
    platform_version = "1.2.3"
    os_version_info = {"Domain": "test", "DomainType": "test_type"}
    with patch("salt.utils.winapi.Com", MagicMock()), patch.object(
        wmi, "WMI", Mock(return_value=WMI)
    ), patch.object(WMI, "Win32_ComputerSystem", return_value=[]), patch.object(
        WMI, "Win32_OperatingSystem", return_value=[]
    ), patch.object(
        WMI, "Win32_BIOS", return_value=[]
    ), patch.object(
        WMI, "Win32_TimeZone", return_value=[]
    ), patch.object(
        WMI, "Win32_ComputerSystemProduct", return_value=mock
    ), patch.object(
        WMI, "Win32_BaseBoard", return_value=[]
    ), patch(
        "platform.version", return_value=platform_version
    ), patch(
        "salt.utils.win_osinfo.get_join_info", return_value=os_version_info
    ):
        result = core._windows_platform_data()
        assert result["uuid"] == "4c4c4544-0043-4610-8030-c2c04f483033"


def test__windows_platform_data_baseboard():
    mock = [
        MagicMock(
            Product="002KVM",
            SerialNumber="/BCF0H03/CNFCW0097F00TM/",
        )
    ]

    WMI = Mock()
    platform_version = "1.2.3"
    os_version_info = {"Domain": "test", "DomainType": "test_type"}
    with patch("salt.utils.winapi.Com", MagicMock()), patch.object(
        wmi, "WMI", Mock(return_value=WMI)
    ), patch.object(WMI, "Win32_ComputerSystem", return_value=[]), patch.object(
        WMI, "Win32_OperatingSystem", return_value=[]
    ), patch.object(
        WMI, "Win32_BIOS", return_value=[]
    ), patch.object(
        WMI, "Win32_TimeZone", return_value=[]
    ), patch.object(
        WMI, "Win32_ComputerSystemProduct", return_value=[]
    ), patch.object(
        WMI, "Win32_BaseBoard", return_value=mock
    ), patch(
        "platform.version", return_value=platform_version
    ), patch(
        "salt.utils.win_osinfo.get_join_info", return_value=os_version_info
    ):
        result = core._windows_platform_data()
        assert result["motherboard"]["productname"] == "002KVM"
        assert result["motherboard"]["serialnumber"] == "/BCF0H03/CNFCW0097F00TM/"
