import pytest

import salt.loader
import salt.modules.win_lgpo as win_lgpo_module
import salt.states.win_lgpo as win_lgpo_state
from tests.support.mock import patch

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
    pytest.mark.slow_test,
]


@pytest.fixture
def configure_loader_modules(minion_opts, modules):
    loader = {
        "__opts__": minion_opts,
        "__salt__": modules,
        "__utils__": salt.loader.utils(minion_opts),
        "__context__": {},
    }
    return {
        win_lgpo_module: loader,
        win_lgpo_state: loader,
    }


@pytest.fixture
def stage_single():
    current_setting = win_lgpo_module.get_policy(
        policy_name="SeTakeOwnershipPrivilege",
        policy_class="machine",
    )
    try:
        win_lgpo_module.set_computer_policy(
            name="SeTakeOwnershipPrivilege",
            setting=["BUILTIN\\Administrators"],
            cumulative_rights_assignments=False,
        )
        yield
    finally:
        win_lgpo_module.set_computer_policy(
            name="SeTakeOwnershipPrivilege",
            setting=current_setting,
            cumulative_rights_assignments=False,
        )


@pytest.fixture
def stage_multiple():
    current_setting = win_lgpo_module.get_policy(
        policy_name="SeTakeOwnershipPrivilege",
        policy_class="machine",
    )
    try:
        win_lgpo_module.set_computer_policy(
            name="SeTakeOwnershipPrivilege",
            setting=["BUILTIN\\Administrators", "BUILTIN\\Backup Operators"],
            cumulative_rights_assignments=False,
        )
        yield
    finally:
        win_lgpo_module.set_computer_policy(
            name="SeTakeOwnershipPrivilege",
            setting=current_setting,
            cumulative_rights_assignments=False,
        )


def test_cumulative_rights_assignments(stage_single):
    expected = ["BUILTIN\\Administrators", "BUILTIN\\Backup Operators"]
    win_lgpo_state.set_(
        name="SeTakeOwnershipPrivilege",
        setting=["BUILTIN\\Backup Operators"],
        policy_class="machine",
        cumulative_rights_assignments=True,
    )
    result = win_lgpo_module.get_policy(
        policy_name="SeTakeOwnershipPrivilege",
        policy_class="machine",
    )
    assert sorted(result) == sorted(expected)


def test_cumulative_rights_assignments_test_true(stage_single):
    expected = {
        "name": "SeTakeOwnershipPrivilege",
        "result": None,
        "changes": {},
        "comment": (
            "The following policies are set to change:\nSeTakeOwnershipPrivilege"
        ),
    }
    with patch.dict(win_lgpo_state.__opts__, {"test": True}):
        result = win_lgpo_state.set_(
            name="SeTakeOwnershipPrivilege",
            setting=["BUILTIN\\Backup Operators"],
            policy_class="machine",
            cumulative_rights_assignments=True,
        )
    assert result == expected


def test_cumulative_rights_assignments_exists(stage_multiple):
    expected = {
        "name": "SeTakeOwnershipPrivilege",
        "result": True,
        "changes": {},
        "comment": "All specified policies are properly configured",
    }
    result = win_lgpo_state.set_(
        name="SeTakeOwnershipPrivilege",
        setting=["BUILTIN\\Backup Operators"],
        policy_class="machine",
        cumulative_rights_assignments=True,
    )
    assert result == expected


def test_cumulative_rights_assignments_exists_test_true(stage_multiple):
    expected = {
        "name": "SeTakeOwnershipPrivilege",
        "result": True,
        "changes": {},
        "comment": "All specified policies are properly configured",
    }
    with patch.dict(win_lgpo_state.__opts__, {"test": True}):
        result = win_lgpo_state.set_(
            name="SeTakeOwnershipPrivilege",
            setting=["BUILTIN\\Backup Operators"],
            policy_class="machine",
            cumulative_rights_assignments=True,
        )
    assert result == expected


def test_non_cumulative_rights_assignments(stage_multiple):
    expected = ["BUILTIN\\Administrators"]
    win_lgpo_state.set_(
        name="SeTakeOwnershipPrivilege",
        setting=["BUILTIN\\Administrators"],
        policy_class="machine",
        cumulative_rights_assignments=False,
    )
    result = win_lgpo_module.get_policy(
        policy_name="SeTakeOwnershipPrivilege",
        policy_class="machine",
    )
    assert sorted(result) == sorted(expected)


def test_non_cumulative_rights_assignments_test_true(stage_multiple):
    expected = {
        "name": "SeTakeOwnershipPrivilege",
        "result": None,
        "changes": {},
        "comment": (
            "The following policies are set to change:\nSeTakeOwnershipPrivilege"
        ),
    }
    with patch.dict(win_lgpo_state.__opts__, {"test": True}):
        result = win_lgpo_state.set_(
            name="SeTakeOwnershipPrivilege",
            setting=["BUILTIN\\Administrators"],
            policy_class="machine",
            cumulative_rights_assignments=False,
        )
    assert result == expected


