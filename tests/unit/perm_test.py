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
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('..')

from integration import CODE_DIR

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
                'master.py',
                'ssh-id-wrapper',
                'build_shar.sh']

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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GitPermTestCase, needs_daemon=False)
