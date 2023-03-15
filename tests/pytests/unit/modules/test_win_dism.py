import pytest

import salt.modules.win_dism as dism
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {dism: {}}


def test_add_capability():
    """
    Test installing a capability with DISM
    """
    mock = MagicMock()
    with patch.dict(dism.__salt__, {"cmd.run_all": mock}):
        with patch.dict(dism.__grains__, {"osversion": 10}):
            dism.add_capability("test")
            mock.assert_called_once_with(
                [
                    dism.bin_dism,
                    "/Quiet",
                    "/Online",
                    "/Add-Capability",
                    "/CapabilityName:test",
                    "/NoRestart",
                ]
            )


def test_add_capability_with_extras():
    """
    Test installing a capability with DISM
    """
    mock = MagicMock()
    with patch.dict(dism.__salt__, {"cmd.run_all": mock}):
        with patch.dict(dism.__grains__, {"osversion": 10}):
            dism.add_capability("test", "life", True)
            mock.assert_called_once_with(
                [
                    dism.bin_dism,
                    "/Quiet",
                    "/Online",
                    "/Add-Capability",
                    "/CapabilityName:test",
                    "/Source:life",
                    "/LimitAccess",
                    "/NoRestart",
                ]
            )


def test_remove_capability():
    """
    Test uninstalling a capability with DISM
    """
    mock = MagicMock()
    with patch.dict(dism.__salt__, {"cmd.run_all": mock}):
        with patch.dict(dism.__grains__, {"osversion": 10}):
            dism.remove_capability("test")
            mock.assert_called_once_with(
                [
                    dism.bin_dism,
                    "/Quiet",
                    "/Online",
                    "/Remove-Capability",
                    "/CapabilityName:test",
                    "/NoRestart",
                ]
            )


def test_get_capabilities():
    """
    Test getting all the capabilities
    """
    capabilties = (
        "Capability Identity : Capa1\r\n State : Installed\r\n"
        "Capability Identity : Capa2\r\n State : Disabled\r\n"
    )

    mock = MagicMock(return_value=capabilties)
    with patch.dict(dism.__salt__, {"cmd.run": mock}):
        with patch.dict(dism.__grains__, {"osversion": 10}):
            out = dism.get_capabilities()
            mock.assert_called_once_with(
                [dism.bin_dism, "/English", "/Online", "/Get-Capabilities"]
            )
            assert out == ["Capa1", "Capa2"]


def test_installed_capabilities():
    """
    Test getting all the installed capabilities
    """
    capabilties = (
        "Capability Identity : Capa1\r\n State : Installed\r\n"
        "Capability Identity : Capa2\r\n State : Disabled\r\n"
    )

    mock = MagicMock(return_value=capabilties)
    with patch.dict(dism.__salt__, {"cmd.run": mock}):
        with patch.dict(dism.__grains__, {"osversion": 10}):
            out = dism.installed_capabilities()
            mock.assert_called_once_with(
                [dism.bin_dism, "/English", "/Online", "/Get-Capabilities"]
            )
            assert out == ["Capa1"]


def test_available_capabilities():
    """
    Test getting all the available capabilities
    """
    capabilties = (
        "Capability Identity : Capa1\r\n State : Installed\r\n"
        "Capability Identity : Capa2\r\n State : Not Present\r\n"
    )

    mock = MagicMock(return_value=capabilties)
    with patch.dict(dism.__salt__, {"cmd.run": mock}):
        with patch.dict(dism.__grains__, {"osversion": 10}):
            out = dism.available_capabilities()
            mock.assert_called_once_with(
                [dism.bin_dism, "/English", "/Online", "/Get-Capabilities"]
            )
            assert out == ["Capa2"]


def test_add_feature():
    """
    Test installing a feature with DISM
    """
    mock = MagicMock()
    with patch.dict(dism.__salt__, {"cmd.run_all": mock}):
        dism.add_feature("test")
        mock.assert_called_once_with(
            [
                dism.bin_dism,
                "/Quiet",
                "/Online",
                "/Enable-Feature",
                "/FeatureName:test",
                "/NoRestart",
            ]
        )


def test_add_feature_with_extras():
    """
    Test installing a feature with DISM
    """
    mock = MagicMock()
    with patch.dict(dism.__salt__, {"cmd.run_all": mock}):
        dism.add_feature("sponge", "bob", "C:\\temp", True, True)
        mock.assert_called_once_with(
            [
                dism.bin_dism,
                "/Quiet",
                "/Online",
                "/Enable-Feature",
                "/FeatureName:sponge",
                "/PackageName:bob",
                "/Source:C:\\temp",
                "/LimitAccess",
                "/All",
                "/NoRestart",
            ]
        )


def test_remove_feature():
    """
    Test uninstalling a capability with DISM
    """
    mock = MagicMock()
    with patch.dict(dism.__salt__, {"cmd.run_all": mock}):
        dism.remove_feature("test")
        mock.assert_called_once_with(
            [
                dism.bin_dism,
                "/Quiet",
                "/Online",
                "/Disable-Feature",
                "/FeatureName:test",
                "/NoRestart",
            ]
        )


