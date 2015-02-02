# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import git
from salt.exceptions import SaltInvocationError

# Globals
git.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GitTestCase(TestCase):
    '''
    Test cases for salt.modules.git
    '''
    # 'get_' function tests: 1

    def test_current_branch(self):
        '''
        Test if it returns the current branch name
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(git.__salt__, {'cmd.run_stdout': mock}):
            self.assertTrue(git.current_branch('develop'))

    # 'revision' function tests: 1

    def test_revision(self):
        '''
        Test if it returns the long hash of a given identifier
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertTrue(git.revision('develop'),)

    # 'clone' function tests: 1

    def test_clone(self):
        '''
        Test if it clone a new repository
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertTrue(git.clone('origin', 'develop'))

    # 'describe' function tests: 1

    def test_describe(self):
        '''
        Test if it returns the git describe string (or the SHA hash
        if there are no tags) for the given revision
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(git.__salt__, {'cmd.run_stdout': mock}):
            self.assertTrue(git.describe('develop'))

    # 'archive' function tests: 1

    def test_archive(self):
        '''
        Test if it exports a tarball from the repository
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        mock_val = MagicMock(return_value='true')
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': mock_val}):
            self.assertTrue(git.archive('develop', 'archive.tar.gz'))

    # 'fetch' function tests: 1

    def test_fetch(self):
        '''
        Test if it perform a fetch on the given repository
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertTrue(git.fetch('develop'))

    # 'pull' function tests: 1

    def test_pull(self):
        '''
        Test if it perform a pull on the given repository
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertTrue(git.pull('develop'))

    # 'rebase' function tests: 1

    def test_rebase(self):
        '''
        Test if it rebase the current branch
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertEqual(git.rebase('develop'), True)

    # 'checkout' function tests: 1

    def test_checkout(self):
        '''
        Test if it checkout a given revision
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertTrue(git.checkout('develop', 'mybranch'))

    # 'merge' function tests: 1

    def test_merge(self):
        '''
        Test if it merge a given branch
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertTrue(git.merge('develop'))

    # 'init' function tests: 1

    def test_init(self):
        '''
        Test if it initialize a new git repository
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertTrue(git.init('develop'))

    # 'submodule' function tests: 1

    def test_submodule(self):
        '''
        Test if it initialize git submodules
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertTrue(git.submodule('develop'))

    # 'status' function tests: 1

    def test_status(self):
        '''
        Test if it return the status of the repository
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertListEqual(git.status('develop'), [])

    # 'add' function tests: 1

    def test_add(self):
        '''
        Test if it add a file to git
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertTrue(git.add('develop',
                                    '/salt/tests/unit/modules/example.py'))

    # 'rm' function tests: 1

    def test_rm(self):
        '''
        Test if it remove a file to git
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertTrue(git.rm('develop',
                                   '/salt/tests/unit/modules/example.py'))

    # 'commit' function tests: 1

    def test_commit(self):
        '''
        Test if it create a commit
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertTrue(git.commit('develop', 'The comit message'))

    # 'push' function tests: 1

    def test_push(self):
        '''
        Test if it Push to remote
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertTrue(git.push('develop', 'remote-name'))

    # 'remotes' function tests: 1

    def test_remotes(self):
        '''
        Test if it gets remotes like git remote -v
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertDictEqual(git.remotes('develop'), {})

    # 'remote_get' function tests: 1

    def test_remote_get(self):
        '''
        Test if it get the fetch and push URL for a specified remote name
        '''
        mock = MagicMock(return_value={'retcode': 0,
                                       'stdout': '\nSalt\nStack'})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertEqual(git.remote_get('develop'), ('Salt', 'Stack'))

        mock = MagicMock(return_value={'retcode': 0,
                                       'stdout': '\norigin\norigin'})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertEqual(git.remote_get('develop'), None)

        mock = MagicMock(return_value={'retcode': 1,
                                       'stdout': '\norigin\norigin',
                                       'stderr': 'error'})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertEqual(git.remote_get('develop'), None)

    # 'remote_set' function tests: 1

    def test_remote_set(self):
        '''
        Test if it sets a remote with name and URL like git remote add name url
        '''
        mock = MagicMock(return_value={'retcode': 0,
                                       'stdout': '\nSalt\nStack'})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertEqual(git.remote_set('develop'), ('Salt', 'Stack'))

    # 'branch' function tests: 1

    def test_branch(self):
        '''
        Test if it interacts with branches
        '''
        mock_all = MagicMock(return_value={'retcode': 0, 'stdout': ''})
        mock_stdout = MagicMock(return_value=True)
        with patch.dict(git.__salt__, {'cmd.run_all': mock_all,
                                       'cmd.run_stdout': mock_stdout}):
            self.assertEqual(git.branch('develop', 'origin/develop'), True)

    # 'reset' function tests: 1

    def test_reset(self):
        '''
        Test if it reset the repository checkout
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertEqual(git.reset('develop'), True)

    # 'stash' function tests: 1

    def test_stash(self):
        '''
        Test if stash changes in the repository checkout
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertEqual(git.stash('develop'), True)

    # 'config_set' function tests: 1

    def test_config_set(self):
        '''
        Test if it sets a key in the git configuration file
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertRaises(TypeError, git.config_set)

        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertRaises(SaltInvocationError, git.config_set,
                              None, 'myname', 'me@example.com')

        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertEqual(git.config_set(None, 'myname', 'me@example.com',
                                            'me', True), True)

    # 'config_get' function tests: 1

    def test_config_get(self):
        '''
        Test if it gets a key or keys from the git configuration file
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertRaises(TypeError, git.config_get)

        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertEqual(git.config_get(None, 'myname', 'me'), True)

    # 'ls_remote' function tests: 1

    def test_ls_remote(self):
        '''
        Test if it returns the upstream hash for any given URL and branch.
        '''
        mock = MagicMock(return_value={'retcode': 0, 'stdout': True})
        with patch.dict(git.__salt__, {'cmd.run_all': mock,
                                       'cmd.run_stdout': True}):
            self.assertEqual(git.ls_remote('develop'), True)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GitTestCase, needs_daemon=False)
