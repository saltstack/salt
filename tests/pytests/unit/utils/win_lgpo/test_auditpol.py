import contextlib
import ctypes
import random
from copy import copy

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


@pytest.fixture(autouse=True)
def reset_auditpol_api_cache():
    with patch.object(win_lgpo_auditpol, "_API", new=None):
        yield


@pytest.fixture
def configure_loader_modules():
    return {
        win_lgpo_auditpol: {
            "__context__": {},
        }
    }


def test_get_settings():
    names = win_lgpo_auditpol._get_valid_names()
    ret = win_lgpo_auditpol.get_settings(category="All")
    for name in names:
        assert name in [k.lower() for k in ret]


def test_get_settings_invalid_category():
    pytest.raises(KeyError, win_lgpo_auditpol.get_settings, category="Fake Category")


@pytest.mark.slow_test
def test_get_setting(settings):
    names = win_lgpo_auditpol._get_valid_names()
    for name in names:
        ret = win_lgpo_auditpol.get_setting(name)
        assert ret in settings


def test_get_setting_invalid_name():
    pytest.raises(KeyError, win_lgpo_auditpol.get_setting, name="Fake Name")


def test_set_setting(settings):
    def noop_security_privilege():
        return contextlib.nullcontext()

    names = ["Credential Validation", "IPsec Driver", "File System", "SAM"]
    mock_set = MagicMock(return_value=True)
    real_api = win_lgpo_auditpol._load_advapi32()
    patched_api = copy(real_api)
    patched_api.AuditSetSystemPolicy = mock_set
    with patch.object(win_lgpo_auditpol, "_API", patched_api):
        with patch.object(
            win_lgpo_auditpol,
            "_enable_se_security_privilege",
            noop_security_privilege,
        ):
            with patch.object(
                win_lgpo_auditpol,
                "_get_valid_names",
                return_value=[k.lower() for k in names],
            ):
                for name in names:
                    value = random.choice(settings)
                    win_lgpo_auditpol.set_setting(name=name, value=value)
                    mask = win_lgpo_auditpol.settings[value]
                    mock_set.assert_called_once()
                    args, _kwargs = mock_set.call_args
                    assert args[1] == 1
                    policy_ptr = ctypes.cast(
                        args[0],
                        ctypes.POINTER(win_lgpo_auditpol._AUDIT_POLICY_INFORMATION),
                    )
                    assert policy_ptr.contents.AuditingInformation == mask
                    mock_set.reset_mock()


def test_set_setting_invalid_setting():
    names = ["Credential Validation", "IPsec Driver", "File System"]
    with patch.object(
        win_lgpo_auditpol,
        "_get_valid_names",
        return_value=[k.lower() for k in names],
    ):
        pytest.raises(
            KeyError,
            win_lgpo_auditpol.set_setting,
            name="Fake Name",
            value="No Auditing",
        )


def test_set_setting_invalid_value():
    names = ["Credential Validation", "IPsec Driver", "File System"]
    with patch.object(
        win_lgpo_auditpol,
        "_get_valid_names",
        return_value=[k.lower() for k in names],
    ):
        pytest.raises(
            KeyError,
            win_lgpo_auditpol.set_setting,
            name="Credential Validation",
            value="Fake Value",
        )


def test_get_auditpol_dump():
    names = win_lgpo_auditpol._get_valid_names()
    dump = win_lgpo_auditpol.get_auditpol_dump()
    for name in names:
        found = False
        for line in dump:
            if name.lower() in line.lower():
                found = True
                break
        assert found is True


def test_get_advaudit_policy_rows_matches_fieldnames():
    rows = win_lgpo_auditpol.get_advaudit_policy_rows()
    assert rows
    expected = win_lgpo_auditpol._FIELDNAMES
    assert list(rows[0].keys()) == expected
