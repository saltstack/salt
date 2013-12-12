# -*- coding: utf-8 -*-
'''
    :codauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import (ensure_in_syspath, destructiveTest)
from salttesting.mock import patch, MagicMock, call, NO_MOCK, NO_MOCK_REASON

ensure_in_syspath('../')

# Import Python libs
import os
import shutil

# Import salt libs
import integration
from salt.fileserver import gitfs

gitfs.__opts__ = {'gitfs_remotes': [''],
                  'gitfs_root': '',
                  'fileserver_backend': 'gitfs',
                  'gitfs_base': 'master',
                  'fileserver_events': True,
}

load = {'saltenv': 'base'}

GITFS_AVAILABLE = None
try:
    import git

    GITFS_AVAILABLE = True
except ImportError:
    pass

if not gitfs.__virtual__():
    GITFS_AVAILABLE = False


# @skipIf(not GITFS_AVAILABLE, "GitFS could not be loaded. Skipping GitFS tests!")
class GitFSTest(integration.ModuleCase):
    def setUp(self):
        '''
        We don't want to check in another .git dir into GH because that just gets messy.
        Instead, we'll create a temporary repo on the fly for the tests to examine.
        :return:
        '''
        self.integration_base_files = os.path.join(integration.FILES, 'file', 'base')
        self.tmp_repo_dir = os.path.join(integration.TMP, 'gitfs_root')
        self.tmp_repo_git = os.path.join(self.tmp_repo_dir, '.git')

        # Create the dir if it doesn't already exist

        try:
            shutil.copytree(self.integration_base_files, self.tmp_repo_dir + '/')
        except OSError as e:
            # We probably caught an error because files already exist. Ignore
            pass

        if not os.path.exists(self.tmp_repo_git):
            os.makedirs(self.tmp_repo_git)
        try:
            git_bin = git.Git(self.tmp_repo_git)
            git_bin.init(self.tmp_repo_dir)
            os.chdir(self.tmp_repo_dir)
            git_bin.add('.', with_keep_cwd=True)  # Is there a way to pass in a .git repo?
            git_bin.commit('-a', '-m', 'Test', with_keep_cwd=True)
        except git.GitCommandError:  # Will throw a command error if you try to init a repo that already exists
            pass

        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_git],
                                         'sock_dir': self.master_opts['sock_dir']}):
            gitfs.update()

    def test_file_list(self):
        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_git],
                                         'sock_dir': self.master_opts['sock_dir']}):
            ret = gitfs.file_list(load)
            self.assertIn('testfile', ret)

    def test_find_file(self):
        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_git],
                                         'sock_dir': self.master_opts['sock_dir']}):
            ret = gitfs.find_file('testfile')
            expected_ret = {'path': '/tmp/salttest/cache/gitfs/refs/master/testfile',
                            'rel': 'testfile'}

            self.assertDictEqual(ret, expected_ret)

    def test_dir_list(self):
        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_git],
                                         'sock_dir': self.master_opts['sock_dir']}):
            ret = gitfs.dir_list(load)
            self.assertIn('grail', ret)

    @skipIf(True, 'This test is failing and for good reason! See #9193')
    def test_file_list_emptydirs(self):
        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_git],
                                         'sock_dir': self.master_opts['sock_dir']}):
            ret = gitfs.file_list_emptydirs(load)
            self.assertIn('empty_dir', ret)

    def test_envs(self):
        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_git],
                                         'sock_dir': self.master_opts['sock_dir']}):
            ret = gitfs.envs()
            self.assertIn('base', ret)

    def test_file_hash_sha1(self):
        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_git],
                                         'sock_dir': self.master_opts['sock_dir'],
                                         'hash_type': 'blob_sha1'}):
            tmp_load = load
            tmp_load['path'] = 'testfile'
            fnd = {'rel': 'testfile',
                   'path': 'testfile'}
            ret = gitfs.file_hash(load, fnd)
            self.assertDictEqual({'hash_type': 'blob_sha1', 'hsum': '0d234303e6451128d756c5c259175de37d767742'}, ret)

    @skipIf(True, 'This test is failing and for good reason! See #9194')
    def test_file_hash_md5(self):
        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_git],
                                         'sock_dir': self.master_opts['sock_dir'],
                                         'hash_type': 'md5'}):
            tmp_load = load
            tmp_load['path'] = 'testfile'
            fnd = {'rel': 'testfile',
                   'path': 'testfile'}
            ret = gitfs.file_hash(load, fnd)
            self.assertDictEqual({'hash_type': 'md5', 'hsum': '98aa509006628302ce38ce521a7f805f'}, ret)

    def test_serve_file(self):
        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_git],
                                         'sock_dir': self.master_opts['sock_dir'],
                                         'file_buffer_size': 262144}):
            fnd = {'rel': 'testfile',
                   'path': 'testfile'}

            tmp_load = load
            tmp_load['loc'] = 0

            ret = gitfs.serve_file(load, fnd)
            self.assertDictEqual({
                                     'data': 'Scene 24\n\n \n  OLD MAN:  Ah, hee he he ha!\n  ARTHUR:  And this enchanter of whom you speak, he has seen the grail?\n  OLD MAN:  Ha ha he he he he!\n  ARTHUR:  Where does he live?  Old man, where does he live?\n  OLD MAN:  He knows of a cave, a cave which no man has entered.\n  ARTHUR:  And the Grail... The Grail is there?\n  OLD MAN:  Very much danger, for beyond the cave lies the Gorge\n      of Eternal Peril, which no man has ever crossed.\n  ARTHUR:  But the Grail!  Where is the Grail!?\n  OLD MAN:  Seek you the Bridge of Death.\n  ARTHUR:  The Bridge of Death, which leads to the Grail?\n  OLD MAN:  Hee hee ha ha!\n\n',
                                     'dest': 'testfile'}, ret)


if __name__ == '__main__':
    integration.run_tests(GitFSTest)
