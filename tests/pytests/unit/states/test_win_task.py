# https://msdn.microsoft.com/en-us/library/windows/desktop/aa383608(v=vs.85).aspx

import pytest

import salt.modules.win_task
import salt.states.win_task as win_task
import salt.utils.platform
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
]


@pytest.fixture
def configure_loader_modules():
    return {win_task: {}}


def test_present():
    kwargs = {
        "action_type": "Execute",
        "cmd": "del /Q /S C:\\\\Temp",
        "trigger_type": "Once",
        "start_data": "2019-05-14",
        "start_time": "01:00 pm",
    }

    ret = {"result": False}
    try:
        with patch.dict(
            win_task.__salt__,
            {
                "task.list_tasks": salt.modules.win_task.list_tasks,
                "task.info": salt.modules.win_task.info,
                "task.create_task": salt.modules.win_task.create_task,
            },
        ), patch.dict(win_task.__opts__, {"test": False}), patch.dict(
            win_task.__grains__, {"osversion": "7.1"}
        ):

            ret = win_task.present(name="salt", location="", force=True, **kwargs)
    finally:
        try:
            salt.modules.win_task.delete_task(name="salt", location="")
        finally:
            pass

    assert ret["result"]


def test_absent():
    with patch.dict(
        win_task.__salt__,
        {
            "task.list_tasks": salt.modules.win_task.list_tasks,
            "task.info": salt.modules.win_task.info,
            "task.delete_task": salt.modules.win_task.delete_task,
        },
    ), patch.dict(win_task.__opts__, {"test": False}):
        ret = win_task.absent("salt", "")

    assert ret["result"]

    kwargs = {
        "action_type": "Execute",
        "cmd": "del /Q /S C:\\\\Temp",
        "trigger_type": "Once",
        "start_data": "2019-05-14",
        "start_time": "01:00 pm",
    }

    try:
        with patch.dict(
            win_task.__salt__,
            {
                "task.list_tasks": salt.modules.win_task.list_tasks,
                "task.info": salt.modules.win_task.info,
                "task.create_task": salt.modules.win_task.create_task,
            },
        ), patch.dict(win_task.__opts__, {"test": False}), patch.dict(
            win_task.__grains__, {"osversion": "7.1"}
        ):

            win_task.present(name="salt", location="", force=True, **kwargs)
    finally:
        try:
            with patch.dict(
                win_task.__salt__,
                {
                    "task.list_tasks": salt.modules.win_task.list_tasks,
                    "task.info": salt.modules.win_task.info,
                    "task.delete_task": salt.modules.win_task.delete_task,
                },
            ), patch.dict(win_task.__opts__, {"test": False}):
                ret = win_task.absent("salt", "")
        finally:
            pass

    assert ret["result"]


def test__get_arguments():
    kwargs = {"salt": True, "cat": "nice", "idk": 404}

    true_ret = {"salt": True, "cat": "nice", "fat": True, "idk": 404}

    ret = win_task._get_arguments(
        kwargs, ["cat"], {"nice": ["idk"], "sad": ["why"]}, {"fat": True, "salt": None}
    )

    assert ret == true_ret


