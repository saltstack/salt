"""
These only test the provider selection and verification logic, they do not init
any remotes.
"""

import tempfile

import pytest
import tornado.ioloop

import salt.fileserver.gitfs
import salt.utils.files
import salt.utils.gitfs
import salt.utils.path
import salt.utils.platform
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.unit import TestCase


def _clear_instance_map():
    try:
        del salt.utils.gitfs.GitFS.instance_map[tornado.ioloop.IOLoop.current()]
    except KeyError:
        pass


class TestGitBase(TestCase, AdaptedConfigurationTestCaseMixin):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        tmp_name = self._tmp_dir.name

        class MockedProvider(
            salt.utils.gitfs.GitProvider
        ):  # pylint: disable=abstract-method
            def __init__(
                self,
                opts,
                remote,
                per_remote_defaults,
                per_remote_only,
                override_params,
                cache_root,
                role="gitfs",
            ):
                self.provider = "mocked"
                self.fetched = False
                super().__init__(
                    opts,
                    remote,
                    per_remote_defaults,
                    per_remote_only,
                    override_params,
                    cache_root,
                    role,
                )

            def init_remote(self):
                self.gitdir = salt.utils.path.join(tmp_name, ".git")
                self.repo = True
                new = False
                return new

            def envs(self):
                return ["base"]

            def fetch(self):
                self.fetched = True

        git_providers = {
            "mocked": MockedProvider,
        }
        gitfs_remotes = ["file://repo1.git", {"file://repo2.git": [{"name": "repo2"}]}]
        self.opts = self.get_temp_config(
            "master", gitfs_remotes=gitfs_remotes, verified_gitfs_provider="mocked"
        )
        self.main_class = salt.utils.gitfs.GitFS(
            self.opts,
            self.opts["gitfs_remotes"],
            per_remote_overrides=salt.fileserver.gitfs.PER_REMOTE_OVERRIDES,
            per_remote_only=salt.fileserver.gitfs.PER_REMOTE_ONLY,
            git_providers=git_providers,
        )

    @classmethod
    def setUpClass(cls):
        # Clear the instance map so that we make sure to create a new instance
        # for this test class.
        _clear_instance_map()

    def tearDown(self):
        # Providers are preserved with GitFS's instance_map
        for remote in self.main_class.remotes:
            remote.fetched = False
        del self.main_class
        self._tmp_dir.cleanup()

    def test_update_all(self):
        self.main_class.update()
        self.assertEqual(len(self.main_class.remotes), 2, "Wrong number of remotes")
        self.assertTrue(self.main_class.remotes[0].fetched)
        self.assertTrue(self.main_class.remotes[1].fetched)

    def test_update_by_name(self):
        self.main_class.update("repo2")
        self.assertEqual(len(self.main_class.remotes), 2, "Wrong number of remotes")
        self.assertFalse(self.main_class.remotes[0].fetched)
        self.assertTrue(self.main_class.remotes[1].fetched)

    def test_update_by_id_and_name(self):
        self.main_class.update([("file://repo1.git", None)])
        self.assertEqual(len(self.main_class.remotes), 2, "Wrong number of remotes")
        self.assertTrue(self.main_class.remotes[0].fetched)
        self.assertFalse(self.main_class.remotes[1].fetched)

    def test_get_cachedir_basename(self):
        self.assertEqual(
            self.main_class.remotes[0].get_cache_basename(),
            "_",
        )
        self.assertEqual(
            self.main_class.remotes[1].get_cache_basename(),
            "_",
        )

    def test_git_provider_mp_lock(self):
        """
        Check that lock is released after provider.lock()
        """
        provider = self.main_class.remotes[0]
        provider.lock()
        # check that lock has been released
        self.assertTrue(provider._master_lock.acquire(timeout=5))
        provider._master_lock.release()

    def test_git_provider_mp_clear_lock(self):
        """
        Check that lock is released after provider.clear_lock()
        """
        provider = self.main_class.remotes[0]
        provider.clear_lock()
        # check that lock has been released
        self.assertTrue(provider._master_lock.acquire(timeout=5))
        provider._master_lock.release()

    @pytest.mark.slow_test
    @pytest.mark.timeout_unless_on_windows(120)
    def test_git_provider_mp_lock_timeout(self):
        """
        Check that lock will time out if master lock is locked.
        """
        provider = self.main_class.remotes[0]
        # Hijack the lock so git provider is fooled into thinking another instance is doing somthing.
        self.assertTrue(provider._master_lock.acquire(timeout=5))
        try:
            # git provider should raise timeout error to avoid lock race conditions
            self.assertRaises(TimeoutError, provider.lock)
        finally:
            provider._master_lock.release()

    @pytest.mark.slow_test
    @pytest.mark.timeout_unless_on_windows(120)
    def test_git_provider_mp_clear_lock_timeout(self):
        """
        Check that clear lock will time out if master lock is locked.
        """
        provider = self.main_class.remotes[0]
        # Hijack the lock so git provider is fooled into thinking another instance is doing somthing.
        self.assertTrue(provider._master_lock.acquire(timeout=5))
        try:
            # git provider should raise timeout error to avoid lock race conditions
            self.assertRaises(TimeoutError, provider.clear_lock)
        finally:
            provider._master_lock.release()
