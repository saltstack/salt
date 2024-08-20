"""
:codeauthor: Shane Lee <slee@saltstack.com>
"""

import pytest

import salt.modules.cmdmod as cmdmod
import salt.modules.win_file as win_file
import salt.modules.win_lgpo as win_lgpo
import salt.utils.win_dacl as win_dacl
import salt.utils.win_lgpo_auditpol as win_lgpo_auditpol
import salt.utils.win_reg as win_reg

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
                "cmd.run": cmdmod.run,
                "file.file_exists": win_file.file_exists,
                "file.makedirs": win_file.makedirs_,
                "file.remove": win_file.remove,
                "file.write": win_file.write,
            },
            "__opts__": {
                "cachedir": str(cachedir),
            },
            "__utils__": {
                "auditpol.get_auditpol_dump": win_lgpo_auditpol.get_auditpol_dump,
                "reg.read_value": win_reg.read_value,
            },
            "__context__": {},
        },
        win_file: {
            "__utils__": {
                "dacl.set_perms": win_dacl.set_perms,
            },
        },
    }


def _get_policy_adm_setting(
    policy_name, policy_class, return_full_policy_names, hierarchical_return
):
    """
    Helper function to get current setting
    """
    try:
        # Enable the policy
        computer_policy = {
            "Point and Print Restrictions": {
                "Users can only point and print to these servers": True,
                "Enter fully qualified server names separated by semicolons": (
                    "fakeserver1;fakeserver2"
                ),
                "Users can only point and print to machines in their forest": True,
                "When installing drivers for a new connection": (
                    "Show warning and elevation prompt"
                ),
                "When updating drivers for an existing connection": (
                    "Show warning only"
                ),
            },
        }
        win_lgpo.set_(computer_policy=computer_policy)
        # Get the policy
        success, policy_obj, _, _ = win_lgpo._lookup_admin_template(
            policy_name=policy_name, policy_class=policy_class, adml_language="en-US"
        )
        if success:
            results = win_lgpo._get_policy_adm_setting(
                admx_policy=policy_obj,
                policy_class=policy_class,
                adml_language="en-US",
                return_full_policy_names=return_full_policy_names,
                hierarchical_return=hierarchical_return,
            )
            return results
        return "Policy Not Found"
    finally:
        win_lgpo.set_computer_policy(
            name="Point and Print Restrictions",
            setting="Not Configured",
        )


@pytest.mark.slow_test
def test_enabled():
    result = _get_policy_adm_setting(
        policy_name="Point and Print Restrictions",
        policy_class="Machine",
        return_full_policy_names=False,
        hierarchical_return=False,
    )
    expected = {
        "PointAndPrint_Restrictions_Win7": {
            "PointAndPrint_NoWarningNoElevationOnInstall_Enum": (
                "Show warning and elevation prompt"
            ),
            "PointAndPrint_NoWarningNoElevationOnUpdate_Enum": "Show warning only",
            "PointAndPrint_TrustedForest_Chk": True,
            "PointAndPrint_TrustedServers_Chk": True,
            "PointAndPrint_TrustedServers_Edit": "fakeserver1;fakeserver2",
        }
    }
    assert result == expected


def test_enabled_hierarchical():
    result = _get_policy_adm_setting(
        policy_name="Point and Print Restrictions",
        policy_class="Machine",
        return_full_policy_names=False,
        hierarchical_return=True,
    )
    expected = {
        "Computer Configuration": {
            "Administrative Templates": {
                "Printers": {
                    "PointAndPrint_Restrictions_Win7": {
                        "PointAndPrint_NoWarningNoElevationOnInstall_Enum": (
                            "Show warning and elevation prompt"
                        ),
                        "PointAndPrint_NoWarningNoElevationOnUpdate_Enum": (
                            "Show warning only"
                        ),
                        "PointAndPrint_TrustedForest_Chk": True,
                        "PointAndPrint_TrustedServers_Chk": True,
                        "PointAndPrint_TrustedServers_Edit": (
                            "fakeserver1;fakeserver2"
                        ),
                    }
                }
            }
        }
    }
    assert result == expected


def test_enabled_full_names():
    result = _get_policy_adm_setting(
        policy_name="Point and Print Restrictions",
        policy_class="Machine",
        return_full_policy_names=True,
        hierarchical_return=False,
    )
    expected = {
        "Printers\\Point and Print Restrictions": {
            "Enter fully qualified server names separated by semicolons": (
                "fakeserver1;fakeserver2"
            ),
            "When installing drivers for a new connection": (
                "Show warning and elevation prompt"
            ),
            "Users can only point and print to machines in their forest": True,
            "Users can only point and print to these servers": True,
            "When updating drivers for an existing connection": "Show warning only",
        }
    }
    assert result == expected


@pytest.mark.slow_test
def test_full_names_hierarchical():
    result = _get_policy_adm_setting(
        policy_name="Point and Print Restrictions",
        policy_class="Machine",
        return_full_policy_names=True,
        hierarchical_return=True,
    )
    expected = {
        "Computer Configuration": {
            "Administrative Templates": {
                "Printers": {
                    "Point and Print Restrictions": {
                        "Enter fully qualified server names separated by semicolons": (
                            "fakeserver1;fakeserver2"
                        ),
                        "When installing drivers for a new connection": (
                            "Show warning and elevation prompt"
                        ),
                        "Users can only point and print to machines in their forest": True,
                        "Users can only point and print to these servers": True,
                        "When updating drivers for an existing connection": (
                            "Show warning only"
                        ),
                    }
                }
            }
        }
    }
    assert result == expected
