import logging
import pathlib

import pytest

import salt.modules.win_file as win_file
import salt.modules.win_lgpo as lgpo_mod
import salt.states.win_lgpo as lgpo
import salt.utils.files

log = logging.getLogger(__name__)

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
        lgpo_mod: {
            "__salt__": {
                "file.file_exists":  win_file.file_exists,
                "file.makedirs": win_file.makedirs_,
            },
            "__opts__": {
                "cachedir": str(cachedir),
            },
            "__context__": {},
        },
        lgpo: {
            "__salt__": {
                "lgpo.get_policy_info": lgpo_mod.get_policy_info,
                "lgpo.get_policy": lgpo_mod.get_policy,
                "lgpo.set": lgpo_mod.set_,
            },
            "__opts__": {
                "test": False,
            }
        },
    }


def test_allow_telemetry_subsequent_runs():
    """
    Tests that the AllowTelemetry policy is applied correctly and that it
    doesn't appear in subsequent group policy states as having changed
    """
    reg_pol = pathlib.Path(r"C:\Windows\System32\GroupPolicy\Machine\Registry.pol")
    reg_pol.unlink(missing_ok=True)
    result = lgpo_mod.set_computer_policy(
        name="AllowTelemetry",
        setting="Disabled",
    )
    assert result is True
    expected = {
        "new": {
            "Computer Configuration": {
                "Manage preview builds": "Disabled"
            }
        },
        "old": {
            "Computer Configuration": {
                "Manage preview builds": "Not Configured"
            }
        },
    }
    result = lgpo.set_(
        name="Manage preview builds",
        setting="Disabled",
        policy_class="Machine",
    )
    assert result["changes"] == expected
    result = lgpo.set_(
        name="Manage preview builds",
        setting="Disabled",
        policy_class="Machine",
    )
    assert result["changes"] == {}
    reg_pol.unlink()
