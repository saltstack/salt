"""
Tests for the salt-run command
"""

import pytest

from tests.support.case import ShellCase


@pytest.mark.windows_whitelisted
@pytest.mark.usefixtures("salt_sub_minion")
class JobsTest(ShellCase):
    """
    Test the jobs runner.
    """

    @pytest.mark.slow_test
    def test_master(self):
        """
        jobs.master
        """
        ret = self.run_run_plus("jobs.master", _output="json")
        self.assertEqual(ret["return"], [])
        self.assertEqual(ret["out"], [])

    @pytest.mark.slow_test
    def test_active(self):
        """
        jobs.active
        """
        ret = self.run_run_plus("jobs.active", _output="json")
        self.assertEqual(ret["return"], {})
        self.assertEqual(ret["out"], {})

    @pytest.mark.slow_test
    def test_lookup_jid(self):
        """
        jobs.lookup_jid
        """
        ret = self.run_run_plus("jobs.lookup_jid", "23974239742394", _output="json")
        self.assertEqual(ret["return"], {})
        self.assertEqual(ret["out"], {})

    @pytest.mark.slow_test
    def test_lookup_jid_invalid(self):
        """
        jobs.lookup_jid
        """
        ret = self.run_run_plus("jobs.lookup_jid", _output="json")
        expected = "Passed invalid arguments:"
        self.assertIn(expected, ret["return"])

    @pytest.mark.slow_test
    def test_list_jobs(self):
        """
        jobs.list_jobs
        """
        self.run_salt("minion test.echo test_list_jobs")
        ret = self.run_run_plus("jobs.list_jobs", _output="json")
        self.assertIsInstance(ret["return"], dict)
        for job in ret["return"].values():
            if job["Function"] != "test.echo":
                continue
            if job["Arguments"] != ["test_list_jobs"]:
                continue
            # We our job in the list, we're good with the test
            break
        else:
            self.fail("Did not our job from the jobs.list_jobs call")


@pytest.mark.windows_whitelisted
class LocalCacheTargetTest(ShellCase):
    """
    Test that a job stored in the local_cache has target information
    """

    @pytest.mark.slow_test
    def test_target_info(self):
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
        self.run_salt("minion test.echo target_info_test")
        ret = self.run_run_plus("jobs.list_jobs", _output="json")
        for item in ret["return"].values():
            if (
                item["Function"] == "test.echo"
                and item["Arguments"][0] == "target_info_test"
            ):
                job_ret = item
        tgt = job_ret["Target"]
        tgt_type = job_ret["Target-type"]

        assert tgt != "unknown-target"
        assert tgt in ["minion", "sub_minion"]
        assert tgt_type == "glob"
