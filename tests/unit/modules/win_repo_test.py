# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
import salt.output
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    mock_open,
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')
# Import Salt Libs
from salt.modules import win_repo

win_repo.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinRepoTestCase(TestCase):
    '''
        Test cases for salt.modules.win_repo
    '''
    def test_genrepo(self):
        '''
            Test to generate win_repo_cachefile
            based on sls files in the win_repo
        '''
        with patch.dict(win_repo.__opts__, {'win_repo': 'c:\\salt'}):
            mock_bool = MagicMock(return_value=True)
            with patch.object(os.path, 'exists', mock_bool):
                with patch.dict(win_repo.__opts__,
                                {'win_repo_cachefile': 'cache.c'}):
                    mock = MagicMock(return_value={})
                    with patch.object(os, 'walk', mock):
                        with patch('salt.utils.fopen', mock_open()):
                            with patch.object(salt.output, 'display_output',
                                              mock_bool):
                                self.assertDictEqual(win_repo.genrepo(), {})

    def test_update_git_repos(self):
        '''
            Test to checkout git repos containing
            Windows Software Package Definitions
        '''
        with patch.dict(win_repo.__opts__, {'win_repo': 'c:\\salt'}):
            with patch.dict(win_repo.__opts__, {'win_gitrepos': {}}):
                mock = MagicMock(return_value=True)
                with patch.object(salt.output, 'display_output', mock):
                    self.assertDictEqual(win_repo.update_git_repos(), {})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinRepoTestCase, needs_daemon=False)
