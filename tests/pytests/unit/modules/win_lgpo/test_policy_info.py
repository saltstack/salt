"""
:codeauthor: Shane Lee <slee@saltstack.com>
"""

import pytest

import salt.modules.win_file as win_file
import salt.modules.win_lgpo as win_lgpo
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
]


@pytest.fixture
def configure_loader_modules(tmp_path):
    cachedir = tmp_path / "__test_admx_policy_cache_dir"
    cachedir.mkdir(parents=True, exist_ok=True)
    return {
        win_lgpo: {
            "__salt__": {
                "file.file_exists": win_file.file_exists,
                "file.makedirs": win_file.makedirs_,
            },
            "__opts__": {
                "cachedir": str(cachedir),
            },
        },
    }


def test_get_policy_name():
    result = win_lgpo.get_policy(
        policy_name="Network firewall: Public: Settings: Display a notification",
        policy_class="machine",
        return_value_only=True,
        return_full_policy_names=True,
        hierarchical_return=False,
    )
    expected = "Not configured"
    assert result == expected


def test_get_adml_display_name_bad_name():
    result = win_lgpo._getAdmlDisplayName("junk", "spongbob")
    assert result is None


def test_get_adml_display_name_no_results():
    patch_xpath = patch.object(win_lgpo, "ADML_DISPLAY_NAME_XPATH", return_value=[])
    with patch_xpath:
        result = win_lgpo._getAdmlDisplayName("junk", "$(spongbob.squarepants)")
    assert result is None


def test_get_policy_id():
    result = win_lgpo.get_policy(
        policy_name="WfwPublicSettingsNotification",
        policy_class="machine",
        return_value_only=True,
        return_full_policy_names=True,
        hierarchical_return=False,
    )
    expected = "Not configured"
    assert result == expected


def test_get_policy_name_full_return():
    result = win_lgpo.get_policy(
        policy_name="Network firewall: Public: Settings: Display a notification",
        policy_class="machine",
        return_value_only=False,
        return_full_policy_names=True,
        hierarchical_return=False,
    )
    expected = {
        "Network firewall: Public: Settings: Display a notification": "Not configured"
    }
    assert result == expected


def test_get_policy_id_full_return():
    result = win_lgpo.get_policy(
        policy_name="WfwPublicSettingsNotification",
        policy_class="machine",
        return_value_only=False,
        return_full_policy_names=True,
        hierarchical_return=False,
    )
    expected = {
        "Network firewall: Public: Settings: Display a notification": "Not configured"
    }
    assert result == expected


def test_get_policy_name_full_return_ids():
    result = win_lgpo.get_policy(
        policy_name="Network firewall: Public: Settings: Display a notification",
        policy_class="machine",
        return_value_only=False,
        return_full_policy_names=False,
        hierarchical_return=False,
    )
    expected = {
        "Network firewall: Public: Settings: Display a notification": "Not configured"
    }
    assert result == expected


def test_get_policy_id_full_return_ids():
    result = win_lgpo.get_policy(
        policy_name="WfwPublicSettingsNotification",
        policy_class="machine",
        return_value_only=False,
        return_full_policy_names=False,
        hierarchical_return=False,
    )
    expected = {"WfwPublicSettingsNotification": "Not configured"}
    assert result == expected


def test_get_policy_id_full_return_ids_hierarchical():
    result = win_lgpo.get_policy(
        policy_name="WfwPublicSettingsNotification",
        policy_class="machine",
        return_value_only=False,
        return_full_policy_names=False,
        hierarchical_return=True,
    )
    expected = {
        "Computer Configuration": {
            "Windows Settings": {
                "Security Settings": {
                    "Windows Firewall with Advanced Security": {
                        "Windows Firewall with Advanced Security - Local Group Policy Object": {
                            "WfwPublicSettingsNotification": "Not configured"
                        }
                    }
                }
            }
        }
    }
    assert result == expected


def test_get_policy_id_full_return_full_names_hierarchical():
    result = win_lgpo.get_policy(
        policy_name="WfwPublicSettingsNotification",
        policy_class="machine",
        return_value_only=False,
        return_full_policy_names=True,
        hierarchical_return=True,
    )
    expected = {
        "Computer Configuration": {
            "Windows Settings": {
                "Security Settings": {
                    "Windows Firewall with Advanced Security": {
                        "Windows Firewall with Advanced Security - Local Group Policy Object": {
                            "Network firewall: Public: Settings: Display a notification": (
                                "Not configured"
                            )
                        }
                    }
                }
            }
        }
    }
    assert result == expected


def test_transform_value_missing_type():
    policy = {"Transform": {"some_type": "junk"}}
    result = win_lgpo._transform_value(
        value="spongebob",
        policy=policy,
        transform_type="different_type",
    )
    assert result == "spongebob"


def test_transform_value_registry():
    policy = {"Registry": {}}
    result = win_lgpo._transform_value(
        value="spongebob",
        policy=policy,
        transform_type="different_type",
    )
    assert result == "spongebob"


def test_transform_value_registry_not_set():
    policy = {"Registry": {}}
    result = win_lgpo._transform_value(
        value="(value not set)",
        policy=policy,
        transform_type="different_type",
    )
    assert result == "Not Defined"


def test_validate_setting_not_in_list():
    policy = {"Settings": ["junk"]}
    result = win_lgpo._validateSetting(value="spongebob", policy=policy)
    assert not result


def test_validate_setting_in_list():
    policy = {"Settings": ["spongebob"]}
    result = win_lgpo._validateSetting(value="spongebob", policy=policy)
    assert result


def test_validate_setting_not_list_or_dict():
    policy = {"Settings": "spongebob"}
    result = win_lgpo._validateSetting(value="spongebob", policy=policy)
    assert result


def test_add_account_rights_error():
    patch_w32sec = patch(
        "win32security.LsaOpenPolicy", MagicMock(side_effect=Exception)
    )
    with patch_w32sec:
        assert win_lgpo._addAccountRights("spongebob", "junk") is False


def test_del_account_rights_error():
    patch_w32sec = patch(
        "win32security.LsaOpenPolicy", MagicMock(side_effect=Exception)
    )
    with patch_w32sec:
        assert win_lgpo._delAccountRights("spongebob", "junk") is False


def test_validate_setting_no_function():
    policy = {
        "Settings": {
            "Function": "_in_range_inclusive",
            "Args": {"min": 0, "max": 24},
        },
    }
    result = win_lgpo._validateSetting(value="spongebob", policy=policy)
    assert not result
