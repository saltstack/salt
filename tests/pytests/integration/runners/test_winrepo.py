"""
Tests the winrepo runner
"""

import logging

import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]

log = logging.getLogger(__name__)


def test_update_winrepo(salt_master, salt_run_cli):
    """
    Simple test to make sure that update_git_repos works.
    """
    winrepo_remotes = salt_master.config["winrepo_remotes"]
    winrepo_remotes_ng = salt_master.config["winrepo_remotes_ng"]
    
    res = salt_run_cli.run("winrepo.update_git_repos").json

    assert res

    for remote in winrepo_remotes:
        assert remote in res
        assert res[remote]

    for remote in winrepo_remotes_ng:
        assert remote in res
        assert res[remote]
