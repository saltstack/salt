import logging
import os
import pathlib

import pytest

import salt.modules.win_file as win_file
import salt.modules.win_lgpo as lgpo_mod
import salt.states.win_lgpo as lgpo
import salt.utils.win_dacl as win_dacl

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
    pytest.mark.slow_test,
]


@pytest.fixture
def configure_loader_modules(tmp_path):
    cachedir = tmp_path / "__test_admx_policy_cache_dir"
    cachedir.mkdir(parents=True, exist_ok=True)
    return {
        lgpo_mod: {
            "__salt__": {
                "file.file_exists": win_file.file_exists,
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
            },
        },
        win_file: {
            "__utils__": {
                "dacl.set_perms": win_dacl.set_perms,
            },
        },
    }


@pytest.fixture
def clean_comp():
    reg_pol = pathlib.Path(
        os.getenv("SystemRoot"), "System32", "GroupPolicy", "Machine", "Registry.pol"
    )
    reg_pol.unlink(missing_ok=True)
    yield reg_pol
    reg_pol.unlink(missing_ok=True)


def test_allow_telemetry_subsequent_runs(clean_comp):
    """
    Tests that the AllowTelemetry policy is applied correctly and that it
    doesn't appear in subsequent group policy states as having changed
    """
    # Set an initial state for RA_Unsolicit
    result = lgpo_mod.set_computer_policy(name="RA_Unsolicit", setting="Not Configured")
    assert result is True
    # Set AllowTelemetry
    result = lgpo_mod.set_computer_policy(name="AllowTelemetry", setting="Disabled")
    assert result is True
    expected = {
        "new": {"Computer Configuration": {"RA_Unsolicit": "Disabled"}},
        "old": {"Computer Configuration": {"RA_Unsolicit": "Not Configured"}},
    }
    # Set RA_Unsolicit with a state. AllowTelemetry should NOT be in the results
    result = lgpo.set_(
        name="RA_Unsolicit",
        setting="Disabled",
        policy_class="Machine",
    )
    # Run it again and there should be no changes
    assert result["changes"] == expected
    result = lgpo.set_(
        name="RA_Unsolicit",
        setting="Disabled",
        policy_class="Machine",
    )
    assert result["changes"] == {}
