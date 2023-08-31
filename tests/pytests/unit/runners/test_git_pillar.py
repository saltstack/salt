"""
unit tests for the git_pillar runner
"""


import logging

import pytest

import salt.runners.git_pillar as git_pillar
import salt.utils.files
import salt.utils.gitfs
from tests.support.gitfs import _OPTS
from tests.support.mock import patch

log = logging.getLogger(__name__)


@pytest.fixture
def cachedir(tmp_path):
    return tmp_path / "cache"


@pytest.fixture
def configure_loader_modules(cachedir):
    opts = _OPTS.copy()
    opts["cachedir"] = str(cachedir)
    opts["verified_git_pillar_provider"] = "gitfoo"
    opts["ext_pillar"] = [
        {
            "git": [
                "master https://someurl/some",
                {"dev https://otherurl/other": [{"name": "somename"}]},
            ]
        }
    ]
    return {git_pillar: {"__opts__": opts}}


def test_update():
    """
    test git_pillar.update
    """

    class MockGitProvider(
        salt.utils.gitfs.GitProvider
    ):  # pylint: disable=abstract-method
        def init_remote(self):
            new = False
            self.repo = True
            return new

        def fetch(self):
            return True

        def clear_lock(self, lock_type="update"):
            pass  # return success, failed

    git_providers = {"gitfoo": MockGitProvider}

    repo1 = {"master https://someurl/some": True}
    repo2 = {"dev https://otherurl/other": True}
    all_repos = {
        "master https://someurl/some": True,
        "dev https://otherurl/other": True,
    }
    with patch.object(salt.utils.gitfs, "GIT_PROVIDERS", git_providers):
        assert git_pillar.update() == all_repos
        assert git_pillar.update(branch="master") == repo1
        assert git_pillar.update(branch="dev") == repo2
        assert git_pillar.update(repo="somename") == repo2
