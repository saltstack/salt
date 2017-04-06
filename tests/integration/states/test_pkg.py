# -*- coding: utf-8 -*-

'''
tests for pkg state
'''
# Import python libs
from __future__ import absolute_import
import logging
import os
import time

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.unit import skipIf
from tests.support.helpers import (
    destructiveTest,
    requires_system_grains,
    requires_salt_modules,
    flaky
)

# Import salt libs
import salt.utils

# Import 3rd-party libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

log = logging.getLogger(__name__)

__testcontext__ = {}

_PKG_TARGETS = {
    'Arch': ['python2-django', 'libpng'],
    'Debian': ['python-plist', 'apg'],
    'RedHat': ['xz-devel', 'zsh-html'],
    'FreeBSD': ['aalib', 'pth'],
    'Suse': ['aalib', 'python-pssh'],
    'MacOS': ['libpng', 'jpeg'],
    'Windows': ['firefox', '7zip'],
}

_PKG_TARGETS_32 = {
    'CentOS': 'xz-devel.i686'
}

# Test packages with dot in pkg name
# (https://github.com/saltstack/salt/issues/8614)
_PKG_TARGETS_DOT = {
    'RedHat': {'5': 'python-migrate0.5',
               '6': 'tomcat6-el-2.1-api',
               '7': 'tomcat-el-2.2-api'}
}

# Test packages with epoch in version
# (https://github.com/saltstack/salt/issues/31619)
_PKG_TARGETS_EPOCH = {
    'RedHat': {'7': 'comps-extras'},
}

_WILDCARDS_SUPPORTED = ('Arch', 'Debian', 'RedHat')


def pkgmgr_avail(run_function, grains):
    '''
    Return True if the package manager is available for use
    '''
    def proc_fd_lsof(path):
        '''
        Return True if any entry in /proc/locks points to path.  Example data:

        .. code-block:: bash

            # cat /proc/locks
            1: FLOCK  ADVISORY  WRITE 596 00:0f:10703 0 EOF
            2: FLOCK  ADVISORY  WRITE 14590 00:0f:11282 0 EOF
            3: POSIX  ADVISORY  WRITE 653 00:0f:11422 0 EOF
        '''
        import glob
        # https://www.centos.org/docs/5/html/5.2/Deployment_Guide/s2-proc-locks.html
        locks = run_function('cmd.run', ['cat /proc/locks']).splitlines()
        for line in locks:
            fields = line.split()
            try:
                major, minor, inode = fields[5].split(':')
                inode = int(inode)
            except (IndexError, ValueError):
                return False

            for fd in glob.glob('/proc/*/fd'):
                fd_path = os.path.realpath(fd)
                # If the paths match and the inode is locked
                if fd_path == path and os.stat(fd_path).st_ino == inode:
                    return True

        return False

    def get_lock(path):
        '''
        Return True if any locks are found for path
        '''
        # Try lsof if it's available
        if salt.utils.which('lsof'):
            lock = run_function('cmd.run', ['lsof {0}'.format(path)])
            return True if len(lock) else False

        # Try to find any locks on path from /proc/locks
        elif grains.get('kernel') == 'Linux':
            return proc_fd_lsof(path)

        return False

    if 'Debian' in grains.get('os_family', ''):
        for path in ['/var/lib/apt/lists/lock']:
            if get_lock(path):
                return False

    return True


def latest_version(run_function, *names):
    '''
    Helper function which ensures that we don't make any unnecessary calls to
    pkg.latest_version to figure out what version we need to install. This
    won't stop pkg.latest_version from being run in a pkg.latest state, but it
    will reduce the amount of times we check the latest version here in the
    test suite.
    '''
    key = 'latest_version'
    if key not in __testcontext__:
        __testcontext__[key] = {}
    targets = [x for x in names if x not in __testcontext__[key]]
    if targets:
        result = run_function('pkg.latest_version', targets, refresh=False)
        try:
            __testcontext__[key].update(result)
        except ValueError:
            # Only a single target, pkg.latest_version returned a string
            __testcontext__[key][targets[0]] = result

    ret = dict([(x, __testcontext__[key][x]) for x in names])
    if len(names) == 1:
        return ret[names[0]]
    return ret


