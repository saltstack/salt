"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import copy
import datetime
import logging

import pytest
import salt.config
import salt.utils.schedule
from salt.utils.schedule import Schedule
from tests.support.mock import MagicMock, patch

# pylint: disable=import-error,unused-import
try:
    import croniter

    _CRON_SUPPORTED = True
except ImportError:
    _CRON_SUPPORTED = False
# pylint: enable=import-error

log = logging.getLogger(__name__)


# pylint: disable=too-many-public-methods,invalid-name
# delete_job tests
@pytest.mark.slow_test
def test_delete_job_exists(setup_teardown_vars):
    """
    Tests ensuring the job exists and deleting it
    """
    schedule = setup_teardown_vars["schedule"]
    schedule.opts.update({"schedule": {"foo": "bar"}, "pillar": {}})
    assert "foo" in schedule.opts["schedule"]

    schedule.delete_job("foo")
    assert "foo" not in schedule.opts["schedule"]


@pytest.mark.slow_test
def test_delete_job_in_pillar(setup_teardown_vars):
    """
    Tests ignoring deletion job from pillar
    """
    schedule = setup_teardown_vars["schedule"]
    schedule.opts.update({"pillar": {"schedule": {"foo": "bar"}}, "schedule": {}})
    assert "foo" in schedule.opts["pillar"]["schedule"]
    schedule.delete_job("foo")

    assert "foo" in schedule.opts["pillar"]["schedule"]


@pytest.mark.slow_test
def test_delete_job_intervals(setup_teardown_vars):
    """
    Tests removing job from intervals
    """
    schedule = setup_teardown_vars["schedule"]
    schedule.opts.update({"pillar": {}, "schedule": {}})
    schedule.intervals = {"foo": "bar"}
    schedule.delete_job("foo")
    assert "foo" not in schedule.intervals


@pytest.mark.slow_test
def test_delete_job_prefix(setup_teardown_vars):
    """
    Tests ensuring jobs exists and deleting them by prefix
    """
    schedule = setup_teardown_vars["schedule"]
    schedule.opts.update(
        {"schedule": {"foobar": "bar", "foobaz": "baz", "fooboo": "boo"}, "pillar": {}}
    )
    ret = copy.deepcopy(schedule.opts)
    del ret["schedule"]["foobar"]
    del ret["schedule"]["foobaz"]
    schedule.delete_job_prefix("fooba")
    assert schedule.opts == ret


@pytest.mark.slow_test
def test_delete_job_prefix_in_pillar(setup_teardown_vars):
    """
    Tests ignoring deletion jobs by prefix from pillar
    """
    schedule = setup_teardown_vars["schedule"]
    schedule.opts.update(
        {
            "pillar": {"schedule": {"foobar": "bar", "foobaz": "baz", "fooboo": "boo"}},
            "schedule": {},
        }
    )
    ret = copy.deepcopy(schedule.opts)
    schedule.delete_job_prefix("fooba")
    assert schedule.opts == ret


# add_job tests
def test_add_job_data_not_dict(setup_teardown_vars):
    """
    Tests if data is a dictionary
    """
    schedule = setup_teardown_vars["schedule"]
    data = "foo"
    pytest.raises(ValueError, Schedule.add_job, schedule, data)


def test_add_job_multiple_jobs(setup_teardown_vars):
    """
    Tests if more than one job is scheduled at a time
    """
    schedule = setup_teardown_vars["schedule"]
    data = {"key1": "value1", "key2": "value2"}
    pytest.raises(ValueError, Schedule.add_job, schedule, data)


@pytest.mark.slow_test
def test_add_job(setup_teardown_vars):
    """
    Tests adding a job to the schedule
    """
    schedule = setup_teardown_vars["schedule"]
    data = {"foo": {"bar": "baz"}}
    ret = copy.deepcopy(schedule.opts)
    ret.update(
        {
            "schedule": {
                "foo": {"bar": "baz", "enabled": True},
                "hello": {"world": "peace", "enabled": True},
            },
            "pillar": {},
        }
    )
    schedule.opts.update(
        {"schedule": {"hello": {"world": "peace", "enabled": True}}, "pillar": {}}
    )
    Schedule.add_job(schedule, data)
    assert schedule.opts == ret


