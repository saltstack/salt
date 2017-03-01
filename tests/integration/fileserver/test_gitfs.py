# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import os
import logging
import pwd
import shutil

# Import Salt Testing libs
import tests.integration as integration
from tests.support.unit import skipIf
from tests.support.mock import patch, NO_MOCK, NO_MOCK_REASON

# Import salt libs
from salt.fileserver import gitfs

gitfs.__opts__ = {'cachedir': '/tmp/gitfs_test_cache',
                  'gitfs_remotes': [''],
                  'gitfs_root': '',
                  'fileserver_backend': ['git'],
                  'gitfs_base': 'master',
                  'fileserver_events': True,
                  'transport': 'zeromq',
                  'gitfs_mountpoint': '',
                  'gitfs_env_whitelist': [],
                  'gitfs_env_blacklist': [],
                  'gitfs_user': '',
                  'gitfs_password': '',
                  'gitfs_insecure_auth': False,
                  'gitfs_privkey': '',
                  'gitfs_pubkey': '',
                  'gitfs_passphrase': '',
                  'gitfs_refspecs': ['+refs/heads/*:refs/remotes/origin/*',
                                     '+refs/tags/*:refs/tags/*'],
                  'gitfs_ssl_verify': True
}

LOAD = {'saltenv': 'base'}

log = logging.getLogger(__name__)

try:
    import git
    GITFS_AVAILABLE = True
except ImportError:
    GITFS_AVAILABLE = False

if not gitfs.__virtual__():
    GITFS_AVAILABLE = False


@skipIf(not GITFS_AVAILABLE, "GitFS could not be loaded. Skipping GitFS tests!")
@skipIf(NO_MOCK, NO_MOCK_REASON)
class GitFSTest(integration.ModuleCase):
    maxDiff = None

    def setUp(self):
        '''
        We don't want to check in another .git dir into GH because that just gets messy.
        Instead, we'll create a temporary repo on the fly for the tests to examine.
        '''
        self.integration_base_files = os.path.join(integration.FILES, 'file', 'base')
        self.tmp_repo_dir = os.path.join(integration.TMP, 'gitfs_root')

        # Create the dir if it doesn't already exist

        try:
            shutil.copytree(self.integration_base_files, self.tmp_repo_dir + '/')
        except OSError:
            # We probably caught an error because files already exist. Ignore
            pass

        try:
            repo = git.Repo(self.tmp_repo_dir)
        except git.exc.InvalidGitRepositoryError:
            repo = git.Repo.init(self.tmp_repo_dir)

        if 'USERNAME' not in os.environ:
            try:
                os.environ['USERNAME'] = pwd.getpwuid(os.geteuid()).pw_name
            except AttributeError:
                log.error('Unable to get effective username, falling back to '
                          '\'root\'.')
                os.environ['USERNAME'] = 'root'

        repo.index.add([x for x in os.listdir(self.tmp_repo_dir)
                        if x != '.git'])
        repo.index.commit('Test')

        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_dir],
                                         'sock_dir': self.master_opts['sock_dir'],
                                         '__role': self.master_opts['__role']}):
            gitfs.update()

    def tearDown(self):
        '''
        Remove the temporary git repository and gitfs cache directory to ensure
        a clean environment for each test.
        '''
        shutil.rmtree(self.tmp_repo_dir)
        shutil.rmtree(os.path.join(self.master_opts['cachedir'], 'gitfs'))

    #@skipIf(True, 'Skipping tests temporarily')
    def test_file_list(self):
        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_dir],
                                         'sock_dir': self.master_opts['sock_dir'],
                                         '__role': self.master_opts['__role']}):
            ret = gitfs.file_list(LOAD)
            self.assertIn('testfile', ret)

    #@skipIf(True, 'Skipping tests temporarily')
    def test_dir_list(self):
        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_dir],
                                         'sock_dir': self.master_opts['sock_dir'],
                                         '__role': self.master_opts['__role']}):
            ret = gitfs.dir_list(LOAD)
            self.assertIn('grail', ret)

    #@skipIf(True, 'Skipping tests temporarily')
    def test_envs(self):
        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_dir],
                                         'sock_dir': self.master_opts['sock_dir'],
                                         '__role': self.master_opts['__role']}):
            ret = gitfs.envs()
            self.assertIn('base', ret)