def test__get_task_state_prediction():
    state = {
        "task_found": True,
        "location_valid": True,
        "task_info": {
            "conditions": {
                "ac_only": True,
                "run_if_idle": False,
                "run_if_network": False,
                "start_when_available": False,
            },
            "actions": [{"cmd": "del /Q /S C:\\\\Temp", "action_type": "Execute"}],
            "triggers": [
                {
                    "delay": False,
                    "execution_time_limit": "3 days",
                    "trigger_type": "OnSessionChange",
                    "start_date": "2019-05-14",
                    "enabled": True,
                    "start_time": "13:00:00",
                }
            ],
            "settings": {
                "delete_after": False,
                "multiple_instances": "No New Instance",
                "execution_time_limit": "3 days",
                "allow_demand_start": True,
                "restart_interval": False,
                "stop_if_on_batteries": True,
                "force_stop": True,
                "wake_to_run": False,
            },
        },
    }

    task_info = {
        "conditions": {
            "ac_only": True,
            "run_if_idle": False,
            "run_if_network": False,
            "start_when_available": False,
        },
        "trigger": {
            "end_date": None,
            "execution_time_limit": "3 days",
            "state_change": "SessionUnlock",
            "random_delay": False,
            "end_time": "00:00:00",
            "start_date": "2019-05-14",
            "repeat_duration": None,
            "start_time": "01:00 pm",
            "repeat_interval": None,
            "delay": False,
            "trigger_enabled": True,
            "trigger_type": "OnSessionChange",
            "repeat_stop_at_duration_end": False,
        },
        "action": {
            "start_in": "",
            "cmd": "del /Q /S C:\\\\Temp",
            "arguments": "",
            "action_type": "Execute",
        },
        "settings": {
            "delete_after": False,
            "multiple_instances": "No New Instance",
            "execution_time_limit": "3 days",
            "allow_demand_start": True,
            "restart_interval": False,
            "stop_if_on_batteries": True,
            "force_stop": True,
            "wake_to_run": False,
        },
    }

    prediction = win_task._get_task_state_prediction(state, task_info)
    assert state == prediction


# The following tests check if the state prediction is correct. A lot of tests
# might look the same but under the hood a lot of checks are happening. The
# Triggers Test does not test Once or Event
def test_daily():
    kwargs = {
        "action_type": "Execute",
        "cmd": "del /Q /S C:\\\\Temp",
        "trigger_type": "Daily",
        "start_date": "2019-05-14",
        "start_time": "01:00 pm",
        "days_interval": 101,
    }

    info = {
        "triggers": [
            {
                "random_delay": False,
                "trigger_type": "Daily",
                "execution_time_limit": "3 days",
                "start_time": "13:00:00",
                "enabled": True,
                "start_date": "2019-05-14",
            }
        ],
        "actions": [{"cmd": "del /Q /S C:\\\\Temp", "action_type": "Execute"}],
        "conditions": {
            "start_when_available": False,
            "run_if_network": False,
            "ac_only": True,
            "run_if_idle": False,
        },
        "settings": {
            "wake_to_run": False,
            "allow_demand_start": True,
            "multiple_instances": "No New Instance",
            "execution_time_limit": "3 days",
            "force_stop": True,
            "delete_after": False,
            "stop_if_on_batteries": True,
            "restart_interval": False,
        },
    }

    with patch.dict(
        win_task.__salt__,
        {
            "task.list_tasks": MagicMock(side_effect=[["salt"]] * 2),
            "task.info": MagicMock(side_effect=[info]),
        },
    ), patch.dict(win_task.__opts__, {"test": True}), patch.dict(
        win_task.__grains__, {"osversion": "7.1"}
    ):
        ret = win_task.present(name="salt", location="", force=True, **kwargs)
        assert ret["result"]


def test_weekly():
    kwargs = {
        "action_type": "Execute",
        "cmd": "del /Q /S C:\\\\Temp",
        "trigger_type": "Weekly",
        "start_date": "2019-05-14",
        "start_time": "01:00 pm",
        "days_of_week": ["Monday", "Wednesday", "Friday"],
        "weeks_interval": 1,
    }

    info = {
        "triggers": [
            {
                "start_date": "2019-05-14",
                "execution_time_limit": "3 days",
                "random_delay": False,
                "enabled": True,
                "start_time": "13:00:00",
                "trigger_type": "Weekly",
            }
        ],
        "actions": [{"cmd": "del /Q /S C:\\\\Temp", "action_type": "Execute"}],
        "conditions": {
            "start_when_available": False,
            "run_if_idle": False,
            "run_if_network": False,
            "ac_only": True,
        },
        "settings": {
            "allow_demand_start": True,
            "wake_to_run": False,
            "execution_time_limit": "3 days",
            "force_stop": True,
            "multiple_instances": "No New Instance",
            "stop_if_on_batteries": True,
            "restart_interval": False,
            "delete_after": False,
        },
    }

    with patch.dict(
        win_task.__salt__,
        {
            "task.list_tasks": MagicMock(side_effect=[["salt"]] * 2),
            "task.info": MagicMock(side_effect=[info]),
        },
    ), patch.dict(win_task.__opts__, {"test": True}), patch.dict(
        win_task.__grains__, {"osversion": "7.1"}
    ):
        ret = win_task.present(name="salt", location="", force=True, **kwargs)
        assert ret["result"]