# enable_job tests
@pytest.mark.slow_test
def test_enable_job(setup_teardown_vars):
    """
    Tests enabling a job
    """
    schedule = setup_teardown_vars["schedule"]
    schedule.opts.update({"schedule": {"name": {"enabled": "foo"}}})
    Schedule.enable_job(schedule, "name")
    assert schedule.opts["schedule"]["name"]["enabled"]


@pytest.mark.slow_test
def test_enable_job_pillar(setup_teardown_vars):
    """
    Tests ignoring enable a job from pillar
    """
    schedule = setup_teardown_vars["schedule"]
    schedule.opts.update({"pillar": {"schedule": {"name": {"enabled": False}}}})
    Schedule.enable_job(schedule, "name", persist=False)
    assert not schedule.opts["pillar"]["schedule"]["name"]["enabled"]


# disable_job tests
@pytest.mark.slow_test
def test_disable_job(setup_teardown_vars):
    """
    Tests disabling a job
    """
    schedule = setup_teardown_vars["schedule"]
    schedule.opts.update({"schedule": {"name": {"enabled": "foo"}}, "pillar": {}})
    Schedule.disable_job(schedule, "name")
    assert not schedule.opts["schedule"]["name"]["enabled"]


@pytest.mark.slow_test
def test_disable_job_pillar(setup_teardown_vars):
    """
    Tests ignoring disable a job in pillar
    """
    schedule = setup_teardown_vars["schedule"]
    schedule.opts.update(
        {"pillar": {"schedule": {"name": {"enabled": True}}}, "schedule": {}}
    )
    Schedule.disable_job(schedule, "name", persist=False)
    assert schedule.opts["pillar"]["schedule"]["name"]["enabled"]


# modify_job tests
@pytest.mark.slow_test
def test_modify_job(setup_teardown_vars):
    """
    Tests modifying a job in the scheduler
    """
    schedule = setup_teardown_vars["schedule"]
    schedule_dict = {"foo": "bar"}
    schedule.opts.update({"schedule": {"name": "baz"}, "pillar": {}})
    ret = copy.deepcopy(schedule.opts)
    ret.update({"schedule": {"name": {"foo": "bar"}}})
    Schedule.modify_job(schedule, "name", schedule_dict)
    assert schedule.opts == ret


def test_modify_job_not_exists(setup_teardown_vars):
    """
    Tests modifying a job in the scheduler if jobs not exists
    """
    schedule = setup_teardown_vars["schedule"]
    schedule_dict = {"foo": "bar"}
    schedule.opts.update({"schedule": {}, "pillar": {}})
    ret = copy.deepcopy(schedule.opts)
    ret.update({"schedule": {"name": {"foo": "bar"}}})
    Schedule.modify_job(schedule, "name", schedule_dict)
    assert schedule.opts == ret


def test_modify_job_pillar(setup_teardown_vars):
    """
    Tests ignoring modification of job from pillar
    """
    schedule = setup_teardown_vars["schedule"]
    schedule_dict = {"foo": "bar"}
    schedule.opts.update({"schedule": {}, "pillar": {"schedule": {"name": "baz"}}})
    ret = copy.deepcopy(schedule.opts)
    Schedule.modify_job(schedule, "name", schedule_dict, persist=False)
    assert schedule.opts == ret


maxDiff = None


# enable_schedule tests
@pytest.mark.slow_test
def test_enable_schedule(setup_teardown_vars):
    """
    Tests enabling the scheduler
    """
    schedule = setup_teardown_vars["schedule"]
    with patch(
        "salt.utils.schedule.Schedule.persist", MagicMock(return_value=None)
    ) as persist_mock:
        schedule.opts.update({"schedule": {"enabled": "foo"}, "pillar": {}})
        Schedule.enable_schedule(schedule)
        assert schedule.opts["schedule"]["enabled"]

    persist_mock.assert_called()


# disable_schedule tests
@pytest.mark.slow_test
def test_disable_schedule(setup_teardown_vars):
    """
    Tests disabling the scheduler
    """
    schedule = setup_teardown_vars["schedule"]
    with patch(
        "salt.utils.schedule.Schedule.persist", MagicMock(return_value=None)
    ) as persist_mock:
        schedule.opts.update({"schedule": {"enabled": "foo"}, "pillar": {}})
        Schedule.disable_schedule(schedule)
        assert not schedule.opts["schedule"]["enabled"]

    persist_mock.assert_called()


