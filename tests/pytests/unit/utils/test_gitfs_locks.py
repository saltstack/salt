"""
These only test the provider selection and verification logic, they do not init
any remotes.
"""

import pytest

import salt.ext.tornado.ioloop
import salt.fileserver.gitfs
import salt.utils.files
import salt.utils.gitfs
import salt.utils.path
import salt.utils.platform
from tests.support.mixins import AdaptedConfigurationTestCaseMixin


def _clear_instance_map():
    try:
        del salt.utils.gitfs.GitFS.instance_map[
            salt.ext.tornado.ioloop.IOLoop.current()
        ]
    except KeyError:
        pass


@pytest.fixture
def get_tmp_dir(tmp_path):
    dirpath = tmp_path / "git_test"
    dirpath.mkdir(parents=True)
    return dirpath

    ## dirpath.cleanup()


class TestGitBase(AdaptedConfigurationTestCaseMixin):
    """
    mocked GitFS provider leveraging tmp_path
    """

    def __init__(
        self,
    ):
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
                self.gitdir = salt.utils.path.join(get_tmp_dir, ".git")
                self.repo = True
                new = False
                return new

            def envs(self):
                return ["base"]

            def fetch(self):
                self.fetched = True

        # Clear the instance map so that we make sure to create a new instance
        # for this test class.
        _clear_instance_map()

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

    def tearDown(self):
        # Providers are preserved with GitFS's instance_map
        for remote in self.main_class.remotes:
            remote.fetched = False
        del self.main_class
        ## self._tmp_dir.cleanup()


@pytest.fixture
def main_class(tmp_path):
    test_git_base = TestGitBase()
    yield test_git_base

    test_git_base.tearDown()


def test_update_all(main_class):
    main_class.update()
    assert len(main_class.remotes) == 2, "Wrong number of remotes"
    assert main_class.remotes[0].fetched
    assert main_class.remotes[1].fetched


def test_update_by_name(main_class):
    main_class.update("repo2")
    assert len(main_class.remotes) == 2, "Wrong number of remotes"
    assert not main_class.remotes[0].fetched
    assert main_class.remotes[1].fetched


def test_update_by_id_and_name(main_class):
    main_class.update([("file://repo1.git", None)])
    assert len(main_class.remotes) == 2, "Wrong number of remotes"
    assert main_class.remotes[0].fetched
    assert not main_class.remotes[1].fetched


def test_get_cachedir_basename(main_class):
    assert main_class.remotes[0].get_cache_basename() == "_"
    assert main_class.remotes[1].get_cache_basename() == "_"


def test_git_provider_mp_lock():
    """
    Check that lock is released after provider.lock()
    """
    provider = main_class.remotes[0]
    provider.lock()
    # check that lock has been released
    assert provider._master_lock.acquire(timeout=5)
    provider._master_lock.release()


def test_git_provider_mp_clear_lock(main_class):
    """
    Check that lock is released after provider.clear_lock()
    """
    provider = main_class.remotes[0]
    provider.clear_lock()
    # check that lock has been released
    assert provider._master_lock.acquire(timeout=5)
    provider._master_lock.release()


@pytest.mark.slow_test
@pytest.mark.timeout_unless_on_windows(120)
def test_git_provider_mp_lock_timeout(main_class):
    """
    Check that lock will time out if master lock is locked.
    """
    provider = main_class.remotes[0]
    # Hijack the lock so git provider is fooled into thinking another instance is doing somthing.
    assert provider._master_lock.acquire(timeout=5)
    try:
        # git provider should raise timeout error to avoid lock race conditions
        pytest.raises(TimeoutError, provider.lock)
    finally:
        provider._master_lock.release()


@pytest.mark.slow_test
@pytest.mark.timeout_unless_on_windows(120)
def test_git_provider_mp_clear_lock_timeout(main_class):
    """
    Check that clear lock will time out if master lock is locked.
    """
    provider = main_class.remotes[0]
    # Hijack the lock so git provider is fooled into thinking another instance is doing somthing.
    assert provider._master_lock.acquire(timeout=5)
    try:
        # git provider should raise timeout error to avoid lock race conditions
        pytest.raises(TimeoutError, provider.clear_lock)
    finally:
        provider._master_lock.release()
