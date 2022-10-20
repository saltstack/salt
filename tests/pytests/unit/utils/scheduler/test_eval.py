import datetime
import logging
import random
import time

import pytest

import salt.utils.platform
import salt.utils.schedule
from tests.support.mock import MagicMock, patch

try:
    import dateutil.parser

    HAS_DATEUTIL_PARSER = True
except ImportError:
    HAS_DATEUTIL_PARSER = False


try:
    import croniter  # pylint: disable=unused-import

    HAS_CRONITER = True
except ImportError:
    HAS_CRONITER = False

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skipif(
        HAS_DATEUTIL_PARSER is False,
        reason="The 'dateutil.parser' library is not available",
    ),
    pytest.mark.windows_whitelisted,
]


def _check_last_run(schedule, job_name, runtime=None):
    """
    Check that last_run time exists and
    is not the previous run time if prev_runtime
    is passed.
    """

    # The number of times to
    # check before bailing out.
    checks = 5

    status = schedule.job_status(job_name)
    count = 0
    while "_last_run" not in status:
        status = schedule.job_status(job_name)
        if count == checks:
            return False
        time.sleep(2)
        count += 1

    if runtime:
        count = 0
        status = schedule.job_status(job_name)
        while status["_last_run"] != runtime:
            if count == checks:
                return False
            status = schedule.job_status(job_name)
            time.sleep(2)
            count += 1
    return True


@pytest.mark.slow_test
@pytest.mark.parametrize("master", [False, True])
def test_eval(schedule, master):
    """
    verify that scheduled job runs
    """

    job_name = "test_eval"
    job = {
        "schedule": {job_name: {"function": "test.ping", "when": "11/29/2017 4:00pm"}}
    }
    run_time2 = dateutil.parser.parse("11/29/2017 4:00pm")
    run_time1 = run_time2 - datetime.timedelta(seconds=1)

    # Add the job to the scheduler
    schedule.opts.update(job)

    # The master does not have grains
    if master:
        schedule.opts.pop("grains", None)

    # Evaluate 1 second before the run time
    schedule.eval(now=run_time1)
    ret = schedule.job_status(job_name)
    assert "_last_run" not in ret

    # Evaluate 1 second at the run time
    schedule.eval(now=run_time2)
    ret = schedule.job_status(job_name)
    assert ret["_last_run"] == run_time2


@pytest.mark.slow_test
def test_eval_multiple_whens(schedule):
    """
    verify that scheduled job runs
    """

    job_name = "test_eval_multiple_whens"
    job = {
        "schedule": {
            job_name: {
                "function": "test.ping",
                "when": ["11/29/2017 4:00pm", "11/29/2017 5:00pm"],
            }
        }
    }
    if salt.utils.platform.is_darwin():
        job["schedule"][job_name]["dry_run"] = True

    run_time1 = dateutil.parser.parse("11/29/2017 4:00pm")
    run_time2 = dateutil.parser.parse("11/29/2017 5:00pm")

    # Add the job to the scheduler
    schedule.opts.update(job)

    # Evaluate run time1
    schedule.eval(now=run_time1)

    # Give the job a chance to finish
    assert _check_last_run(schedule, job_name, run_time1)

    # Evaluate run time2
    schedule.eval(now=run_time2)

    # Give the job a chance to finish and check
    assert _check_last_run(schedule, job_name, run_time2)


@pytest.mark.slow_test
def test_eval_whens(schedule):
    """
    verify that scheduled job runs
    """

    schedule.opts["grains"]["whens"] = {"tea time": "11/29/2017 12:00pm"}

    job_name = "test_eval_whens"
    job = {"schedule": {job_name: {"function": "test.ping", "when": "tea time"}}}
    run_time = dateutil.parser.parse("11/29/2017 12:00pm")

    # Add the job to the scheduler
    schedule.opts.update(job)

    # Evaluate run time1
    schedule.eval(now=run_time)
    assert _check_last_run(schedule, job_name, run_time)


