# -*- coding: utf-8 -*-

'''
tests for pkg state
'''
# Import python libs
from __future__ import absolute_import
import os
import time

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import (
    destructiveTest,
    ensure_in_syspath,
    requires_system_grains,
    requires_salt_modules
)
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils

# Import 3rd-party libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

_PKG_TARGETS = {
    'Arch': ['python2-django', 'libpng'],
    'Debian': ['python-plist', 'apg'],
    'RedHat': ['xz-devel', 'zsh-html'],
    'FreeBSD': ['aalib', 'pth'],
    'SUSE': ['aalib', 'python-pssh'],
    'MacOS': ['libpng', 'jpeg'],
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


@destructiveTest
@requires_salt_modules('pkg.version', 'pkg.latest_version')
class PkgTest(integration.ModuleCase,
              integration.SaltReturnAssertsMixIn):
    '''
    pkg.installed state tests
    '''
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
            for idx in range(13):
                if idx == 12:
                    raise Exception('Package database locked after 60 seconds, '
                                    'bailing out')
                if not os.path.isfile('/var/lib/pacman/db.lck'):
                    break
                time.sleep(5)

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
#        self.assertFalse(any(version.values()))

        ret = self.run_state('pkg.installed', name=None, pkgs=pkg_targets)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('pkg.removed', name=None, pkgs=pkg_targets)
        self.assertSaltTrueReturn(ret)

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
        self.assertTrue(bool(pkg_targets))

        if os_family == 'Arch':
            for idx in range(13):
                if idx == 12:
                    raise Exception('Package database locked after 60 seconds, '
                                    'bailing out')
                if not os.path.isfile('/var/lib/pacman/db.lck'):
                    break
                time.sleep(5)

        version = self.run_function('pkg.latest_version', [pkg_targets[0]])

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so these
        # packages need to not be installed before we run the states below
        self.assertTrue(bool(version))

        pkgs = [{pkg_targets[0]: version}, pkg_targets[1]]

        ret = self.run_state('pkg.installed', name=None, pkgs=pkgs)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('pkg.removed', name=None, pkgs=pkg_targets)
        self.assertSaltTrueReturn(ret)

    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_005_installed_32bit(self, grains=None):
        '''
        This is a destructive test as it installs and then removes a package
        '''
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

            ret = self.run_state('pkg.installed', name=target)
            self.assertSaltTrueReturn(ret)
            ret = self.run_state('pkg.removed', name=target)
            self.assertSaltTrueReturn(ret)

    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_006_installed_32bit_with_version(self, grains=None):
        '''
        This is a destructive test as it installs and then removes a package
        '''
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

            version = self.run_function('pkg.latest_version', [target])

            # If this assert fails, we need to find a new target. This test
            # needs to be able to test successful installation of the package, so
            # the target needs to not be installed before we run the states
            # below
            self.assertTrue(bool(version))

            ret = self.run_state('pkg.installed', name=target, version=version)
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
        os_family = grains.get('os_family', '')
        os_version = grains.get('osmajorrelease', [''])[0]
        target = _PKG_TARGETS_DOT.get(os_family, {}).get(os_version)
        if target:
            version = self.run_function('pkg.latest_version', [target])
            # If this assert fails, we need to find a new target. This test
            # needs to be able to test successful installation of the package, so
            # the target needs to not be installed before we run the
            # pkg.installed state below
            self.assertTrue(bool(version))
            ret = self.run_state('pkg.installed', name=target)
            self.assertSaltTrueReturn(ret)
            ret = self.run_state('pkg.removed', name=target)
            self.assertSaltTrueReturn(ret)

    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_with_epoch_in_version(self, grains=None):
        '''
        This tests for the regression found in the following issue:
        https://github.com/saltstack/salt/issues/8614

        This is a destructive test as it installs a package
        '''
        os_family = grains.get('os_family', '')
        os_version = grains.get('osmajorrelease', [''])[0]
        target = _PKG_TARGETS_EPOCH.get(os_family, {}).get(os_version)
        if target:
            version = self.run_function('pkg.latest_version', [target])
            # If this assert fails, we need to find a new target. This test
            # needs to be able to test successful installation of the package, so
            # the target needs to not be installed before we run the
            # pkg.installed state below
            self.assertTrue(bool(version))
            ret = self.run_state('pkg.installed', name=target, version=version)
            self.assertSaltTrueReturn(ret)
            ret = self.run_state('pkg.removed', name=target)
            self.assertSaltTrueReturn(ret)

    @destructiveTest
    @skipIf(salt.utils.is_windows(), 'minion is windows')
    def test_pkg_008_latest_with_epoch(self):
        '''
        This tests for the following issue:
        https://github.com/saltstack/salt/issues/31014

        This is a destructive test as it installs a package
        '''

        ret = self.run_function('state.sls', mods='pkg_latest_epoch')
        self.assertSaltTrueReturn(ret)

    @requires_salt_modules('pkg.info_installed')
    def test_pkg_009_latest_with_epoch_and_info_installed(self):
        '''
        Need to check to ensure the package has been
        installed after the pkg_latest_epoch sls
        file has been run. This needs to be broken up into
        a seperate method so I can add the requires_salt_modules
        decorator to only the pkg.info_installed command.
        '''

        package = 'bash-completion'
        pkgquery = 'version'

        ret = self.run_function('pkg.info_installed', [package])
        self.assertTrue(pkgquery in str(ret))

if __name__ == '__main__':
    from integration import run_tests
    run_tests(PkgTest)
