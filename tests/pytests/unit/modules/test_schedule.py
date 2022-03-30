"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import datetime
import logging

import pytest
import salt.modules.schedule as schedule
import salt.utils.odict
from salt.utils.event import SaltEvent
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock, call, mock_open, patch

log = logging.getLogger(__name__)


@pytest.fixture
def job1():
    return {
        "function": "test.ping",
        "maxrunning": 1,
        "name": "job1",
        "jid_include": True,
        "enabled": True,
    }


@pytest.fixture
def sock_dir(tmp_path):
    return str(tmp_path / "test-socks")


@pytest.fixture
def configure_loader_modules():
    return {schedule: {}}


# 'purge' function tests: 1
@pytest.mark.slow_test
def test_purge(sock_dir, job1):
    """
    Test if it purge all the jobs currently scheduled on the minion.
    """
    _schedule_data = {"job1": job1}
    with patch.dict(schedule.__opts__, {"schedule": {}, "sock_dir": sock_dir}):
        mock = MagicMock(return_value=True)
        with patch.dict(schedule.__salt__, {"event.fire": mock}):
            _ret_value = {"complete": True, "schedule": {}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                with patch.object(
                    schedule, "list_", MagicMock(return_value=_schedule_data)
                ):
                    assert schedule.purge() == {
                        "comment": ["Deleted job: job1 from schedule."],
                        "changes": {"job1": "removed"},
                        "result": True,
                    }

    _schedule_data = {"job1": job1, "job2": job1, "job3": job1}
    comm = [
        "Deleted job: job1 from schedule.",
        "Deleted job: job2 from schedule.",
        "Deleted job: job3 from schedule.",
    ]

    changes = {"job1": "removed", "job2": "removed", "job3": "removed"}

    schedule_config_file = schedule._get_schedule_config_file()
    with patch.dict(
        schedule.__opts__, {"schedule": {"job1": "salt"}, "sock_dir": sock_dir}
    ):
        with patch("salt.utils.files.fopen", mock_open(read_data="")) as fopen_mock:
            with patch.object(
                schedule, "list_", MagicMock(return_value=_schedule_data)
            ):
                ret = schedule.purge(offline=True)
                assert any([True for item in comm if item in ret["comment"]])
                assert ret["changes"] == changes
                assert ret["result"]

                _call = call(b"schedule: {}\n")
                write_calls = fopen_mock.filehandles[schedule_config_file][
                    0
                ].write._mock_mock_calls
                assert _call in write_calls


# 'delete' function tests: 1
@pytest.mark.slow_test
def test_delete(sock_dir, job1):
    """
    Test if it delete a job from the minion's schedule.
    """
    with patch.dict(schedule.__opts__, {"schedule": {}, "sock_dir": sock_dir}):
        mock = MagicMock(return_value=True)
        with patch.dict(schedule.__salt__, {"event.fire": mock}):
            _ret_value = {"complete": True, "schedule": {}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                assert schedule.delete("job1") == {
                    "comment": "Job job1 does not exist.",
                    "changes": {},
                    "result": False,
                }

    _schedule_data = {"job1": job1}
    comm = "Deleted Job job1 from schedule."
    changes = {"job1": "removed"}
    schedule_config_file = schedule._get_schedule_config_file()
    with patch.dict(
        schedule.__opts__, {"schedule": {"job1": "salt"}, "sock_dir": sock_dir}
    ):
        with patch("salt.utils.files.fopen", mock_open(read_data="")) as fopen_mock:
            with patch.object(
                schedule, "list_", MagicMock(return_value=_schedule_data)
            ):
                assert schedule.delete("job1", offline="True") == {
                    "comment": comm,
                    "changes": changes,
                    "result": True,
                }

                _call = call(b"schedule: {}\n")
                write_calls = fopen_mock.filehandles[schedule_config_file][
                    0
                ].write._mock_mock_calls
                assert _call in write_calls


# 'build_schedule_item' function tests: 1
def test_build_schedule_item(sock_dir):
    """
    Test if it build a schedule job.
    """
    comment = (
        'Unable to use "seconds", "minutes", "hours", '
        'or "days" with "when" or "cron" options.'
    )
    comment1 = 'Unable to use "when" and "cron" options together.  Ignoring.'
    with patch.dict(schedule.__opts__, {"job1": {}}):
        assert schedule.build_schedule_item("") == {
            "comment": "Job name is required.",
            "result": False,
        }

        assert schedule.build_schedule_item("job1", function="test.ping") == {
            "function": "test.ping",
            "maxrunning": 1,
            "name": "job1",
            "jid_include": True,
            "enabled": True,
        }

        assert schedule.build_schedule_item(
            "job1", function="test.ping", seconds=3600, when="2400"
        ) == {"comment": comment, "result": False}

        assert schedule.build_schedule_item(
            "job1", function="test.ping", when="2400", cron="2"
        ) == {"comment": comment1, "result": False}


# 'build_schedule_item_invalid_when' function tests: 1


def test_build_schedule_item_invalid_when(sock_dir):
    """
    Test if it build a schedule job.
    """
    comment = 'Schedule item garbage for "when" in invalid.'
    with patch.dict(schedule.__opts__, {"job1": {}}):
        assert schedule.build_schedule_item(
            "job1", function="test.ping", when="garbage"
        ) == {"comment": comment, "result": False}


def test_build_schedule_item_invalid_jobs_args(sock_dir):
    """
    Test failure if job_arg and job_kwargs are passed correctly
    """
    comment1 = "job_kwargs is not a dict. please correct and try again."
    comment2 = "job_args is not a list. please correct and try again."
    with patch.dict(schedule.__opts__, {"job1": {}}):
        assert schedule.build_schedule_item(
            "job1", function="test.args", job_kwargs=[{"key1": "value1"}]
        ) == {"comment": comment1, "result": False}
    with patch.dict(schedule.__opts__, {"job1": {}}):
        assert schedule.build_schedule_item(
            "job1", function="test.args", job_args={"positional"}
        ) == {"comment": comment2, "result": False}


# 'add' function tests: 1


@pytest.mark.slow_test
def test_add(sock_dir):
    """
    Test if it add a job to the schedule.
    """
    comm1 = "Job job1 already exists in schedule."
    comm2 = (
        'Error: Unable to use "seconds", "minutes", "hours", '
        'or "days" with "when" or "cron" options.'
    )
    comm3 = 'Unable to use "when" and "cron" options together.  Ignoring.'
    comm4 = "Job: job2 would be added to schedule."
    with patch.dict(
        schedule.__opts__, {"schedule": {"job1": "salt"}, "sock_dir": sock_dir}
    ):
        mock = MagicMock(return_value=True)
        with patch.dict(schedule.__salt__, {"event.fire": mock}):
            _ret_value = {"complete": True, "schedule": {"job1": {"salt": "salt"}}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                assert schedule.add("job1") == {
                    "comment": comm1,
                    "changes": {},
                    "result": False,
                }

            _ret_value = {"complete": True, "schedule": {}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                assert schedule.add(
                    "job2", function="test.ping", seconds=3600, when="2400"
                ) == {"comment": comm2, "changes": {}, "result": False}

            _ret_value = {"complete": True, "schedule": {}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                assert schedule.add(
                    "job2", function="test.ping", when="2400", cron="2"
                ) == {"comment": comm3, "changes": {}, "result": False}
            _ret_value = {"complete": True, "schedule": {}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                assert schedule.add("job2", function="test.ping", test=True) == {
                    "comment": comm4,
                    "changes": {},
                    "result": True,
                }

    schedule_config_file = schedule._get_schedule_config_file()
    comm1 = "Added job: job3 to schedule."
    changes1 = {"job3": "added"}
    with patch.dict(
        schedule.__opts__, {"schedule": {"job1": "salt"}, "sock_dir": sock_dir}
    ):
        with patch("os.path.exists", MagicMock(return_value=True)):
            with patch("salt.utils.files.fopen", mock_open(read_data="")) as fopen_mock:
                assert schedule.add(
                    "job3", function="test.ping", seconds=3600, offline="True"
                ) == {"comment": comm1, "changes": changes1, "result": True}

                _call = call(
                    b"schedule:\n  job3: {function: test.ping, seconds: 3600, maxrunning: 1, name: job3, enabled: true,\n    jid_include: true}\n"
                )
                write_calls = fopen_mock.filehandles[schedule_config_file][
                    1
                ].write._mock_mock_calls
                assert _call in write_calls


# 'run_job' function tests: 1


@pytest.mark.slow_test
def test_run_job(sock_dir, job1):
    """
    Test if it run a scheduled job on the minion immediately.
    """
    with patch.dict(
        schedule.__opts__, {"schedule": {"job1": job1}, "sock_dir": sock_dir}
    ):
        mock = MagicMock(return_value=True)
        with patch.dict(schedule.__salt__, {"event.fire": mock}):
            _ret_value = {"complete": True, "schedule": {"job1": job1}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                assert schedule.run_job("job1") == {
                    "comment": "Scheduling Job job1 on minion.",
                    "result": True,
                }


# 'enable_job' function tests: 1


@pytest.mark.slow_test
def test_enable_job(sock_dir):
    """
    Test if it enable a job in the minion's schedule.
    """
    with patch.dict(schedule.__opts__, {"schedule": {}, "sock_dir": sock_dir}):
        mock = MagicMock(return_value=True)
        with patch.dict(schedule.__salt__, {"event.fire": mock}):
            _ret_value = {"complete": True, "schedule": {}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                assert schedule.enable_job("job1") == {
                    "comment": "Job job1 does not exist.",
                    "changes": {},
                    "result": False,
                }


# 'disable_job' function tests: 1


@pytest.mark.slow_test
def test_disable_job(sock_dir):
    """
    Test if it disable a job in the minion's schedule.
    """
    with patch.dict(schedule.__opts__, {"schedule": {}, "sock_dir": sock_dir}):
        mock = MagicMock(return_value=True)
        with patch.dict(schedule.__salt__, {"event.fire": mock}):
            _ret_value = {"complete": True, "schedule": {}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                assert schedule.disable_job("job1") == {
                    "comment": "Job job1 does not exist.",
                    "changes": {},
                    "result": False,
                }


# 'save' function tests: 1


@pytest.mark.slow_test
def test_save(sock_dir):
    """
    Test if it save all scheduled jobs on the minion.
    """
    comm1 = "Schedule (non-pillar items) saved."
    with patch.dict(
        schedule.__opts__,
        {"schedule": {}, "default_include": "/tmp", "sock_dir": sock_dir},
    ):

        mock = MagicMock(return_value=True)
        with patch.dict(schedule.__salt__, {"event.fire": mock}):
            _ret_value = {"complete": True, "schedule": {}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                assert schedule.save() == {"comment": comm1, "result": True}


# 'enable' function tests: 1


def test_enable(sock_dir):
    """
    Test if it enable all scheduled jobs on the minion.
    """
    assert schedule.enable(test=True) == {
        "comment": "Schedule would be enabled.",
        "changes": {},
        "result": True,
    }


# 'disable' function tests: 1


def test_disable(sock_dir):
    """
    Test if it disable all scheduled jobs on the minion.
    """
    assert schedule.disable(test=True) == {
        "comment": "Schedule would be disabled.",
        "changes": {},
        "result": True,
    }


# 'move' function tests: 1


@pytest.mark.slow_test
def test_move(sock_dir, job1):
    """
    Test if it move scheduled job to another minion or minions.
    """
    comm1 = "no servers answered the published schedule.add command"
    comm2 = "the following minions return False"
    comm3 = "Moved Job job1 from schedule."
    with patch.dict(
        schedule.__opts__, {"schedule": {"job1": job1}, "sock_dir": sock_dir}
    ):
        mock = MagicMock(return_value=True)
        with patch.dict(schedule.__salt__, {"event.fire": mock}):
            _ret_value = {"complete": True, "schedule": {"job1": job1}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                mock = MagicMock(return_value={})
                with patch.dict(schedule.__salt__, {"publish.publish": mock}):
                    assert schedule.move("job1", "minion1") == {
                        "comment": comm1,
                        "result": True,
                    }

                mock = MagicMock(return_value={"minion1": ""})
                with patch.dict(schedule.__salt__, {"publish.publish": mock}):
                    assert schedule.move("job1", "minion1") == {
                        "comment": comm2,
                        "minions": ["minion1"],
                        "result": True,
                    }

                mock = MagicMock(return_value={"minion1": "job1"})
                with patch.dict(schedule.__salt__, {"publish.publish": mock}):
                    mock = MagicMock(return_value=True)
                    with patch.dict(schedule.__salt__, {"event.fire": mock}):
                        assert schedule.move("job1", "minion1") == {
                            "comment": comm3,
                            "minions": ["minion1"],
                            "result": True,
                        }

                assert schedule.move("job3", "minion1") == {
                    "comment": "Job job3 does not exist.",
                    "result": False,
                }

    mock = MagicMock(side_effect=[{}, {"job1": {}}])
    with patch.dict(schedule.__opts__, {"schedule": mock, "sock_dir": sock_dir}):
        mock = MagicMock(return_value=True)
        with patch.dict(schedule.__salt__, {"event.fire": mock}):
            _ret_value = {"complete": True, "schedule": {"job1": job1}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                with patch.dict(schedule.__pillar__, {"schedule": {"job1": job1}}):
                    mock = MagicMock(return_value={})
                    with patch.dict(schedule.__salt__, {"publish.publish": mock}):
                        assert schedule.move("job1", "minion1") == {
                            "comment": comm1,
                            "result": True,
                        }

                    mock = MagicMock(return_value={"minion1": ""})
                    with patch.dict(schedule.__salt__, {"publish.publish": mock}):
                        assert schedule.move("job1", "minion1") == {
                            "comment": comm2,
                            "minions": ["minion1"],
                            "result": True,
                        }

                    mock = MagicMock(return_value={"minion1": "job1"})
                    with patch.dict(schedule.__salt__, {"publish.publish": mock}):
                        mock = MagicMock(return_value=True)
                        with patch.dict(schedule.__salt__, {"event.fire": mock}):
                            assert schedule.move("job1", "minion1") == {
                                "comment": comm3,
                                "minions": ["minion1"],
                                "result": True,
                            }


# 'copy' function tests: 1


@pytest.mark.slow_test
def test_copy(sock_dir, job1):
    """
    Test if it copy scheduled job to another minion or minions.
    """
    comm1 = "no servers answered the published schedule.add command"
    comm2 = "the following minions return False"
    comm3 = "Copied Job job1 from schedule to minion(s)."
    with patch.dict(
        schedule.__opts__, {"schedule": {"job1": job1}, "sock_dir": sock_dir}
    ):
        mock = MagicMock(return_value=True)
        with patch.dict(schedule.__salt__, {"event.fire": mock}):
            _ret_value = {"complete": True, "schedule": {"job1": {"job1": job1}}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                mock = MagicMock(return_value={})
                with patch.dict(schedule.__salt__, {"publish.publish": mock}):
                    assert schedule.copy("job1", "minion1") == {
                        "comment": comm1,
                        "result": True,
                    }

                mock = MagicMock(return_value={"minion1": ""})
                with patch.dict(schedule.__salt__, {"publish.publish": mock}):
                    assert schedule.copy("job1", "minion1") == {
                        "comment": comm2,
                        "minions": ["minion1"],
                        "result": True,
                    }

                mock = MagicMock(return_value={"minion1": "job1"})
                with patch.dict(schedule.__salt__, {"publish.publish": mock}):
                    mock = MagicMock(return_value=True)
                    with patch.dict(schedule.__salt__, {"event.fire": mock}):
                        assert schedule.copy("job1", "minion1") == {
                            "comment": comm3,
                            "minions": ["minion1"],
                            "result": True,
                        }

                assert schedule.copy("job3", "minion1") == {
                    "comment": "Job job3 does not exist.",
                    "result": False,
                }

    mock = MagicMock(side_effect=[{}, {"job1": {}}])
    with patch.dict(schedule.__opts__, {"schedule": mock, "sock_dir": sock_dir}):
        with patch.dict(schedule.__pillar__, {"schedule": {"job1": job1}}):
            mock = MagicMock(return_value=True)
            with patch.dict(schedule.__salt__, {"event.fire": mock}):
                _ret_value = {
                    "complete": True,
                    "schedule": {"job1": {"job1": job1}},
                }
                with patch.object(SaltEvent, "get_event", return_value=_ret_value):

                    mock = MagicMock(return_value={})
                    with patch.dict(schedule.__salt__, {"publish.publish": mock}):
                        assert schedule.copy("job1", "minion1") == {
                            "comment": comm1,
                            "result": True,
                        }

                    mock = MagicMock(return_value={"minion1": ""})
                    with patch.dict(schedule.__salt__, {"publish.publish": mock}):
                        assert schedule.copy("job1", "minion1") == {
                            "comment": comm2,
                            "minions": ["minion1"],
                            "result": True,
                        }

                    mock = MagicMock(return_value={"minion1": "job1"})
                    with patch.dict(schedule.__salt__, {"publish.publish": mock}):
                        mock = MagicMock(return_value=True)
                        with patch.dict(schedule.__salt__, {"event.fire": mock}):
                            assert schedule.copy("job1", "minion1") == {
                                "comment": comm3,
                                "minions": ["minion1"],
                                "result": True,
                            }


# 'modify' function tests: 1


@pytest.mark.slow_test
def test_modify(sock_dir, job1):
    """
    Test if modifying job to the schedule.
    """
    current_job1 = {
        "function": "salt",
        "seconds": "3600",
        "maxrunning": 1,
        "name": "job1",
        "enabled": True,
        "jid_include": True,
    }

    new_job1 = {
        "function": "salt",
        "seconds": "60",
        "maxrunning": 1,
        "name": "job1",
        "enabled": True,
        "jid_include": True,
    }

    comm1 = "Modified job: job1 in schedule."
    changes1 = {
        "job1": {
            "new": salt.utils.odict.OrderedDict(new_job1),
            "old": salt.utils.odict.OrderedDict(current_job1),
        }
    }

    new_job4 = {
        "function": "test.version",
        "seconds": "3600",
        "maxrunning": 1,
        "name": "job1",
        "enabled": True,
        "jid_include": True,
    }

    changes4 = {
        "job1": {
            "new": salt.utils.odict.OrderedDict(new_job4),
            "old": salt.utils.odict.OrderedDict(current_job1),
        }
    }

    expected1 = {"comment": comm1, "changes": changes1, "result": True}

    comm2 = (
        'Error: Unable to use "seconds", "minutes", "hours", '
        'or "days" with "when" option.'
    )
    expected2 = {"comment": comm2, "changes": {}, "result": False}

    comm3 = 'Unable to use "when" and "cron" options together.  Ignoring.'
    expected3 = {"comment": comm3, "changes": {}, "result": False}

    comm4 = "Job: job1 would be modified in schedule."
    expected4 = {"comment": comm4, "changes": changes4, "result": True}

    comm5 = "Job job2 does not exist in schedule."
    expected5 = {"comment": comm5, "changes": {}, "result": False}

    with patch.dict(
        schedule.__opts__, {"schedule": {"job1": current_job1}, "sock_dir": sock_dir}
    ):
        mock = MagicMock(return_value=True)
        with patch.dict(schedule.__salt__, {"event.fire": mock}):
            _ret_value = {"complete": True, "schedule": {"job1": current_job1}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                ret = schedule.modify("job1", seconds="60")
                assert "job1" in ret["changes"]
                assert "new" in ret["changes"]["job1"]
                assert "old" in ret["changes"]["job1"]

                for key in [
                    "maxrunning",
                    "function",
                    "seconds",
                    "jid_include",
                    "name",
                    "enabled",
                ]:
                    assert (
                        ret["changes"]["job1"]["new"][key]
                        == expected1["changes"]["job1"]["new"][key]
                    )
                    assert (
                        ret["changes"]["job1"]["old"][key]
                        == expected1["changes"]["job1"]["old"][key]
                    )

                assert ret["comment"] == expected1["comment"]
                assert ret["result"] == expected1["result"]

            _ret_value = {"complete": True, "schedule": {"job1": current_job1}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                ret = schedule.modify(
                    "job1", function="test.ping", seconds=3600, when="2400"
                )
                assert ret == expected2

            _ret_value = {"complete": True, "schedule": {"job1": current_job1}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                ret = schedule.modify(
                    "job1", function="test.ping", when="2400", cron="2"
                )
                assert ret == expected3

            _ret_value = {"complete": True, "schedule": {"job1": current_job1}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                ret = schedule.modify("job1", function="test.version", test=True)

                assert "job1" in ret["changes"]
                assert "new" in ret["changes"]["job1"]
                assert "old" in ret["changes"]["job1"]

                for key in [
                    "maxrunning",
                    "function",
                    "jid_include",
                    "name",
                    "enabled",
                ]:
                    assert (
                        ret["changes"]["job1"]["new"][key]
                        == expected4["changes"]["job1"]["new"][key]
                    )
                    assert (
                        ret["changes"]["job1"]["old"][key]
                        == expected4["changes"]["job1"]["old"][key]
                    )

                assert ret["comment"] == expected4["comment"]
                assert ret["result"] == expected4["result"]

            _ret_value = {"complete": True, "schedule": {}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                ret = schedule.modify("job2", function="test.version", test=True)
                assert ret == expected5

    _schedule_data = {"job1": job1}
    comm = "Modified job: job1 in schedule."
    changes = {"job1": "removed"}

    changes = {
        "job1": {
            "new": OrderedDict(
                [
                    ("function", "test.version"),
                    ("maxrunning", 1),
                    ("name", "job1"),
                    ("enabled", True),
                    ("jid_include", True),
                ]
            ),
            "old": OrderedDict(
                [
                    ("function", "test.ping"),
                    ("maxrunning", 1),
                    ("name", "job1"),
                    ("jid_include", True),
                    ("enabled", True),
                ]
            ),
        }
    }
    schedule_config_file = schedule._get_schedule_config_file()
    with patch.dict(
        schedule.__opts__, {"schedule": {"job1": "salt"}, "sock_dir": sock_dir}
    ):
        with patch("salt.utils.files.fopen", mock_open(read_data="")) as fopen_mock:
            with patch.object(
                schedule, "list_", MagicMock(return_value=_schedule_data)
            ):
                ret = schedule.modify("job1", function="test.version", offline="True")
                assert ret["comment"] == comm
                assert ret["result"]
                assert all(
                    [
                        True
                        for k, v in ret["changes"]["job1"]["old"].items()
                        if v == changes["job1"]["old"][k]
                    ]
                )
                assert all(
                    [
                        True
                        for k, v in ret["changes"]["job1"]["new"].items()
                        if v == changes["job1"]["new"][k]
                    ]
                )

                _call = call(
                    b"schedule:\n  job1: {enabled: true, function: test.version, jid_include: true, maxrunning: 1,\n    name: job1}\n"
                )
                write_calls = fopen_mock.filehandles[schedule_config_file][
                    0
                ].write._mock_mock_calls
                assert _call in write_calls


# 'is_enabled' function tests: 1


def test_is_enabled(sock_dir):
    """
    Test is_enabled
    """
    job1 = {"function": "salt", "seconds": 3600}

    comm1 = "Modified job: job1 in schedule."

    mock_schedule = {"enabled": True, "job1": job1}

    mock_lst = MagicMock(return_value=mock_schedule)

    with patch.dict(
        schedule.__opts__, {"schedule": {"job1": job1}, "sock_dir": sock_dir}
    ):
        mock = MagicMock(return_value=True)
        with patch.dict(
            schedule.__salt__, {"event.fire": mock, "schedule.list": mock_lst}
        ):
            _ret_value = {"complete": True, "schedule": {"job1": job1}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                ret = schedule.is_enabled("job1")
                assert ret == job1

                ret = schedule.is_enabled()
                assert ret


# 'job_status' function tests: 1


def test_job_status(sock_dir):
    """
    Test is_enabled
    """
    job1 = {
        "_last_run": datetime.datetime(2021, 11, 1, 12, 36, 57),
        "_next_fire_time": datetime.datetime(2021, 11, 1, 13, 36, 57),
        "function": "salt",
        "seconds": 3600,
    }

    comm1 = "Modified job: job1 in schedule."

    mock_schedule = {"enabled": True, "job1": job1}

    mock_lst = MagicMock(return_value=mock_schedule)

    with patch.dict(
        schedule.__opts__, {"schedule": {"job1": job1}, "sock_dir": sock_dir}
    ):
        mock = MagicMock(return_value=True)
        with patch.dict(schedule.__salt__, {"event.fire": mock}):
            _ret_value = {"complete": True, "data": job1}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                ret = schedule.job_status("job1")
                assert ret == {
                    "_last_run": "2021-11-01T12:36:57",
                    "_next_fire_time": "2021-11-01T13:36:57",
                    "function": "salt",
                    "seconds": 3600,
                }


# 'purge' function tests: 1
@pytest.mark.slow_test
def test_list(sock_dir, job1):
    """
    Test schedule.list
    """
    _schedule_data = {"job1": job1}
    with patch.dict(schedule.__opts__, {"schedule": {}, "sock_dir": sock_dir}):
        mock = MagicMock(return_value=True)
        with patch.dict(schedule.__salt__, {"event.fire": mock}):
            _ret_schedule_data = {
                "function": "test.ping",
                "seconds": 10,
                "maxrunning": 1,
                "name": "job1",
                "enabled": True,
                "jid_include": True,
            }
            _ret_value = {"complete": True, "schedule": {"job1": _ret_schedule_data}}
            saved_schedule = """schedule:
  job1: {enabled: true, function: test.ping, jid_include: true, maxrunning: 1, name: job1,
    seconds: 10}
"""

            expected = """schedule:
  job1:
    enabled: true
    function: test.ping
    jid_include: true
    maxrunning: 1
    name: job1
    saved: true
    seconds: 10
"""

            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                with patch("os.path.exists", MagicMock(return_value=True)), patch(
                    "salt.utils.files.fopen", mock_open(read_data=saved_schedule)
                ) as fopen_mock:
                    ret = schedule.list_(offline=True)
                    assert ret == expected

    _schedule_data = {"job1": job1}
    with patch.dict(schedule.__opts__, {"schedule": {}, "sock_dir": sock_dir}):
        mock = MagicMock(return_value=True)
        with patch.dict(schedule.__salt__, {"event.fire": mock}):
            _ret_schedule_data = {
                "function": "test.ping",
                "seconds": 10,
                "maxrunning": 1,
                "name": "job1",
                "enabled": True,
                "jid_include": True,
            }
            _ret_value = {"complete": True, "schedule": {"job1": _ret_schedule_data}}
            expected = """schedule:
  job1:
    enabled: true
    function: test.ping
    jid_include: true
    maxrunning: 1
    name: job1
    saved: false
    seconds: 10
"""
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                with patch("os.path.exists", MagicMock(return_value=True)), patch(
                    "salt.utils.files.fopen", mock_open(read_data="")
                ) as fopen_mock:
                    ret = schedule.list_()
                    assert ret == expected

    _schedule_data = {"job1": job1}
    with patch.dict(schedule.__opts__, {"schedule": {}, "sock_dir": sock_dir}):
        mock = MagicMock(return_value=True)
        with patch.dict(schedule.__salt__, {"event.fire": mock}):
            _ret_schedule_data = {
                "function": "test.ping",
                "seconds": 10,
                "maxrunning": 1,
                "name": "job1",
                "enabled": True,
                "jid_include": True,
            }
            _ret_value = {"complete": True, "schedule": {"job1": _ret_schedule_data}}
            saved_schedule = """schedule:
  job1: {enabled: true, function: test.ping, jid_include: true, maxrunning: 1, name: job1,
    seconds: 10}
"""

            expected = """schedule:
  job1:
    enabled: true
    function: test.ping
    jid_include: true
    maxrunning: 1
    name: job1
    saved: true
    seconds: 10
"""
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                with patch("os.path.exists", MagicMock(return_value=True)), patch(
                    "salt.utils.files.fopen", mock_open(read_data=saved_schedule)
                ) as fopen_mock:
                    ret = schedule.list_()
                    assert ret == expected
