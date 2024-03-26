"""
Test the win_task execution module
"""

from datetime import datetime

import pytest

import salt.modules.win_task as win_task

pytestmark = [
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
]


@pytest.fixture(scope="function")
def base_task():
    task_name = "SaltTest"
    result = win_task.create_task(
        task_name,
        user_name="System",
        force=True,
        action_type="Execute",
        cmd="c:\\salt\\salt-call.bat",
    )
    assert result is True
    yield task_name
    result = win_task.delete_task(task_name)
    assert result is True


def test_repeat_interval(base_task):
    result = win_task.add_trigger(
        base_task,
        trigger_type="Daily",
        trigger_enabled=True,
        repeat_duration="30 minutes",
        repeat_interval="30 minutes",
    )
    assert result is True

    result = win_task.info(base_task)
    assert result["triggers"][0]["enabled"] is True
    assert result["triggers"][0]["trigger_type"] == "Daily"
    assert result["triggers"][0]["repeat_duration"] == "30 minutes"
    assert result["triggers"][0]["repeat_interval"] == "30 minutes"


def test_repeat_interval_and_indefinitely(base_task):
    result = win_task.add_trigger(
        base_task,
        trigger_type="Daily",
        trigger_enabled=True,
        repeat_duration="Indefinitely",
        repeat_interval="30 minutes",
    )
    assert result is True

    result = win_task.info(base_task)
    assert result["triggers"][0]["enabled"] is True
    assert result["triggers"][0]["trigger_type"] == "Daily"
    assert result["triggers"][0]["repeat_duration"] == "Indefinitely"
    assert result["triggers"][0]["repeat_interval"] == "30 minutes"


def test_edit_task_delete_after(base_task):
    result = win_task.add_trigger(
        base_task,
        trigger_type="Daily",
        trigger_enabled=True,
        end_date=datetime.today().strftime("%Y-%m-%d"),
        end_time="23:59:59",
    )
    assert result is True

    result = win_task.edit_task(base_task, delete_after="30 days")
    assert result is True

    result = win_task.info(base_task)
    assert result["settings"]["delete_after"] == "30 days"

    result = win_task.edit_task(base_task, delete_after=False)
    assert result is True

    result = win_task.info(base_task)
    assert result["settings"]["delete_after"] is False
