"""
These only test the provider selection and verification logic, they do not init
any remotes.
"""


import os
import shutil
from time import time

import salt.fileserver.gitfs
import salt.utils.files
import salt.utils.gitfs
import salt.utils.platform
import tests.support.paths
from salt.exceptions import FileserverConfigError
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

try:
    HAS_PYGIT2 = (
        salt.utils.gitfs.PYGIT2_VERSION >= salt.utils.gitfs.PYGIT2_MINVER
        and salt.utils.gitfs.LIBGIT2_VERSION >= salt.utils.gitfs.LIBGIT2_MINVER
    )
except AttributeError:
    HAS_PYGIT2 = False


if HAS_PYGIT2:
    import pygit2


def _clear_instance_map():
    try:
        del salt.utils.gitfs.GitFS.instance_map[
            salt.ext.tornado.ioloop.IOLoop.current()
        ]
    except KeyError:
        pass


class TestGitBase(TestCase, AdaptedConfigurationTestCaseMixin):
    def setUp(self):
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


class TestGitFSProvider(TestCase):
    def setUp(self):
        self.opts = {"cachedir": "/tmp/gitfs-test-cache"}

    def tearDown(self):
        self.opts = None

    def test_provider_case_insensitive(self):
        """
        Ensure that both lowercase and non-lowercase values are supported
        """
        provider = "GitPython"
        for role_name, role_class in (
            ("gitfs", salt.utils.gitfs.GitFS),
            ("git_pillar", salt.utils.gitfs.GitPillar),
            ("winrepo", salt.utils.gitfs.WinRepo),
        ):

            key = "{}_provider".format(role_name)
            with patch.object(
                role_class, "verify_gitpython", MagicMock(return_value=True)
            ):
                with patch.object(
                    role_class, "verify_pygit2", MagicMock(return_value=False)
                ):
                    args = [self.opts, {}]
                    kwargs = {"init_remotes": False}
                    if role_name == "winrepo":
                        kwargs["cache_root"] = "/tmp/winrepo-dir"
                    with patch.dict(self.opts, {key: provider}):
                        # Try to create an instance with uppercase letters in
                        # provider name. If it fails then a
                        # FileserverConfigError will be raised, so no assert is
                        # necessary.
                        role_class(*args, **kwargs)
                    # Now try to instantiate an instance with all lowercase
                    # letters. Again, no need for an assert here.
                    role_class(*args, **kwargs)

    def test_valid_provider(self):
        """
        Ensure that an invalid provider is not accepted, raising a
        FileserverConfigError.
        """

        def _get_mock(verify, provider):
            """
            Return a MagicMock with the desired return value
            """
            return MagicMock(return_value=verify.endswith(provider))

        for role_name, role_class in (
            ("gitfs", salt.utils.gitfs.GitFS),
            ("git_pillar", salt.utils.gitfs.GitPillar),
            ("winrepo", salt.utils.gitfs.WinRepo),
        ):
            key = "{}_provider".format(role_name)
            for provider in salt.utils.gitfs.GIT_PROVIDERS:
                verify = "verify_gitpython"
                mock1 = _get_mock(verify, provider)
                with patch.object(role_class, verify, mock1):
                    verify = "verify_pygit2"
                    mock2 = _get_mock(verify, provider)
                    with patch.object(role_class, verify, mock2):
                        args = [self.opts, {}]
                        kwargs = {"init_remotes": False}
                        if role_name == "winrepo":
                            kwargs["cache_root"] = "/tmp/winrepo-dir"

                        with patch.dict(self.opts, {key: provider}):
                            role_class(*args, **kwargs)

                        with patch.dict(self.opts, {key: "foo"}):
                            # Set the provider name to a known invalid provider
                            # and make sure it raises an exception.
                            self.assertRaises(
                                FileserverConfigError, role_class, *args, **kwargs
                            )