def test_remove_feature_with_extras():
    """
    Test uninstalling a capability with DISM
    """
    mock = MagicMock()
    with patch.dict(dism.__salt__, {"cmd.run_all": mock}):
        dism.remove_feature("sponge", True)
        mock.assert_called_once_with(
            [
                dism.bin_dism,
                "/Quiet",
                "/Online",
                "/Disable-Feature",
                "/FeatureName:sponge",
                "/Remove",
                "/NoRestart",
            ]
        )


def test_get_features():
    """
    Test getting all the features
    """
    features = (
        "Feature Name : Capa1\r\n State : Enabled\r\n"
        "Feature Name : Capa2\r\n State : Disabled\r\n"
    )

    mock = MagicMock(return_value=features)
    with patch.dict(dism.__salt__, {"cmd.run": mock}):
        out = dism.get_features()
        mock.assert_called_once_with(
            [dism.bin_dism, "/English", "/Online", "/Get-Features"]
        )
        assert out == ["Capa1", "Capa2"]


def test_installed_features():
    """
    Test getting all the installed features
    """
    features = (
        "Feature Name : Capa1\r\n State : Enabled\r\n"
        "Feature Name : Capa2\r\n State : Disabled\r\n"
    )

    mock = MagicMock(return_value=features)
    with patch.dict(dism.__salt__, {"cmd.run": mock}):
        out = dism.installed_features()
        mock.assert_called_once_with(
            [dism.bin_dism, "/English", "/Online", "/Get-Features"]
        )
        assert out == ["Capa1"]


def test_available_features():
    """
    Test getting all the available features
    """
    features = (
        "Feature Name : Capa1\r\n State : Enabled\r\n"
        "Feature Name : Capa2\r\n State : Disabled\r\n"
    )

    mock = MagicMock(return_value=features)
    with patch.dict(dism.__salt__, {"cmd.run": mock}):
        out = dism.available_features()
        mock.assert_called_once_with(
            [dism.bin_dism, "/English", "/Online", "/Get-Features"]
        )
        assert out == ["Capa2"]


def test_add_package():
    """
    Test installing a package with DISM
    """
    mock = MagicMock()
    with patch.dict(dism.__salt__, {"cmd.run_all": mock}):
        dism.add_package("test")
        mock.assert_called_once_with(
            [
                dism.bin_dism,
                "/Quiet",
                "/Online",
                "/Add-Package",
                "/PackagePath:test",
                "/NoRestart",
            ]
        )


def test_add_package_with_extras():
    """
    Test installing a package with DISM
    """
    mock = MagicMock()
    with patch.dict(dism.__salt__, {"cmd.run_all": mock}):
        dism.add_package("sponge", True, True)
        mock.assert_called_once_with(
            [
                dism.bin_dism,
                "/Quiet",
                "/Online",
                "/Add-Package",
                "/PackagePath:sponge",
                "/IgnoreCheck",
                "/PreventPending",
                "/NoRestart",
            ]
        )


def test_remove_package():
    """
    Test uninstalling a package with DISM
    """
    mock = MagicMock()
    with patch.dict(dism.__salt__, {"cmd.run_all": mock}):
        dism.remove_package("test")
        mock.assert_called_once_with(
            [
                dism.bin_dism,
                "/Quiet",
                "/Online",
                "/Remove-Package",
                "/NoRestart",
                "/PackagePath:test",
            ]
        )


def test_remove_kb():
    """
    Test uninstalling a KB with DISM
    """
    pkg_name = "Package_for_KB1002345~31bf3856ad364e35~amd64~~22000.345.1.1"
    mock_search = MagicMock(return_value=[pkg_name])
    mock_remove = MagicMock()
    with patch("salt.modules.win_dism.installed_packages", mock_search):
        with patch("salt.modules.win_dism.remove_package", mock_remove):
            dism.remove_kb("KB1002345")
            mock_remove.assert_called_once_with(
                package=pkg_name,
                image=None,
                restart=False,
            )


def test_remove_kb_number():
    """
    Test uninstalling a KB with DISM with just the KB number
    """
    pkg_name = "Package_for_KB1002345~31bf3856ad364e35~amd64~~22000.345.1.1"
    mock_search = MagicMock(return_value=[pkg_name])
    mock_remove = MagicMock()
    with patch("salt.modules.win_dism.installed_packages", mock_search):
        with patch("salt.modules.win_dism.remove_package", mock_remove):
            dism.remove_kb("1002345")
            mock_remove.assert_called_once_with(
                package=pkg_name,
                image=None,
                restart=False,
            )


def test_remove_kb_not_found():
    pkg_name = "Package_for_KB1002345~31bf3856ad364e35~amd64~~22000.345.1.1"
    mock_search = MagicMock(return_value=[pkg_name])
    with patch("salt.modules.win_dism.installed_packages", mock_search):
        with pytest.raises(CommandExecutionError) as err:
            dism.remove_kb("1001111")
        assert str(err.value) == "1001111 not installed"


def test_installed_packages():
    """
    Test getting all the installed features
    """
    features = (
        "Package Identity : Capa1\r\n State : Installed\r\n"
        "Package Identity : Capa2\r\n State : Installed\r\n"
    )

    mock = MagicMock(return_value=features)
    with patch.dict(dism.__salt__, {"cmd.run": mock}):
        out = dism.installed_packages()
        mock.assert_called_once_with(
            [dism.bin_dism, "/English", "/Online", "/Get-Packages"]
        )
        assert out == ["Capa1", "Capa2"]
