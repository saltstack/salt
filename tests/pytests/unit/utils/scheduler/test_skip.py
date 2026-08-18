import logging

import pytest

try:
    import dateutil.parser

    HAS_DATEUTIL_PARSER = True
except ImportError:
    HAS_DATEUTIL_PARSER = False

log = logging.getLogger(__name__)


pytestmark = pytest.mark.skipif(
    HAS_DATEUTIL_PARSER is False,
    reason="The 'dateutil.parser' library is not available",
)


@pytest.mark.slow_test
def test_skip(schedule):
    """
    verify that scheduled job is skipped at the specified time
    """
    job_name = "test_skip"
    job = {
        "schedule": {
            job_name: {
                "function": "test.ping",
                "when": ["11/29/2017 4pm", "11/29/2017 5pm"],
            }
        }
    }

    # Add job to schedule
    schedule.opts.update(job)

    run_time = dateutil.parser.parse("11/29/2017 4:00pm")
    schedule.skip_job(
        job_name,
        {
            "time": run_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "time_fmt": "%Y-%m-%dT%H:%M:%S",
        },
    )

    # Run 11/29/2017 at 4pm
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)
    assert "_last_run" not in ret
    assert ret["_skip_reason"] == "skip_explicit"
    assert ret["_skipped_time"] == run_time

    # Run 11/29/2017 at 5pm
    run_time = dateutil.parser.parse("11/29/2017 5:00pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)
    assert ret["_last_run"] == run_time


@pytest.mark.slow_test
def test_skip_during_range(schedule):
    """
    verify that scheduled job is skipped during the specified range
    """
    job_name = "test_skip_during_range"
    job = {
        "schedule": {
            job_name: {
                "function": "test.ping",
                "hours": "1",
                "skip_during_range": {
                    "start": "11/29/2017 2pm",
                    "end": "11/29/2017 3pm",
                },
            }
        }
    }

    # Add job to schedule
    schedule.opts.update(job)

    # eval at 1:30pm to prime.
    run_time = dateutil.parser.parse("11/29/2017 1:30pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)

    # eval at 2:30pm, will not run during range.
    run_time = dateutil.parser.parse("11/29/2017 2:30pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)
    assert "_last_run" not in ret
    assert ret["_skip_reason"] == "in_skip_range"
    assert ret["_skipped_time"] == run_time

    # eval at 3:30pm, will run.
    run_time = dateutil.parser.parse("11/29/2017 3:30pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)
    assert ret["_last_run"] == run_time


def test_skip_during_range_invalid_datestring(schedule):
    """
    verify that scheduled job is not not and returns the right error string
    """
    run_time = dateutil.parser.parse("11/29/2017 2:30pm")

    job_name1 = "skip_during_range_invalid_datestring1"
    job1 = {
        "schedule": {
            job_name1: {
                "function": "test.ping",
                "hours": "1",
                "_next_fire_time": run_time,
                "skip_during_range": {"start": "25pm", "end": "3pm"},
            }
        }
    }

    job_name2 = "skip_during_range_invalid_datestring2"
    job2 = {
        "schedule": {
            job_name2: {
                "function": "test.ping",
                "hours": "1",
                "_next_fire_time": run_time,
                "skip_during_range": {"start": "2pm", "end": "25pm"},
            }
        }
    }

    # Add job1 to schedule
    schedule.opts.update(job1)

    # Eval
    schedule.eval(now=run_time)

    # Check the first job
    ret = schedule.job_status(job_name1)
    _expected = (
        "Invalid date string for start in skip_during_range. Ignoring job {}."
    ).format(job_name1)
    assert ret["_error"] == _expected

    # Clear out schedule
    schedule.opts["schedule"] = {}

    # Add job2 to schedule
    schedule.opts.update(job2)

    # Eval
    schedule.eval(now=run_time)

    # Check the second job
    ret = schedule.job_status(job_name2)
    _expected = (
        "Invalid date string for end in skip_during_range. Ignoring job {}."
    ).format(job_name2)
    assert ret["_error"] == _expected


@pytest.mark.slow_test
def test_skip_during_range_global(schedule):
    """
    verify that scheduled job is skipped during the specified range
    """
    job_name = "skip_during_range_global"
    job = {
        "schedule": {
            "skip_during_range": {
                "start": "11/29/2017 2:00pm",
                "end": "11/29/2017 3:00pm",
            },
            job_name: {"function": "test.ping", "hours": "1"},
        }
    }

    # Add job to schedule
    schedule.opts.update(job)

    # eval at 1:30pm to prime.
    run_time = dateutil.parser.parse("11/29/2017 1:30pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)

    # eval at 2:30pm, will not run during range.
    run_time = dateutil.parser.parse("11/29/2017 2:30pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)
    assert "_last_run" not in ret
    assert ret["_skip_reason"] == "in_skip_range"
    assert ret["_skipped_time"] == run_time

    # eval at 3:30pm, will run.
    run_time = dateutil.parser.parse("11/29/2017 3:30pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)
    assert ret["_last_run"] == run_time


@pytest.mark.slow_test
def test_run_after_skip_range(schedule):
    """
    verify that scheduled job is skipped during the specified range
    """
    job_name = "skip_run_after_skip_range"
    job = {
        "schedule": {
            job_name: {
                "function": "test.ping",
                "when": "11/29/2017 2:30pm",
                "run_after_skip_range": True,
                "skip_during_range": {
                    "start": "11/29/2017 2pm",
                    "end": "11/29/2017 3pm",
                },
            }
        }
    }

    # Add job to schedule
    schedule.opts.update(job)

    # eval at 2:30pm, will not run during range.
    run_time = dateutil.parser.parse("11/29/2017 2:30pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)
    assert "_last_run" not in ret
    assert ret["_skip_reason"] == "in_skip_range"
    assert ret["_skipped_time"] == run_time

    # eval at 3:00:01pm, will run.
    run_time = dateutil.parser.parse("11/29/2017 3:00:01pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)
    assert ret["_last_run"] == run_time


@pytest.mark.slow_test
def test_run_seconds_skip(schedule):
    """
    verify that scheduled job is skipped during the specified range
    """
    job_name = "run_seconds_skip"
    job = {"schedule": {job_name: {"function": "test.ping", "seconds": "10"}}}

    # Add job to schedule
    schedule.opts.update(job)

    # eval at 2:00pm, to prime the scheduler
    run_time = dateutil.parser.parse("11/29/2017 2:00pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)

    # eval at 2:00:10pm
    run_time = dateutil.parser.parse("11/29/2017 2:00:10pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)

    # Skip at 2:00:20pm
    run_time = dateutil.parser.parse("11/29/2017 2:00:20pm")
    schedule.skip_job(
        job_name,
        {
            "time": run_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "time_fmt": "%Y-%m-%dT%H:%M:%S",
        },
    )
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)
    assert "_next_fire_time" in ret
    assert ret["_skip_reason"] == "skip_explicit"
    assert ret["_skipped_time"] == run_time

    # Run at 2:00:30pm
    run_time = dateutil.parser.parse("11/29/2017 2:00:30pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status(job_name)
    assert "_last_run" in ret
