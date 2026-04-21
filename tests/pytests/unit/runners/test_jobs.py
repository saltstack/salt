"""
unit tests for the jobs runner
"""

import pytest

import salt.minion
import salt.runners.jobs as jobs
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {
        jobs: {"__opts__": {"ext_job_cache": None, "master_job_cache": "local_cache"}}
    }


def test_list_jobs_with_search_target():
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
        assert jobs.list_jobs() == returns["all"]

        assert (
            jobs.list_jobs(search_target=["node-1-1*", "node-1-2*"]) == returns["all"]
        )

        assert jobs.list_jobs(search_target="node-1-1.com") == returns["node-1-1.com"]

        assert jobs.list_jobs(search_target="node-1-2.com") == returns["node-1-2.com"]

        assert jobs.list_jobs(search_target="non-existant") == returns["non-existant"]


def test_list_jobs_with_non_iterable_target(caplog):
    """
    Regression for #68780: failed/aborted jobs can leave Target as None or
    some other non-iterable value in the job cache. list_jobs used to
    iterate blindly and crash with TypeError; it must now skip those
    entries and continue filtering the rest of the cache.
    """
    mock_jobs_cache = {
        # Valid entry with a real target - must still be matched.
        "20260421000000000001": {
            "Arguments": [],
            "Function": "test.ping",
            "StartTime": "2026, Apr 21 00:00:00.000001",
            "Target": "node-1-1.com",
            "Target-type": "glob",
            "User": "root",
        },
        # Non-iterable Target (None is the real-world case from the bug
        # report). Must not trip list_jobs, and must be logged at debug.
        "20260421000000000002": {
            "Arguments": [],
            "Function": "test.ping",
            "StartTime": "2026, Apr 21 00:00:00.000002",
            "Target": None,
            "Target-type": "glob",
            "User": "root",
        },
    }

    def return_mock_jobs():
        return mock_jobs_cache

    class MockMasterMinion:
        returners = {"local_cache.get_jids": return_mock_jobs}

        def __init__(self, *args, **kwargs):
            pass

    with patch.object(salt.minion, "MasterMinion", MockMasterMinion):
        import logging

        with caplog.at_level(logging.DEBUG, logger="salt.runners.jobs"):
            # Must return the entry that has a valid target without raising
            # or masking the match quietly.
            result = jobs.list_jobs(search_target="node-1-1.com")

        assert "20260421000000000001" in result
        assert "20260421000000000002" not in result
        # The skipped job id should appear in the debug log so operators
        # can find and fix the malformed cache row instead of discovering
        # it via a crash.
        assert "20260421000000000002" in caplog.text
