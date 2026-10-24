"""
    Test cases for salt.modules.win_licence
"""

import pytest

import salt.exceptions
import salt.modules.win_license as win_license
from tests.support.mock import MagicMock, patch

MOCK_CIM_PRODUCT = {
    "Name": "Windows(R) Operating System",
    "Description": "Windows Operating System - Windows(R) 10, OEM_DM channel",
    "PartialProductKey": "ABCDE",
    "LicenseStatus": 1,
}


@pytest.fixture
def configure_loader_modules():
    return {win_license: {}}


def test_installed():
    """
    Test to see if the given license key is installed
    """
    mock = MagicMock(return_value=MOCK_CIM_PRODUCT)
    with patch("salt.utils.win_pwsh.run_dict", mock):
        out = win_license.installed("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        assert out is True


def test_installed_diff():
    """
    Test to see if the given license key is installed when the key is different
    """
    mock = MagicMock(return_value=None)
    with patch("salt.utils.win_pwsh.run_dict", mock):
        out = win_license.installed("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-12345")
        assert out is False


def test_install():
    """
    Test installing the given product key
    """
    mock = MagicMock(return_value={})
    with patch("salt.utils.win_pwsh.run_dict", mock):
        result = win_license.install("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        assert "successfully" in result.lower()


def test_install_failure():
    """
    Test installing the given product key when it fails
    """
    mock = MagicMock(
        side_effect=salt.exceptions.CommandExecutionError("Install failed")
    )
    with patch("salt.utils.win_pwsh.run_dict", mock):
        with pytest.raises(salt.exceptions.CommandExecutionError):
            win_license.install("INVALID-KEY")


def test_uninstall():
    """
    Test uninstalling the current product key
    """
    mock_pwsh = MagicMock(return_value={})

    with patch("salt.utils.win_pwsh.run_dict", mock_pwsh):
        with patch.object(
            win_license, "_get_license_product", return_value=MOCK_CIM_PRODUCT
        ):
            result = win_license.uninstall()
            assert "successfully" in result.lower()


def test_uninstall_specific_key():
    """
    Test uninstalling a specific product key
    """
    mock_pwsh = MagicMock(return_value={})

    with patch("salt.utils.win_pwsh.run_dict", mock_pwsh):
        with patch.object(
            win_license, "_get_license_product", return_value=MOCK_CIM_PRODUCT
        ):
            result = win_license.uninstall(
                product_key="AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE"
            )
            assert "successfully" in result.lower()


def test_uninstall_no_key():
    """
    Test uninstalling when no product key is installed
    """
    with patch.object(win_license, "_get_license_product", return_value=None):
        with pytest.raises(salt.exceptions.CommandExecutionError):
            win_license.uninstall()


def test_activate():
    """
    Test activating the current product key
    """
    mock_pwsh = MagicMock(return_value={})

    with patch("salt.utils.win_pwsh.run_dict", mock_pwsh):
        with patch.object(
            win_license, "_get_license_product", return_value=MOCK_CIM_PRODUCT
        ):
            result = win_license.activate()
            assert "successfully" in result.lower()


def test_activate_specific_key():
    """
    Test activating a specific product key
    """
    mock_pwsh = MagicMock(return_value={})

    with patch("salt.utils.win_pwsh.run_dict", mock_pwsh):
        with patch.object(
            win_license, "_get_license_product", return_value=MOCK_CIM_PRODUCT
        ):
            result = win_license.activate(
                product_key="AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE"
            )
            assert "successfully" in result.lower()


def test_activate_no_key():
    """
    Test activating when no product key is installed
    """
    with patch.object(win_license, "_get_license_product", return_value=None):
        with pytest.raises(salt.exceptions.CommandExecutionError):
            win_license.activate()


def test_licensed():
    """
    Test checking if the minion is licensed
    """
    with patch.object(
        win_license, "_get_license_product", return_value=MOCK_CIM_PRODUCT
    ):
        result = win_license.licensed()
        assert result is True


def test_licensed_unlicensed():
    """
    Test checking if the minion is licensed when it's not
    """
    unlicensed_product = MOCK_CIM_PRODUCT.copy()
    unlicensed_product["LicenseStatus"] = 0

    with patch.object(
        win_license, "_get_license_product", return_value=unlicensed_product
    ):
        result = win_license.licensed()
        assert result is False


def test_licensed_specific_key():
    """
    Test checking if a specific product is licensed
    """
    with patch.object(
        win_license, "_get_license_product", return_value=MOCK_CIM_PRODUCT
    ):
        result = win_license.licensed(product_key="AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        assert result is True


def test_license_status():
    """
    Test getting the license status
    """
    with patch.object(
        win_license, "_get_license_product", return_value=MOCK_CIM_PRODUCT
    ):
        result = win_license.license_status()
        assert result == 1


def test_license_status_no_key():
    """
    Test getting the license status when no key is installed
    """
    with patch.object(win_license, "_get_license_product", return_value=None):
        result = win_license.license_status()
        assert result == 0


def test_info():
    """
    Test getting the info about the current license key
    """
    with patch.object(
        win_license, "_get_license_product", return_value=MOCK_CIM_PRODUCT
    ):
        out = win_license.info()
        assert out["name"] == "Windows(R) Operating System"
        assert (
            out["description"]
            == "Windows Operating System - Windows(R) 10, OEM_DM channel"
        )
        assert out["partial_key"] == "ABCDE"
        assert out["licensed"] is True
        assert out["status"] == 1
        assert out["status_name"] == "Licensed"


def test_info_no_key():
    """
    Test getting the info about the current license key when none is installed
    """
    with patch.object(win_license, "_get_license_product", return_value=None):
        out = win_license.info()
        assert out is None


def test_set_kms_host():
    """
    Test setting the KMS host
    """
    mock = MagicMock(return_value={})
    with patch("salt.utils.win_pwsh.run_dict", mock):
        result = win_license.set_kms_host("kms.example.com")
        assert "successfully" in result.lower()


def test_set_kms_port():
    """
    Test setting the KMS port
    """
    mock = MagicMock(return_value={})
    with patch("salt.utils.win_pwsh.run_dict", mock):
        result = win_license.set_kms_port(1688)
        assert "successfully" in result.lower()


def test_clear_kms_host():
    """
    Test clearing the KMS host
    """
    mock = MagicMock(return_value={})
    with patch("salt.utils.win_pwsh.run_dict", mock):
        result = win_license.clear_kms_host()
        assert "successfully" in result.lower()


def test_clear_kms_port():
    """
    Test clearing the KMS port
    """
    mock = MagicMock(return_value={})
    with patch("salt.utils.win_pwsh.run_dict", mock):
        result = win_license.clear_kms_port()
        assert "successfully" in result.lower()


def test_get_kms_host():
    """
    Test getting the KMS host
    """
    mock = MagicMock(return_value={"KeyManagementServiceMachine": "kms.example.com"})
    with patch("salt.utils.win_pwsh.run_dict", mock):
        result = win_license.get_kms_host()
        assert result == "kms.example.com"


def test_get_kms_host_not_set():
    """
    Test getting the KMS host when it's not set
    """
    mock = MagicMock(return_value={"KeyManagementServiceMachine": ""})
    with patch("salt.utils.win_pwsh.run_dict", mock):
        result = win_license.get_kms_host()
        assert result is None


def test_get_kms_port():
    """
    Test getting the KMS port
    """
    mock = MagicMock(return_value={"KeyManagementServicePort": 1688})
    with patch("salt.utils.win_pwsh.run_dict", mock):
        result = win_license.get_kms_port()
        assert result == 1688


def test_get_kms_port_not_set():
    """
    Test getting the KMS port when it's not set
    """
    mock = MagicMock(return_value={"KeyManagementServicePort": 0})
    with patch("salt.utils.win_pwsh.run_dict", mock):
        result = win_license.get_kms_port()
        assert result is None
