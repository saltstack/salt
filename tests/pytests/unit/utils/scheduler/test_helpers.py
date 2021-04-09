import logging

import pytest

log = logging.getLogger(__name__)


@pytest.fixture()
def loop_interval(schedule):
    schedule.opts["loop_interval"] = 1


def test_get_schedule(setup_teardown_vars):
    """
    verify that the _get_schedule function works
    when remove_hidden is True and schedule data
    contains enabled key
    """
    schedule = setup_teardown_vars["schedule"]

    job_name = "test_get_schedule"
    job = {
        "schedule": {
            "enabled": True,
            job_name: {"function": "test.ping", "seconds": 60},
        }
    }
    # Add the job to the scheduler
    schedule.opts.update(job)

    ret = schedule._get_schedule(remove_hidden=True)
    assert job["schedule"] == ret
