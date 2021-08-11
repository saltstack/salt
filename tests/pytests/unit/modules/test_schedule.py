"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import logging

import pytest
import salt.modules.schedule as schedule
import salt.utils.odict
from salt.utils.event import SaltEvent
from tests.support.mock import MagicMock, patch

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
def test_purge(sock_dir):
    """
    Test if it purge all the jobs currently scheduled on the minion.
    """
    with patch.dict(schedule.__opts__, {"schedule": {}, "sock_dir": sock_dir}):
        mock = MagicMock(return_value=True)
        with patch.dict(schedule.__salt__, {"event.fire": mock}):
            _ret_value = {"complete": True, "schedule": {}}
            with patch.object(SaltEvent, "get_event", return_value=_ret_value):
                assert schedule.purge() == {
                    "comment": ["Deleted job: schedule from schedule."],
                    "result": True,
                }


# 'delete' function tests: 1
@pytest.mark.slow_test
def test_delete(sock_dir):
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
def test_modify(sock_dir):
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
                    "seconds",
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
    job1 = {"function": "salt", "seconds": 3600}

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
                assert ret == job1
