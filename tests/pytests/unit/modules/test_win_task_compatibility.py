"""
Unit tests for the compatibility parameter in win_task.create_task and
win_task.edit_task. These tests use mocks and run on any platform.
"""

import sys
import types

import pytest

from tests.support.mock import MagicMock, patch

# Inject a stub win32com into sys.modules if not already present so that
# salt.modules.win_task can be imported on non-Windows hosts.
if "win32com" not in sys.modules:
    _win32com = types.ModuleType("win32com")
    _win32com_client = types.ModuleType("win32com.client")
    _win32com_client.Dispatch = MagicMock()
    _win32com.client = _win32com_client
    sys.modules["win32com"] = _win32com
    sys.modules["win32com.client"] = _win32com_client
if "pythoncom" not in sys.modules:
    sys.modules["pythoncom"] = types.ModuleType("pythoncom")
if "pywintypes" not in sys.modules:
    sys.modules["pywintypes"] = types.ModuleType("pywintypes")

import salt.modules.win_task as win_task  # noqa: E402


@pytest.mark.parametrize(
    "compatibility",
    [
        0,  # Windows 2000/XP/2003
        1,  # Windows Vista/2008 (V1 task)
        2,  # Windows 7/2008 R2 (V2 task)
        3,  # Windows 10
    ],
)
def test_edit_task_compatibility(compatibility):
    """
    edit_task sets Settings.Compatibility to the given value when a
    task_definition is passed directly (no COM lookup needed).
    """
    mock_task_def = MagicMock()
    mock_task_def.Principal.UserID = "SYSTEM"
    mock_task_def.Principal.LogonType = 5  # TASK_LOGON_SERVICE_ACCOUNT

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
    mock_task_def.Principal.UserID = "SYSTEM"
    mock_task_def.Principal.LogonType = 5

    # Snapshot the auto-generated MagicMock child before the call
    sentinel = mock_task_def.Settings.Compatibility

    with patch("salt.utils.winapi.Com", MagicMock()):
        win_task.edit_task(
            task_definition=mock_task_def,
            compatibility=None,
        )

    # If the branch was skipped, the attribute is still the same mock object
    assert mock_task_def.Settings.Compatibility is sentinel


def test_create_task_passes_compatibility_to_edit_task():
    """
    create_task forwards its compatibility= argument to edit_task so that
    Settings.Compatibility is set on the new task definition.
    """
    mock_task_def = MagicMock()
    mock_task_def.Principal.UserID = "SYSTEM"
    mock_task_def.Principal.LogonType = 5

    mock_task_service = MagicMock()
    mock_task_service.NewTask.return_value = mock_task_def

    with (
        patch("salt.utils.winapi.Com", MagicMock()),
        patch.object(
            win_task.win32com.client, "Dispatch", return_value=mock_task_service
        ),
        patch.object(win_task, "list_tasks", return_value=[]),
        patch.object(win_task, "add_action", return_value=True),
        patch.object(win_task, "add_trigger", return_value=True),
        patch.object(win_task, "_save_task_definition", return_value=True),
    ):
        win_task.create_task(
            "TestTask",
            user_name="System",
            force=True,
            compatibility=1,
            action_type="Execute",
            cmd="cmd.exe",
        )

    assert mock_task_def.Settings.Compatibility == 1
