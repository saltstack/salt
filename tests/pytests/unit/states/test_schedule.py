"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
    :codeauthor: Gareth J. Greenaway <ggreenaway@vmware.com>
"""

import pytest

import salt.modules.schedule as schedule_mod
import salt.states.schedule as schedule
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock, mock_open, patch


@pytest.fixture
def configure_loader_modules():
    return {schedule: {}}


def test_present():
    """
    Test to ensure a job is present in the schedule.
    """
    name = "job1"

    job1 = {
        "function": "test.ping",
        "maxrunning": 1,
        "name": "job1",
        "enabled": True,
        "jid_include": True,
        "when": "4:00am",
    }
    mock_lst = MagicMock(side_effect=[{}, {"job1": job1}])

    mock_build_schedule = OrderedDict(
        [
            ("function", "test.ping"),
            ("maxrunning", 1),
            ("name", "job1"),
            ("enabled", True),
            ("jid_include", True),
            ("when", "4:00am"),
        ]
    )

    mock_add = {
        "comment": "Added job: test-schedule to schedule.",
        "result": True,
        "changes": {"test-schedule": "added"},
    }

    with patch.dict(
        schedule.__salt__,
        {
            "schedule.list": mock_lst,
            "schedule.build_schedule_item": MagicMock(return_value=mock_build_schedule),
            "schedule.add": MagicMock(return_value=mock_add),
        },
    ):
        ret = {
            "name": "job1",
            "result": True,
            "changes": {"test-schedule": "added"},
            "comment": "Adding new job job1 to schedule",
        }
        _res = schedule.present(name)
        assert _res == ret

        ret = {
            "name": "job1",
            "result": True,
            "changes": {},
            "comment": "Job job1 in correct state",
        }
        _res = schedule.present(name)
        assert _res == ret

    job1 = {
        "function": "test.ping",
        "maxrunning": 1,
        "name": "job1",
        "enabled": True,
        "jid_include": True,
        "when": "4:00am",
    }
    job1_update = {
        "function": "test.ping",
        "maxrunning": 1,
        "name": "job1",
        "enabled": True,
        "jid_include": True,
        "when": "6:00am",
    }
    mock_lst = MagicMock(side_effect=[{"job1": job1}, {"job1": job1_update}])

    mock_build_schedule = OrderedDict(
        [
            ("function", "test.ping"),
            ("maxrunning", 1),
            ("name", "job1"),
            ("enabled", True),
            ("jid_include", True),
            ("when", "6:00am"),
        ]
    )

    mock_modify = {
        "comment": "Modified job: test-schedule in schedule.",
        "changes": {
            "test-schedule": {
                "old": OrderedDict(
                    [
                        ("function", "test.ping"),
                        ("maxrunning", 1),
                        ("name", "test-schedule"),
                        ("enabled", True),
                        ("jid_include", True),
                        ("when", "4:00am"),
                    ]
                ),
                "new": OrderedDict(
                    [
                        ("function", "test.ping"),
                        ("maxrunning", 1),
                        ("name", "test-schedule"),
                        ("enabled", True),
                        ("jid_include", True),
                        ("when", "6:00am"),
                    ]
                ),
            }
        },
        "result": True,
    }

    with patch.dict(
        schedule.__salt__,
        {
            "schedule.list": mock_lst,
            "schedule.build_schedule_item": MagicMock(return_value=mock_build_schedule),
            "schedule.modify": MagicMock(return_value=mock_modify),
        },
    ):
        ret = {
            "name": "job1",
            "result": True,
            "changes": {
                "test-schedule": {
                    "old": OrderedDict(
                        [
                            ("function", "test.ping"),
                            ("maxrunning", 1),
                            ("name", "test-schedule"),
                            ("enabled", True),
                            ("jid_include", True),
                            ("when", "4:00am"),
                        ]
                    ),
                    "new": OrderedDict(
                        [
                            ("function", "test.ping"),
                            ("maxrunning", 1),
                            ("name", "test-schedule"),
                            ("enabled", True),
                            ("jid_include", True),
                            ("when", "6:00am"),
                        ]
                    ),
                }
            },
            "comment": "Modifying job job1 in schedule",
        }
        _res = schedule.present(name)
        assert _res == ret

        ret = {
            "name": "job1",
            "result": True,
            "changes": {},
            "comment": "Job job1 in correct state",
        }
        _res = schedule.present(name)
        assert _res == ret

    job1 = {
        "function": "test.ping",
        "maxrunning": 1,
        "name": "job1",
        "enabled": True,
        "jid_include": True,
        "when": "4:00am",
    }
    mock_lst = MagicMock(side_effect=[{}])

    mock_build_schedule = OrderedDict(
        [
            ("function", "test.ping"),
            ("maxrunning", 1),
            ("name", "job1"),
            ("enabled", True),
            ("jid_include", True),
            ("when", "4:00am"),
        ]
    )

    mock_add = {
        "comment": "Job: test-schedule would be added to schedule.",
        "result": True,
        "changes": {},
    }

    with patch.dict(
        schedule.__salt__,
        {
            "schedule.list": mock_lst,
            "schedule.build_schedule_item": MagicMock(return_value=mock_build_schedule),
            "schedule.add": MagicMock(return_value=mock_add),
        },
    ):
        ret = {
            "name": "job1",
            "result": True,
            "changes": {},
            "comment": "Job: test-schedule would be added to schedule.",
        }
        with patch.dict(schedule.__opts__, {"test": True}):
            _res = schedule.present(name)
            assert _res == ret

    job1 = {
        "function": "test.ping",
        "maxrunning": 1,
        "name": "job1",
        "enabled": True,
        "jid_include": True,
        "when": "4:00am",
    }
    job1_update = {
        "function": "test.ping",
        "maxrunning": 1,
        "name": "job1",
        "enabled": True,
        "jid_include": True,
        "when": "6:00am",
    }
    mock_lst = MagicMock(side_effect=[{"job1": job1}, {"job1": job1_update}])

    mock_build_schedule = OrderedDict(
        [
            ("function", "test.ping"),
            ("maxrunning", 1),
            ("name", "job1"),
            ("enabled", True),
            ("jid_include", True),
            ("when", "6:00am"),
        ]
    )

    mock_modify = {
        "comment": "Job: test-schedule would be modified in schedule.",
        "changes": {
            "test-schedule": {
                "old": OrderedDict(
                    [
                        ("function", "test.ping"),
                        ("maxrunning", 1),
                        ("name", "test-schedule"),
                        ("enabled", True),
                        ("jid_include", True),
                        ("when", "4:00am"),
                    ]
                ),
                "new": OrderedDict(
                    [
                        ("function", "test.ping"),
                        ("maxrunning", 1),
                        ("name", "test-schedule"),
                        ("enabled", True),
                        ("jid_include", True),
                        ("when", "6:00am"),
                    ]
                ),
            }
        },
        "result": True,
    }

    with patch.dict(
        schedule.__salt__,
        {
            "schedule.list": mock_lst,
            "schedule.build_schedule_item": MagicMock(return_value=mock_build_schedule),
            "schedule.modify": MagicMock(return_value=mock_modify),
        },
    ):
        ret = {
            "name": "job1",
            "result": True,
            "changes": {
                "test-schedule": {
                    "old": OrderedDict(
                        [
                            ("function", "test.ping"),
                            ("maxrunning", 1),
                            ("name", "test-schedule"),
                            ("enabled", True),
                            ("jid_include", True),
                            ("when", "4:00am"),
                        ]
                    ),
                    "new": OrderedDict(
                        [
                            ("function", "test.ping"),
                            ("maxrunning", 1),
                            ("name", "test-schedule"),
                            ("enabled", True),
                            ("jid_include", True),
                            ("when", "6:00am"),
                        ]
                    ),
                }
            },
            "comment": "Job: test-schedule would be modified in schedule.",
        }
        with patch.dict(schedule.__opts__, {"test": True}):
            _res = schedule.present(name)
            assert _res == ret

    # Add job to schedule when offline=True
    job1 = {
        "function": "test.ping",
        "maxrunning": 1,
        "name": "job1",
        "enabled": True,
        "jid_include": True,
        "when": "4:00am",
        "offline": True,
    }
    mock_lst = MagicMock(return_value={})

    mock_build_schedule = OrderedDict(
        [
            ("function", "test.ping"),
            ("maxrunning", 1),
            ("name", "job1"),
            ("enabled", True),
            ("jid_include", True),
            ("when", "4:00am"),
        ]
    )

    mock_add = {
        "comment": "Adding new job test-schedule to schedule.",
        "result": True,
        "changes": {"test-schedule": "added"},
    }

    event_enter = MagicMock()
    event_enter.send.side_effect = (lambda data, tag, cb=None, timeout=60: True,)
    event = MagicMock()
    event.__enter__.return_value = event_enter

    with patch("salt.utils.event.get_event", return_value=event):
        with patch.dict(
            schedule.__salt__,
            {
                "schedule.list": mock_lst,
                "schedule.build_schedule_item": MagicMock(
                    return_value=mock_build_schedule
                ),
                "schedule.add": MagicMock(return_value=mock_add),
            },
        ):
            with patch.object(schedule_mod, "list_", mock_lst):
                with patch.object(
                    schedule_mod,
                    "_get_schedule_config_file",
                    MagicMock(return_value="/etc/salt/minion.d/_schedule.conf"),
                ):
                    with patch("salt.utils.files.fopen", mock_open()):
                        ret = {
                            "comment": "Adding new job job1 to schedule",
                            "result": True,
                            "name": "job1",
                            "changes": {"test-schedule": "added"},
                        }

                        _res = schedule.present(name, offline=True)
                        assert _res == ret
                        assert event.call_count == 0


def test_absent():
    """
    Test to ensure a job is absent from the schedule.
    """

    # Delete job from schedule
    name = "job1"

    job1 = {
        "function": "test.ping",
        "maxrunning": 1,
        "name": "job1",
        "enabled": True,
        "jid_include": True,
        "when": "4:00am",
    }
    mock_lst = MagicMock(side_effect=[{"job1": job1}])

    mock_delete = {
        "comment": "Deleted job test-schedule from schedule.",
        "result": True,
        "changes": {"test-schedule": "removed"},
    }

    with patch.dict(
        schedule.__salt__,
        {
            "schedule.list": mock_lst,
            "schedule.delete": MagicMock(return_value=mock_delete),
        },
    ):
        ret = {
            "name": "job1",
            "result": True,
            "changes": {"test-schedule": "removed"},
            "comment": "Removed job job1 from schedule",
        }
        _res = schedule.absent(name)
        assert _res == ret

    # Delete job from schedule when job does not exist
    job1 = {
        "function": "test.ping",
        "maxrunning": 1,
        "name": "job1",
        "enabled": True,
        "jid_include": True,
        "when": "4:00am",
    }
    mock_lst = MagicMock(side_effect=[{}])

    mock_delete = {
        "comment": "Job test-schedule does not exist.",
        "result": True,
        "changes": {},
    }

    with patch.dict(
        schedule.__salt__,
        {
            "schedule.list": mock_lst,
            "schedule.delete": MagicMock(return_value=mock_delete),
        },
    ):
        ret = {
            "name": "job1",
            "result": True,
            "changes": {},
            "comment": "Job job1 not present in schedule",
        }
        _res = schedule.absent(name)
        assert _res == ret

    # Delete job from schedule when test=True
    job1 = {
        "function": "test.ping",
        "maxrunning": 1,
        "name": "job1",
        "enabled": True,
        "jid_include": True,
        "when": "4:00am",
    }
    mock_lst = MagicMock(side_effect=[{"job1": job1}])

    mock_delete = {
        "comment": "Job: job1 would be deleted from schedule.",
        "result": True,
        "changes": {},
    }

    with patch.dict(
        schedule.__salt__,
        {
            "schedule.list": mock_lst,
            "schedule.delete": MagicMock(return_value=mock_delete),
        },
    ):
        ret = {
            "name": "job1",
            "result": True,
            "changes": {},
            "comment": "Job: job1 would be deleted from schedule.",
        }

        with patch.dict(schedule.__opts__, {"test": True}):
            _res = schedule.absent(name)
            assert _res == ret

    # Delete job from schedule when offline=True
    job1 = {
        "function": "test.ping",
        "maxrunning": 1,
        "name": "job1",
        "enabled": True,
        "jid_include": True,
        "when": "4:00am",
        "offline": True,
    }
    mock_lst = MagicMock(return_value={"job1": job1})

    mock_delete = {
        "comment": "Deleted Job job1 from schedule.",
        "result": True,
        "changes": {"job1": "removed"},
    }

    event_enter = MagicMock()
    event_enter.send.side_effect = (lambda data, tag, cb=None, timeout=60: True,)
    event = MagicMock()
    event.__enter__.return_value = event_enter

    with patch("salt.utils.event.get_event", return_value=event):
        with patch.dict(
            schedule.__salt__,
            {
                "schedule.list": mock_lst,
                "schedule.delete": schedule_mod.delete,
            },
        ):
            with patch.object(schedule_mod, "list_", mock_lst):
                with patch.object(
                    schedule_mod,
                    "_get_schedule_config_file",
                    MagicMock(return_value="/etc/salt/minion.d/_schedule.conf"),
                ):
                    with patch("salt.utils.files.fopen", mock_open()):
                        ret = {
                            "comment": "Removed job job1 from schedule",
                            "result": True,
                            "name": "job1",
                            "changes": {"job1": "removed"},
                        }

                        _res = schedule.absent(name, offline=True)
                        assert _res == ret
                        assert event.call_count == 0
