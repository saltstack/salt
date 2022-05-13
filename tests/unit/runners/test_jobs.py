"""
unit tests for the jobs runner
"""


import salt.minion
import salt.runners.jobs as jobs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase


class JobsTest(TestCase, LoaderModuleMockMixin):
    """
    Validate the jobs runner
    """

    def setup_loader_modules(self):
        return {
            jobs: {
                "__opts__": {"ext_job_cache": None, "master_job_cache": "local_cache"}
            }
        }

    def test_list_jobs_with_search_target(self):
        """
        test jobs.list_jobs runner with search_target args
        """
        mock_jobs_cache = {
            "20160524035503086853": {
                "Arguments": [],
                "Function": "test.ping",
                "StartTime": "2016, May 24 03:55:03.086853",
                "Target": "node-1-1.com",
                "Target-type": "glob",
                "User": "root",
            },
            "20160524035524895387": {
                "Arguments": [],
                "Function": "test.ping",
                "StartTime": "2016, May 24 03:55:24.895387",
                "Target": ["node-1-2.com", "node-1-1.com"],
                "Target-type": "list",
                "User": "sudo_ubuntu",
            },
        }

        def return_mock_jobs():
            return mock_jobs_cache

        class MockMasterMinion:

            returners = {"local_cache.get_jids": return_mock_jobs}

            def __init__(self, *args, **kwargs):
                pass

        returns = {
            "all": mock_jobs_cache,
            "node-1-1.com": mock_jobs_cache,
            "node-1-2.com": {
                "20160524035524895387": mock_jobs_cache["20160524035524895387"]
            },
            "non-existant": {},
        }

        with patch.object(salt.minion, "MasterMinion", MockMasterMinion):
            self.assertEqual(jobs.list_jobs(), returns["all"])

            self.assertEqual(
                jobs.list_jobs(search_target=["node-1-1*", "node-1-2*"]), returns["all"]
            )

            self.assertEqual(
                jobs.list_jobs(search_target="node-1-1.com"), returns["node-1-1.com"]
            )

            self.assertEqual(
                jobs.list_jobs(search_target="node-1-2.com"), returns["node-1-2.com"]
            )

            self.assertEqual(
                jobs.list_jobs(search_target="non-existant"), returns["non-existant"]
            )