@pytest.mark.slow_test
def test_eval_loop_interval(schedule):
    """
    verify that scheduled job runs
    """

    job_name = "test_eval_loop_interval"
    job = {
        "schedule": {job_name: {"function": "test.ping", "when": "11/29/2017 4:00pm"}}
    }
    # 30 second loop interval
    LOOP_INTERVAL = random.randint(30, 59)
    schedule.opts["loop_interval"] = LOOP_INTERVAL

    run_time2 = dateutil.parser.parse("11/29/2017 4:00pm")

    # Add the job to the scheduler
    schedule.opts.update(job)

    # Evaluate 1 second at the run time
    schedule.eval(now=run_time2 + datetime.timedelta(seconds=LOOP_INTERVAL))

    assert _check_last_run(
        schedule, job_name, run_time2 + datetime.timedelta(seconds=LOOP_INTERVAL)
    )


@pytest.mark.slow_test
def test_eval_multiple_whens_loop_interval(schedule):
    """
    verify that scheduled job runs
    """

    job_name = "test_eval_multiple_whens_loop_interval"
    job = {
        "schedule": {
            job_name: {
                "function": "test.ping",
                "when": ["11/29/2017 4:00pm", "11/29/2017 5:00pm"],
            }
        }
    }
    if salt.utils.platform.is_darwin():
        job["schedule"][job_name]["dry_run"] = True

    # 30 second loop interval
    LOOP_INTERVAL = random.randint(30, 59)
    schedule.opts["loop_interval"] = LOOP_INTERVAL

    run_time1 = dateutil.parser.parse("11/29/2017 4:00pm") + datetime.timedelta(
        seconds=LOOP_INTERVAL
    )
    run_time2 = dateutil.parser.parse("11/29/2017 5:00pm") + datetime.timedelta(
        seconds=LOOP_INTERVAL
    )

    # Add the job to the scheduler
    schedule.opts.update(job)

    # Evaluate 1 second at the run time
    schedule.eval(now=run_time1)

    # Give the job a chance to finish
    assert _check_last_run(schedule, job_name, run_time1)

    # Evaluate 1 second at the run time
    schedule.eval(now=run_time2)

    # Give the job a chance to finish
    assert _check_last_run(schedule, job_name, run_time2)


@pytest.mark.slow_test
def test_eval_once(schedule):
    """
    verify that scheduled job runs
    """

    job_name = "test_once"
    job = {
        "schedule": {job_name: {"function": "test.ping", "once": "2017-12-13T13:00:00"}}
    }
    run_time = dateutil.parser.parse("12/13/2017 1:00pm")

    # Add the job to the scheduler
    schedule.opts["schedule"] = {}
    schedule.opts.update(job)

    # Evaluate 1 second at the run time
    schedule.eval(now=run_time)
    assert _check_last_run(schedule, job_name, run_time)


@pytest.mark.slow_test
def test_eval_once_loop_interval(schedule):
    """
    verify that scheduled job runs
    """

    job_name = "test_eval_once_loop_interval"
    job = {
        "schedule": {job_name: {"function": "test.ping", "once": "2017-12-13T13:00:00"}}
    }
    # Randomn second loop interval
    LOOP_INTERVAL = random.randint(0, 59)
    schedule.opts["loop_interval"] = LOOP_INTERVAL

    # Run the job at the right plus LOOP_INTERVAL
    run_time = dateutil.parser.parse("12/13/2017 1:00pm") + datetime.timedelta(
        seconds=LOOP_INTERVAL
    )

    # Add the job to the scheduler
    schedule.opts.update(job)

    # Evaluate at the run time
    schedule.eval(now=run_time)
    assert _check_last_run(schedule, job_name, run_time)


@pytest.mark.skipif(not HAS_CRONITER, reason="Cannot find croniter python module")
def test_eval_cron(schedule):
    """
    verify that scheduled job runs
    """

    job_name = "test_eval_cron"
    job = {"schedule": {job_name: {"function": "test.ping", "cron": "0 16 29 11 *"}}}

    # Add the job to the scheduler
    schedule.opts.update(job)

    run_time = dateutil.parser.parse("11/29/2017 4:00pm")
    with patch("croniter.croniter.get_next", MagicMock(return_value=run_time)):
        schedule.eval(now=run_time)
    assert _check_last_run(schedule, job_name, run_time)