def test_non_cumulative_rights_assignments_exists(stage_single):
    expected = {
        "name": "SeTakeOwnershipPrivilege",
        "result": True,
        "changes": {},
        "comment": "All specified policies are properly configured",
    }
    result = win_lgpo_state.set_(
        name="SeTakeOwnershipPrivilege",
        setting=["BUILTIN\\Administrators"],
        policy_class="machine",
        cumulative_rights_assignments=False,
    )
    assert result == expected


def test_non_cumulative_rights_assignments_exists_test_true(stage_single):
    expected = {
        "name": "SeTakeOwnershipPrivilege",
        "result": True,
        "changes": {},
        "comment": "All specified policies are properly configured",
    }
    with patch.dict(win_lgpo_state.__opts__, {"test": True}):
        result = win_lgpo_state.set_(
            name="SeTakeOwnershipPrivilege",
            setting=["BUILTIN\\Administrators"],
            policy_class="machine",
            cumulative_rights_assignments=False,
        )
    assert result == expected


def test_cumulative_rights_assignments_resolve_name(stage_single):
    expected = ["BUILTIN\\Administrators", "BUILTIN\\Backup Operators"]
    win_lgpo_state.set_(
        name="SeTakeOwnershipPrivilege",
        setting=["Backup Operators"],
        policy_class="machine",
        cumulative_rights_assignments=True,
    )
    result = win_lgpo_module.get_policy(
        policy_name="SeTakeOwnershipPrivilege",
        policy_class="machine",
    )
    assert sorted(result) == sorted(expected)


def test_cumulative_rights_assignments_resolve_name_test_true(stage_single):
    expected = {
        "name": "SeTakeOwnershipPrivilege",
        "result": None,
        "changes": {},
        "comment": (
            "The following policies are set to change:\nSeTakeOwnershipPrivilege"
        ),
    }
    with patch.dict(win_lgpo_state.__opts__, {"test": True}):
        result = win_lgpo_state.set_(
            name="SeTakeOwnershipPrivilege",
            setting=["Backup Operators"],
            policy_class="machine",
            cumulative_rights_assignments=True,
        )
    assert result == expected


def test_cumulative_rights_assignments_resolve_name_exists(stage_multiple):
    expected = {
        "name": "SeTakeOwnershipPrivilege",
        "result": True,
        "changes": {},
        "comment": "All specified policies are properly configured",
    }
    result = win_lgpo_state.set_(
        name="SeTakeOwnershipPrivilege",
        setting=["Backup Operators"],
        policy_class="machine",
        cumulative_rights_assignments=True,
    )
    assert result == expected


def test_cumulative_rights_assignments_resolve_name_exists_test_true(stage_multiple):
    expected = {
        "name": "SeTakeOwnershipPrivilege",
        "result": True,
        "changes": {},
        "comment": "All specified policies are properly configured",
    }
    with patch.dict(win_lgpo_state.__opts__, {"test": True}):
        result = win_lgpo_state.set_(
            name="SeTakeOwnershipPrivilege",
            setting=["Backup Operators"],
            policy_class="machine",
            cumulative_rights_assignments=True,
        )
    assert result == expected


def test_non_cumulative_rights_assignments_resolve_name(stage_multiple):
    expected = ["BUILTIN\\Administrators"]
    win_lgpo_state.set_(
        name="SeTakeOwnershipPrivilege",
        setting=["Administrators"],
        policy_class="machine",
        cumulative_rights_assignments=False,
    )
    result = win_lgpo_module.get_policy(
        policy_name="SeTakeOwnershipPrivilege",
        policy_class="machine",
    )
    assert sorted(result) == sorted(expected)


def test_non_cumulative_rights_assignments_resolve_name_test_true(stage_multiple):
    expected = {
        "name": "SeTakeOwnershipPrivilege",
        "result": None,
        "changes": {},
        "comment": (
            "The following policies are set to change:\nSeTakeOwnershipPrivilege"
        ),
    }
    with patch.dict(win_lgpo_state.__opts__, {"test": True}):
        result = win_lgpo_state.set_(
            name="SeTakeOwnershipPrivilege",
            setting=["Administrators"],
            policy_class="machine",
            cumulative_rights_assignments=False,
        )
    assert result == expected


def test_non_cumulative_rights_assignments_resolve_name_exists(stage_single):
    expected = {
        "name": "SeTakeOwnershipPrivilege",
        "result": True,
        "changes": {},
        "comment": "All specified policies are properly configured",
    }
    result = win_lgpo_state.set_(
        name="SeTakeOwnershipPrivilege",
        setting=["Administrators"],
        policy_class="machine",
        cumulative_rights_assignments=False,
    )
    assert result == expected


def test_non_cumulative_rights_assignments_resolve_name_exists_test_true(stage_single):
    expected = {
        "name": "SeTakeOwnershipPrivilege",
        "result": True,
        "changes": {},
        "comment": "All specified policies are properly configured",
    }
    with patch.dict(win_lgpo_state.__opts__, {"test": True}):
        result = win_lgpo_state.set_(
            name="SeTakeOwnershipPrivilege",
            setting=["Administrators"],
            policy_class="machine",
            cumulative_rights_assignments=False,
        )
    assert result == expected
