# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Erik Johnson <erik@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import
import errno
import os
import shutil
import tempfile
import textwrap
import tornado.ioloop
import logging
import stat
try:
    import pwd
except ImportError:
    pass

# Import 3rd-party libs
try:
    import git  # pylint: disable=unused-import
    HAS_GITPYTHON = True
    GITFS_AVAILABLE = True
except ImportError:
    HAS_GITPYTHON = False
    GITFS_AVAILABLE = False

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch
from tests.support.paths import TMP, FILES

# Import salt libs
import salt.fileserver.gitfs as gitfs
import salt.utils.gitfs
import salt.utils.platform
import salt.utils.win_functions
import salt.utils.yaml

log = logging.getLogger(__name__)

TMP_SOCK_DIR = tempfile.mkdtemp(dir=TMP)
TMP_REPO_DIR = os.path.join(TMP, 'gitfs_root')
INTEGRATION_BASE_FILES = os.path.join(FILES, 'file', 'base')


def _rmtree_error(func, path, excinfo):
    os.chmod(path, stat.S_IWRITE)
    func(path)


@skipIf(not HAS_GITPYTHON, 'GitPython is not installed')
class GitfsConfigTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        self.tmp_cachedir = tempfile.mkdtemp(dir=TMP)
        return {
            gitfs: {
                '__opts__': {
                    'cachedir': self.tmp_cachedir,
                    'sock_dir': TMP_SOCK_DIR,
                    'gitfs_root': 'salt',
                    'fileserver_backend': ['git'],
                    'gitfs_base': 'master',
                    'fileserver_events': True,
                    'transport': 'zeromq',
                    'gitfs_mountpoint': '',
                    'gitfs_saltenv': [],
                    'gitfs_env_whitelist': [],
                    'gitfs_env_blacklist': [],
                    'gitfs_saltenv_whitelist': [],
                    'gitfs_saltenv_blacklist': [],
                    'gitfs_user': '',
                    'gitfs_password': '',
                    'gitfs_insecure_auth': False,
                    'gitfs_privkey': '',
                    'gitfs_pubkey': '',
                    'gitfs_passphrase': '',
                    'gitfs_refspecs': [
                        '+refs/heads/*:refs/remotes/origin/*',
                        '+refs/tags/*:refs/tags/*'
                    ],
                    'gitfs_ssl_verify': True,
                    'gitfs_disable_saltenv_mapping': False,
                    'gitfs_ref_types': ['branch', 'tag', 'sha'],
                    '__role': 'master',
                }
            }
        }

    @classmethod
    def setUpClass(cls):
        # Clear the instance map so that we make sure to create a new instance
        # for this test class.
        try:
            del salt.utils.gitfs.GitFS.instance_map[tornado.ioloop.IOLoop.current()]
        except KeyError:
            pass

    def tearDown(self):
        shutil.rmtree(self.tmp_cachedir)

    def test_per_saltenv_config(self):
        opts_override = textwrap.dedent('''
            gitfs_saltenv:
              - baz:
                # when loaded, the "salt://" prefix will be removed
                - mountpoint: salt://baz_mountpoint
                - ref: baz_branch
                - root: baz_root

            gitfs_remotes:

              - file://tmp/repo1:
                - saltenv:
                  - foo:
                    - ref: foo_branch
                    - root: foo_root

              - file://tmp/repo2:
                - mountpoint: repo2
                - saltenv:
                  - baz:
                    - mountpoint: abc
        ''')
        with patch.dict(gitfs.__opts__, salt.utils.yaml.safe_load(opts_override)):
            git_fs = salt.utils.gitfs.GitFS(
                gitfs.__opts__,
                gitfs.__opts__['gitfs_remotes'],
                per_remote_overrides=gitfs.PER_REMOTE_OVERRIDES,
                per_remote_only=gitfs.PER_REMOTE_ONLY)

        # repo1 (branch: foo)
        # The mountpoint should take the default (from gitfs_mountpoint), while
        # ref and root should take the per-saltenv params.
        self.assertEqual(git_fs.remotes[0].mountpoint('foo'), '')
        self.assertEqual(git_fs.remotes[0].ref('foo'), 'foo_branch')
        self.assertEqual(git_fs.remotes[0].root('foo'), 'foo_root')

        # repo1 (branch: bar)
        # The 'bar' branch does not have a per-saltenv configuration set, so
        # each of the below values should fall back to global values.
        self.assertEqual(git_fs.remotes[0].mountpoint('bar'), '')
        self.assertEqual(git_fs.remotes[0].ref('bar'), 'bar')
        self.assertEqual(git_fs.remotes[0].root('bar'), 'salt')

        # repo1 (branch: baz)
        # The 'baz' branch does not have a per-saltenv configuration set, but
        # it is defined in the gitfs_saltenv parameter, so the values
        # from that parameter should be returned.
        self.assertEqual(git_fs.remotes[0].mountpoint('baz'), 'baz_mountpoint')
        self.assertEqual(git_fs.remotes[0].ref('baz'), 'baz_branch')
        self.assertEqual(git_fs.remotes[0].root('baz'), 'baz_root')

        # repo2 (branch: foo)
        # The mountpoint should take the per-remote mountpoint value of
        # 'repo2', while ref and root should fall back to global values.
        self.assertEqual(git_fs.remotes[1].mountpoint('foo'), 'repo2')
        self.assertEqual(git_fs.remotes[1].ref('foo'), 'foo')
        self.assertEqual(git_fs.remotes[1].root('foo'), 'salt')

        # repo2 (branch: bar)
        # The 'bar' branch does not have a per-saltenv configuration set, so
        # the mountpoint should take the per-remote mountpoint value of
        # 'repo2', while ref and root should fall back to global values.
        self.assertEqual(git_fs.remotes[1].mountpoint('bar'), 'repo2')
        self.assertEqual(git_fs.remotes[1].ref('bar'), 'bar')
        self.assertEqual(git_fs.remotes[1].root('bar'), 'salt')

        # repo2 (branch: baz)
        # The 'baz' branch has the mountpoint configured as a per-saltenv
        # parameter. The other two should take the values defined in
        # gitfs_saltenv.
        self.assertEqual(git_fs.remotes[1].mountpoint('baz'), 'abc')
        self.assertEqual(git_fs.remotes[1].ref('baz'), 'baz_branch')
        self.assertEqual(git_fs.remotes[1].root('baz'), 'baz_root')