@pytest.mark.skipif(not HAS_CRONITER, reason="Cannot find croniter python module")
def test_eval_cron_loop_interval(schedule):
    """
    verify that scheduled job runs
    """

    job_name = "test_eval_cron_loop_interval"
    job = {"schedule": {job_name: {"function": "test.ping", "cron": "0 16 29 11 *"}}}
    # Randomn second loop interval
    LOOP_INTERVAL = random.randint(0, 59)
    schedule.opts["loop_interval"] = LOOP_INTERVAL

    # Add the job to the scheduler
    schedule.opts.update(job)

    run_time = dateutil.parser.parse("11/29/2017 4:00pm")
    with patch("croniter.croniter.get_next", MagicMock(return_value=run_time)):
        schedule.eval(now=run_time)
    assert _check_last_run(schedule, job_name, run_time)


@pytest.mark.slow_test
def test_eval_until(schedule):
    """
    verify that scheduled job is skipped once the current
    time reaches the specified until time
    """

    job_name = "test_eval_until"
    job = {
        "schedule": {
            job_name: {
                "function": "test.ping",
                "hours": "1",
                "until": "11/29/2017 5:00pm",
            }
        }
    }

    if salt.utils.platform.is_darwin():
        job["schedule"][job_name]["dry_run"] = True

    # Add job to schedule
    schedule.delete_job("test_eval_until")
    schedule.opts.update(job)

    # eval at 2:00pm to prime, simulate minion start up.
    run_time = dateutil.parser.parse("11/29/2017 2:00pm")
    schedule.eval(now=run_time)

    # eval at 3:00pm, will run.
    run_time = dateutil.parser.parse("11/29/2017 3:00pm")
    schedule.eval(now=run_time)

    # Give the job a chance to finish
    assert _check_last_run(schedule, job_name, run_time)

    # eval at 4:00pm, will run.
    run_time = dateutil.parser.parse("11/29/2017 4:00pm")
    schedule.eval(now=run_time)

    # Give the job a chance to finish
    assert _check_last_run(schedule, job_name, run_time)

    # eval at 5:00pm, will not run
    run_time = dateutil.parser.parse("11/29/2017 5:00pm")
    schedule.eval(now=run_time)

    ret = schedule.job_status(job_name)

    assert ret["_skip_reason"] == "until_passed"
    assert ret["_skipped_time"] == run_time


