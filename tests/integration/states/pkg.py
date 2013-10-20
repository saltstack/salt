'''
tests for pkg state
'''

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import (
    destructiveTest,
    ensure_in_syspath,
    requires_system_grains,
    requires_salt_modules
)
ensure_in_syspath('../../')

# Import python libs
import os
import time

# Import salt libs
import integration
import salt.utils

_PKG_TARGETS = {
    'Arch': ['python2-django', 'finch'],
    'Debian': ['python-plist', 'finch'],
    'RedHat': ['python-meh', 'finch'],
    'FreeBSD': ['aalib', 'pth'],
    'Suse': ['aalib', 'finch']
}

_PKG_TARGETS_32 = {
    'Debian': '',
    'RedHat': 'zlib.i686'
}


def _wait_for_pkgdb_lock():
    '''
    Package tests tend to fail on Arch Linux due to pkgdb lockfile being
    present. This will wait up to 60 seconds before bailing.
    '''
    for idx in xrange(12):
        if not os.path.isfile('/var/lib/pacman/db.lck'):
            return
        time.sleep(5)
    raise Exception('Package database locked after 60 seconds, bailing out')


@requires_salt_modules('pkg.version', 'pkg.latest_version')
class PkgTest(integration.ModuleCase,
              integration.SaltReturnAssertsMixIn):
    '''
    pkg.installed state tests
    '''
    @destructiveTest
    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_001_installed(self, grains=None):
        '''
        This is a destructive test as it installs and then removes a package
        '''
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

        ret = self.run_state('pkg.installed', name=target)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('pkg.removed', name=target)
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_002_installed_with_version(self, grains=None):
        '''
        This is a destructive test as it installs and then removes a package
        '''
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
            _wait_for_pkgdb_unlock()

        target = pkg_targets[0]
        version = self.run_function('pkg.latest_version', [target])

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so this package
        # needs to not be installed before we run the states below
        self.assertTrue(version)

        ret = self.run_state('pkg.installed', name=target, version=version)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('pkg.removed', name=target)
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_003_installed_multipkg(self, grains=None):
        '''
        This is a destructive test as it installs and then removes two packages
        '''
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

        ret = self.run_state('pkg.installed', name=None, pkgs=pkg_targets)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('pkg.removed', name=None, pkgs=pkg_targets)
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_004_installed_multipkg_with_version(self, grains=None):
        '''
        This is a destructive test as it installs and then removes two packages
        '''
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
            _wait_for_pkgdb_unlock()

        version = self.run_function('pkg.latest_version', [pkg_targets[0]])

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so these
        # packages need to not be installed before we run the states below
        self.assertTrue(version)

        pkgs = [{pkg_targets[0]: version}, pkg_targets[1]]

        ret = self.run_state('pkg.installed', name=None, pkgs=pkgs)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('pkg.removed', name=None, pkgs=pkg_targets)
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_005_installed_32bit(self, grains=None):
        '''
        This is a destructive test as it installs and then removes a package
        '''
        os_family = grains.get('os_family', '')
        target = _PKG_TARGETS_32.get(os_family, '')

        # _PKG_TARGETS_32 is only populated for the OS families for which Salt
        # has to munge package names for 32-bit-on-x86_64 (Currently only
        # Debian and Redhat). Don't actually perform this test on other
        # platforms.
        if target:
            version = self.run_function('pkg.version', [target])

            # If this assert fails, we need to find a new target. This test
            # needs to be able to test successful installation of packages, so
            # the target needs to not be installed before we run the states
            # below
            self.assertFalse(version)

            ret = self.run_state('pkg.installed', name=target)
            self.assertSaltTrueReturn(ret)
            ret = self.run_state('pkg.removed', name=target)
            self.assertSaltTrueReturn(ret)

    @destructiveTest
    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_006_installed_32bit_with_version(self, grains=None):
        '''
        This is a destructive test as it installs and then removes a package
        '''
        os_family = grains.get('os_family', '')
        target = _PKG_TARGETS_32.get(os_family, '')

        # _PKG_TARGETS_32 is only populated for the OS families for which Salt
        # has to munge package names for 32-bit-on-x86_64 (Currently only
        # Debian and Redhat). Don't actually perform this test on other
        # platforms.
        if target:
            if os_family == 'Arch':
                _wait_for_pkgdb_unlock()

            version = self.run_function('pkg.latest_version', [target])

            # If this assert fails, we need to find a new target. This test
            # needs to be able to test successful installation of the package, so
            # the target needs to not be installed before we run the states
            # below
            self.assertTrue(version)

            ret = self.run_state('pkg.installed', name=target, version=version)
            self.assertSaltTrueReturn(ret)
            ret = self.run_state('pkg.removed', name=target)
            self.assertSaltTrueReturn(ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PkgTest)
