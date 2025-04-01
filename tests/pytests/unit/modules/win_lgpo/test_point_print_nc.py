"""
:codeauthor: Shane Lee <slee@saltstack.com>
"""

import pytest

import salt.config
import salt.grains.core
import salt.loader
import salt.modules.cmdmod as cmdmod
import salt.modules.win_file as win_file
import salt.modules.win_lgpo as win_lgpo
import salt.states.win_lgpo
import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
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
    # Get the policy
    success, policy_obj, _, _ = salt.modules.win_lgpo._lookup_admin_template(
        policy_name=policy_name, policy_class=policy_class, adml_language="en-US"
    )
    if success:
        return salt.modules.win_lgpo._get_policy_adm_setting(
            admx_policy=policy_obj,
            policy_class=policy_class,
            adml_language="en-US",
            return_full_policy_names=return_full_policy_names,
            hierarchical_return=hierarchical_return,
        )
    return "Policy Not Found"


def test_not_configured():
    result = _get_policy_adm_setting(
        policy_name="Point and Print Restrictions",
        policy_class="Machine",
        return_full_policy_names=False,
        hierarchical_return=False,
    )
    expected = {"PointAndPrint_Restrictions_Win7": "Not Configured"}
    assert result == expected


def test_not_configured_hierarchical():
    result = _get_policy_adm_setting(
        policy_name="Point and Print Restrictions",
        policy_class="Machine",
        return_full_policy_names=False,
        hierarchical_return=True,
    )
    expected = {
        "Computer Configuration": {
            "Administrative Templates": {
                "Printers": {"PointAndPrint_Restrictions_Win7": "Not Configured"}
            }
        }
    }
    assert result == expected


def test_not_configured_full_names():
    result = _get_policy_adm_setting(
        policy_name="Point and Print Restrictions",
        policy_class="Machine",
        return_full_policy_names=True,
        hierarchical_return=False,
    )
    expected = {"Printers\\Point and Print Restrictions": "Not Configured"}
    assert result == expected


def test_not_configured_full_names_hierarchical():
    result = _get_policy_adm_setting(
        policy_name="Point and Print Restrictions",
        policy_class="Machine",
        return_full_policy_names=True,
        hierarchical_return=True,
    )
    expected = {
        "Computer Configuration": {
            "Administrative Templates": {
                "Printers": {"Point and Print Restrictions": "Not Configured"}
            }
        }
    }
    assert result == expected