def test_monthly():
    kwargs = {
        "action_type": "Execute",
        "cmd": "del /Q /S C:\\\\Temp",
        "trigger_type": "Monthly",
        "start_date": "2019-05-14",
        "start_time": "01:00 pm",
        "months_of_year": ["January", "July"],
        "days_of_month": [6, 16, 26],
        "last_day_of_month": True,
    }

    info = {
        "triggers": [
            {
                "start_date": "2019-05-14",
                "random_delay": False,
                "trigger_type": "Monthly",
                "execution_time_limit": "3 days",
                "start_time": "13:00:00",
                "enabled": True,
            }
        ],
        "actions": [{"cmd": "del /Q /S C:\\\\Temp", "action_type": "Execute"}],
        "conditions": {
            "run_if_idle": False,
            "run_if_network": False,
            "start_when_available": False,
            "ac_only": True,
        },
        "settings": {
            "force_stop": True,
            "allow_demand_start": True,
            "delete_after": False,
            "multiple_instances": "No New Instance",
            "execution_time_limit": "3 days",
            "stop_if_on_batteries": True,
            "restart_interval": False,
            "wake_to_run": False,
        },
    }

    with patch.dict(
        win_task.__salt__,
        {
            "task.list_tasks": MagicMock(side_effect=[["salt"]] * 2),
            "task.info": MagicMock(side_effect=[info]),
        },
    ), patch.dict(win_task.__opts__, {"test": True}), patch.dict(
        win_task.__grains__, {"osversion": "7.1"}
    ):
        ret = win_task.present(name="salt", location="", force=True, **kwargs)
        assert ret["result"]


def test_monthly_day():
    kwargs = {
        "action_type": "Execute",
        "cmd": "del /Q /S C:\\\\Temp",
        "trigger_type": "MonthlyDay",
        "start_date": "2019-05-14",
        "start_time": "01:00 pm",
        "months_of_year": ["January", "July"],
        "weeks_of_month": ["First", "Third"],
        "last_week_of_month": True,
        "days_of_week": ["Monday", "Wednesday", "Friday"],
    }

    info = {
        "triggers": [
            {
                "start_date": "2019-05-14",
                "random_delay": False,
                "trigger_type": "MonthlyDay",
                "execution_time_limit": "3 days",
                "start_time": "13:00:00",
                "enabled": True,
            }
        ],
        "actions": [{"cmd": "del /Q /S C:\\\\Temp", "action_type": "Execute"}],
        "conditions": {
            "run_if_idle": False,
            "run_if_network": False,
            "start_when_available": False,
            "ac_only": True,
        },
        "settings": {
            "force_stop": True,
            "allow_demand_start": True,
            "delete_after": False,
            "multiple_instances": "No New Instance",
            "execution_time_limit": "3 days",
            "stop_if_on_batteries": True,
            "restart_interval": False,
            "wake_to_run": False,
        },
    }

    with patch.dict(
        win_task.__salt__,
        {
            "task.list_tasks": MagicMock(side_effect=[["salt"]] * 2),
            "task.info": MagicMock(side_effect=[info]),
        },
    ), patch.dict(win_task.__opts__, {"test": True}), patch.dict(
        win_task.__grains__, {"osversion": "7.1"}
    ):

        ret = win_task.present(name="salt", location="", force=True, **kwargs)
        assert ret["result"]