LOAD = {'saltenv': 'base'}


@skipIf(not GITFS_AVAILABLE, "GitFS could not be loaded. Skipping GitFS tests!")
@skipIf(NO_MOCK, NO_MOCK_REASON)
class GitFSTest(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        self.tmp_cachedir = tempfile.mkdtemp(dir=TMP)
        return {
            gitfs: {
                '__opts__': {
                    'cachedir': self.tmp_cachedir,
                    'sock_dir': TMP_SOCK_DIR,
                    'gitfs_remotes': ['file://' + TMP_REPO_DIR],
                    'gitfs_root': '',
                    'fileserver_backend': ['git'],
                    'gitfs_base': 'master',
                    'fileserver_events': True,
                    'transport': 'zeromq',
                    'gitfs_mountpoint': '',
                    'gitfs_saltenv': [],
                    'gitfs_env_whitelist': [],
                    'gitfs_env_blacklist': [],
                    'gitfs_saltenv_whitelist': [],
                    'gitfs_saltenv_blacklist': [],
                    'gitfs_user': '',
                    'gitfs_password': '',
                    'gitfs_insecure_auth': False,
                    'gitfs_privkey': '',
                    'gitfs_pubkey': '',
                    'gitfs_passphrase': '',
                    'gitfs_refspecs': [
                        '+refs/heads/*:refs/remotes/origin/*',
                        '+refs/tags/*:refs/tags/*'
                    ],
                    'gitfs_ssl_verify': True,
                    'gitfs_disable_saltenv_mapping': False,
                    'gitfs_ref_types': ['branch', 'tag', 'sha'],
                    '__role': 'master',
                }
            }
        }

    @classmethod
    def setUpClass(cls):
        # Clear the instance map so that we make sure to create a new instance
        # for this test class.
        try:
            del salt.utils.gitfs.GitFS.instance_map[tornado.ioloop.IOLoop.current()]
        except KeyError:
            pass

        # Create the dir if it doesn't already exist
        try:
            shutil.copytree(INTEGRATION_BASE_FILES, TMP_REPO_DIR + '/')
        except OSError:
            # We probably caught an error because files already exist. Ignore
            pass

        try:
            repo = git.Repo(TMP_REPO_DIR)
        except git.exc.InvalidGitRepositoryError:
            repo = git.Repo.init(TMP_REPO_DIR)

        if 'USERNAME' not in os.environ:
            try:
                if salt.utils.platform.is_windows():
                    os.environ['USERNAME'] = salt.utils.win_functions.get_current_user()
                else:
                    os.environ['USERNAME'] = pwd.getpwuid(os.geteuid()).pw_name
            except AttributeError:
                log.error('Unable to get effective username, falling back to '
                          '\'root\'.')
                os.environ['USERNAME'] = 'root'

        repo.index.add([x for x in os.listdir(TMP_REPO_DIR)
                        if x != '.git'])
        repo.index.commit('Test')

    def setUp(self):
        '''
        We don't want to check in another .git dir into GH because that just
        gets messy. Instead, we'll create a temporary repo on the fly for the
        tests to examine.
        '''
        if not gitfs.__virtual__():
            self.skipTest("GitFS could not be loaded. Skipping GitFS tests!")
        self.tmp_cachedir = tempfile.mkdtemp(dir=TMP)
        gitfs.update()

    def tearDown(self):
        '''
        Remove the temporary git repository and gitfs cache directory to ensure
        a clean environment for each test.
        '''
        try:
            shutil.rmtree(self.tmp_cachedir, onerror=_rmtree_error)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise

    def test_file_list(self):
        ret = gitfs.file_list(LOAD)
        self.assertIn('testfile', ret)

    def test_dir_list(self):
        ret = gitfs.dir_list(LOAD)
        self.assertIn('grail', ret)

    def test_envs(self):
        ret = gitfs.envs()
        self.assertIn('base', ret)
