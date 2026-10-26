"""
Unit tests for the compatibility parameter in win_task.create_task and
win_task.edit_task. These tests use mocks and run on any platform.
"""

import types

import pytest

import salt.modules.win_task as win_task
from tests.support.mock import MagicMock, patch


@pytest.mark.parametrize(
    "compatibility",
    [
        0,  # AT command compatibility
        1,  # Task Scheduler 1.0 (Server 2003/XP/2000)
        2,  # Task Scheduler 2.0 (Vista/2008 and later)
        3,  # Task Scheduler 3.0 (Windows 10 and later)
    ],
)
def test_edit_task_compatibility(compatibility):
    """
    edit_task sets Settings.Compatibility to the given value when a
    task_definition is passed directly (no COM lookup needed).
    """
    mock_task_def = MagicMock()

    with patch("salt.utils.winapi.Com", MagicMock()):
        win_task.edit_task(
            task_definition=mock_task_def,
            compatibility=compatibility,
        )

    assert mock_task_def.Settings.Compatibility == compatibility


def test_edit_task_compatibility_none_leaves_unset():
    """
    edit_task does not touch Settings.Compatibility when compatibility=None.
    """
    mock_task_def = MagicMock()

    # Snapshot the auto-generated MagicMock child before the call
    sentinel = mock_task_def.Settings.Compatibility

    with patch("salt.utils.winapi.Com", MagicMock()):
        win_task.edit_task(
            task_definition=mock_task_def,
            compatibility=None,
        )

    # If the branch was skipped, the attribute is still the same mock object
    assert mock_task_def.Settings.Compatibility is sentinel


@pytest.mark.parametrize("compatibility", [-1, 4, "V1"])
def test_edit_task_compatibility_invalid(compatibility):
    """
    edit_task rejects compatibility values outside 0-3 and leaves the
    task definition untouched.
    """
    mock_task_def = MagicMock()

    # Snapshot the auto-generated MagicMock child before the call
    sentinel = mock_task_def.Settings.Compatibility

    with patch("salt.utils.winapi.Com", MagicMock()):
        result = win_task.edit_task(
            task_definition=mock_task_def,
            compatibility=compatibility,
        )

    assert result == 'Invalid value for "compatibility"'
    assert mock_task_def.Settings.Compatibility is sentinel


def test_create_task_passes_compatibility_to_edit_task():
    """
    create_task forwards its compatibility= argument to edit_task so that
    Settings.Compatibility is set on the new task definition.
    """
    stub_client = MagicMock()
    stub_client.Dispatch.return_value = MagicMock()
    stub_win32com = types.SimpleNamespace(client=stub_client)

    with patch("salt.utils.winapi.Com", MagicMock()), patch.object(
        win_task, "win32com", stub_win32com, create=True
    ), patch.object(win_task, "edit_task") as mock_edit, patch.object(
        win_task, "list_tasks", return_value=[]
    ), patch.object(
        win_task, "add_action", return_value=True
    ), patch.object(
        win_task, "add_trigger", return_value=True
    ), patch.object(
        win_task, "_save_task_definition", return_value=True
    ):
        win_task.create_task(
            "TestTask",
            user_name="System",
            force=True,
            compatibility=1,
            action_type="Execute",
            cmd="cmd.exe",
        )

    assert mock_edit.call_args.kwargs["compatibility"] == 1
