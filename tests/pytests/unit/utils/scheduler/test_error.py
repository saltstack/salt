import logging

import pytest

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
]


@pytest.mark.skipif(not HAS_CRONITER, reason="Cannot find croniter python module")
def test_eval_cron_invalid(schedule):
    """
    verify that scheduled job runs
    """
    job = {"schedule": {"job1": {"function": "test.ping", "cron": "0 16 29 13 *"}}}

    # Add the job to the scheduler
    schedule.opts.update(job)

    run_time = dateutil.parser.parse("11/29/2017 4:00pm")
    with patch("croniter.croniter.get_next", MagicMock(return_value=run_time)):
        schedule.eval(now=run_time)

    ret = schedule.job_status("job1")
    assert ret["_error"] == "Invalid cron string. Ignoring job job1."


def test_eval_when_invalid_date(schedule):
    """
    verify that scheduled job does not run
    and returns the right error
    """
    run_time = dateutil.parser.parse("11/29/2017 4:00pm")

    job = {"schedule": {"job1": {"function": "test.ping", "when": "13/29/2017 1:00pm"}}}

    # Add the job to the scheduler
    schedule.opts.update(job)

    # Evaluate 1 second before the run time
    schedule.eval(now=run_time)
    ret = schedule.job_status("job1")
    assert ret["_error"] == "Invalid date string 13/29/2017 1:00pm. Ignoring job job1."


def test_eval_whens_grain_not_dict(schedule):
    """
    verify that scheduled job does not run
    and returns the right error
    """
    schedule.opts["grains"]["whens"] = {"tea time": "11/29/2017 12:00pm"}

    run_time = dateutil.parser.parse("11/29/2017 4:00pm")

    job = {"schedule": {"job1": {"function": "test.ping", "when": "tea time"}}}

    schedule.opts["grains"]["whens"] = ["tea time"]

    # Add the job to the scheduler
    schedule.opts.update(job)

    # Evaluate 1 second before the run time
    schedule.eval(now=run_time)
    ret = schedule.job_status("job1")
    assert ret["_error"] == 'Grain "whens" must be a dict. Ignoring job job1.'


def test_eval_once_invalid_datestring(schedule):
    """
    verify that scheduled job does not run
    and returns the right error
    """
    job = {
        "schedule": {"job1": {"function": "test.ping", "once": "2017-13-13T13:00:00"}}
    }
    run_time = dateutil.parser.parse("12/13/2017 1:00pm")

    # Add the job to the scheduler
    schedule.opts.update(job)

    # Evaluate 1 second at the run time
    schedule.eval(now=run_time)
    ret = schedule.job_status("job1")
    _expected = (
        "Date string could not be parsed: "
        "2017-13-13T13:00:00, %Y-%m-%dT%H:%M:%S. "
        "Ignoring job job1."
    )
    assert ret["_error"] == _expected


def test_eval_skip_during_range_invalid_date(schedule):
    """
    verify that scheduled job does not run
    and returns the right error
    """

    job = {
        "schedule": {
            "job1": {
                "function": "test.ping",
                "hours": 1,
                "skip_during_range": {"start": "1:00pm", "end": "25:00pm"},
            }
        }
    }

    # Add the job to the scheduler
    schedule.opts.update(job)

    # eval at 3:00pm to prime, simulate minion start up.
    run_time = dateutil.parser.parse("11/29/2017 3:00pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status("job1")

    # eval at 4:00pm to prime
    run_time = dateutil.parser.parse("11/29/2017 4:00pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status("job1")
    _expected = "Invalid date string for end in skip_during_range. Ignoring job job1."
    assert ret["_error"] == _expected


def test_eval_skip_during_range_end_before_start(schedule):
    """
    verify that scheduled job does not run
    and returns the right error
    """

    job = {
        "schedule": {
            "job1": {
                "function": "test.ping",
                "hours": 1,
                "skip_during_range": {"start": "1:00pm", "end": "12:00pm"},
            }
        }
    }

    # Add the job to the scheduler
    schedule.opts.update(job)

    # eval at 3:00pm to prime, simulate minion start up.
    run_time = dateutil.parser.parse("11/29/2017 3:00pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status("job1")

    # eval at 4:00pm to prime
    run_time = dateutil.parser.parse("11/29/2017 4:00pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status("job1")
    _expected = (
        "schedule.handle_func: Invalid "
        "range, end must be larger than "
        "start. Ignoring job job1."
    )
    assert ret["_error"] == _expected


def test_eval_skip_during_range_not_dict(schedule):
    """
    verify that scheduled job does not run
    and returns the right error
    """

    job = {
        "schedule": {
            "job1": {
                "function": "test.ping",
                "hours": 1,
                "skip_during_range": ["start", "1:00pm", "end", "12:00pm"],
            }
        }
    }

    # Add the job to the scheduler
    schedule.opts.update(job)

    # eval at 3:00pm to prime, simulate minion start up.
    run_time = dateutil.parser.parse("11/29/2017 3:00pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status("job1")

    # eval at 4:00pm to prime
    run_time = dateutil.parser.parse("11/29/2017 4:00pm")
    schedule.eval(now=run_time)
    ret = schedule.job_status("job1")
    _expected = (
        "schedule.handle_func: Invalid, "
        "range must be specified as a "
        "dictionary. Ignoring job job1."
    )
    assert ret["_error"] == _expected
