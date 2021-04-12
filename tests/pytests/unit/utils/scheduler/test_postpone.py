import datetime
import logging

import pytest

try:
    import dateutil.parser

    HAS_DATEUTIL_PARSER = True
except ImportError:
    HAS_DATEUTIL_PARSER = False

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skipif(
        HAS_DATEUTIL_PARSER is False,
        reason="The 'dateutil.parser' library is not available",
    ),
    pytest.mark.windows_whitelisted,
]


@pytest.mark.slow_test
def test_postpone(schedule):
    """
    verify that scheduled job is postponed until the specified time.
    """
    job = {"schedule": {"job1": {"function": "test.ping", "when": "11/29/2017 4pm"}}}

    # 11/29/2017 4pm
    run_time = dateutil.parser.parse("11/29/2017 4:00pm")

    # 5 minute delay
    delay = 300

    # Add job to schedule
    schedule.opts.update(job)

    # Postpone the job by 5 minutes
    schedule.postpone_job(
        "job1",
        {
            "time": run_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "new_time": (run_time + datetime.timedelta(seconds=delay)).strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
        },
    )
    # Run at the original time
    schedule.eval(now=run_time)
    ret = schedule.job_status("job1")
    assert "_last_run" not in ret

    # Run 5 minutes later
    schedule.eval(now=run_time + datetime.timedelta(seconds=delay))
    ret = schedule.job_status("job1")
    assert ret["_last_run"] == run_time + datetime.timedelta(seconds=delay)

    # Run 6 minutes later
    schedule.eval(now=run_time + datetime.timedelta(seconds=delay + 1))
    ret = schedule.job_status("job1")
    assert ret["_last_run"] == run_time + datetime.timedelta(seconds=delay)
