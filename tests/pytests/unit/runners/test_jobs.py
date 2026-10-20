"""
unit tests for the jobs runner
"""

import pytest

import salt.minion
import salt.runners.jobs as jobs
import salt.utils.jid
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


def test_list_jobs_search_metadata_state_apply():
    """
    Ensure list_jobs search_metadata matches jobs whose metadata was
    passed through the CLI as a keyword argument to state.apply (the
    metadata then lives inside ``Arguments`` as a ``__kwarg__`` dict
    rather than at the top of the job instance).

    Regression test for #68481.
    """
    # Already-formatted job entries as returned by the
    # ``local_cache.get_jids`` returner via ``format_jid_instance``. The
    # cmd.run job exposes ``Metadata`` directly while the state.apply job
    # carries its metadata inside ``Arguments`` because it was passed as
    # a keyword argument from the command line (``__kwarg__: True``).
    state_apply_job = salt.utils.jid.format_job_instance(
        {
            "fun": "state.apply",
            "arg": [
                "Sandbox.create_test_file",
                {
                    "__kwarg__": True,
                    "metadata": {
                        "task_id": "bb52013a",
                        "source": "flask",
                    },
                },
            ],
            "tgt": ["salt-minion"],
            "tgt_type": "list",
            "user": "root",
        }
    )
    cmd_run_job = salt.utils.jid.format_job_instance(
        {
            "fun": "cmd.run",
            "arg": ["echo 'test'"],
            "metadata": {"task_id": "0c47889f", "source": "Flask"},
            "tgt": "salt-minion",
            "tgt_type": "glob",
            "user": "root",
        }
    )
    other_job = salt.utils.jid.format_job_instance(
        {
            "fun": "state.apply",
            "arg": [
                "Sandbox.create_test_file",
                {
                    "__kwarg__": True,
                    "metadata": {"task_id": "different"},
                },
            ],
            "tgt": ["salt-minion"],
            "tgt_type": "list",
            "user": "root",
        }
    )
    mock_jobs_cache = {
        "20251121134552341171": state_apply_job,
        "20251121100403664430": cmd_run_job,
        "20251121134652341171": other_job,
    }

    def return_mock_jobs():
        return mock_jobs_cache

    class MockMasterMinion:

        returners = {"local_cache.get_jids": return_mock_jobs}

        def __init__(self, *args, **kwargs):
            pass

    with patch.object(salt.minion, "MasterMinion", MockMasterMinion):
        result = jobs.list_jobs(search_metadata={"task_id": "bb52013a"})
        assert "20251121134552341171" in result
        assert "20251121100403664430" not in result
        assert "20251121134652341171" not in result

        result = jobs.list_jobs(search_metadata={"task_id": "0c47889f"})
        assert "20251121100403664430" in result
        assert "20251121134552341171" not in result