def test_on_idle():
    kwargs = {
        "action_type": "Execute",
        "cmd": "del /Q /S C:\\\\Temp",
        "trigger_type": "OnIdle",
        "start_date": "2019-05-14",
        "start_time": "01:00 pm",
    }

    info = {
        "triggers": [
            {
                "start_date": "2019-05-14",
                "random_delay": False,
                "trigger_type": "OnIdle",
                "execution_time_limit": "3 days",
                "start_time": "13:00:00",
                "enabled": True,
            }
        ],
        "actions": [{"cmd": "del /Q /S C:\\\\Temp", "action_type": "Execute"}],
        "conditions": {
            "run_if_idle": False,
            "run_if_network": False,
            "start_when_available": False,
            "ac_only": True,
        },
        "settings": {
            "force_stop": True,
            "allow_demand_start": True,
            "delete_after": False,
            "multiple_instances": "No New Instance",
            "execution_time_limit": "3 days",
            "stop_if_on_batteries": True,
            "restart_interval": False,
            "wake_to_run": False,
        },
    }

    with patch.dict(
        win_task.__salt__,
        {
            "task.list_tasks": MagicMock(side_effect=[["salt"]] * 2),
            "task.info": MagicMock(side_effect=[info]),
        },
    ), patch.dict(win_task.__opts__, {"test": True}), patch.dict(
        win_task.__grains__, {"osversion": "7.1"}
    ):
        ret = win_task.present(name="salt", location="", force=True, **kwargs)
        assert ret["result"]


def test_on_task_creation():
    kwargs = {
        "action_type": "Execute",
        "cmd": "del /Q /S C:\\\\Temp",
        "trigger_type": "OnTaskCreation",
        "start_date": "2019-05-14",
        "start_time": "01:00 pm",
    }

    info = {
        "triggers": [
            {
                "start_date": "2019-05-14",
                "random_delay": False,
                "trigger_type": "OnTaskCreation",
                "execution_time_limit": "3 days",
                "start_time": "13:00:00",
                "enabled": True,
            }
        ],
        "actions": [{"cmd": "del /Q /S C:\\\\Temp", "action_type": "Execute"}],
        "conditions": {
            "run_if_idle": False,
            "run_if_network": False,
            "start_when_available": False,
            "ac_only": True,
        },
        "settings": {
            "force_stop": True,
            "allow_demand_start": True,
            "delete_after": False,
            "multiple_instances": "No New Instance",
            "execution_time_limit": "3 days",
            "stop_if_on_batteries": True,
            "restart_interval": False,
            "wake_to_run": False,
        },
    }

    with patch.dict(
        win_task.__salt__,
        {
            "task.list_tasks": MagicMock(side_effect=[["salt"]] * 2),
            "task.info": MagicMock(side_effect=[info]),
        },
    ), patch.dict(win_task.__opts__, {"test": True}), patch.dict(
        win_task.__grains__, {"osversion": "7.1"}
    ):

        ret = win_task.present(name="salt", location="", force=True, **kwargs)
        assert ret["result"]


