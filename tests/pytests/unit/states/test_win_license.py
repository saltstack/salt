import pytest

import salt.exceptions
import salt.states.win_license as win_license
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {win_license: {"__opts__": {"test": False}}}


def test_activate():
    """
    Test activating the given product key when key and activation are both needed
    """
    expected_keys = {"name", "result", "comment", "changes"}

    info = {
        "description": "Prof",
        "licensed": False,
        "name": "Win7",
        "partial_key": "XXXXX",
    }

    info_mock = MagicMock(return_value=info)
    install_mock = MagicMock(return_value="Installed successfully")
    activate_mock = MagicMock(return_value="Activated successfully")
    with patch.dict(
        win_license.__salt__,
        {
            "license.info": info_mock,
            "license.install": install_mock,
            "license.activate": activate_mock,
        },
    ):
        out = win_license.activate("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        # info is called twice: once to get current state, once to verify
        info_mock.assert_called_with("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        install_mock.assert_called_once_with("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        activate_mock.assert_called_once_with("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        assert all(key in out for key in expected_keys)
        assert out["result"] is True
        assert "configured successfully" in out["comment"].lower()


def test_activate_test_mode():
    """
    Test activating the given product key in test mode
    """
    info = {
        "description": "Prof",
        "licensed": False,
        "name": "Win7",
        "partial_key": "XXXXX",
    }
    info_mock = MagicMock(return_value=info)
    with patch.dict(win_license.__opts__, {"test": True}):
        with patch.dict(win_license.__salt__, {"license.info": info_mock}):
            out = win_license.activate("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
            assert out["result"] is None
            assert "would be configured" in out["comment"].lower()


def test_installed_not_activated():
    """
    Test activating the given product key when the key is installed but not activated
    """
    info = {
        "description": "Prof",
        "licensed": False,
        "name": "Win7",
        "partial_key": "ABCDE",
    }

    info_mock = MagicMock(return_value=info)
    install_mock = MagicMock(return_value="Installed successfully")
    activate_mock = MagicMock(return_value="Activated successfully")
    with patch.dict(
        win_license.__salt__,
        {
            "license.info": info_mock,
            "license.install": install_mock,
            "license.activate": activate_mock,
        },
    ):
        out = win_license.activate("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        # info is called twice: once to get current state, once to verify
        info_mock.assert_called_with("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        assert not install_mock.called
        activate_mock.assert_called_once_with("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        assert out["result"] is True
        assert "configured successfully" in out["comment"].lower()


def test_installed_activated():
    """
    Test activating the given product key when its already activated
    """
    info = {
        "description": "Prof",
        "licensed": True,
        "name": "Win7",
        "partial_key": "ABCDE",
    }

    info_mock = MagicMock(return_value=info)
    install_mock = MagicMock(return_value="Installed successfully")
    activate_mock = MagicMock(return_value="Activated successfully")
    with patch.dict(
        win_license.__salt__,
        {
            "license.info": info_mock,
            "license.install": install_mock,
            "license.activate": activate_mock,
        },
    ):
        out = win_license.activate("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        # no changes needed — info called only once
        info_mock.assert_called_once_with("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        assert not install_mock.called
        assert not activate_mock.called
        assert out["result"] is True
        assert "already in desired state" in out["comment"].lower()


def test_installed_install_fail():
    """
    Test activating the given product key when the install fails
    """
    info = {
        "description": "Prof",
        "licensed": False,
        "name": "Win7",
        "partial_key": "12345",
    }

    info_mock = MagicMock(return_value=info)
    install_mock = MagicMock(
        side_effect=salt.exceptions.CommandExecutionError("Install failed")
    )
    activate_mock = MagicMock()
    with patch.dict(
        win_license.__salt__,
        {
            "license.info": info_mock,
            "license.install": install_mock,
            "license.activate": activate_mock,
        },
    ):
        out = win_license.activate("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        info_mock.assert_called_once_with("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        install_mock.assert_called_once_with("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        assert not activate_mock.called
        assert out["result"] is False
        assert "failed to configure" in out["comment"].lower()


def test_installed_activate_fail():
    """
    Test activating the given product key when the activate fails
    """
    info = {
        "description": "Prof",
        "licensed": False,
        "name": "Win7",
        "partial_key": "ABCDE",
    }

    info_mock = MagicMock(return_value=info)
    install_mock = MagicMock()
    activate_mock = MagicMock(
        side_effect=salt.exceptions.CommandExecutionError("Activate failed")
    )
    with patch.dict(
        win_license.__salt__,
        {
            "license.info": info_mock,
            "license.install": install_mock,
            "license.activate": activate_mock,
        },
    ):
        out = win_license.activate("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        info_mock.assert_called_once_with("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        assert not install_mock.called
        activate_mock.assert_called_once_with("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        assert out["result"] is False
        assert "failed to configure" in out["comment"].lower()


def test_present_key_already_installed():
    """
    Test present state when key is already installed and no changes needed
    """
    info_mock = MagicMock(return_value={"partial_key": "ABCDE", "licensed": False})
    installed_mock = MagicMock(return_value=True)
    kms_host_mock = MagicMock(return_value=None)
    kms_port_mock = MagicMock(return_value=None)
    with patch.dict(
        win_license.__salt__,
        {
            "license.installed": installed_mock,
            "license.info": info_mock,
            "license.get_kms_host": kms_host_mock,
            "license.get_kms_port": kms_port_mock,
        },
    ):
        out = win_license.present("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        assert out["result"] is True
        assert "already in desired state" in out["comment"].lower()


def test_absent_key_installed():
    """
    Test absent state when key is installed — should uninstall it
    """
    # info returns the key on first call, None on second (after removal)
    info_mock = MagicMock(side_effect=[{"partial_key": "ABCDE"}, None])
    uninstall_mock = MagicMock()

    with patch.dict(
        win_license.__salt__,
        {
            "license.info": info_mock,
            "license.uninstall": uninstall_mock,
        },
    ):
        out = win_license.absent("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        uninstall_mock.assert_called_once_with("AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE")
        assert out["result"] is True
        assert "removed successfully" in out["comment"].lower()
