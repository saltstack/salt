import pytest

import salt.modules.win_appx as win_appx
from tests.support.mock import MagicMock, call, patch

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture
def configure_loader_modules():
    return {win_appx: {}}


def test__pkg_list_empty():
    assert win_appx._pkg_list("") is None


def test__pkg_list_single():
    raw = {
        "Name": "MicrosoftTeams",
        "Version": "22042.702.1226.2352",
        "PackageFullName": "MicrosoftTeams_22042.702.1226.2352_x64__8wekyb3d8bbwe",
        "PackageFamilyName": "MicrosoftTeams_8wekyb3d8bbwe",
    }
    assert win_appx._pkg_list(raw=raw) == ["MicrosoftTeams"]


def test__pkg_list_multiple():
    raw = [
        {
            "Name": "MicrosoftTeams",
            "Version": "22042.702.1226.2352",
            "PackageFullName": "MicrosoftTeams_22042.702.1226.2352_x64__8wekyb3d8bbwe",
            "PackageFamilyName": "MicrosoftTeams_8wekyb3d8bbwe",
        },
        {
            "Name": "Microsoft.BingWeather",
            "Version": "4.53.51361.0",
            "PackageFullName": "Microsoft.BingWeather_4.53.51361.0_x64__8wekyb3d8bbwe",
            "PackageFamilyName": "Microsoft.BingWeather_8wekyb3d8bbwe",
        },
    ]
    assert win_appx._pkg_list(raw=raw) == ["MicrosoftTeams", "Microsoft.BingWeather"]


def test__pkg_list_single_field():
    raw = {
        "Name": "MicrosoftTeams",
        "Version": "22042.702.1226.2352",
        "PackageFullName": "MicrosoftTeams_22042.702.1226.2352_x64__8wekyb3d8bbwe",
        "PackageFamilyName": "MicrosoftTeams_8wekyb3d8bbwe",
    }
    assert win_appx._pkg_list(raw=raw, field="PackageFamilyName") == [
        "MicrosoftTeams_8wekyb3d8bbwe"
    ]


def test__pkg_list_multiple_field():
    raw = [
        {
            "Name": "MicrosoftTeams",
            "Version": "22042.702.1226.2352",
            "PackageFullName": "MicrosoftTeams_22042.702.1226.2352_x64__8wekyb3d8bbwe",
            "PackageFamilyName": "MicrosoftTeams_8wekyb3d8bbwe",
        },
        {
            "Name": "Microsoft.BingWeather",
            "Version": "4.53.51361.0",
            "PackageFullName": "Microsoft.BingWeather_4.53.51361.0_x64__8wekyb3d8bbwe",
            "PackageFamilyName": "Microsoft.BingWeather_8wekyb3d8bbwe",
        },
    ]
    assert win_appx._pkg_list(raw=raw, field="PackageFamilyName") == [
        "MicrosoftTeams_8wekyb3d8bbwe",
        "Microsoft.BingWeather_8wekyb3d8bbwe",
    ]


def test_list():
    mock_run_dict = MagicMock()
    with patch("salt.utils.win_pwsh.run_dict", mock_run_dict):
        win_appx.list_("*test*")
    cmd = [
        "Get-AppxPackage -AllUsers -PackageTypeFilter Bundle -Name *test*",
        'Where-Object {$_.name -notlike "Microsoft.WindowsStore*"}',
        "Where-Object -Property IsFramework -eq $false",
        "Where-Object -Property NonRemovable -eq $false",
        "Sort-Object Name",
    ]
    mock_run_dict.assert_called_once_with(" | ".join(cmd))


def test_list_field_none():
    mock_run_dict = MagicMock()
    with patch("salt.utils.win_pwsh.run_dict", mock_run_dict):
        win_appx.list_("*test*", field=None)
    cmd = [
        "Get-AppxPackage -AllUsers -PackageTypeFilter Bundle -Name *test*",
        'Where-Object {$_.name -notlike "Microsoft.WindowsStore*"}',
        "Where-Object -Property IsFramework -eq $false",
        "Where-Object -Property NonRemovable -eq $false",
        "Sort-Object Name",
        "Select Name, Version, PackageFullName, PackageFamilyName, IsBundle, IsFramework",
    ]
    mock_run_dict.assert_called_once_with(" | ".join(cmd))


def test_list_other_options_flipped():
    mock_run_dict = MagicMock()
    with patch("salt.utils.win_pwsh.run_dict", mock_run_dict):
        win_appx.list_("*test*", include_store=True, frameworks=True, bundles=False)
    cmd = [
        "Get-AppxPackage -AllUsers -Name *test*",
        "Where-Object -Property NonRemovable -eq $false",
        "Sort-Object Name",
    ]
    mock_run_dict.assert_called_once_with(" | ".join(cmd))


def test_remove():
    mock_run_dict = MagicMock()
    mock_list_return = {
        "Name": "Microsoft.BingWeather",
        "PackageFullName": "Microsoft.BingWeather_full_name",
        "IsBundle": True,
    }
    mock_list = MagicMock(return_value=mock_list_return)
    with patch("salt.utils.win_pwsh.run_dict", mock_run_dict), patch.object(
        win_appx, "list_", mock_list
    ):
        assert win_appx.remove("*test*") is True
    cmd = "Remove-AppxPackage -AllUsers -Package Microsoft.BingWeather_full_name"
    mock_run_dict.assert_called_with(cmd)


