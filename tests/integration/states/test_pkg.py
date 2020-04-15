# -*- coding: utf-8 -*-

"""
tests for pkg state
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import time

# Import Salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.pkg.rpm
import salt.utils.platform

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

# Import Salt Testing libs
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


@destructiveTest
class PkgTest(ModuleCase, SaltReturnAssertsMixin):
    _PKG_EPOCH_TARGETS = []
    _PKG_32_TARGETS = []
    _PKG_CAP_TARGETS = []
    _PKG_DOT_TARGETS = []
    _WILDCARDS_SUPPORTED = False
    _VERSION_SPEC_SUPPORTED = True

    @classmethod
    @requires_system_grains
    def setUpClass(cls, grains=None):  # pylint:disable=W0221
        cls.ctx = {}
        cls._PKG_TARGETS = ["figlet", "sl"]
        if grains["os"] == "Windows":
            cls._PKG_TARGETS = ["7zip", "putty"]
        elif grains["os"] == "freebsd":
            cls._VERSION_SPEC_SUPPORTED = False
        elif grains["os_family"] in ("Arch", "Debian"):
            cls._WILDCARDS_SUPPORTED = True
        elif grains["os"] == "Amazon":
            cls._PKG_TARGETS = ["lynx", "gnuplot"]
        elif grains["os_family"] == "RedHat":
            cls._PKG_TARGETS = ["units", "zsh-html"]
            cls._WILDCARDS_SUPPORTED = True
            if grains["os"] == "CentOS":
                if grains["osmajorrelease"] == 5:
                    cls._PKG_32_TARGETS = ["xz-devel.i386"]
                else:
                    cls._PKG_32_TARGETS.append("xz-devel.i686")
            if grains["osmajorrelease"] == 5:
                cls._PKG_DOT_TARGETS = ["python-migrate0.5"]
            elif grains["osmajorrelease"] == 6:
                cls._PKG_DOT_TARGETS = ["tomcat6-el-2.1-api"]
            elif grains["osmajorrelease"] == 7:
                cls._PKG_DOT_TARGETS = ["tomcat-el-2.2-api"]
                cls._PKG_EPOCH_TARGETS = ["comps-extras"]
        elif grains["os_family"] == "Suse":
            cls._PKG_TARGETS = ["lynx", "htop"]
            if grains["os"] == "SUSE":
                cls._PKG_CAP_TARGETS = [("perl(ZNC)", "znc-perl")]

    @classmethod
    def tearDownClass(cls):
        del cls.ctx

    def latest_version(self, *names):
        """
        Helper function which ensures that we don't make any unnecessary calls to
        pkg.latest_version to figure out what version we need to install. This
        won't stop pkg.latest_version from being run in a pkg.latest state, but it
        will reduce the amount of times we check the latest version here in the
        test suite.
        """
        key = "latest_version"
        if key not in self.ctx:
            self.ctx[key] = dict()
        targets = [x for x in names if x not in self.ctx[key]]
        if targets:
            result = self.run_function("pkg.latest_version", targets, refresh=False)
            try:
                self.ctx[key].update(result)
            except ValueError:
                # Only a single target, pkg.latest_version returned a string
                self.ctx[key][targets[0]] = result

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

    @skipIf(not _VERSION_SPEC_SUPPORTED, "Version specification not supported")
    @requires_salt_states("pkg.installed", "pkg.removed")
    def test_pkg_002_installed_with_version(self):
        """
        This is a destructive test as it installs and then removes a package
        """
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

    @requires_salt_states("pkg.installed", "pkg.removed")
    def test_pkg_003_installed_multipkg(self):
        """
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

    @skipIf(not _VERSION_SPEC_SUPPORTED, "Version specification not supported")
    @requires_salt_states("pkg.installed", "pkg.removed")
    def test_pkg_004_installed_multipkg_with_version(self):
        """
        This is a destructive test as it installs and then removes two packages
        """
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

    @skipIf(not _PKG_32_TARGETS, "No 32 bit packages have been specified for testing")
    @requires_salt_modules("pkg.version")
    @requires_salt_states("pkg.installed", "pkg.removed")
    def test_pkg_005_installed_32bit(self):
        """
        This is a destructive test as it installs and then removes a package
        """
        target = self._PKG_32_TARGETS[0]

        # _PKG_TARGETS_32 is only populated for platforms for which Salt has to
        # munge package names for 32-bit-on-x86_64 (Currently only Ubuntu and
        # RHEL-based). Don't actually perform this test on other platforms.
        version = self.run_function("pkg.version", [target])

        # If this assert fails, we need to find a new target. This test
        # needs to be able to test successful installation of packages, so
        # the target needs to not be installed before we run the states
        # below
        self.assertFalse(version)

        ret = self.run_state("pkg.installed", name=target, refresh=False)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state("pkg.removed", name=target)
        self.assertSaltTrueReturn(ret)

    @skipIf(not _PKG_32_TARGETS, "No 32 bit packages have been specified for testing")
    @requires_salt_states("pkg.installed", "pkg.removed")
    def test_pkg_006_installed_32bit_with_version(self):
        """
        This is a destructive test as it installs and then removes a package
        """
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

    @skipIf(
        not _PKG_DOT_TARGETS,
        'No packages with "." in their name have been configured for',
    )
    @requires_salt_states("pkg.installed", "pkg.removed")
    def test_pkg_007_with_dot_in_pkgname(self=None):
        """
        This tests for the regression found in the following issue:
        https://github.com/saltstack/salt/issues/8614

        This is a destructive test as it installs a package
        """
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

    @skipIf(
        not _PKG_EPOCH_TARGETS,
        'No targets have been configured with "epoch" in the version',
    )
    @requires_salt_states("pkg.installed", "pkg.removed")
    def test_pkg_008_epoch_in_version(self):
        """
        This tests for the regression found in the following issue:
        https://github.com/saltstack/salt/issues/8614

        This is a destructive test as it installs a package
        """
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

    @requires_salt_states("pkg.latest", "pkg.removed")
    def test_pkg_010_latest(self):
        """
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

    @requires_salt_modules("pkg.list_pkgs", "pkg.list_upgrades", "pkg.version")
    @requires_salt_states("pkg.latest")
    @runs_on(kernel="linux", os_family="Debian")
    def test_pkg_011_latest_only_upgrade(self):
        """
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

    @skipIf(not _WILDCARDS_SUPPORTED, "Wildcards in pkg.install are not supported")
    @requires_salt_modules("pkg.version")
    @requires_salt_states("pkg.installed", "pkg.removed")
    def test_pkg_012_installed_with_wildcard_version(self):
        """
        This is a destructive test as it installs and then removes a package
        """
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

    @requires_salt_modules("pkg.version", "pkg.latest_version")
    @requires_salt_states("pkg.installed", "pkg.removed")
    @runs_on(kernel="linux", os_family=["Debian", "RedHat"])
    def test_pkg_013_installed_with_comparison_operator(self):
        """
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

    @requires_salt_modules("pkg.version")
    @requires_salt_states("pkg.installed", "pkg.removed")
    @runs_on(kernel="linux", os_familiy="RedHat")
    def test_pkg_014_installed_missing_release(self):
        """
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

    @requires_salt_modules("pkg.hold", "pkg.unhold", "pkg.version", "pkg.list_pkgs")
    @requires_salt_states("pkg.installed", "pkg.removed")
    @requires_system_grains
    def test_pkg_015_installed_held(self, grains=None):
        """
        Tests that a package can be held even when the package is already installed.
        """
        versionlock_pkg = None
        if grains["os_family"] == "RedHat":
            pkgs = {
                p for p in self.run_function("pkg.list_pkgs") if "-versionlock" in p
            }
            if not pkgs:
                self.skipTest("No versionlock package found in repositories")
            for versionlock_pkg in pkgs:
                ret = self.run_state(
                    "pkg.installed", name=versionlock_pkg, refresh=False
                )
                # Exit loop if a versionlock package installed correctly
                try:
                    self.assertSaltTrueReturn(ret)
                    log.debug(
                        "Installed versionlock package: {}".format(versionlock_pkg)
                    )
                    break
                except AssertionError as e:
                    log.debug("Versionlock package not found:\n{}".format(e))
            else:
                self.fail("Could not install versionlock package from {}".format(pkgs))

        target = self._PKG_TARGETS[0]

        # First we ensure that the package is installed
        ret = self.run_state("pkg.installed", name=target, refresh=False,)
        self.assertSaltTrueReturn(ret)

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

    @skipIf(not _PKG_CAP_TARGETS, "Capability not provided")
    @requires_salt_modules("pkg.version")
    @requires_salt_states("pkg.installed", "pkg.removed")
    def test_pkg_cap_001_installed(self):
        """
        This is a destructive test as it installs and then removes a package
        """

        target, realpkg = self._PKG_CAP_TARGETS[0]
        version = self.run_function("pkg.version", [target])
        realver = self.run_function("pkg.version", [realpkg])

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

    @skipIf(not _PKG_CAP_TARGETS, "Capability not available")
    @requires_salt_states("pkg.installed", "pkg.removed")
    def test_pkg_cap_002_already_installed(self):
        """
        This is a destructive test as it installs and then removes a package
        """
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

    @skipIf(not _PKG_CAP_TARGETS, "Capability not available")
    @skipIf(not _VERSION_SPEC_SUPPORTED, "Version specification not supported")
    @requires_salt_states("pkg.installed", "pkg.removed")
    def test_pkg_cap_003_installed_multipkg_with_version(self):
        """
        This is a destructive test as it installs and then removes two packages
        """
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

    @skipIf(not _PKG_CAP_TARGETS, "Capability not available")
    @requires_salt_modules("pkg.version")
    @requires_salt_states("pkg.latest", "pkg.removed")
    def test_pkg_cap_004_latest(self):
        """
        This tests pkg.latest with a package that has no epoch (or a zero
        epoch).
        """
        target, realpkg = self._PKG_CAP_TARGETS[0]
        version = self.run_function("pkg.version", [target])
        realver = self.run_function("pkg.version", [realpkg])

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

    @skipIf(not _PKG_CAP_TARGETS, "Capability not available")
    @requires_salt_modules("pkg.version")
    @requires_salt_states("pkg.installed", "pkg.removed", "pkg.downloaded")
    def test_pkg_cap_005_downloaded(self):
        """
        This is a destructive test as it installs and then removes a package
        """
        target, realpkg = self._PKG_CAP_TARGETS[0]
        version = self.run_function("pkg.version", [target])
        realver = self.run_function("pkg.version", [realpkg])

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

    @skipIf(not _PKG_CAP_TARGETS, "Capability not available")
    @requires_salt_modules("pkg.version")
    @requires_salt_states("pkg.installed", "pkg.removed", "pkg.uptodate")
    def test_pkg_cap_006_uptodate(self):
        """
        This is a destructive test as it installs and then removes a package
        """
        target, realpkg = self._PKG_CAP_TARGETS[0]
        version = self.run_function("pkg.version", [target])
        realver = self.run_function("pkg.version", [realpkg])

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