def test_on_boot():
    kwargs = {
        "action_type": "Execute",
        "cmd": "del /Q /S C:\\\\Temp",
        "trigger_type": "OnBoot",
        "start_date": "2019-05-14",
        "start_time": "01:00 pm",
    }

    info = {
        "triggers": [
            {
                "start_date": "2019-05-14",
                "random_delay": False,
                "trigger_type": "OnBoot",
                "execution_time_limit": "3 days",
                "start_time": "13:00:00",
                "enabled": True,
                "delay": False,
            }
        ],
        "actions": [{"cmd": "del /Q /S C:\\\\Temp", "action_type": "Execute"}],
        "conditions": {
            "run_if_idle": False,
            "run_if_network": False,
            "start_when_available": False,
            "ac_only": True,
        },
        "settings": {
            "force_stop": True,
            "allow_demand_start": True,
            "delete_after": False,
            "multiple_instances": "No New Instance",
            "execution_time_limit": "3 days",
            "stop_if_on_batteries": True,
            "restart_interval": False,
            "wake_to_run": False,
        },
    }

    with patch.dict(
        win_task.__salt__,
        {
            "task.list_tasks": MagicMock(side_effect=[["salt"]] * 2),
            "task.info": MagicMock(side_effect=[info]),
        },
    ), patch.dict(win_task.__opts__, {"test": True}), patch.dict(
        win_task.__grains__, {"osversion": "7.1"}
    ):

        ret = win_task.present(name="salt", location="", force=True, **kwargs)
        assert ret["result"]


def test_on_logon():
    kwargs = {
        "action_type": "Execute",
        "cmd": "del /Q /S C:\\\\Temp",
        "trigger_type": "OnLogon",
        "start_date": "2019-05-14",
        "start_time": "01:00 pm",
    }

    info = {
        "triggers": [
            {
                "start_date": "2019-05-14",
                "random_delay": False,
                "trigger_type": "OnLogon",
                "execution_time_limit": "3 days",
                "start_time": "13:00:00",
                "enabled": True,
            }
        ],
        "actions": [{"cmd": "del /Q /S C:\\\\Temp", "action_type": "Execute"}],
        "conditions": {
            "run_if_idle": False,
            "run_if_network": False,
            "start_when_available": False,
            "ac_only": True,
        },
        "settings": {
            "force_stop": True,
            "allow_demand_start": True,
            "delete_after": False,
            "multiple_instances": "No New Instance",
            "execution_time_limit": "3 days",
            "stop_if_on_batteries": True,
            "restart_interval": False,
            "wake_to_run": False,
        },
    }

    with patch.dict(
        win_task.__salt__,
        {
            "task.list_tasks": MagicMock(side_effect=[["salt"]] * 2),
            "task.info": MagicMock(side_effect=[info]),
        },
    ), patch.dict(win_task.__opts__, {"test": True}), patch.dict(
        win_task.__grains__, {"osversion": "7.1"}
    ):

        ret = win_task.present(name="salt", location="", force=True, **kwargs)
        assert ret["result"]


def test_on_session_change():
    kwargs = {
        "action_type": "Execute",
        "cmd": "del /Q /S C:\\\\Temp",
        "trigger_type": "OnSessionChange",
        "start_date": "2019-05-14",
        "start_time": "01:00 pm",
        "state_change": "SessionUnlock",
    }

    info = {
        "actions": [{"cmd": "del /Q /S C:\\\\Temp", "action_type": "Execute"}],
        "settings": {
            "delete_after": False,
            "execution_time_limit": "3 days",
            "wake_to_run": False,
            "force_stop": True,
            "multiple_instances": "No New Instance",
            "stop_if_on_batteries": True,
            "restart_interval": False,
            "allow_demand_start": True,
        },
        "triggers": [
            {
                "trigger_type": "OnSessionChange",
                "execution_time_limit": "3 days",
                "delay": False,
                "enabled": True,
                "start_date": "2019-05-14",
                "start_time": "13:00:00",
            }
        ],
        "conditions": {
            "run_if_idle": False,
            "ac_only": True,
            "run_if_network": False,
            "start_when_available": False,
        },
    }

    with patch.dict(
        win_task.__salt__,
        {
            "task.list_tasks": MagicMock(side_effect=[["salt"]] * 2),
            "task.info": MagicMock(side_effect=[info]),
        },
    ), patch.dict(win_task.__opts__, {"test": True}), patch.dict(
        win_task.__grains__, {"osversion": "7.1"}
    ):
        ret = win_task.present(name="salt", location="", force=True, **kwargs)

        assert ret["result"]
