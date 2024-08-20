import logging

log = logging.getLogger(__name__)


def test_run_job(schedule):
    """
    verify that scheduled job runs
    """
    job_name = "test_run_job"
    job = {"schedule": {job_name: {"function": "test.ping"}}}
    # Add the job to the scheduler
    schedule.opts.update(job)

    # Run job
    schedule.run_job(job_name)
    ret = schedule.job_status(job_name)
    expected = {"function": "test.ping", "run": True, "name": "test_run_job"}
    assert ret == expected
