"""
unit tests for the git_pillar runner
"""


import errno
import logging
import tempfile

import salt.runners.git_pillar as git_pillar
import salt.utils.files
import salt.utils.gitfs
from tests.support.gitfs import _OPTS
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class GitPillarTest(TestCase, LoaderModuleMockMixin):
    """
    Validate the git_pillar runner
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp_cachedir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)

    @classmethod
    def tearDownClass(cls):
        try:
            salt.utils.files.rm_rf(cls.tmp_cachedir)
        except OSError as exc:
            if exc.errno == errno.EACCES:
                log.error("Access error removing file %s", cls.tmp_cachedir)
            elif exc.errno != errno.EEXIST:
                raise

    def setup_loader_modules(self):
        opts = _OPTS.copy()
        opts["cachedir"] = self.tmp_cachedir
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

    def test_update(self):
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
            self.assertEqual(git_pillar.update(), all_repos)
            self.assertEqual(git_pillar.update(branch="master"), repo1)
            self.assertEqual(git_pillar.update(branch="dev"), repo2)
            self.assertEqual(git_pillar.update(repo="somename"), repo2)
