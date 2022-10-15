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


def test__getAdmlPresentationRefId():
    resources = win_lgpo._get_policy_resources(language="en-US")
    ref_id = "LetAppsAccessAccountInfo_Enum"
    expected = "Default for all apps"
    result = win_lgpo._getAdmlPresentationRefId(resources, ref_id)
    assert result == expected


def test__getAdmlPresentationRefId_result_text_is_none():
    resources = win_lgpo._get_policy_resources(language="en-US")
    ref_id = "LetAppsAccessAccountInfo_UserInControlOfTheseApps_List"
    expected = "Put user in control of these specific apps (use Package Family Names)"
    result = win_lgpo._getAdmlPresentationRefId(resources, ref_id)
    assert result == expected
