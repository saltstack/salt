import random

import pytest

import salt.utils.win_lgpo_auditpol as win_lgpo_auditpol
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture(scope="module")
def settings():
    return ["No Auditing", "Success", "Failure", "Success and Failure"]


@pytest.fixture(params=list(win_lgpo_auditpol.SETTINGS))
def settings_name(request):
    return request.param


def test_get_settings():
    ret = win_lgpo_auditpol.get_settings(category="All")
    for name in win_lgpo_auditpol.SETTINGS_LC_KEYS:
        assert name in [k.lower() for k in ret]


def test_get_settings_invalid_category():
    pytest.raises(KeyError, win_lgpo_auditpol.get_settings, category="Fake Category")


@pytest.mark.slow_test
def test_get_setting(settings, settings_name):
    ret = win_lgpo_auditpol.get_setting(settings_name)
    assert ret in settings


def test_get_setting_invalid_name():
    pytest.raises(KeyError, win_lgpo_auditpol.get_setting, name="Fake Name")


def test_set_setting(settings):
    names = ["Credential Validation", "IPsec Driver", "File System", "SAM"]
    mock_set = MagicMock(return_value={"retcode": 0, "stdout": "Success"})
    with patch("salt.utils.win_lgpo_auditpol._auditpol_cmd", return_value=mock_set):
        with patch("salt.modules.cmdmod.run_all", tuple(k.lower() for k in names)):
            for name in names:
                value = random.choice(settings)
                win_lgpo_auditpol.set_setting(name=name, value=value)
                switches = win_lgpo_auditpol.SETTINGS[value]
                cmd = f'auditpol /set /subcategory:"{name}" {switches}'
                mock_set.assert_called_once_with(cmd=cmd, python_shell=True)
                mock_set.reset_mock()


def test_set_setting_invalid_setting():
    names = ["Credential Validation", "IPsec Driver", "File System"]
    with patch(
        "salt.utils.win_lgpo_auditpol.SETTINGS_LC_KEYS", tuple(k.lower() for k in names)
    ):
        pytest.raises(
            KeyError,
            win_lgpo_auditpol.set_setting,
            name="Fake Name",
            value="No Auditing",
        )


def test_set_setting_invalid_value():
    names = ["Credential Validation", "IPsec Driver", "File System"]
    with patch(
        "salt.utils.win_lgpo_auditpol.SETTINGS_LC_KEYS", tuple(k.lower() for k in names)
    ):
        pytest.raises(
            KeyError,
            win_lgpo_auditpol.set_setting,
            name="Credential Validation",
            value="Fake Value",
        )


def test_get_auditpol_dump():
    dump = win_lgpo_auditpol.get_auditpol_dump()
    for name in win_lgpo_auditpol.SETTINGS_LC_KEYS:
        found = False
        for line in dump:
            if name.lower() in line.lower():
                found = True
                break
        assert found is True
