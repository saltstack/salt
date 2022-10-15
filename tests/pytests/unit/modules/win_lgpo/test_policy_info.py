"""
:codeauthor: Shane Lee <slee@saltstack.com>
"""
import pytest

import salt.modules.win_file as win_file
import salt.modules.win_lgpo as win_lgpo

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
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