@flaky
@destructiveTest
@requires_salt_modules('pkg.version', 'pkg.latest_version')
class PkgTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    pkg.installed state tests
    '''
    def setUp(self):
        '''
        Ensure that we only refresh the first time we run a test
        '''
        super(PkgTest, self).setUp()
        if 'refresh' not in __testcontext__:
            self.run_function('pkg.refresh_db')
            __testcontext__['refresh'] = True

    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_001_installed(self, grains=None):
        '''
        This is a destructive test as it installs and then removes a package
        '''
        # Skip test if package manager not available
        if not pkgmgr_avail(self.run_function, self.run_function('grains.items')):
            self.skipTest('Package manager is not available')

        os_family = grains.get('os_family', '')
        pkg_targets = _PKG_TARGETS.get(os_family, [])

        # Make sure that we have targets that match the os_family. If this
        # fails then the _PKG_TARGETS dict above needs to have an entry added,
        # with two packages that are not installed before these tests are run
        self.assertTrue(pkg_targets)

        target = pkg_targets[0]
        version = self.run_function('pkg.version', [target])

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so this package
        # needs to not be installed before we run the states below
        self.assertFalse(version)

        ret = self.run_state('pkg.installed', name=target, refresh=False)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('pkg.removed', name=target)
        self.assertSaltTrueReturn(ret)

    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_002_installed_with_version(self, grains=None):
        '''
        This is a destructive test as it installs and then removes a package
        '''
        # Skip test if package manager not available
        if not pkgmgr_avail(self.run_function, self.run_function('grains.items')):
            self.skipTest('Package manager is not available')

        os_family = grains.get('os_family', '')
        pkg_targets = _PKG_TARGETS.get(os_family, [])

        # Don't perform this test on FreeBSD since version specification is not
        # supported.
        if os_family == 'FreeBSD':
            return

        # Make sure that we have targets that match the os_family. If this
        # fails then the _PKG_TARGETS dict above needs to have an entry added,
        # with two packages that are not installed before these tests are run
        self.assertTrue(pkg_targets)

        if os_family == 'Arch':
            for idx in range(13):
                if idx == 12:
                    raise Exception('Package database locked after 60 seconds, '
                                    'bailing out')
                if not os.path.isfile('/var/lib/pacman/db.lck'):
                    break
                time.sleep(5)

        target = pkg_targets[0]
        version = latest_version(self.run_function, target)

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so this package
        # needs to not be installed before we run the states below
        self.assertTrue(version)

        ret = self.run_state('pkg.installed',
                             name=target,
                             version=version,
                             refresh=False)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('pkg.removed', name=target)
        self.assertSaltTrueReturn(ret)

    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_003_installed_multipkg(self, grains=None):
        '''
        This is a destructive test as it installs and then removes two packages
        '''
        # Skip test if package manager not available
        if not pkgmgr_avail(self.run_function, self.run_function('grains.items')):
            self.skipTest('Package manager is not available')

        os_family = grains.get('os_family', '')
        pkg_targets = _PKG_TARGETS.get(os_family, [])

        # Make sure that we have targets that match the os_family. If this
        # fails then the _PKG_TARGETS dict above needs to have an entry added,
        # with two packages that are not installed before these tests are run
        self.assertTrue(pkg_targets)
        version = self.run_function('pkg.version', pkg_targets)

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so these
        # packages need to not be installed before we run the states below
        self.assertFalse(any(version.values()))

        ret = self.run_state('pkg.installed',
                             name=None,
                             pkgs=pkg_targets,
                             refresh=False)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('pkg.removed', name=None, pkgs=pkg_targets)
        self.assertSaltTrueReturn(ret)

    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_004_installed_multipkg_with_version(self, grains=None):
        '''
        This is a destructive test as it installs and then removes two packages
        '''
        # Skip test if package manager not available
        if not pkgmgr_avail(self.run_function, self.run_function('grains.items')):
            self.skipTest('Package manager is not available')

        os_family = grains.get('os_family', '')
        pkg_targets = _PKG_TARGETS.get(os_family, [])

        # Don't perform this test on FreeBSD since version specification is not
        # supported.
        if os_family == 'FreeBSD':
            return

        # Make sure that we have targets that match the os_family. If this
        # fails then the _PKG_TARGETS dict above needs to have an entry added,
        # with two packages that are not installed before these tests are run
        self.assertTrue(bool(pkg_targets))

        if os_family == 'Arch':
            for idx in range(13):
                if idx == 12:
                    raise Exception('Package database locked after 60 seconds, '
                                    'bailing out')
                if not os.path.isfile('/var/lib/pacman/db.lck'):
                    break
                time.sleep(5)

        version = latest_version(self.run_function, pkg_targets[0])

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so these
        # packages need to not be installed before we run the states below
        self.assertTrue(bool(version))

        pkgs = [{pkg_targets[0]: version}, pkg_targets[1]]

        ret = self.run_state('pkg.installed',
                             name=None,
                             pkgs=pkgs,
                             refresh=False)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('pkg.removed', name=None, pkgs=pkg_targets)
        self.assertSaltTrueReturn(ret)

    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_005_installed_32bit(self, grains=None):
        '''
        This is a destructive test as it installs and then removes a package
        '''
        # Skip test if package manager not available
        if not pkgmgr_avail(self.run_function, self.run_function('grains.items')):
            self.skipTest('Package manager is not available')

        os_name = grains.get('os', '')
        target = _PKG_TARGETS_32.get(os_name, '')

        # _PKG_TARGETS_32 is only populated for platforms for which Salt has to
        # munge package names for 32-bit-on-x86_64 (Currently only Ubuntu and
        # RHEL-based). Don't actually perform this test on other platforms.
        if target:
            # CentOS 5 has .i386 arch designation for 32-bit pkgs
            if os_name == 'CentOS' \
                    and grains['osrelease'].startswith('5.'):
                target = target.replace('.i686', '.i386')

            version = self.run_function('pkg.version', [target])

            # If this assert fails, we need to find a new target. This test
            # needs to be able to test successful installation of packages, so
            # the target needs to not be installed before we run the states
            # below
            self.assertFalse(bool(version))

            ret = self.run_state('pkg.installed',
                                 name=target,
                                 refresh=False)
            self.assertSaltTrueReturn(ret)
            ret = self.run_state('pkg.removed', name=target)
            self.assertSaltTrueReturn(ret)

    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_006_installed_32bit_with_version(self, grains=None):
        '''
        This is a destructive test as it installs and then removes a package
        '''
        # Skip test if package manager not available
        if not pkgmgr_avail(self.run_function, self.run_function('grains.items')):
            self.skipTest('Package manager is not available')

        os_name = grains.get('os', '')
        target = _PKG_TARGETS_32.get(os_name, '')

        # _PKG_TARGETS_32 is only populated for platforms for which Salt has to
        # munge package names for 32-bit-on-x86_64 (Currently only Ubuntu and
        # RHEL-based). Don't actually perform this test on other platforms.
        if target:
            if grains.get('os_family', '') == 'Arch':
                for idx in range(13):
                    if idx == 12:
                        raise Exception('Package database locked after 60 seconds, '
                                        'bailing out')
                    if not os.path.isfile('/var/lib/pacman/db.lck'):
                        break
                    time.sleep(5)

            # CentOS 5 has .i386 arch designation for 32-bit pkgs
            if os_name == 'CentOS' \
                    and grains['osrelease'].startswith('5.'):
                target = target.replace('.i686', '.i386')

            version = latest_version(self.run_function, target)

            # If this assert fails, we need to find a new target. This test
            # needs to be able to test successful installation of the package, so
            # the target needs to not be installed before we run the states
            # below
            self.assertTrue(bool(version))

            ret = self.run_state('pkg.installed',
                                 name=target,
                                 version=version,
                                 refresh=False)
            self.assertSaltTrueReturn(ret)
            ret = self.run_state('pkg.removed', name=target)
            self.assertSaltTrueReturn(ret)

    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_007_with_dot_in_pkgname(self, grains=None):
        '''
        This tests for the regression found in the following issue:
        https://github.com/saltstack/salt/issues/8614

        This is a destructive test as it installs a package
        '''
        # Skip test if package manager not available
        if not pkgmgr_avail(self.run_function, self.run_function('grains.items')):
            self.skipTest('Package manager is not available')

        os_family = grains.get('os_family', '')
        os_version = grains.get('osmajorrelease')
        target = _PKG_TARGETS_DOT.get(os_family, {}).get(os_version)
        if target:
            version = latest_version(self.run_function, target)
            # If this assert fails, we need to find a new target. This test
            # needs to be able to test successful installation of the package, so
            # the target needs to not be installed before we run the
            # pkg.installed state below
            self.assertTrue(bool(version))
            ret = self.run_state('pkg.installed', name=target, refresh=False)
            self.assertSaltTrueReturn(ret)
            ret = self.run_state('pkg.removed', name=target)
            self.assertSaltTrueReturn(ret)

    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_008_epoch_in_version(self, grains=None):
        '''
        This tests for the regression found in the following issue:
        https://github.com/saltstack/salt/issues/8614

        This is a destructive test as it installs a package
        '''
        # Skip test if package manager not available
        if not pkgmgr_avail(self.run_function, self.run_function('grains.items')):
            self.skipTest('Package manager is not available')

        os_family = grains.get('os_family', '')
        os_version = grains.get('osmajorrelease')
        target = _PKG_TARGETS_EPOCH.get(os_family, {}).get(os_version)
        if target:
            version = latest_version(self.run_function, target)
            # If this assert fails, we need to find a new target. This test
            # needs to be able to test successful installation of the package, so
            # the target needs to not be installed before we run the
            # pkg.installed state below
            self.assertTrue(bool(version))
            ret = self.run_state('pkg.installed',
                                 name=target,
                                 version=version,
                                 refresh=False)
            self.assertSaltTrueReturn(ret)
            ret = self.run_state('pkg.removed', name=target)
            self.assertSaltTrueReturn(ret)

    @skipIf(salt.utils.is_windows(), 'minion is windows')
    def test_pkg_009_latest_with_epoch(self):
        '''
        This tests for the following issue:
        https://github.com/saltstack/salt/issues/31014

        This is a destructive test as it installs a package
        '''
        # Skip test if package manager not available
        if not pkgmgr_avail(self.run_function, self.run_function('grains.items')):
            self.skipTest('Package manager is not available')

        ret = self.run_state('pkg.installed',
                             name='bash-completion',
                             refresh=False)
        self.assertSaltTrueReturn(ret)

    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_salt_modules('pkg.info_installed')
    def test_pkg_010_latest_with_epoch_and_info_installed(self):
        '''
        Need to check to ensure the package has been
        installed after the pkg_latest_epoch sls
        file has been run. This needs to be broken up into
        a seperate method so I can add the requires_salt_modules
        decorator to only the pkg.info_installed command.
        '''
        # Skip test if package manager not available
        if not pkgmgr_avail(self.run_function, self.run_function('grains.items')):
            self.skipTest('Package manager is not available')

        package = 'bash-completion'
        pkgquery = 'version'

        ret = self.run_function('pkg.info_installed', [package])
        self.assertTrue(pkgquery in str(ret))

    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_011_latest(self, grains=None):
        '''
        This tests pkg.latest with a package that has no epoch (or a zero
        epoch).
        '''
        # Skip test if package manager not available
        if not pkgmgr_avail(self.run_function, self.run_function('grains.items')):
            self.skipTest('Package manager is not available')

        os_family = grains.get('os_family', '')
        pkg_targets = _PKG_TARGETS.get(os_family, [])

        # Make sure that we have targets that match the os_family. If this
        # fails then the _PKG_TARGETS dict above needs to have an entry added,
        # with two packages that are not installed before these tests are run
        self.assertTrue(pkg_targets)

        target = pkg_targets[0]
        version = latest_version(self.run_function, target)

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so this package
        # needs to not be installed before we run the states below
        self.assertTrue(version)

        ret = self.run_state('pkg.latest', name=target, refresh=False)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('pkg.removed', name=target)
        self.assertSaltTrueReturn(ret)

    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_012_latest_only_upgrade(self, grains=None):
        '''
        WARNING: This test will pick a package with an available upgrade (if
        there is one) and upgrade it to the latest version.
        '''
        os_family = grains.get('os_family', '')
        if os_family != 'Debian':
            self.skipTest('Minion is not Debian/Ubuntu')

        # Skip test if package manager not available
        if not pkgmgr_avail(self.run_function, self.run_function('grains.items')):
            self.skipTest('Package manager is not available')

        pkg_targets = _PKG_TARGETS.get(os_family, [])

        # Make sure that we have targets that match the os_family. If this
        # fails then the _PKG_TARGETS dict above needs to have an entry added,
        # with two packages that are not installed before these tests are run
        self.assertTrue(pkg_targets)

        target = pkg_targets[0]
        version = latest_version(self.run_function, target)

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test that the state fails when you try to run the state
        # with only_upgrade=True on a package which is not already installed,
        # so the targeted package needs to not be installed before we run the
        # state below.
        self.assertTrue(version)

        ret = self.run_state('pkg.latest', name=target, refresh=False,
                             only_upgrade=True)
        self.assertSaltFalseReturn(ret)

        # Now look for updates and try to run the state on a package which is
        # already up-to-date.
        installed_pkgs = self.run_function('pkg.list_pkgs')
        updates = self.run_function('pkg.list_upgrades', refresh=False)

        for pkgname in updates:
            if pkgname in installed_pkgs:
                target = pkgname
                break
        else:
            target = ''
            log.warning(
                'No available upgrades to installed packages, skipping '
                'only_upgrade=True test with already-installed package. For '
                'best results run this test on a machine with upgrades '
                'available.'
            )

        if target:
            ret = self.run_state('pkg.latest', name=target, refresh=False,
                                 only_upgrade=True)
            self.assertSaltTrueReturn(ret)
            new_version = self.run_function('pkg.version', [target])
            self.assertEqual(new_version, updates[target])
            ret = self.run_state('pkg.latest', name=target, refresh=False,
                                 only_upgrade=True)
            self.assertEqual(
                ret['pkg_|-{0}_|-{0}_|-latest'.format(target)]['comment'],
                'Package {0} is already up-to-date'.format(target)
            )

    @requires_system_grains
    def test_pkg_013_installed_with_wildcard_version(self, grains=None):
        '''
        This is a destructive test as it installs and then removes a package
        '''
        # Skip test if package manager not available
        if not pkgmgr_avail(self.run_function, self.run_function('grains.items')):
            self.skipTest('Package manager is not available')

        os_family = grains.get('os_family', '')

        if os_family not in _WILDCARDS_SUPPORTED:
            self.skipTest(
                'Wildcards only supported on {0}'.format(
                    ', '.join(_WILDCARDS_SUPPORTED)
                )
            )

        pkg_targets = _PKG_TARGETS.get(os_family, [])

        # Make sure that we have targets that match the os_family. If this
        # fails then the _PKG_TARGETS dict above needs to have an entry added,
        # with two packages that are not installed before these tests are run
        self.assertTrue(pkg_targets)

        target = pkg_targets[0]
        version = self.run_function('pkg.version', [target])

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so this package
        # needs to not be installed before we run the states below
        self.assertFalse(version)

        ret = self.run_state(
            'pkg.installed',
            name=target,
            version='*',
            refresh=False,
        )
        self.assertSaltTrueReturn(ret)

        # Repeat state, should pass
        ret = self.run_state(
            'pkg.installed',
            name=target,
            version='*',
            refresh=False,
        )

        expected_comment = (
            'All specified packages are already installed and are at the '
            'desired version'
        )
        self.assertSaltTrueReturn(ret)
        self.assertEqual(ret[next(iter(ret))]['comment'], expected_comment)

        # Repeat one more time with unavailable version, test should fail
        ret = self.run_state(
            'pkg.installed',
            name=target,
            version='93413*',
            refresh=False,
        )
        self.assertSaltFalseReturn(ret)

        # Clean up
        ret = self.run_state('pkg.removed', name=target)
        self.assertSaltTrueReturn(ret)

    @requires_salt_modules('pkg.group_install')
    @requires_system_grains
    def test_group_installed_handle_missing_package_group(self, grains=None):  # pylint: disable=unused-argument
        '''
        Tests that a CommandExecutionError is caught and the state returns False when
        the package group is missing. Before this fix, the state would stacktrace.
        See Issue #35819 for bug report.
        '''
        # Skip test if package manager not available
        if not pkgmgr_avail(self.run_function, self.run_function('grains.items')):
            self.skipTest('Package manager is not available')

        # Group install not available message
        grp_install_msg = 'pkg.group_install not available for this platform'

        # Run the pkg.group_installed state with a fake package group
        ret = self.run_state('pkg.group_installed', name='handle_missing_pkg_group',
                             skip=['foo-bar-baz'])
        ret_comment = ret['pkg_|-handle_missing_pkg_group_|-handle_missing_pkg_group_|-group_installed']['comment']

        # Not all package managers support group_installed. Skip this test if not supported.
        if ret_comment == grp_install_msg:
            self.skipTest(grp_install_msg)

        # Test state should return False and should have the right comment
        self.assertSaltFalseReturn(ret)
        self.assertEqual(ret_comment, 'An error was encountered while installing/updating group '
                                      '\'handle_missing_pkg_group\': Group \'handle_missing_pkg_group\' '
                                      'not found.')
