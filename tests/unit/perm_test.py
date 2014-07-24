# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com`


    Tests to ensure that the file permissions are set correctly when
    importing from the git repo.
'''

# Import python libs
import os
import stat
import pprint

# Import salt testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('..')

from integration import CODE_DIR

EXEMPT_DIRS = []
EXEMPT_FILES = [
    'debian/rules',
    'doc/.scripts/compile-translation-catalogs',
    'doc/.scripts/download-translation-catalog',
    'doc/.scripts/setup-transifex-config',
    'doc/.scripts/update-transifex-source-translations',
    'pkg/arch/Makefile',
    'pkg/arch/PKGBUILD',
    'pkg/arch/PKGBUILD-git',
    'pkg/arch/PKGBUILD-local',
    'pkg/arch/git/PKGBUILD',
    'pkg/rpm/build.py',
    'pkg/rpm/salt-master',
    'pkg/rpm/salt-minion',
    'pkg/rpm/salt-syndic',
    'pkg/shar/build_shar.sh',
    'pkg/smartos/esky/install.sh',
    'salt/cloud/deploy/bootstrap-salt.sh',
    'salt/templates/git/ssh-id-wrapper',
    'salt/templates/lxc/salt_tarball',
    'scripts/salt',
    'scripts/salt-call',
    'scripts/salt-cloud',
    'scripts/salt-cp',
    'scripts/salt-key',
    'scripts/salt-master',
    'scripts/salt-minion',
    'scripts/salt-run',
    'scripts/salt-ssh',
    'scripts/salt-syndic',
    'setup.py',
    'tests/integration/mockbin/su',
    'tests/runtests.py',
    'tests/saltsh.py',
]

IGNORE_PATHS = [
    '.git',
    '.wti',
    'build',
    'dist',
    'salt.egg-info',
    '.ropeproject',
]


@skipIf(True, 'Need to adjust perms')
class GitPermTestCase(TestCase):
    def test_perms(self):
        suspect_entries = []
        for root, dirnames, filenames in os.walk(CODE_DIR, topdown=True):
            for dirname in dirnames:
                entry = os.path.join(root, dirname)
                if entry in IGNORE_PATHS:
                    continue

                skip_entry = False
                for ignore_path in IGNORE_PATHS:
                    if entry.startswith(ignore_path):
                        skip_entry = True
                        break

                if skip_entry:
                    continue

                fn_mode = stat.S_IMODE(os.stat(entry).st_mode)
                if fn_mode != 493 and entry not in EXEMPT_DIRS:  # In octal! 493 == 0755
                    suspect_entries.append(entry)

            for filename in filenames:
                entry = os.path.join(root, filename)
                if entry in IGNORE_PATHS:
                    continue

                skip_entry = False
                for ignore_path in IGNORE_PATHS:
                    if entry.startswith(ignore_path):
                        skip_entry = True
                        break

                if skip_entry:
                    continue

                fn_mode = stat.S_IMODE(os.stat(entry).st_mode)
                if fn_mode != 420 and entry not in EXEMPT_FILES:  # In octal! 420 == 0644
                    suspect_entries.append(entry)

        try:
            self.assertEqual(suspect_entries, [])
        except AssertionError:
            self.fail(
                'Found file(s) with incorrect permissions:\n{0}'.format(
                    pprint.pformat(sorted(suspect_entries))
                )
            )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GitPermTestCase, needs_daemon=False)
