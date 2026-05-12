import copy
import datetime
import logging

log = logging.getLogger(__name__)


def test_get_schedule_remove_hidden_true(schedule):
    """
    verify that the _get_schedule function works
    when remove_hidden is True and schedule data
    contains enabled key and that opts["schedule"]
    is not changed.
    """

    job_name = "test_get_schedule"
    job = {
        "schedule": {
            "enabled": True,
            job_name: {
                "function": "test.ping",
                "seconds": 60,
                "_next_fire_time": datetime.datetime(2023, 2, 13, 18, 25, 16, 271796),
                "_splay": None,
                "_seconds": 3600,
                "_next_scheduled_fire_time": datetime.datetime(
                    2023, 2, 13, 18, 25, 16, 271796
                ),
                "_skip_reason": "disabled",
                "_skipped_time": datetime.datetime(2023, 2, 13, 17, 26, 16, 271381),
                "_skipped": True,
            },
        }
    }

    expected_ret = {
        "enabled": True,
        job_name: {"function": "test.ping", "seconds": 60},
    }
    # Add the job to the scheduler
    schedule.opts.update(copy.deepcopy(job))

    ret = schedule._get_schedule(remove_hidden=True)
    assert expected_ret == ret
    assert schedule.opts["schedule"][job_name] == job["schedule"][job_name]


def test_get_schedule_remove_hidden_false(schedule):
    """
    verify that the _get_schedule function works
    when remove_hidden is False and schedule data
    contains enabled key and that opts["schedule"]
    is not changed.
    """

    job_name = "test_get_schedule"
    job = {
        "schedule": {
            "enabled": True,
            job_name: {
                "function": "test.ping",
                "seconds": 60,
                "_next_fire_time": datetime.datetime(2023, 2, 13, 18, 25, 16),
                "_splay": None,
                "_seconds": 3600,
                "_next_scheduled_fire_time": datetime.datetime(2023, 2, 13, 18, 25, 16),
                "_skip_reason": "disabled",
                "_skipped_time": datetime.datetime(2023, 2, 13, 17, 26, 16),
                "_skipped": True,
            },
        }
    }
    # Add the job to the scheduler
    schedule.opts.update(copy.deepcopy(job))

    ret = schedule._get_schedule(remove_hidden=False)
    assert job["schedule"] == ret
