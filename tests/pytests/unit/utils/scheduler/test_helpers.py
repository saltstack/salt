import logging

log = logging.getLogger(__name__)


def test_get_schedule(schedule):
    """
    verify that the _get_schedule function works
    when remove_hidden is True and schedule data
    contains enabled key
    """

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
