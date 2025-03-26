import pytest

import salt.modules.win_servermanager as win_servermanager
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {win_servermanager: {"__grains__": {"osversion": "6.2"}}}


def test_install():
    """
    Test win_servermanager.install
    """
    mock_out = {
        "Success": True,
        "RestartNeeded": 1,
        "FeatureResult": [
            {
                "Id": 338,
                "Name": "XPS-Viewer",
                "DisplayName": "XPS Viewer",
                "Success": True,
                "RestartNeeded": False,
                "Message": "",
                "SkipReason": 0,
            }
        ],
        "ExitCode": 0,
    }
    expected = {
        "ExitCode": 0,
        "RestartNeeded": False,
        "Restarted": False,
        "Features": {
            "XPS-Viewer": {
                "DisplayName": "XPS Viewer",
                "Message": "",
                "RestartNeeded": False,
                "SkipReason": 0,
                "Success": True,
            }
        },
        "Success": True,
    }

    mock_reboot = MagicMock(return_value=True)
    with patch("salt.utils.win_pwsh.run_dict", return_value=mock_out), patch.dict(
        win_servermanager.__salt__, {"system.reboot": mock_reboot}
    ):
        result = win_servermanager.install("XPS-Viewer")
        assert result == expected


def test_install_restart():
    """
    Test win_servermanager.install when restart=True
    """
    mock_out = {
        "Success": True,
        "RestartNeeded": 1,
        "FeatureResult": [
            {
                "Id": 338,
                "Name": "XPS-Viewer",
                "DisplayName": "XPS Viewer",
                "Success": True,
                "RestartNeeded": True,
                "Message": "",
                "SkipReason": 0,
            }
        ],
        "ExitCode": 0,
    }
    expected = {
        "ExitCode": 0,
        "RestartNeeded": True,
        "Restarted": True,
        "Features": {
            "XPS-Viewer": {
                "DisplayName": "XPS Viewer",
                "Message": "",
                "RestartNeeded": True,
                "SkipReason": 0,
                "Success": True,
            }
        },
        "Success": True,
    }

    mock_reboot = MagicMock(return_value=True)
    with patch("salt.utils.win_pwsh.run_dict", return_value=mock_out), patch.dict(
        win_servermanager.__salt__, {"system.reboot": mock_reboot}
    ):
        result = win_servermanager.install("XPS-Viewer", restart=True)
        mock_reboot.assert_called_once()
        assert result == expected
