import pytest

import salt.states.mac_assistive as assistive
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {assistive: {}}


def test_installed():
    """
    Test installing a bundle ID as being allowed to run with assistive access
    """
    expected = {
        "changes": {},
        "comment": "Installed com.apple.Chess into the assistive access panel",
        "name": "com.apple.Chess",
        "result": True,
    }

    installed_mock = MagicMock(return_value=False)
    install_mock = MagicMock()

    with patch.dict(
        assistive.__salt__,
        {"assistive.installed": installed_mock, "assistive.install": install_mock},
    ):
        out = assistive.installed("com.apple.Chess")
        installed_mock.assert_called_once_with("com.apple.Chess")
        install_mock.assert_called_once_with("com.apple.Chess", True)
        assert out == expected


def test_installed_not_enabled():
    """
    Test installing a bundle ID as being allowed to run with disabled assistive access
    """
    expected = {
        "changes": {},
        "comment": "Updated enable to True",
        "name": "com.apple.Chess",
        "result": True,
    }

    installed_mock = MagicMock(return_value=True)
    install_mock = MagicMock()
    enabled_mock = MagicMock(return_value=False)
    enable_mock = MagicMock()

    with patch.dict(
        assistive.__salt__,
        {
            "assistive.installed": installed_mock,
            "assistive.install": install_mock,
            "assistive.enabled": enabled_mock,
            "assistive.enable": enable_mock,
        },
    ):
        out = assistive.installed("com.apple.Chess")
        enabled_mock.assert_called_once_with("com.apple.Chess")
        enable_mock.assert_called_once_with("com.apple.Chess", True)
        assert not install_mock.called
        assert out == expected


def test_installed_enabled():
    """
    Test enabling an already enabled bundle ID
    """
    expected = {
        "changes": {},
        "comment": "Already in the correct state",
        "name": "com.apple.Chess",
        "result": True,
    }

    installed_mock = MagicMock(return_value=True)
    install_mock = MagicMock()
    enabled_mock = MagicMock(return_value=True)
    enable_mock = MagicMock()

    with patch.dict(
        assistive.__salt__,
        {
            "assistive.installed": installed_mock,
            "assistive.install": install_mock,
            "assistive.enabled": enabled_mock,
            "assistive.enable": enable_mock,
        },
    ):
        out = assistive.installed("com.apple.Chess")
        enabled_mock.assert_called_once_with("com.apple.Chess")
        assert not enable_mock.called
        assert not install_mock.called
        assert out == expected


def test_installed_not_disabled():
    """
    Test disabling an enabled and installed bundle ID
    """
    expected = {
        "changes": {},
        "comment": "Updated enable to False",
        "name": "com.apple.Chess",
        "result": True,
    }

    installed_mock = MagicMock(return_value=True)
    install_mock = MagicMock()
    enabled_mock = MagicMock(return_value=True)
    enable_mock = MagicMock()

    with patch.dict(
        assistive.__salt__,
        {
            "assistive.installed": installed_mock,
            "assistive.install": install_mock,
            "assistive.enabled": enabled_mock,
            "assistive.enable": enable_mock,
        },
    ):
        out = assistive.installed("com.apple.Chess", False)
        enabled_mock.assert_called_once_with("com.apple.Chess")
        enable_mock.assert_called_once_with("com.apple.Chess", False)
        assert not install_mock.called
        assert out == expected