@skipIf(not HAS_PYGIT2, "This host lacks proper pygit2 support")
@skipIf(
    salt.utils.platform.is_windows(),
    "Skip Pygit2 on windows, due to pygit2 access error on windows",
)
class TestPygit2(TestCase):
    def _prepare_remote_repository(self, path):
        shutil.rmtree(path, ignore_errors=True)

        filecontent = "This is an empty README file"
        filename = "README"

        signature = pygit2.Signature(
            "Dummy Commiter", "dummy@dummy.com", int(time()), 0
        )

        repository = pygit2.init_repository(path, False)
        builder = repository.TreeBuilder()
        tree = builder.write()
        commit = repository.create_commit(
            "HEAD", signature, signature, "Create master branch", tree, []
        )
        repository.create_reference("refs/tags/simple_tag", commit)

        with salt.utils.files.fopen(
            os.path.join(repository.workdir, filename), "w"
        ) as file:
            file.write(filecontent)

        blob = repository.create_blob_fromworkdir(filename)
        builder = repository.TreeBuilder()
        builder.insert(filename, blob, pygit2.GIT_FILEMODE_BLOB)
        tree = builder.write()

        repository.index.read()
        repository.index.add(filename)
        repository.index.write()

        commit = repository.create_commit(
            "HEAD",
            signature,
            signature,
            "Added a README",
            tree,
            [repository.head.target],
        )
        repository.create_tag(
            "annotated_tag", commit, pygit2.GIT_OBJ_COMMIT, signature, "some message"
        )

    def _prepare_cache_repository(self, remote, cache):
        opts = {
            "cachedir": cache,
            "__role": "minion",
            "gitfs_disable_saltenv_mapping": False,
            "gitfs_base": "master",
            "gitfs_insecure_auth": False,
            "gitfs_mountpoint": "",
            "gitfs_passphrase": "",
            "gitfs_password": "",
            "gitfs_privkey": "",
            "gitfs_provider": "pygit2",
            "gitfs_pubkey": "",
            "gitfs_ref_types": ["branch", "tag", "sha"],
            "gitfs_refspecs": [
                "+refs/heads/*:refs/remotes/origin/*",
                "+refs/tags/*:refs/tags/*",
            ],
            "gitfs_root": "",
            "gitfs_saltenv_blacklist": [],
            "gitfs_saltenv_whitelist": [],
            "gitfs_ssl_verify": True,
            "gitfs_update_interval": 3,
            "gitfs_user": "",
            "verified_gitfs_provider": "pygit2",
        }
        per_remote_defaults = {
            "base": "master",
            "disable_saltenv_mapping": False,
            "insecure_auth": False,
            "ref_types": ["branch", "tag", "sha"],
            "passphrase": "",
            "mountpoint": "",
            "password": "",
            "privkey": "",
            "pubkey": "",
            "refspecs": [
                "+refs/heads/*:refs/remotes/origin/*",
                "+refs/tags/*:refs/tags/*",
            ],
            "root": "",
            "saltenv_blacklist": [],
            "saltenv_whitelist": [],
            "ssl_verify": True,
            "update_interval": 60,
            "user": "",
        }
        per_remote_only = ("all_saltenvs", "name", "saltenv")
        override_params = tuple(per_remote_defaults.keys())
        cache_root = os.path.join(cache, "gitfs")
        role = "gitfs"
        shutil.rmtree(cache_root, ignore_errors=True)
        provider = salt.utils.gitfs.Pygit2(
            opts,
            remote,
            per_remote_defaults,
            per_remote_only,
            override_params,
            cache_root,
            role,
        )
        return provider

    def test_checkout(self):
        remote = os.path.join(tests.support.paths.TMP, "pygit2-repo")
        cache = os.path.join(tests.support.paths.TMP, "pygit2-repo-cache")
        self._prepare_remote_repository(remote)
        provider = self._prepare_cache_repository(remote, cache)
        provider.remotecallbacks = None
        provider.credentials = None
        provider.init_remote()
        provider.fetch()
        provider.branch = "master"
        self.assertIn(provider.cachedir, provider.checkout())
        provider.branch = "simple_tag"
        self.assertIn(provider.cachedir, provider.checkout())
        provider.branch = "annotated_tag"
        self.assertIn(provider.cachedir, provider.checkout())
        provider.branch = "does_not_exist"
        self.assertIsNone(provider.checkout())