# reload tests
def test_reload_update_schedule_key(setup_teardown_vars):
    """
    Tests reloading the schedule from saved schedule where both the
    saved schedule and schedule.opts contain a schedule key
    """
    schedule = setup_teardown_vars["schedule"]
    saved = {"schedule": {"foo": "bar"}}
    ret = copy.deepcopy(schedule.opts)
    ret.update({"schedule": {"foo": "bar", "hello": "world"}})
    schedule.opts.update({"schedule": {"hello": "world"}})
    Schedule.reload(schedule, saved)
    assert schedule.opts == ret


def test_reload_update_schedule_no_key(setup_teardown_vars):
    """
    Tests reloading the schedule from saved schedule that does not
    contain a schedule key but schedule.opts does
    """
    schedule = setup_teardown_vars["schedule"]
    saved = {"foo": "bar"}
    ret = copy.deepcopy(schedule.opts)
    ret.update({"schedule": {"foo": "bar", "hello": "world"}})
    schedule.opts.update({"schedule": {"hello": "world"}})
    Schedule.reload(schedule, saved)
    assert schedule.opts == ret


def test_reload_no_schedule_in_opts(setup_teardown_vars):
    """
    Tests reloading the schedule from saved schedule that does not
    contain a schedule key and neither does schedule.opts
    """
    schedule = setup_teardown_vars["schedule"]
    saved = {"foo": "bar"}
    ret = copy.deepcopy(schedule.opts)
    ret["schedule"] = {"foo": "bar"}
    schedule.opts.pop("schedule", None)
    Schedule.reload(schedule, saved)
    assert schedule.opts == ret


def test_reload_schedule_in_saved_but_not_opts(setup_teardown_vars):
    """
    Tests reloading the schedule from saved schedule that contains
    a schedule key, but schedule.opts does not
    """
    schedule = setup_teardown_vars["schedule"]
    saved = {"schedule": {"foo": "bar"}}
    ret = copy.deepcopy(schedule.opts)
    ret["schedule"] = {"foo": "bar"}
    schedule.opts.pop("schedule", None)
    Schedule.reload(schedule, saved)
    assert schedule.opts == ret


# eval tests
def test_eval_schedule_is_not_dict(setup_teardown_vars):
    """
    Tests eval if the schedule is not a dictionary
    """
    schedule = setup_teardown_vars["schedule"]
    schedule.opts.update({"schedule": "", "pillar": {"schedule": {}}})
    pytest.raises(ValueError, Schedule.eval, schedule)


def test_eval_schedule_is_not_dict_in_pillar(setup_teardown_vars):
    """
    Tests eval if the schedule from pillar is not a dictionary
    """
    schedule = setup_teardown_vars["schedule"]
    schedule.opts.update({"schedule": {}, "pillar": {"schedule": ""}})
    pytest.raises(ValueError, Schedule.eval, schedule)


def test_eval_schedule_time(setup_teardown_vars):
    """
    Tests eval if the schedule setting time is in the future
    """
    schedule = setup_teardown_vars["schedule"]
    schedule.opts.update({"pillar": {"schedule": {}}})
    schedule.opts.update(
        {"schedule": {"testjob": {"function": "test.true", "seconds": 60}}}
    )
    now = datetime.datetime.now()
    schedule.eval()
    assert schedule.opts["schedule"]["testjob"]["_next_fire_time"] > now


def test_eval_schedule_time_eval(setup_teardown_vars):
    """
    Tests eval if the schedule setting time is in the future plus splay
    """
    schedule = setup_teardown_vars["schedule"]
    schedule.opts.update({"pillar": {"schedule": {}}})
    schedule.opts.update(
        {"schedule": {"testjob": {"function": "test.true", "seconds": 60, "splay": 5}}}
    )
    now = datetime.datetime.now()
    schedule.eval()
    assert schedule.opts["schedule"]["testjob"]["_splay"] - now > datetime.timedelta(
        seconds=60
    )


@pytest.mark.skipif(not _CRON_SUPPORTED, reason="croniter module not installed")
def test_eval_schedule_cron(setup_teardown_vars):
    """
    Tests eval if the schedule is defined with cron expression
    """
    schedule = setup_teardown_vars["schedule"]
    schedule.opts.update({"pillar": {"schedule": {}}})
    schedule.opts.update(
        {"schedule": {"testjob": {"function": "test.true", "cron": "* * * * *"}}}
    )
    now = datetime.datetime.now()
    schedule.eval()
    assert schedule.opts["schedule"]["testjob"]["_next_fire_time"] > now