@pytest.mark.slow_test
def test_eval_after(schedule):
    """
    verify that scheduled job is skipped until after the specified
    time has been reached.
    """

    job_name = "test_eval_after"
    job = {
        "schedule": {
            job_name: {
                "function": "test.ping",
                "hours": "1",
                "after": "11/29/2017 5:00pm",
            }
        }
    }

    # Add job to schedule
    schedule.opts.update(job)

    # eval at 2:00pm to prime, simulate minion start up.
    run_time = dateutil.parser.parse("11/29/2017 2:00pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)

    # eval at 3:00pm, will not run.
    run_time = dateutil.parser.parse("11/29/2017 3:00pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)
    assert ret["_skip_reason"] == "after_not_passed"
    assert ret["_skipped_time"] == run_time

    # eval at 4:00pm, will not run.
    run_time = dateutil.parser.parse("11/29/2017 4:00pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)
    assert ret["_skip_reason"] == "after_not_passed"
    assert ret["_skipped_time"] == run_time

    # eval at 5:00pm, will not run
    run_time = dateutil.parser.parse("11/29/2017 5:00pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)
    assert ret["_skip_reason"] == "after_not_passed"
    assert ret["_skipped_time"] == run_time

    # eval at 6:00pm, will run
    run_time = dateutil.parser.parse("11/29/2017 6:00pm")
    schedule.eval(now=run_time)
    assert _check_last_run(schedule, job_name, run_time)


@pytest.mark.slow_test
def test_eval_enabled(schedule):
    """
    verify that scheduled job does not run
    """

    job_name = "test_eval_enabled"
    job = {
        "schedule": {
            "enabled": True,
            job_name: {"function": "test.ping", "when": "11/29/2017 4:00pm"},
        }
    }
    run_time1 = dateutil.parser.parse("11/29/2017 4:00pm")

    # Add the job to the scheduler
    schedule.opts.update(job)

    # Evaluate 1 second at the run time
    schedule.eval(now=run_time1)
    assert _check_last_run(schedule, job_name, run_time1)


@pytest.mark.slow_test
def test_eval_enabled_key(schedule):
    """
    verify that scheduled job runs
    when the enabled key is in place
    https://github.com/saltstack/salt/issues/47695
    """

    job_name = "test_eval_enabled_key"
    job = {
        "schedule": {
            "enabled": True,
            job_name: {"function": "test.ping", "when": "11/29/2017 4:00pm"},
        }
    }
    run_time2 = dateutil.parser.parse("11/29/2017 4:00pm")
    run_time1 = run_time2 - datetime.timedelta(seconds=1)

    # Add the job to the scheduler
    schedule.opts.update(job)

    # Evaluate 1 second before the run time
    schedule.eval(now=run_time1)
    ret = schedule.job_status("test_eval_enabled_key")
    assert "_last_run" not in ret

    # Evaluate 1 second at the run time
    schedule.eval(now=run_time2)
    assert _check_last_run(schedule, job_name, run_time2)


def test_eval_disabled(schedule):
    """
    verify that scheduled job does not run
    """

    job_name = "test_eval_disabled"
    job = {
        "schedule": {
            "enabled": False,
            job_name: {"function": "test.ping", "when": "11/29/2017 4:00pm"},
        }
    }
    run_time1 = dateutil.parser.parse("11/29/2017 4:00pm")

    # Add the job to the scheduler
    schedule.opts.update(job)

    # Evaluate 1 second at the run time
    schedule.eval(now=run_time1)
    ret = schedule.job_status(job_name)
    assert "_last_run" not in ret
    assert ret["_skip_reason"] == "disabled"

    # Ensure job data still matches
    assert ret == job["schedule"][job_name]


def test_eval_global_disabled_job_enabled(schedule):
    """
    verify that scheduled job does not run
    """

    job_name = "test_eval_global_disabled"
    job = {
        "schedule": {
            "enabled": False,
            job_name: {
                "function": "test.ping",
                "when": "11/29/2017 4:00pm",
                "enabled": True,
            },
        }
    }
    run_time1 = dateutil.parser.parse("11/29/2017 4:00pm")

    # Add the job to the scheduler
    schedule.opts.update(job)

    # Evaluate 1 second at the run time
    schedule.eval(now=run_time1)
    ret = schedule.job_status(job_name)
    assert "_last_run" not in ret
    assert ret["_skip_reason"] == "disabled"

    # Ensure job is still enabled
    assert ret["enabled"]


@pytest.mark.slow_test
def test_eval_run_on_start(schedule):
    """
    verify that scheduled job is run when minion starts
    """

    job_name = "test_eval_run_on_start"
    job = {
        "schedule": {
            job_name: {"function": "test.ping", "hours": "1", "run_on_start": True}
        }
    }

    # Add job to schedule
    schedule.opts.update(job)

    # eval at 2:00pm, will run.
    run_time = dateutil.parser.parse("11/29/2017 2:00pm")
    schedule.eval(now=run_time)
    assert _check_last_run(schedule, job_name, run_time)

    # eval at 3:00pm, will run.
    run_time = dateutil.parser.parse("11/29/2017 3:00pm")
    schedule.eval(now=run_time)
    assert _check_last_run(schedule, job_name, run_time)


@pytest.mark.slow_test
def test_eval_splay(schedule):
    """
    verify that scheduled job runs with splayed time
    """

    job_name = "job_eval_splay"
    job = {
        "schedule": {
            job_name: {"function": "test.ping", "seconds": "30", "splay": "10"}
        }
    }

    # Add job to schedule
    schedule.opts.update(job)

    with patch("random.randint", MagicMock(return_value=10)):
        # eval at 2:00pm to prime, simulate minion start up.
        run_time = dateutil.parser.parse("11/29/2017 2:00pm")
        schedule.eval(now=run_time)

        # eval at 2:00:40pm, will run.
        run_time = dateutil.parser.parse("11/29/2017 2:00:40pm")
        schedule.eval(now=run_time)
        assert _check_last_run(schedule, job_name, run_time)


@pytest.mark.slow_test
def test_eval_splay_range(schedule):
    """
    verify that scheduled job runs with splayed time
    """

    job_name = "job_eval_splay_range"
    job = {
        "schedule": {
            job_name: {
                "function": "test.ping",
                "seconds": "30",
                "splay": {"start": 5, "end": 10},
            }
        }
    }

    # Add job to schedule
    schedule.opts.update(job)

    with patch("random.randint", MagicMock(return_value=10)):
        # eval at 2:00pm to prime, simulate minion start up.
        run_time = dateutil.parser.parse("11/29/2017 2:00pm")
        schedule.eval(now=run_time)

        # eval at 2:00:40pm, will run.
        run_time = dateutil.parser.parse("11/29/2017 2:00:40pm")
        schedule.eval(now=run_time)
        assert _check_last_run(schedule, job_name, run_time)


@pytest.mark.slow_test
def test_eval_splay_global(schedule):
    """
    verify that scheduled job runs with splayed time
    """

    job_name = "job_eval_splay_global"
    job = {
        "schedule": {
            "splay": {"start": 5, "end": 10},
            job_name: {"function": "test.ping", "seconds": "30"},
        }
    }

    # Add job to schedule
    schedule.opts.update(job)

    with patch("random.randint", MagicMock(return_value=10)):
        # eval at 2:00pm to prime, simulate minion start up.
        run_time = dateutil.parser.parse("11/29/2017 2:00pm")
        schedule.eval(now=run_time)

        # eval at 2:00:40pm, will run.
        run_time = dateutil.parser.parse("11/29/2017 2:00:40pm")
        schedule.eval(now=run_time)
        assert _check_last_run(schedule, job_name, run_time)


@pytest.mark.slow_test
def test_eval_seconds(schedule):
    """
    verify that scheduled job run mutiple times with seconds
    """

    with patch.dict(schedule.opts, {"run_schedule_jobs_in_background": False}):
        job_name = "job_eval_seconds"
        job = {"schedule": {job_name: {"function": "test.ping", "seconds": "30"}}}

        if salt.utils.platform.is_darwin():
            job["schedule"][job_name]["dry_run"] = True

        # Add job to schedule
        schedule.opts.update(job)

        # eval at 2:00pm to prime, simulate minion start up.
        run_time = dateutil.parser.parse("11/29/2017 2:00pm")
        next_run_time = run_time + datetime.timedelta(seconds=30)
        jids = schedule.eval(now=run_time)
        assert len(jids) == 0
        ret = schedule.job_status(job_name)
        assert ret["_next_fire_time"] == next_run_time

        # eval at 2:00:01pm, will not run.
        run_time = dateutil.parser.parse("11/29/2017 2:00:01pm")
        jids = schedule.eval(now=run_time)
        assert len(jids) == 0
        ret = schedule.job_status(job_name)
        assert "_last_run" not in ret
        assert ret["_next_fire_time"] == next_run_time

        # eval at 2:00:30pm, will run.
        run_time = dateutil.parser.parse("11/29/2017 2:00:30pm")
        next_run_time = run_time + datetime.timedelta(seconds=30)
        jids = schedule.eval(now=run_time)
        assert len(jids) == 1
        ret = schedule.job_status(job_name)
        assert ret["_last_run"] == run_time
        assert ret["_next_fire_time"] == next_run_time

        # eval at 2:01:00pm, will run.
        run_time = dateutil.parser.parse("11/29/2017 2:01:00pm")
        next_run_time = run_time + datetime.timedelta(seconds=30)
        jids = schedule.eval(now=run_time)
        assert len(jids) == 1
        ret = schedule.job_status(job_name)
        assert ret["_last_run"] == run_time
        assert ret["_next_fire_time"] == next_run_time

        # eval at 2:01:30pm, will run.
        run_time = dateutil.parser.parse("11/29/2017 2:01:30pm")
        next_run_time = run_time + datetime.timedelta(seconds=30)
        jids = schedule.eval(now=run_time)
        assert len(jids) == 1
        ret = schedule.job_status(job_name)
        assert ret["_last_run"] == run_time
        assert ret["_next_fire_time"] == next_run_time


@pytest.mark.slow_test
def test_eval_minutes(schedule):
    """
    verify that scheduled job run mutiple times with minutes
    """

    with patch.dict(schedule.opts, {"run_schedule_jobs_in_background": False}):
        job_name = "job_eval_minutes"
        job = {"schedule": {job_name: {"function": "test.ping", "minutes": "30"}}}

        if salt.utils.platform.is_darwin():
            job["schedule"][job_name]["dry_run"] = True

        # Add job to schedule
        schedule.opts.update(job)

        # eval at 2:00pm to prime, simulate minion start up.
        run_time = dateutil.parser.parse("11/29/2017 2:00pm")
        next_run_time = run_time + datetime.timedelta(minutes=30)
        jids = schedule.eval(now=run_time)
        assert len(jids) == 0
        ret = schedule.job_status(job_name)
        assert ret["_next_fire_time"] == next_run_time

        # eval at 2:00:01pm, will not run.
        run_time = dateutil.parser.parse("11/29/2017 2:00:01pm")
        jids = schedule.eval(now=run_time)
        assert len(jids) == 0
        ret = schedule.job_status(job_name)
        assert "_last_run" not in ret
        assert ret["_next_fire_time"] == next_run_time

        # eval at 2:30:00pm, will run.
        run_time = dateutil.parser.parse("11/29/2017 2:30:00pm")
        jids = schedule.eval(now=run_time)
        assert len(jids) == 1
        ret = schedule.job_status(job_name)
        assert ret["_last_run"] == run_time

        # eval at 3:00:00pm, will run.
        run_time = dateutil.parser.parse("11/29/2017 3:00:00pm")
        jids = schedule.eval(now=run_time)
        assert len(jids) == 1
        ret = schedule.job_status(job_name)
        assert ret["_last_run"] == run_time

        # eval at 3:30:00pm, will run.
        run_time = dateutil.parser.parse("11/29/2017 3:30:00pm")
        jids = schedule.eval(now=run_time)
        assert len(jids) == 1
        ret = schedule.job_status(job_name)
        assert ret["_last_run"] == run_time


@pytest.mark.slow_test
def test_eval_hours(schedule):
    """
    verify that scheduled job run mutiple times with hours
    """

    with patch.dict(schedule.opts, {"run_schedule_jobs_in_background": False}):
        job_name = "job_eval_hours"
        job = {"schedule": {job_name: {"function": "test.ping", "hours": "2"}}}

        if salt.utils.platform.is_darwin():
            job["schedule"][job_name]["dry_run"] = True

        # Add job to schedule
        schedule.opts.update(job)

        # eval at 2:00pm to prime, simulate minion start up.
        run_time = dateutil.parser.parse("11/29/2017 2:00pm")
        next_run_time = run_time + datetime.timedelta(hours=2)
        jids = schedule.eval(now=run_time)
        assert len(jids) == 0
        ret = schedule.job_status(job_name)
        assert ret["_next_fire_time"] == next_run_time

        # eval at 2:00:01pm, will not run.
        run_time = dateutil.parser.parse("11/29/2017 2:00:01pm")
        jids = schedule.eval(now=run_time)
        assert len(jids) == 0
        ret = schedule.job_status(job_name)
        assert "_last_run" not in ret
        assert ret["_next_fire_time"] == next_run_time

        # eval at 4:00:00pm, will run.
        run_time = dateutil.parser.parse("11/29/2017 4:00:00pm")
        jids = schedule.eval(now=run_time)
        assert len(jids) == 1
        ret = schedule.job_status(job_name)
        assert ret["_last_run"] == run_time

        # eval at 6:00:00pm, will run.
        run_time = dateutil.parser.parse("11/29/2017 6:00:00pm")
        jids = schedule.eval(now=run_time)
        assert len(jids) == 1

        ret = schedule.job_status(job_name)
        assert ret["_last_run"] == run_time

        # eval at 8:00:00pm, will run.
        run_time = dateutil.parser.parse("11/29/2017 8:00:00pm")
        pids = schedule.eval(now=run_time)
        assert len(jids) == 1

        ret = schedule.job_status(job_name)
        assert ret["_last_run"] == run_time


@pytest.mark.slow_test
def test_eval_days(schedule):
    """
    verify that scheduled job run mutiple times with days
    """

    job_name = "job_eval_days"
    job = {
        "schedule": {job_name: {"function": "test.ping", "days": "2", "dry_run": True}}
    }

    if salt.utils.platform.is_darwin():
        job["schedule"][job_name]["dry_run"] = True

    # Add job to schedule
    schedule.opts.update(job)

    # eval at 11/23/2017 2:00pm to prime, simulate minion start up.
    run_time = dateutil.parser.parse("11/23/2017 2:00pm")
    next_run_time = run_time + datetime.timedelta(days=2)
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)
    assert ret["_next_fire_time"] == next_run_time

    # eval at 11/25/2017 2:00:00pm, will run.
    run_time = dateutil.parser.parse("11/25/2017 2:00:00pm")
    next_run_time = run_time + datetime.timedelta(days=2)
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)
    assert ret["_last_run"] == run_time
    assert ret["_next_fire_time"] == next_run_time

    # eval at 11/26/2017 2:00:00pm, will not run.
    run_time = dateutil.parser.parse("11/26/2017 2:00:00pm")
    last_run_time = run_time - datetime.timedelta(days=1)
    schedule.eval(now=run_time)

    # Give the job a chance to finish
    time.sleep(5)

    ret = schedule.job_status(job_name)

    assert ret["_last_run"] == last_run_time
    assert ret["_next_fire_time"] == next_run_time

    # eval at 11/27/2017 2:00:00pm, will run.
    run_time = dateutil.parser.parse("11/27/2017 2:00:00pm")
    next_run_time = run_time + datetime.timedelta(days=2)
    schedule.eval(now=run_time)

    # Give the job a chance to finish
    time.sleep(5)

    ret = schedule.job_status(job_name)

    assert ret["_last_run"] == run_time
    assert ret["_next_fire_time"] == next_run_time

    # eval at 11/28/2017 2:00:00pm, will not run.
    run_time = dateutil.parser.parse("11/28/2017 2:00:00pm")
    last_run_time = run_time - datetime.timedelta(days=1)
    schedule.eval(now=run_time)

    # Give the job a chance to finish
    time.sleep(5)

    ret = schedule.job_status(job_name)

    assert ret["_last_run"] == last_run_time
    assert ret["_next_fire_time"] == next_run_time

    # eval at 11/29/2017 2:00:00pm, will run.
    run_time = dateutil.parser.parse("11/29/2017 2:00:00pm")
    next_run_time = run_time + datetime.timedelta(days=2)
    schedule.eval(now=run_time)

    # Give the job a chance to finish
    time.sleep(5)

    ret = schedule.job_status(job_name)

    assert ret["_last_run"] == run_time
    assert ret["_next_fire_time"] == next_run_time


@pytest.mark.slow_test
def test_eval_when_splay(schedule):
    """
    verify that scheduled job runs
    """

    job_name = "test_eval_when_splay"
    splay = 300
    job = {
        "schedule": {
            job_name: {
                "function": "test.ping",
                "when": "11/29/2017 4:00pm",
                "splay": splay,
            }
        }
    }
    run_time1 = dateutil.parser.parse("11/29/2017 4:00pm")
    run_time2 = run_time1 + datetime.timedelta(seconds=splay)
    run_time3 = run_time2 + datetime.timedelta(seconds=1)

    # Add the job to the scheduler
    schedule.opts.update(job)

    with patch("random.randint", MagicMock(return_value=splay)):
        # Evaluate to prime
        run_time = dateutil.parser.parse("11/29/2017 3:00pm")
        schedule.eval(now=run_time)
        ret = schedule.job_status(job_name)

        # Evaluate at expected runtime1, should not run
        schedule.eval(now=run_time1)
        ret = schedule.job_status(job_name)
        assert "_last_run" not in ret

        # Evaluate at expected runtime2, should run
        schedule.eval(now=run_time2)
        ret = schedule.job_status(job_name)
        assert ret["_last_run"] == run_time2

        # Evaluate at expected runtime3, should not run
        # _next_fire_time should be None
        schedule.eval(now=run_time3)
        ret = schedule.job_status(job_name)
        assert ret["_last_run"] == run_time2
        assert ret["_next_fire_time"] is None


def test_eval_when_splay_in_past(schedule):
    """
    verify that scheduled job runs
    """

    job_name = "test_eval_when_splay_in_past"
    splay = 300
    job = {
        "schedule": {
            job_name: {
                "function": "test.ping",
                "when": ["11/29/2017 6:00am"],
                "splay": splay,
            }
        }
    }
    run_time1 = dateutil.parser.parse("11/29/2017 4:00pm")

    # Add the job to the scheduler
    schedule.opts.update(job)

    # Evaluate to prime
    run_time = dateutil.parser.parse("11/29/2017 3:00pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)

    # Evaluate at expected runtime1, should not run
    # and _next_fire_time should be None
    schedule.eval(now=run_time1)
    ret = schedule.job_status(job_name)
    assert "_last_run" not in ret
    assert ret["_next_fire_time"] is None
