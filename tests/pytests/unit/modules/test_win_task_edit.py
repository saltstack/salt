"""
Unit tests for the win_task execution module's edit_task validation logic.

These tests mock the win32com Task Definition object so the validation
logic in :func:`salt.modules.win_task.edit_task` can be exercised on any
platform.
"""

import pytest

import salt.modules.win_task as win_task
from tests.support.mock import MagicMock, patch


@pytest.fixture
def task_definition():
    """
    A MagicMock standing in for a win32com Task Definition object.

    ``Settings.RestartInterval`` is set to a truthy value so the
    ``restart_count`` validation branch in ``edit_task`` is reached.
    """
    definition = MagicMock()
    definition.Settings.RestartInterval = "PT1H"
    definition.Settings.RunOnlyIfIdle = False
    definition.Settings.RunOnlyIfNetworkAvailable = False
    return definition


@pytest.mark.parametrize("restart_count", [1, 500, 998, 999])
def test_edit_task_restart_count_accepts_valid_range(task_definition, restart_count):
    """
    ``edit_task`` must accept restart_count values 1 through 999 inclusive
    when restart_every is set.

    Regression test for https://github.com/saltstack/salt/issues/68419 —
    the validation used ``range(1, 999)`` which excluded 999 even though
    the error message claims ``"must be a value between 1 and 999"``.
    """
    with patch.object(win_task.salt.utils.winapi, "Com", MagicMock()):
        result = win_task.edit_task(
            name="dummy",
            restart_every="1 hour",
            restart_count=restart_count,
            task_definition=task_definition,
        )

    # The validation error string must not be returned for valid values.
    assert result != '"restart_count" must be a value between 1 and 999'
    # And RestartCount must have been assigned to the mock.
    assert task_definition.Settings.RestartCount == restart_count


@pytest.mark.parametrize("restart_count", [0, 1000, -1])
def test_edit_task_restart_count_rejects_invalid(task_definition, restart_count):
    """
    ``edit_task`` must reject restart_count values outside 1..999.
    """
    with patch.object(win_task.salt.utils.winapi, "Com", MagicMock()):
        result = win_task.edit_task(
            name="dummy",
            restart_every="1 hour",
            restart_count=restart_count,
            task_definition=task_definition,
        )

    assert result == '"restart_count" must be a value between 1 and 999'