@pytest.mark.skipif(not _CRON_SUPPORTED, reason="croniter module not installed")
def test_eval_schedule_cron_splay(setup_teardown_vars):
    """
    Tests eval if the schedule is defined with cron expression plus splay
    """
    schedule = setup_teardown_vars["schedule"]
    schedule.opts.update({"pillar": {"schedule": {}}})
    schedule.opts.update(
        {
            "schedule": {
                "testjob": {"function": "test.true", "cron": "* * * * *", "splay": 5}
            }
        }
    )
    schedule.eval()
    assert (
        schedule.opts["schedule"]["testjob"]["_splay"]
        > schedule.opts["schedule"]["testjob"]["_next_fire_time"]
    )


@pytest.mark.slow_test
def test_handle_func_schedule_minion_blackout(setup_teardown_vars):
    """
    Tests eval if the schedule from pillar is not a dictionary
    """
    schedule = setup_teardown_vars["schedule"]
    schedule.opts.update({"pillar": {"schedule": {}}})
    schedule.opts.update({"grains": {"minion_blackout": True}})

    schedule.opts.update(
        {"schedule": {"testjob": {"function": "test.true", "seconds": 60}}}
    )
    data = {
        "function": "test.true",
        "_next_scheduled_fire_time": datetime.datetime(2018, 11, 21, 14, 9, 53, 903438),
        "run": True,
        "name": "testjob",
        "seconds": 60,
        "_splay": None,
        "_seconds": 60,
        "jid_include": True,
        "maxrunning": 1,
        "_next_fire_time": datetime.datetime(2018, 11, 21, 14, 8, 53, 903438),
    }

    with patch.object(salt.utils.schedule, "log") as log_mock:
        with patch("salt.utils.process.daemonize"), patch("sys.platform", "linux2"):
            schedule.handle_func(False, "test.ping", data)
            assert log_mock.exception.called


def test_handle_func_check_data(setup_teardown_vars):
    """
    Tests handle_func to ensure that __pub_fun_args is not
    being duplicated in the value of kwargs in data.
    """
    schedule = setup_teardown_vars["schedule"]

    data = {
        "function": "test.arg",
        "_next_scheduled_fire_time": datetime.datetime(2018, 11, 21, 14, 9, 53, 903438),
        "run": True,
        "args": ["arg1", "arg2"],
        "kwargs": {"key1": "value1", "key2": "value2"},
        "name": "testjob",
        "seconds": 60,
        "_splay": None,
        "_seconds": 60,
        "jid_include": True,
        "maxrunning": 1,
        "_next_fire_time": datetime.datetime(2018, 11, 21, 14, 8, 53, 903438),
    }

    with patch("salt.utils.process.daemonize"), patch("sys.platform", "linux2"):
        with patch.object(schedule, "standalone", return_value=True):
            # run handle_func once
            schedule.handle_func(False, "test.arg", data)

            # run handle_func and ensure __pub_fun_args
            # is not in kwargs
            schedule.handle_func(False, "test.arg", data)

            assert "kwargs" in data
            assert "__pub_fun_args" not in data["kwargs"]


def test_handle_func_check_dicts(setup_teardown_vars):
    """
    Tests that utils, functions, and returners dicts are not
    empty after handle_func has run on Windows.
    """
    schedule = setup_teardown_vars["schedule"]

    data = {
        "function": "test.arg",
        "_next_scheduled_fire_time": datetime.datetime(2018, 11, 21, 14, 9, 53, 903438),
        "run": True,
        "args": ["arg1", "arg2"],
        "kwargs": {"key1": "value1", "key2": "value2"},
        "name": "testjob",
        "seconds": 60,
        "_splay": None,
        "_seconds": 60,
        "jid_include": True,
        "maxrunning": 1,
        "_next_fire_time": datetime.datetime(2018, 11, 21, 14, 8, 53, 903438),
    }

    with patch("salt.utils.process.daemonize"):
        with patch.object(schedule, "standalone", return_value=True):
            # simulate what happens before handle_func is called on Windows
            schedule.functions = {}
            schedule.returners = {}
            schedule.utils = {}
            schedule.handle_func(False, "test.arg", data)

            assert {} != schedule.functions
            assert {} != schedule.returners
            assert {} != schedule.utils
