# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Erik Johnson <erik@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import
import copy
import logging
import os
import subprocess

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    Mock,
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.utils.versions import LooseVersion
import salt.modules.git as git_mod  # Don't potentially shadow GitPython

log = logging.getLogger(__name__)

WORKTREE_ROOT = '/tmp/salt-tests-tmpdir/main'
WORKTREE_INFO = {
    WORKTREE_ROOT: {
        'HEAD': '119f025073875a938f2456f5ffd7d04e79e5a427',
        'branch': 'refs/heads/master',
        'stale': False,
    },
    '/tmp/salt-tests-tmpdir/worktree1': {
        'HEAD': 'd8d19cf75d7cc3bdc598dc2d472881d26b51a6bf',
        'branch': 'refs/heads/worktree1',
        'stale': False,
    },
    '/tmp/salt-tests-tmpdir/worktree2': {
        'HEAD': '56332ca504aa8b37bb62b54272d52b1d6d832629',
        'branch': 'refs/heads/worktree2',
        'stale': True,
    },
    '/tmp/salt-tests-tmpdir/worktree3': {
        'HEAD': 'e148ea2d521313579f661373fbb93a48a5a6d40d',
        'branch': 'detached',
        'tags': ['v1.1'],
        'stale': False,
    },
    '/tmp/salt-tests-tmpdir/worktree4': {
        'HEAD': '6bbac64d3ad5582b3147088a708952df185db020',
        'branch': 'detached',
        'stale': True,
    },
}


def _git_version():
    git_version = subprocess.Popen(
        ['git', '--version'],
        shell=False,
        close_fds=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE).communicate()[0]
    if not git_version:
        log.error('Git not installed')
        return False
    log.debug('Detected git version ' + git_version)
    return LooseVersion(git_version.split()[-1])


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GitTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.git
    '''
    def setup_loader_modules(self):
        return {
            git_mod: {
                '__utils__': {
                    'ssh.key_is_encrypted': Mock(return_value=False)
                },
            }
        }

    def test_list_worktrees(self):
        '''
        This tests git.list_worktrees
        '''
        def _build_worktree_output(path):
            '''
            Build 'git worktree list' output for a given path
            '''
            return 'worktree {0}\nHEAD {1}\n{2}\n'.format(
                path,
                WORKTREE_INFO[path]['HEAD'],
                'branch {0}'.format(WORKTREE_INFO[path]['branch'])
                    if WORKTREE_INFO[path]['branch'] != 'detached'
                    else 'detached'
            )

        # Build dict for _cmd_run_side_effect below. Start with the output from
        # 'git worktree list'.
        _cmd_run_values = {
            'git worktree list --porcelain': '\n'.join(
                [_build_worktree_output(x) for x in WORKTREE_INFO]
            ),
            'git --version': 'git version 2.7.0',
        }
        # Add 'git tag --points-at' output for detached HEAD worktrees with
        # tags pointing at HEAD.
        for path in WORKTREE_INFO:
            if WORKTREE_INFO[path]['branch'] != 'detached':
                continue
            key = 'git tag --points-at ' + WORKTREE_INFO[path]['HEAD']
            _cmd_run_values[key] = '\n'.join(
                WORKTREE_INFO[path].get('tags', [])
            )

        def _cmd_run_side_effect(key, **kwargs):
            # Not using dict.get() here because we want to know if
            # _cmd_run_values doesn't account for all uses of cmd.run_all.
            return {'stdout': _cmd_run_values[' '.join(key)],
                    'stderr': '',
                    'retcode': 0,
                    'pid': 12345}

        def _isdir_side_effect(key):
            # os.path.isdir() would return True on a non-stale worktree
            return not WORKTREE_INFO[key].get('stale', False)

        # Build return dict for comparison
        worktree_ret = copy.deepcopy(WORKTREE_INFO)
        for key in worktree_ret:
            ptr = worktree_ret.get(key)
            ptr['detached'] = ptr['branch'] == 'detached'
            ptr['branch'] = None \
                if ptr['detached'] \
                else ptr['branch'].replace('refs/heads/', '', 1)

        cmd_run_mock = MagicMock(side_effect=_cmd_run_side_effect)
        isdir_mock = MagicMock(side_effect=_isdir_side_effect)
        with patch.dict(git_mod.__salt__, {'cmd.run_all': cmd_run_mock}):
            with patch.object(os.path, 'isdir', isdir_mock):
                # Test all=True. Include all return data.
                self.maxDiff = None
                self.assertEqual(
                    git_mod.list_worktrees(
                        WORKTREE_ROOT, all=True, stale=False
                    ),
                    worktree_ret
                )
                # Test all=False and stale=False. Exclude stale worktrees from
                # return data.
                self.assertEqual(
                    git_mod.list_worktrees(
                        WORKTREE_ROOT, all=False, stale=False
                    ),
                    dict([(x, worktree_ret[x]) for x in WORKTREE_INFO
                          if not WORKTREE_INFO[x].get('stale', False)])
                )
                # Test stale=True. Exclude non-stale worktrees from return
                # data.
                self.assertEqual(
                    git_mod.list_worktrees(
                        WORKTREE_ROOT, all=False, stale=True
                    ),
                    dict([(x, worktree_ret[x]) for x in WORKTREE_INFO
                          if WORKTREE_INFO[x].get('stale', False)])
                )

    def test__git_run_tmp_wrapper(self):
        '''
        When an identity file is specified, make sure we don't attempt to
        remove a temp wrapper that wasn't created. Windows doesn't use temp
        wrappers, and *NIX won't unless no username was specified and the path
        is not executable.
        '''
        file_remove_mock = Mock()
        mock_true = Mock(return_value=True)
        mock_false = Mock(return_value=False)
        cmd_mock = MagicMock(return_value={
            'retcode': 0,
            'stdout': '',
            'stderr': '',
        })
        with patch.dict(git_mod.__salt__, {'file.file_exists': mock_true,
                                           'file.remove': file_remove_mock,
                                           'cmd.run_all': cmd_mock,
                                           'ssh.key_is_encrypted': mock_false}):

            # Non-windows
            with patch('salt.utils.is_windows', mock_false), \
                    patch.object(git_mod, '_path_is_executable_others',
                                 mock_true):

                # Command doesn't really matter here since we're mocking
                git_mod._git_run(
                    ['git', 'rev-parse', 'HEAD'],
                    cwd='/some/path',
                    user=None,
                    identity='/root/.ssh/id_rsa')

                file_remove_mock.assert_not_called()

            file_remove_mock.reset_mock()
            with patch('salt.utils.is_windows', mock_true), \
                    patch.object(git_mod, '_find_ssh_exe',
                                 MagicMock(return_value=r'C:\Git\ssh.exe')):
                # Command doesn't really matter here since we're mocking
                git_mod._git_run(
                    ['git', 'rev-parse', 'HEAD'],
                    cwd=r'C:\some\path',
                    user=None,
                    identity=r'C:\ssh\id_rsa')

                file_remove_mock.assert_not_called()
