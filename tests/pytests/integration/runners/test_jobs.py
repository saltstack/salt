"""
Tests for the salt-run command
"""

import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


def test_master(salt_run_cli, salt_minion):
    """
    jobs.master
    """
    ret = salt_run_cli.run("jobs.master")
    assert ret.data == []
    assert ret.stdout.strip() == "[]"


def test_active(salt_run_cli, salt_minion):
    """
    jobs.active
    """
    ret = salt_run_cli.run("jobs.active")
    assert ret.data == {}
    assert ret.stdout.strip() == "{}"


def test_lookup_jid(salt_run_cli, salt_minion):
    """
    jobs.lookup_jid
    """
    ret = salt_run_cli.run("jobs.lookup_jid", "23974239742394")
    assert ret.data == {}
    assert ret.stdout.strip() == "{}"


def test_lookup_jid_invalid(salt_run_cli, salt_minion):
    """
    jobs.lookup_jid
    """
    ret = salt_run_cli.run("jobs.lookup_jid")
    expected = "Passed invalid arguments:"
    assert expected in ret.stdout


def test_list_jobs(salt_run_cli, salt_minion, salt_cli):
    """
    jobs.list_jobs
    """
    salt_cli.run("test.echo", "test_list_jobs", minion_tgt=salt_minion.id)
    ret = salt_run_cli.run("jobs.list_jobs")
    assert isinstance(ret.data, dict)
    for job in ret.data.values():
        if job["Function"] != "test.echo":
            continue
        if job["Arguments"] != ["test_list_jobs"]:
            continue
        # We found our job in the list, we're good with the test
        break
    else:
        pytest.fail("Did not find our job from the jobs.list_jobs call")


def test_target_info(salt_run_cli, salt_minion, salt_cli):
    """
    This is a test case for issue #48734

    PR #43454 fixed an issue where "jobs.lookup_jid" was not working
    correctly with external job caches. However, this fix for external
    job caches broke some inner workings of job storage when using the
    local_cache.

    We need to preserve the previous behavior for the local_cache, but
    keep the new behavior for other external job caches.

    If "savefstr" is called in the local cache, the target data does not
    get written to the local_cache, and the target-type gets listed as a
    "list" type instead of "glob".

    This is a regression test for fixing the local_cache behavior.
    """
    salt_cli.run("test.echo", "target_info_test", minion_tgt=salt_minion.id)
    ret = salt_run_cli.run("jobs.list_jobs")
    for item in ret.data.values():
        if (
            item["Function"] == "test.echo"
            and item["Arguments"][0] == "target_info_test"
        ):
            job_ret = item
    tgt = job_ret["Target"]
    tgt_type = job_ret["Target-type"]

    assert tgt != "unknown-target"
    assert tgt == salt_minion.id
    assert tgt_type == "glob"


def test_jobs_runner(salt_run_cli, salt_minion):
    """
    Test when running a runner job and then
    running jobs_list to ensure the job was saved
    properly in the cache
    """
    salt_run_cli.run("test.arg", "arg1", kwarg1="kwarg1")
    ret = salt_run_cli.run("jobs.list_jobs")
    jid = None
    for key, item in ret.data.items():
        if item["Function"] == "runner.test.arg":
            jid = key

    get_job = salt_run_cli.run("jobs.list_job", jid)
    assert not get_job.data.get("Error")
    assert get_job.data["jid"] == jid


def test_target_info_salt_call(salt_run_cli, salt_minion, salt_call_cli):
    """
    Check the job infor for a call initiated
    with salt call
    """
    test = salt_call_cli.run("test.echo", "target_info_test", minion_tgt=salt_minion.id)
    ret = salt_run_cli.run("jobs.list_jobs")
    for item in ret.data.values():
        if (
            item["Function"] == "test.echo"
            and item["Arguments"][0] == "target_info_test"
        ):
            job_ret = item
    tgt = job_ret["Target"]
    tgt_type = job_ret["Target-type"]

    assert tgt != "unknown-target"
    assert tgt == salt_minion.id
    assert tgt_type == "glob"
