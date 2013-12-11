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
                  'gitfs_root': os.path.join(integration.TMP, 'gitfs_root'),
                  'fileserver_backend': 'gitfs',
                  }

GITFS_AVAILABLE = None
try:
    import git
    GITFS_AVAILABLE = True
except ImportError:
    pass

if not gitfs.__virtual__():
    GITFS_AVAILABLE = False


@skipIf(not GITFS_AVAILABLE, "GitFS could not be loaded. Skipping GitFS tests!")
class GitFSTest(integration.ModuleCase):
    def setUp(self):
        '''
        We don't want to check in another .git dir into GH because that just gets messy.
        Instead, we'll create a temporary repo on the fly for the tests to examine.
        :return:
        '''
        integration_base_files = os.path.join(integration.FILES, 'file', 'base')
        tmp_repo_dir = os.path.join(integration.TMP, 'gitfs_root')
        tmp_repo_git = os.path.join(tmp_repo_dir, '.git')

        # Create the dir if it doesn't already exist
        os.mkdirs(tmp_repo_git)

        git.Repo.create(tmp_repo_git, bare=True)

        shutil.copytree(integration_base_files, tmp_repo_dir, symlinks=True)

        git_bin = git.Git(tmp_repo_git)
        git_bin.add(tmp_repo_dir)

    def test_fake(self):
        pass
