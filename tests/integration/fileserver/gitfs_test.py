# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import patch, NO_MOCK, NO_MOCK_REASON

ensure_in_syspath('../..')

# Import Python libs
import copy
import os
import shutil

# Import salt libs
import integration
from salt.fileserver import gitfs

gitfs.__opts__ = {'gitfs_remotes': [''],
                  'gitfs_root': '',
                  'fileserver_backend': ['git'],
                  'gitfs_base': 'master',
                  'fileserver_events': True,
                  'transport': 'zeromq',
                  'gitfs_mountpoint': '',
                  'gitfs_env_whitelist': [],
                  'gitfs_env_blacklist': []
}

LOAD = {'saltenv': 'base'}

GITFS_AVAILABLE = None
try:
    import git

    GITFS_AVAILABLE = True
except ImportError:
    pass

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

        repo.index.add([x for x in os.listdir(self.tmp_repo_dir)
                        if x != '.git'])
        repo.index.commit('Test')

        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_dir],
                                         'sock_dir': self.master_opts['sock_dir']}):
            gitfs.update()

    def tearDown(self):
        '''
        Remove the temporary git repository and gitfs cache directory to ensure
        a clean environment for each test.
        '''
        shutil.rmtree(self.tmp_repo_dir)
        shutil.rmtree(os.path.join(self.master_opts['cachedir'], 'gitfs'))

    @skipIf(True, 'This test is failing and for good reason! See #9193')
    def test_file_list(self):
        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_dir],
                                         'sock_dir': self.master_opts['sock_dir']}):
            ret = gitfs.file_list(LOAD)
            self.assertIn('testfile', ret)

    @skipIf(True, 'This test is failing and for good reason! See #9193')
    def test_find_file(self):
        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_dir],
                                         'sock_dir': self.master_opts['sock_dir']}):

            path = os.path.join(self.master_opts['cachedir'],
                                'gitfs/refs',
                                LOAD['saltenv'],
                                'testfile')

            ret = gitfs.find_file('testfile')
            expected_ret = {'path': path, 'rel': 'testfile'}
            self.assertDictEqual(ret, expected_ret)

    @skipIf(True, 'This test is failing and for good reason! See #9193')
    def test_dir_list(self):
        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_dir],
                                         'sock_dir': self.master_opts['sock_dir']}):
            ret = gitfs.dir_list(LOAD)
            self.assertIn('grail', ret)

    @skipIf(True, 'This test is failing and for good reason! See #9193')
    def test_file_list_emptydirs(self):
        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_dir],
                                         'sock_dir': self.master_opts['sock_dir']}):
            ret = gitfs.file_list_emptydirs(LOAD)
            self.assertIn('empty_dir', ret)

    @skipIf(True, 'This test is failing and for good reason! See #9193')
    def test_envs(self):
        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_dir],
                                         'sock_dir': self.master_opts['sock_dir']}):
            ret = gitfs.envs()
            self.assertIn('base', ret)

    @skipIf(True, 'This test is failing and for good reason! See #9193')
    def test_file_hash_sha1(self):
        '''
        NOTE: This test requires that gitfs.find_file is executed to ensure
        that the file exists in the gitfs cache.
        '''
        target = 'testfile'
        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_dir],
                                         'sock_dir': self.master_opts['sock_dir']}):
            # This needs to be in its own patch because we are using a
            # different hash_type for this test (sha1) from the one the master
            # is using (md5), which will cause the find_file to fail when the
            # repo URI is hashed to determine the cachedir.
            gitfs.find_file(target)

        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_dir],
                                         'sock_dir': self.master_opts['sock_dir'],
                                         'hash_type': 'sha1'}):
            tmp_load = copy.deepcopy(LOAD)
            tmp_load['loc'] = 0
            tmp_load['path'] = target
            fnd = {'rel': target,
                   'path': os.path.join(gitfs.__opts__['cachedir'],
                                        'gitfs/refs',
                                        tmp_load['saltenv'],
                                        tmp_load['path'])}

            ret = gitfs.file_hash(tmp_load, fnd)
            self.assertDictEqual(
                {'hash_type': 'sha1',
                 'hsum': '6b18d04b61238ba13b5e4626b13ac5fb7432b5e2'},
                ret)

    @skipIf(True, 'This test is failing and for good reason! See #9193')
    def test_serve_file(self):
        '''
        NOTE: This test requires that gitfs.find_file is executed to ensure
        that the file exists in the gitfs cache.
        '''
        target = 'testfile'
        with patch.dict(gitfs.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'gitfs_remotes': ['file://' + self.tmp_repo_dir],
                                         'sock_dir': self.master_opts['sock_dir'],
                                         'file_buffer_size': 262144}):
            tmp_load = copy.deepcopy(LOAD)
            tmp_load['loc'] = 0
            tmp_load['path'] = target
            fnd = {'rel': target,
                   'path': os.path.join(gitfs.__opts__['cachedir'],
                                        'gitfs/refs',
                                        tmp_load['saltenv'],
                                        tmp_load['path'])}

            gitfs.find_file(tmp_load['path'])
            ret = gitfs.serve_file(tmp_load, fnd)
            self.assertDictEqual({
                'data': 'Scene 24\n\n \n  OLD MAN:  Ah, hee he he ha!\n  '
                        'ARTHUR:  And this enchanter of whom you speak, he '
                        'has seen the grail?\n  OLD MAN:  Ha ha he he he '
                        'he!\n  ARTHUR:  Where does he live?  Old man, where '
                        'does he live?\n  OLD MAN:  He knows of a cave, a '
                        'cave which no man has entered.\n  ARTHUR:  And the '
                        'Grail... The Grail is there?\n  OLD MAN:  Very much '
                        'danger, for beyond the cave lies the Gorge\n      of '
                        'Eternal Peril, which no man has ever crossed.\n  '
                        'ARTHUR:  But the Grail!  Where is the Grail!?\n  OLD '
                        'MAN:  Seek you the Bridge of Death.\n  ARTHUR:  The '
                        'Bridge of Death, which leads to the Grail?\n  OLD '
                        'MAN:  Hee hee ha ha!\n\n',
                'dest': target},
                ret)


if __name__ == '__main__':
    integration.run_tests(GitFSTest)
