# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com`


    Tests to ensure that the file permissions are set correctly when
    importing from the git repo.
'''

# Import python libs
import os
import stat

# Import salt testing libs
from salttesting import TestCase

INTEGRATION_TEST_DIR = os.path.dirname(
    os.path.normpath(os.path.abspath(__file__))
)

CODE_DIR = os.path.dirname(os.path.dirname(INTEGRATION_TEST_DIR))

EXEMPT_FILES = ['setup.py',
                'runtests.py',
                'saltsh.py',
                'PKGBUILD-git',
                'Makefile',
                'PKGBUILD',
                'salt-minion',
                'build.py',
                'salt-syncic',
                'salt-master',
                'install.sh',
                'salt-minion',
                'salt-call',
                'salt-cp',
                'salt-ssh',
                'salt-key',
                'salt-cloud',
                'salt-run',
                'salt-syndic',
                'salt',
                'rules',
                'pre-applypatch.sample',
                'pre-commit.sample',
                'commit-msg.sample',
                'pre-push.sample',
                'update.sample',
                'pre-rebase.sample',
                'post-update.sample',
                'prepare-commit-msg.sample',
                'applypatch-msg.sample',
                'master.py']

EXEMPT_DIRS = ['tests', '.git', 'doc']


class GitPermTestCase(TestCase):
    def test_perms(self):
        suspect_files = []
        for root, dirs, files in os.walk(CODE_DIR, topdown=True):
            dirs[:] = [dir for dir in dirs if dir not in EXEMPT_DIRS]
            for fn_ in files:
                fn_path = os.path.join(root, fn_)
                fn_mode = stat.S_IMODE(os.stat(fn_path).st_mode)  # In octal! 420 == 0644
                if fn_mode != 420 and fn_ not in EXEMPT_FILES:
                    suspect_files.append(fn_)

        self.assertEqual(suspect_files, [], 'Found file(s) with incorrect permissions: {0}'.format(suspect_files))
