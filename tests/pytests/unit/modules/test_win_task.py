"""
Test the win_task execution module
"""

from datetime import datetime

import pytest

import salt.modules.win_task as win_task
from salt.exceptions import CommandExecutionError

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


def test_execution_time_limit(base_task):
    result = win_task.add_trigger(
        base_task,
        trigger_type="Daily",
        trigger_enabled=True,
        end_date=datetime.today().strftime("%Y-%m-%d"),
        end_time="23:59:59",
    )
    assert result is True

    result = win_task.edit_task(base_task, execution_time_limit="1 hour")
    assert result is True

    result = win_task.info(base_task)
    assert result["settings"]["execution_time_limit"] == "1 hour"

    result = win_task.edit_task(base_task, execution_time_limit=False)
    assert result is True

    result = win_task.info(base_task)
    assert result["settings"]["execution_time_limit"] is False


@pytest.mark.parametrize(
    "exitcode, expect",
    [
        (0, "The operation completed successfully"),
        (3221225786, "The application terminated as a result of CTRL+C"),
        (4289449455, "Unknown Task Result: 0xffabcdef"),
    ],
)
def test_run_result_code(exitcode, expect):
    task_name = "SaltTest"
    try:
        result = win_task.create_task(
            task_name,
            user_name="System",
            force=True,
            action_type="Execute",
            cmd="cmd.exe",
            arguments=f"/c exit {exitcode}",
        )
        assert result is True

        result = win_task.info(task_name)
        assert result["last_run_result"] == "Task has not yet run"

        result = win_task.run_wait(task_name)
        assert result is True

        result = win_task.info(task_name)
        assert result["last_run_result"] == expect
    finally:
        result = win_task.delete_task(task_name)
        assert result is True


def test_create_task_from_xml():
    task_name = "SaltTest"
    task_xml = '<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"><Actions><Exec><Command>cmd.exe</Command><Arguments>/c exit</Arguments></Exec></Actions></Task>'
    try:
        result = win_task.create_task_from_xml(
            task_name, user_name="System", xml_text=task_xml
        )
        assert result is True

        result = win_task.info(task_name)
        assert result["actions"][0]["action_type"] == "Execute"
        assert result["actions"][0]["cmd"] == "cmd.exe"
        assert result["actions"][0]["arguments"] == "/c exit"

    finally:
        result = win_task.delete_task(task_name)
        assert result is True


def test_create_task_from_xml_error():
    task_name = "SaltTest"
    try:
        with pytest.raises(CommandExecutionError) as excinfo:
            result = win_task.create_task_from_xml(
                task_name, user_name="System", xml_text="test"
            )
            assert result is False
        assert "The task XML is malformed" in str(excinfo.value)
    finally:
        result = win_task.delete_task(task_name)
        assert result is not True