def test_remove_duplicate():
    mock_run_dict = MagicMock()
    mock_list_return_1 = [
        {
            "Name": "Microsoft.BingWeather",
            "PackageFullName": "Microsoft.BingWeather_full_name_1",
            "IsBundle": False,
        },
        {
            "Name": "Microsoft.BingWeather",
            "PackageFullName": "Microsoft.BingWeather_full_name_2",
            "IsBundle": False,
        },
    ]
    mock_list_return_2 = [
        {
            "Name": "Microsoft.BingWeather",
            "PackageFullName": "Microsoft.BingWeather_full_name_1",
            "IsBundle": True,
        },
        {
            "Name": "Microsoft.BingWeather",
            "PackageFullName": "Microsoft.BingWeather_full_name_2",
            "IsBundle": True,
        },
    ]
    mock_list_return_3 = [
        {
            "Name": "Microsoft.BingWeather",
            "PackageFullName": "Microsoft.BingWeather_full_name_2",
            "IsBundle": True,
        },
    ]
    mock_list = MagicMock(
        side_effect=[mock_list_return_1, mock_list_return_2, mock_list_return_3]
    )
    with patch("salt.utils.win_pwsh.run_dict", mock_run_dict), patch.object(
        win_appx, "list_", mock_list
    ):
        assert win_appx.remove("*bingweather*") is True
    cmd_1 = "Remove-AppxPackage -AllUsers -Package Microsoft.BingWeather_full_name_1"
    cmd_2 = "Remove-AppxPackage -AllUsers -Package Microsoft.BingWeather_full_name_2"
    mock_run_dict.assert_has_calls([call(cmd_1), call(cmd_2)])


def test_remove_deprovision_only():
    mock_run_dict = MagicMock()
    mock_list_return = {
        "Name": "Microsoft.BingWeather",
        "PackageFullName": "Microsoft.BingWeather_full_name",
        "IsBundle": True,
    }
    mock_list = MagicMock(return_value=mock_list_return)
    with patch("salt.utils.win_pwsh.run_dict", mock_run_dict), patch.object(
        win_appx, "list_", mock_list
    ):
        assert win_appx.remove("*test*", deprovision_only=True) is True
    cmd = "Remove-AppxProvisionedPackage -Online -PackageName Microsoft.BingWeather_full_name"
    mock_run_dict.assert_called_with(cmd)


def test_remove_non_bundle():
    mock_run_dict = MagicMock()
    mock_list_return = [
        {
            "Name": "Microsoft.BingWeather",
            "PackageFullName": "Microsoft.BingWeather_non_bundle",
            "IsBundle": False,
        },
        {
            "Name": "Microsoft.BingWeather",
            "PackageFullName": "Microsoft.BingWeather_bundle",
            "IsBundle": True,
        },
    ]
    mock_list = MagicMock(side_effect=mock_list_return)
    with patch("salt.utils.win_pwsh.run_dict", mock_run_dict), patch.object(
        win_appx, "list_", mock_list
    ):
        assert win_appx.remove("*test*", deprovision_only=True) is True
    cmd = "Remove-AppxProvisionedPackage -Online -PackageName Microsoft.BingWeather_bundle"
    mock_run_dict.assert_called_with(cmd)


def test_remove_not_found_empty_dict():
    mock_run_dict = MagicMock()
    mock_list_return = {}
    mock_list = MagicMock(return_value=mock_list_return)
    with patch("salt.utils.win_pwsh.run_dict", mock_run_dict), patch.object(
        win_appx, "list_", mock_list
    ):
        assert win_appx.remove("*test*", deprovision_only=True) is None


def test_remove_not_found_none():
    mock_run_dict = MagicMock()
    mock_list_return = None
    mock_list = MagicMock(return_value=mock_list_return)
    with patch("salt.utils.win_pwsh.run_dict", mock_run_dict), patch.object(
        win_appx, "list_", mock_list
    ):
        assert win_appx.remove("*test*", deprovision_only=True) is None


def test_list_deprovisioned():
    mock_list_keys = MagicMock(return_value=["Deprovisioned1", "Deprovisioned2"])
    with patch("salt.utils.win_reg.list_keys", mock_list_keys):
        expected = ["Deprovisioned1", "Deprovisioned2"]
        assert win_appx.list_deprovisioned() == expected


def test_list_deprovisioned_query():
    mock_list_keys = MagicMock(return_value=["Deprovisioned1", "Deprovisioned2"])
    with patch("salt.utils.win_reg.list_keys", mock_list_keys):
        expected = ["Deprovisioned1"]
        assert win_appx.list_deprovisioned(query="*ed1*") == expected


def test_install():
    mock_dism = MagicMock(return_value={"retcode": 0})
    with patch.dict(win_appx.__salt__, {"dism.add_provisioned_package": mock_dism}):
        assert win_appx.install("C:\\Test.appx") is True
    mock_dism.assert_called_once_with("C:\\Test.appx")
