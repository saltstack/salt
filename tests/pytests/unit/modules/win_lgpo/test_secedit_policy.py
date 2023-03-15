import re

import pytest
from saltfactories.utils import random_string

import salt.modules.cmdmod as cmdmod
import salt.modules.win_file as win_file
import salt.modules.win_lgpo as lgpo
import salt.utils.files

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
]


@pytest.fixture
def configure_loader_modules(tmp_path):
    cachedir = tmp_path / "__test_admx_policy_cache_dir"
    cachedir.mkdir(parents=True, exist_ok=True)
    return {
        lgpo: {
            "__salt__": {
                "file.file_exists": win_file.file_exists,
                "file.makedirs": win_file.makedirs_,
                "file.remove": win_file.remove,
                "cmd.retcode": cmdmod.retcode,
            },
            "__opts__": {
                "cachedir": str(cachedir),
            },
        },
    }


@pytest.mark.parametrize(
    "name, setting, exp_regexes, cumulative_rights",
    [
        ("LockoutThreshold", 3, [r"^LockoutBadCount = 3"], True),
        ("LockoutDuration", 60, [r"^LockoutDuration = 60"], True),
        ("LockoutWindow", 60, [r"^ResetLockoutCount = 60"], True),
        ("LockoutDuration", 0, [r"^LockoutDuration = -1"], True),
        ("GuestAccountStatus", "Enabled", [r"^EnableGuestAccount = 1"], True),
        ("GuestAccountStatus", "Disabled", [r"^EnableGuestAccount = 0"], True),
        ("PasswordComplexity", "Enabled", [r"^PasswordComplexity = 1"], True),
        (
            "Password must meet complexity requirements",
            "Disabled",
            [r"^PasswordComplexity = 0"],
            True,
        ),
        ("MinPasswordLen", 10, [r"^MinimumPasswordLength = 10"], True),
        ("Minimum password length", 0, [r"^MinimumPasswordLength = 0"], True),
        (
            "Access this computer from the network",
            ["Administrators"],
            [r"^SeNetworkLogonRight = \*S-1-5-32-544"],
            False,
        ),
        (
            "SeNetworkLogonRight",
            ["Everyone", "Administrators", "Users", "Backup Operators"],
            [
                r"^SeNetworkLogonRight = "
                r"\*S-1-1-0,\*S-1-5-32-544,\*S-1-5-32-545,\*S-1-5-32-551"
            ],
            False,
        ),
    ],
)
def test_secedit_policy(shell, name, setting, exp_regexes, cumulative_rights, tmp_path):
    result = lgpo.set_computer_policy(
        name=name,
        setting=setting,
        cumulative_rights_assignments=cumulative_rights,
    )
    assert result is True
    temp_file = tmp_path / random_string("secedit-output-")
    ret = shell.run("secedit", "/export", "/cfg", "{}".format(temp_file))
    assert ret.returncode == 0
    with salt.utils.files.fopen(temp_file, encoding="utf-16") as reader:
        content = reader.read()
    for exp_regex in exp_regexes:
        match = re.search(exp_regex, content, re.IGNORECASE | re.MULTILINE)
        assert match is not None
