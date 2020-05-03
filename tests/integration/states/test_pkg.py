# -*- coding: utf-8 -*-

"""
tests for pkg state
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import time

import pytest
import salt.utils.files
import salt.utils.path
import salt.utils.pkg.rpm
import salt.utils.platform
from salt.ext import six
from salt.ext.six.moves import range
from tests.support.case import ModuleCase
from tests.support.helpers import (
    destructiveTest,
    not_runs_on,
    requires_salt_modules,
    requires_salt_states,
    requires_system_grains,
    runs_on,
)
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.unit import skipIf

log = logging.getLogger(__name__)

__testcontext__ = {}

_PKG_TARGETS = {
    'Arch': ['sl', 'libpng'],
    'Debian': ['python-plist', 'apg'],
    'RedHat': ['units', 'zsh-html'],
    'FreeBSD': ['aalib', 'pth'],
    'Suse': ['aalib', 'htop'],
    'MacOS': ['libpng', 'jpeg'],
    'Windows': ['putty', '7zip'],
}

_PKG_CAP_TARGETS = {
    'Suse': [('perl(ZNC)', 'znc-perl')],
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
        if salt.utils.path.which('lsof'):
            lock = run_function('cmd.run', ['lsof {0}'.format(path)])
            return True if lock else False

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

@destructiveTest
@pytest.mark.windows_whitelisted
class PkgTest(ModuleCase, SaltReturnAssertsMixin):
    _PKG_EPOCH_TARGETS = []
    _PKG_32_TARGETS = []
    _PKG_CAP_TARGETS = []
    _PKG_DOT_TARGETS = []
    _WILDCARDS_SUPPORTED = False
    _VERSION_SPEC_SUPPORTED = True

    @classmethod
    @requires_system_grains
    def test_pkg_001_installed(self, grains):
        '''
        This is a destructive test as it installs and then removes a package
        '''
        # Skip test if package manager not available
        if not pkgmgr_avail(self.run_function, self.run_function('grains.items')):
            self.skipTest('Package manager is not available')

        os_family = grains.get('os_family', '')
        pkg_targets = _PKG_TARGETS.get(os_family, [])

        ret = dict([(x, self.ctx[key].get(x, "")) for x in names])
        if len(names) == 1:
            return ret[names[0]]
        return ret

    @requires_system_grains
    def setUp(self, grains=None):  # pylint:disable=W0221
        super(PkgTest, self).setUp()
        if "refresh" not in self.ctx:
            self.run_function("pkg.refresh_db")
            self.ctx["refresh"] = True

        # If this is Arch Linux, check if pacman is in use by another process
        if grains["os_family"] == "Arch":
            for _ in range(12):
                if not os.path.isfile("/var/lib/pacman/db.lck"):
                    break
                else:
                    time.sleep(5)
            else:
                raise Exception("Package database locked after 60 seconds, bailing out")

    @requires_salt_modules("pkg.version")
    @requires_salt_states("pkg.installed", "pkg.removed")
    @skipIf(True, "SLOWTEST skip")
    def test_pkg_001_installed(self):
        """
        This is a destructive test as it installs and then removes a package
        """
        target = self._PKG_TARGETS[0]
        version = self.run_function("pkg.version", [target])

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so this package
        # needs to not be installed before we run the states below
        self.assertFalse(version)

        ret = self.run_state("pkg.installed", name=target, refresh=False)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state("pkg.removed", name=target)
        self.assertSaltTrueReturn(ret)

    @requires_system_grains
    def test_pkg_002_installed_with_version(self, grains):
        '''
        This is a destructive test as it installs and then removes a package
        """
        if not self._VERSION_SPEC_SUPPORTED:
            self.skipTest("Version specification not supported")

        target = self._PKG_TARGETS[0]
        version = self.latest_version(target)

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so this package
        # needs to not be installed before we run the states below
        self.assertTrue(version)

        ret = self.run_state(
            "pkg.installed", name=target, version=version, refresh=False
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_state("pkg.removed", name=target)
        self.assertSaltTrueReturn(ret)

    @requires_system_grains
    def test_pkg_003_installed_multipkg(self, grains):
        '''
        This is a destructive test as it installs and then removes two packages
        """
        version = self.run_function("pkg.version", self._PKG_TARGETS)

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so these
        # packages need to not be installed before we run the states below
        self.assertFalse(any(version.values()))
        self.assertSaltTrueReturn(
            self.run_state("pkg.removed", name=None, pkgs=self._PKG_TARGETS)
        )

        try:
            ret = self.run_state(
                "pkg.installed", name=None, pkgs=self._PKG_TARGETS, refresh=False
            )
            self.assertSaltTrueReturn(ret)
        finally:
            ret = self.run_state("pkg.removed", name=None, pkgs=self._PKG_TARGETS)
            self.assertSaltTrueReturn(ret)

    @requires_system_grains
    def test_pkg_004_installed_multipkg_with_version(self, grains):
        '''
        This is a destructive test as it installs and then removes two packages
        """
        if not self._VERSION_SPEC_SUPPORTED:
            self.skipTest("Version specification not supported")

        version = self.latest_version(self._PKG_TARGETS[0])

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so these
        # packages need to not be installed before we run the states below
        self.assertTrue(bool(version))

        pkgs = [{self._PKG_TARGETS[0]: version}, self._PKG_TARGETS[1]]

        try:
            ret = self.run_state("pkg.installed", name=None, pkgs=pkgs, refresh=False)
            self.assertSaltTrueReturn(ret)
        finally:
            ret = self.run_state("pkg.removed", name=None, pkgs=self._PKG_TARGETS)
            self.assertSaltTrueReturn(ret)

    @requires_system_grains
    def test_pkg_005_installed_32bit(self, grains):
        '''
        This is a destructive test as it installs and then removes a package
        """
        if not self._PKG_32_TARGETS:
            self.skipTest("No 32 bit packages have been specified for testing")

        target = self._PKG_32_TARGETS[0]

        # _PKG_TARGETS_32 is only populated for platforms for which Salt has to
        # munge package names for 32-bit-on-x86_64 (Currently only Ubuntu and
        # RHEL-based). Don't actually perform this test on other platforms.
        version = self.run_function("pkg.version", [target])

    @requires_system_grains
    def test_pkg_006_installed_32bit_with_version(self, grains):
        '''
        This is a destructive test as it installs and then removes a package
        """
        if not self._PKG_32_TARGETS:
            self.skipTest("No 32 bit packages have been specified for testing")

        target = self._PKG_32_TARGETS[0]

        # _PKG_TARGETS_32 is only populated for platforms for which Salt has to
        # munge package names for 32-bit-on-x86_64 (Currently only Ubuntu and
        # RHEL-based). Don't actually perform this test on other platforms.
        version = self.latest_version(target)

        # If this assert fails, we need to find a new target. This test
        # needs to be able to test successful installation of the package, so
        # the target needs to not be installed before we run the states
        # below
        self.assertTrue(version)

        ret = self.run_state(
            "pkg.installed", name=target, version=version, refresh=False
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_state("pkg.removed", name=target)
        self.assertSaltTrueReturn(ret)

    @requires_system_grains
    def test_pkg_007_with_dot_in_pkgname(self, grains):
        '''
        This tests for the regression found in the following issue:
        https://github.com/saltstack/salt/issues/8614

        This is a destructive test as it installs a package
        """
        if not self._PKG_DOT_TARGETS:
            self.skipTest('No packages with "." in their name have been specified',)

        target = self._PKG_DOT_TARGETS[0]

        version = self.latest_version(target)
        # If this assert fails, we need to find a new target. This test
        # needs to be able to test successful installation of the package, so
        # the target needs to not be installed before we run the
        # pkg.installed state below
        self.assertTrue(bool(version))
        ret = self.run_state("pkg.installed", name=target, refresh=False)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state("pkg.removed", name=target)
        self.assertSaltTrueReturn(ret)

    @requires_system_grains
    def test_pkg_008_epoch_in_version(self, grains):
        '''
        This tests for the regression found in the following issue:
        https://github.com/saltstack/salt/issues/8614

        This is a destructive test as it installs a package
        """
        if not self._PKG_EPOCH_TARGETS:
            self.skipTest('No targets have been configured with "epoch" in the version')

        target = self._PKG_EPOCH_TARGETS[0]

        version = self.latest_version(target)
        # If this assert fails, we need to find a new target. This test
        # needs to be able to test successful installation of the package, so
        # the target needs to not be installed before we run the
        # pkg.installed state below
        self.assertTrue(version)
        ret = self.run_state(
            "pkg.installed", name=target, version=version, refresh=False
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_state("pkg.removed", name=target)
        self.assertSaltTrueReturn(ret)

    @requires_salt_modules("pkg.version", "pkg.info_installed")
    @requires_salt_states("pkg.installed", "pkg.removed")
    @runs_on(kernel="linux")
    @not_runs_on(os="Amazon")
    @skipIf(True, "SLOWTEST skip")
    def test_pkg_009_latest_with_epoch(self):
        """
        This tests for the following issue:
        https://github.com/saltstack/salt/issues/31014

        This is a destructive test as it installs a package
        """
        package = "bash-completion"
        pkgquery = "version"

        ret = self.run_state("pkg.installed", name=package, refresh=False)
        self.assertSaltTrueReturn(ret)

        ret = self.run_function("pkg.info_installed", [package])
        self.assertTrue(pkgquery in six.text_type(ret))

    @requires_system_grains
    def test_pkg_011_latest(self, grains):
        '''
        This tests pkg.latest with a package that has no epoch (or a zero
        epoch).
        """
        target = self._PKG_TARGETS[0]
        version = self.latest_version(target)

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so this package
        # needs to not be installed before we run the states below
        self.assertTrue(version)

        ret = self.run_state("pkg.latest", name=target, refresh=False)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state("pkg.removed", name=target)
        self.assertSaltTrueReturn(ret)

    @requires_system_grains
    def test_pkg_012_latest_only_upgrade(self, grains):
        '''
        WARNING: This test will pick a package with an available upgrade (if
        there is one) and upgrade it to the latest version.
        """
        target = self._PKG_TARGETS[0]

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test that the state fails when you try to run the state
        # with only_upgrade=True on a package which is not already installed,
        # so the targeted package needs to not be installed before we run the
        # state below.
        version = self.latest_version(target)
        self.assertTrue(version)

        ret = self.run_state(
            "pkg.latest", name=target, refresh=False, only_upgrade=True
        )
        self.assertSaltFalseReturn(ret)

        # Now look for updates and try to run the state on a package which is already up-to-date.
        installed_pkgs = self.run_function("pkg.list_pkgs")
        updates = self.run_function("pkg.list_upgrades", refresh=False)

        for pkgname in updates:
            if pkgname in installed_pkgs:
                target = pkgname
                break
        else:
            target = ""
            log.warning(
                "No available upgrades to installed packages, skipping "
                "only_upgrade=True test with already-installed package. For "
                "best results run this test on a machine with upgrades "
                "available."
            )

        if target:
            ret = self.run_state(
                "pkg.latest", name=target, refresh=False, only_upgrade=True
            )
            self.assertSaltTrueReturn(ret)
            new_version = self.run_function("pkg.version", [target])
            self.assertEqual(new_version, updates[target])
            ret = self.run_state(
                "pkg.latest", name=target, refresh=False, only_upgrade=True
            )
            self.assertEqual(
                ret["pkg_|-{0}_|-{0}_|-latest".format(target)]["comment"],
                "Package {0} is already up-to-date".format(target),
            )

    @requires_system_grains
    def test_pkg_013_installed_with_wildcard_version(self, grains):
        '''
        This is a destructive test as it installs and then removes a package
        """
        if not self._WILDCARDS_SUPPORTED:
            self.skipTest("Wildcards in pkg.install are not supported")

        target = self._PKG_TARGETS[0]
        version = self.run_function("pkg.version", [target])

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so this package
        # needs to not be installed before we run the states below
        self.assertFalse(version)

        ret = self.run_state("pkg.installed", name=target, version="*", refresh=False,)
        self.assertSaltTrueReturn(ret)

        # Repeat state, should pass
        ret = self.run_state("pkg.installed", name=target, version="*", refresh=False,)

        expected_comment = (
            "All specified packages are already installed and are at the "
            "desired version"
        )
        self.assertSaltTrueReturn(ret)
        self.assertEqual(ret[next(iter(ret))]["comment"], expected_comment)

        # Repeat one more time with unavailable version, test should fail
        ret = self.run_state(
            "pkg.installed", name=target, version="93413*", refresh=False,
        )
        self.assertSaltFalseReturn(ret)

        # Clean up
        ret = self.run_state("pkg.removed", name=target)
        self.assertSaltTrueReturn(ret)

    @requires_system_grains
    def test_pkg_014_installed_with_comparison_operator(self, grains):
        '''
        This is a destructive test as it installs and then removes a package
        """
        target = self._PKG_TARGETS[0]
        version = self.run_function("pkg.version", [target])

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so this package
        # needs to not be installed before we run the states below
        self.assertFalse(version)

        latest_version = self.run_function(
            "pkg.latest_version", [target], refresh=False
        )

        try:
            ret = self.run_state(
                "pkg.installed", name=target, version="<9999999", refresh=False,
            )
            self.assertSaltTrueReturn(ret)

            # The version that was installed should be the latest available
            version = self.run_function("pkg.version", [target])
            self.assertTrue(version, latest_version)
        finally:
            # Clean up
            ret = self.run_state("pkg.removed", name=target)
            self.assertSaltTrueReturn(ret)

    @requires_system_grains
    def test_pkg_014_installed_missing_release(self, grains):
        '''
        Tests that a version number missing the release portion still resolves
        as correctly installed. For example, version 2.0.2 instead of 2.0.2-1.el7
        """
        target = self._PKG_TARGETS[0]
        version = self.run_function("pkg.version", [target])

        # If this assert fails, we need to find new targets, this test needs to
        # be able to test successful installation of packages, so this package
        # needs to not be installed before we run the states below
        self.assertFalse(version)

        ret = self.run_state(
            "pkg.installed",
            name=target,
            version=salt.utils.pkg.rpm.version_to_evr(version)[1],
            refresh=False,
        )
        self.assertSaltTrueReturn(ret)

        # Clean up
        ret = self.run_state("pkg.removed", name=target)
        self.assertSaltTrueReturn(ret)

    @requires_salt_modules('pkg.group_install')
    def test_group_installed_handle_missing_package_group(self):  # pylint: disable=unused-argument
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

    @skipIf(salt.utils.platform.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_cap_001_installed(self, grains):
        '''
        This is a destructive test as it installs and then removes a package
        '''
        # Skip test if package manager not available
        if not pkgmgr_avail(self.run_function, self.run_function('grains.items')):
            self.skipTest('Package manager is not available')

        os_family = grains.get('os_family', '')
        pkg_cap_targets = _PKG_CAP_TARGETS.get(os_family, [])
        if not pkg_cap_targets:
            self.skipTest('Capability not provided')

        # Then we check that the package is now held
        ret = self.run_state("pkg.installed", name=target, hold=True, refresh=False,)

        if versionlock_pkg and "-versionlock is not installed" in str(ret):
            self.skipTest("{}  `{}` is installed".format(ret, versionlock_pkg))

        # changes from pkg.hold for Red Hat family are different
        target_changes = {}
        if grains["os_family"] == "RedHat":
            target_changes = {"new": "hold", "old": ""}
        elif grains["os_family"] == "Debian":
            target_changes = {"new": "hold", "old": "install"}

        try:
            tag = "pkg_|-{0}_|-{0}_|-installed".format(target)
            self.assertSaltTrueReturn(ret)
            self.assertIn(tag, ret)
            self.assertIn("changes", ret[tag])
            self.assertIn(target, ret[tag]["changes"])
            if not target_changes:
                self.skipTest(
                    "Test needs to be configured for {}: {}".format(
                        grains["os"], ret[tag]["changes"][target]
                    )
                )
            self.assertEqual(ret[tag]["changes"][target], target_changes)
        finally:
            # Clean up, unhold package and remove
            self.run_function("pkg.unhold", name=target)
            ret = self.run_state("pkg.removed", name=target)
            self.assertSaltTrueReturn(ret)
            if versionlock_pkg:
                ret = self.run_state("pkg.removed", name=versionlock_pkg)
                self.assertSaltTrueReturn(ret)

    @skipIf(salt.utils.platform.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_cap_002_already_installed(self, grains):
        '''
        This is a destructive test as it installs and then removes a package
        """
        if not self._PKG_CAP_TARGETS:
            self.skipTest("Capability not provided")

        os_family = grains.get('os_family', '')
        pkg_cap_targets = _PKG_CAP_TARGETS.get(os_family, [])
        if not pkg_cap_targets:
            self.skipTest('Capability not provided')

        # If this condition is False, we need to find new targets.
        # This needs to be able to test successful installation of packages.
        # These packages need to not be installed before we run the states below
        if not (version and realver):
            self.skipTest("TODO: New pkg cap targets required")

        try:
            ret = self.run_state(
                "pkg.installed",
                name=target,
                refresh=False,
                resolve_capabilities=True,
                test=True,
            )
            self.assertInSaltComment(
                "The following packages would be installed/updated: {0}".format(
                    realpkg
                ),
                ret,
            )
            ret = self.run_state(
                "pkg.installed", name=target, refresh=False, resolve_capabilities=True
            )
            self.assertSaltTrueReturn(ret)
        finally:
            ret = self.run_state("pkg.removed", name=realpkg)
            self.assertSaltTrueReturn(ret)

    @requires_salt_states("pkg.installed", "pkg.removed")
    def test_pkg_cap_002_already_installed(self):
        """
        This is a destructive test as it installs and then removes a package
        """
        if not self._PKG_CAP_TARGETS:
            self.skipTest("Capability not provided")

        target, realpkg = self._PKG_CAP_TARGETS[0]
        version = self.run_function("pkg.version", [target])
        realver = self.run_function("pkg.version", [realpkg])

        # If this condition is False, we need to find new targets.
        # This needs to be able to test successful installation of packages.
        # These packages need to not be installed before we run the states below
        if not (version and realver):
            self.skipTest("TODO: New pkg cap targets required")

        try:
            # install the package
            ret = self.run_state("pkg.installed", name=realpkg, refresh=False)
            self.assertSaltTrueReturn(ret)

            # Try to install again. Nothing should be installed this time.
            ret = self.run_state(
                "pkg.installed",
                name=target,
                refresh=False,
                resolve_capabilities=True,
                test=True,
            )
            self.assertInSaltComment(
                "All specified packages are already installed", ret
            )

            ret = self.run_state(
                "pkg.installed", name=target, refresh=False, resolve_capabilities=True
            )
            self.assertSaltTrueReturn(ret)

            self.assertInSaltComment("packages are already installed", ret)
        finally:
            ret = self.run_state("pkg.removed", name=realpkg)
            self.assertSaltTrueReturn(ret)

    @skipIf(salt.utils.platform.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_cap_003_installed_multipkg_with_version(self, grains):
        '''
        This is a destructive test as it installs and then removes two packages
        '''
        # Skip test if package manager not available
        if not pkgmgr_avail(self.run_function, self.run_function('grains.items')):
            self.skipTest('Package manager is not available')

        os_family = grains.get('os_family', '')
        pkg_cap_targets = _PKG_CAP_TARGETS.get(os_family, [])
        if not pkg_cap_targets:
            self.skipTest('Capability not provided')
        pkg_targets = _PKG_TARGETS.get(os_family, [])

        # Don't perform this test on FreeBSD since version specification is not
        # supported.
        if os_family == 'FreeBSD':
            return

        # Make sure that we have targets that match the os_family. If this
        # fails then the _PKG_TARGETS dict above needs to have an entry added,
        # with two packages that are not installed before these tests are run
        self.assertTrue(pkg_cap_targets)
        self.assertTrue(pkg_targets)

        if os_family == 'Arch':
            for idx in range(13):
                if idx == 12:
                    raise Exception('Package database locked after 60 seconds, '
                                    'bailing out')
                if not os.path.isfile('/var/lib/pacman/db.lck'):
                    break
                time.sleep(5)

        if not self._VERSION_SPEC_SUPPORTED:
            self.skipTest("Version specification not supported")

        target, realpkg = self._PKG_CAP_TARGETS[0]
        version = self.latest_version(target)
        realver = self.latest_version(realpkg)

        # If this condition is False, we need to find new targets.
        # This needs to be able to test successful installation of packages.
        # These packages need to not be installed before we run the states below
        if not (version and realver):
            self.skipTest("TODO: New pkg cap targets required")

        cleanup_pkgs = self._PKG_TARGETS
        try:
            pkgs = [
                {self._PKG_TARGETS[0]: version},
                self._PKG_TARGETS[1],
                {target: realver},
            ]
            ret = self.run_state(
                "pkg.installed",
                name="test_pkg_cap_003_installed_multipkg_with_version-install",
                pkgs=pkgs,
                refresh=False,
            )
            self.assertSaltFalseReturn(ret)

            ret = self.run_state(
                "pkg.installed",
                name="test_pkg_cap_003_installed_multipkg_with_version-install-capability",
                pkgs=pkgs,
                refresh=False,
                resolve_capabilities=True,
                test=True,
            )
            self.assertInSaltComment("packages would be installed/updated", ret)
            self.assertInSaltComment("{0}={1}".format(realpkg, realver), ret)

            ret = self.run_state(
                "pkg.installed",
                name="test_pkg_cap_003_installed_multipkg_with_version-install-capability",
                pkgs=pkgs,
                refresh=False,
                resolve_capabilities=True,
            )
            self.assertSaltTrueReturn(ret)
            cleanup_pkgs.append(realpkg)
        finally:
            ret = self.run_state(
                "pkg.removed",
                name="test_pkg_cap_003_installed_multipkg_with_version-remove",
                pkgs=cleanup_pkgs,
            )
            self.assertSaltTrueReturn(ret)

    @skipIf(salt.utils.platform.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_cap_004_latest(self, grains):
        '''
        This tests pkg.latest with a package that has no epoch (or a zero
        epoch).
        """
        if not self._PKG_CAP_TARGETS:
            self.skipTest("Capability not provided")

        os_family = grains.get('os_family', '')
        pkg_cap_targets = _PKG_CAP_TARGETS.get(os_family, [])
        if not pkg_cap_targets:
            self.skipTest('Capability not provided')

        # If this condition is False, we need to find new targets.
        # This needs to be able to test successful installation of packages.
        # These packages need to not be installed before we run the states below
        if not (version and realver):
            self.skipTest("TODO: New pkg cap targets required")

        try:
            ret = self.run_state(
                "pkg.latest",
                name=target,
                refresh=False,
                resolve_capabilities=True,
                test=True,
            )
            self.assertInSaltComment(
                "The following packages would be installed/upgraded: {0}".format(
                    realpkg
                ),
                ret,
            )
            ret = self.run_state(
                "pkg.latest", name=target, refresh=False, resolve_capabilities=True
            )
            self.assertSaltTrueReturn(ret)

            ret = self.run_state(
                "pkg.latest", name=target, refresh=False, resolve_capabilities=True
            )
            self.assertSaltTrueReturn(ret)
            self.assertInSaltComment("is already up-to-date", ret)
        finally:
            ret = self.run_state("pkg.removed", name=realpkg)
            self.assertSaltTrueReturn(ret)

    @skipIf(salt.utils.platform.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_cap_005_downloaded(self, grains):
        '''
        This is a destructive test as it installs and then removes a package
        """
        if not self._PKG_CAP_TARGETS:
            self.skipTest("Capability not provided")

        os_family = grains.get('os_family', '')
        pkg_cap_targets = _PKG_CAP_TARGETS.get(os_family, [])
        if not pkg_cap_targets:
            self.skipTest('Capability not provided')

        # If this condition is False, we need to find new targets.
        # This needs to be able to test successful installation of packages.
        # These packages need to not be installed before we run the states below
        if not (version and realver):
            self.skipTest("TODO: New pkg cap targets required")

        ret = self.run_state("pkg.downloaded", name=target, refresh=False)
        self.assertSaltFalseReturn(ret)

        ret = self.run_state(
            "pkg.downloaded",
            name=target,
            refresh=False,
            resolve_capabilities=True,
            test=True,
        )
        self.assertInSaltComment(
            "The following packages would be downloaded: {0}".format(realpkg), ret
        )

        ret = self.run_state(
            "pkg.downloaded", name=target, refresh=False, resolve_capabilities=True
        )
        self.assertSaltTrueReturn(ret)

    @skipIf(salt.utils.platform.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkg_cap_006_uptodate(self, grains):
        '''
        This is a destructive test as it installs and then removes a package
        """
        if not self._PKG_CAP_TARGETS:
            self.skipTest("Capability not provided")

        os_family = grains.get('os_family', '')
        pkg_cap_targets = _PKG_CAP_TARGETS.get(os_family, [])
        if not pkg_cap_targets:
            self.skipTest('Capability not provided')

        # If this condition is False, we need to find new targets.
        # This needs to be able to test successful installation of packages.
        # These packages need to not be installed before we run the states below
        if not (version and realver):
            self.skipTest("TODO: New pkg cap targets required")

        try:
            ret = self.run_state(
                "pkg.installed", name=target, refresh=False, resolve_capabilities=True
            )
            self.assertSaltTrueReturn(ret)

    @requires_salt_modules('pkg.hold', 'pkg.unhold')
    @requires_system_grains
    def test_pkg_015_installed_held(self, grains):
        '''
        Tests that a package can be held even when the package is already installed.
        '''
        os_family = grains.get('os_family', '')

        if os_family.lower() != 'redhat' and os_family.lower() != 'debian':
            self.skipTest('Test only runs on RedHat or Debian family')

        pkg_targets = _PKG_TARGETS.get(os_family, [])

        if os_family.lower() == 'redhat':
            # If we're in the Red Hat family first we ensure that
            # the yum-plugin-versionlock package is installed
            ret = self.run_state(
                "pkg.uptodate",
                name="test_pkg_cap_006_uptodate",
                pkgs=[target],
                refresh=False,
                resolve_capabilities=True,
            )
            self.assertSaltTrueReturn(ret)
            self.assertInSaltComment("System is already up-to-date", ret)
        finally:
            ret = self.run_state("pkg.removed", name=realpkg)
            self.assertSaltTrueReturn(ret)
