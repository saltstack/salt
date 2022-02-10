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


def test_update_winrepo(salt_run_cli):
    """
    Simple test to make sure that update_git_repos works.
    """
    res = salt_run_cli.run("winrepo.update_git_repos")
    for key in res.json:
        assert ".git" in key
