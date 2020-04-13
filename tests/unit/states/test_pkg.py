# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

import salt.states.pkg as pkg

# Import Salt Libs
from salt.ext import six
from salt.ext.six.moves import zip

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class PkgTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.pkg
    """

    pkgs = {
        "pkga": {"old": "1.0.1", "new": "2.0.1"},
        "pkgb": {"old": "1.0.2", "new": "2.0.2"},
        "pkgc": {"old": "1.0.3", "new": "2.0.3"},
    }

    def setup_loader_modules(self):
        return {pkg: {"__grains__": {"os": "CentOS"}}}

    def test_uptodate_with_changes(self):
        """
        Test pkg.uptodate with simulated changes
        """
        list_upgrades = MagicMock(
            return_value={
                pkgname: pkgver["new"] for pkgname, pkgver in six.iteritems(self.pkgs)
            }
        )
        upgrade = MagicMock(return_value=self.pkgs)
        version = MagicMock(side_effect=lambda pkgname: self.pkgs[pkgname]["old"])

        with patch.dict(
            pkg.__salt__,
            {
                "pkg.list_upgrades": list_upgrades,
                "pkg.upgrade": upgrade,
                "pkg.version": version,
            },
        ):

            # Run state with test=false
            with patch.dict(pkg.__opts__, {"test": False}):

                ret = pkg.uptodate("dummy", test=True)
                self.assertTrue(ret["result"])
                self.assertDictEqual(ret["changes"], self.pkgs)

            # Run state with test=true
            with patch.dict(pkg.__opts__, {"test": True}):
                ret = pkg.uptodate("dummy", test=True)
                self.assertIsNone(ret["result"])
                self.assertDictEqual(ret["changes"], self.pkgs)

    def test_uptodate_with_pkgs_with_changes(self):
        """
        Test pkg.uptodate with simulated changes
        """

        pkgs = {
            "pkga": {"old": "1.0.1", "new": "2.0.1"},
            "pkgb": {"old": "1.0.2", "new": "2.0.2"},
            "pkgc": {"old": "1.0.3", "new": "2.0.3"},
        }

        list_upgrades = MagicMock(
            return_value={
                pkgname: pkgver["new"] for pkgname, pkgver in six.iteritems(self.pkgs)
            }
        )
        upgrade = MagicMock(return_value=self.pkgs)
        version = MagicMock(side_effect=lambda pkgname: pkgs[pkgname]["old"])

        with patch.dict(
            pkg.__salt__,
            {
                "pkg.list_upgrades": list_upgrades,
                "pkg.upgrade": upgrade,
                "pkg.version": version,
            },
        ):
            # Run state with test=false
            with patch.dict(pkg.__opts__, {"test": False}):
                ret = pkg.uptodate(
                    "dummy",
                    test=True,
                    pkgs=[pkgname for pkgname in six.iterkeys(self.pkgs)],
                )
                self.assertTrue(ret["result"])
                self.assertDictEqual(ret["changes"], pkgs)

            # Run state with test=true
            with patch.dict(pkg.__opts__, {"test": True}):
                ret = pkg.uptodate(
                    "dummy",
                    test=True,
                    pkgs=[pkgname for pkgname in six.iterkeys(self.pkgs)],
                )
                self.assertIsNone(ret["result"])
                self.assertDictEqual(ret["changes"], pkgs)

    def test_uptodate_no_changes(self):
        """
        Test pkg.uptodate with no changes
        """
        list_upgrades = MagicMock(return_value={})
        upgrade = MagicMock(return_value={})

        with patch.dict(
            pkg.__salt__, {"pkg.list_upgrades": list_upgrades, "pkg.upgrade": upgrade}
        ):

            # Run state with test=false
            with patch.dict(pkg.__opts__, {"test": False}):

                ret = pkg.uptodate("dummy", test=True)
                self.assertTrue(ret["result"])
                self.assertDictEqual(ret["changes"], {})

            # Run state with test=true
            with patch.dict(pkg.__opts__, {"test": True}):
                ret = pkg.uptodate("dummy", test=True)
                self.assertTrue(ret["result"])
                self.assertDictEqual(ret["changes"], {})

    def test_uptodate_with_pkgs_no_changes(self):
        """
        Test pkg.uptodate with no changes
        """
        list_upgrades = MagicMock(return_value={})
        upgrade = MagicMock(return_value={})

        with patch.dict(
            pkg.__salt__, {"pkg.list_upgrades": list_upgrades, "pkg.upgrade": upgrade}
        ):
            # Run state with test=false
            with patch.dict(pkg.__opts__, {"test": False}):
                ret = pkg.uptodate(
                    "dummy",
                    test=True,
                    pkgs=[pkgname for pkgname in six.iterkeys(self.pkgs)],
                )
                self.assertTrue(ret["result"])
                self.assertDictEqual(ret["changes"], {})

            # Run state with test=true
            with patch.dict(pkg.__opts__, {"test": True}):
                ret = pkg.uptodate(
                    "dummy",
                    test=True,
                    pkgs=[pkgname for pkgname in six.iterkeys(self.pkgs)],
                )
                self.assertTrue(ret["result"])
                self.assertDictEqual(ret["changes"], {})

    def test_uptodate_with_failed_changes(self):
        """
        Test pkg.uptodate with simulated failed changes
        """

        pkgs = {
            "pkga": {"old": "1.0.1", "new": "2.0.1"},
            "pkgb": {"old": "1.0.2", "new": "2.0.2"},
            "pkgc": {"old": "1.0.3", "new": "2.0.3"},
        }

        list_upgrades = MagicMock(
            return_value={
                pkgname: pkgver["new"] for pkgname, pkgver in six.iteritems(self.pkgs)
            }
        )
        upgrade = MagicMock(return_value={})
        version = MagicMock(side_effect=lambda pkgname: pkgs[pkgname]["old"])

        with patch.dict(
            pkg.__salt__,
            {
                "pkg.list_upgrades": list_upgrades,
                "pkg.upgrade": upgrade,
                "pkg.version": version,
            },
        ):
            # Run state with test=false
            with patch.dict(pkg.__opts__, {"test": False}):
                ret = pkg.uptodate(
                    "dummy",
                    test=True,
                    pkgs=[pkgname for pkgname in six.iterkeys(self.pkgs)],
                )
                self.assertFalse(ret["result"])
                self.assertDictEqual(ret["changes"], {})

            # Run state with test=true
            with patch.dict(pkg.__opts__, {"test": True}):
                ret = pkg.uptodate(
                    "dummy",
                    test=True,
                    pkgs=[pkgname for pkgname in six.iterkeys(self.pkgs)],
                )
                self.assertIsNone(ret["result"])
                self.assertDictEqual(ret["changes"], pkgs)

    def test_parse_version_string(self):
        test_parameters = [
            (
                "> 1.0.0, < 15.0.0, != 14.0.1",
                [(">", "1.0.0"), ("<", "15.0.0"), ("!=", "14.0.1")],
            ),
            (
                "> 1.0.0,< 15.0.0,!= 14.0.1",
                [(">", "1.0.0"), ("<", "15.0.0"), ("!=", "14.0.1")],
            ),
            (">= 1.0.0, < 15.0.0", [(">=", "1.0.0"), ("<", "15.0.0")]),
            (">=1.0.0,< 15.0.0", [(">=", "1.0.0"), ("<", "15.0.0")]),
            ("< 15.0.0", [("<", "15.0.0")]),
            ("<15.0.0", [("<", "15.0.0")]),
            ("15.0.0", [("==", "15.0.0")]),
            ("", []),
        ]
        for version_string, expected_version_conditions in test_parameters:
            version_conditions = pkg._parse_version_string(version_string)
            self.assertEqual(len(expected_version_conditions), len(version_conditions))
            for expected_version_condition, version_condition in zip(
                expected_version_conditions, version_conditions
            ):
                self.assertEqual(expected_version_condition[0], version_condition[0])
                self.assertEqual(expected_version_condition[1], version_condition[1])

    def test_fulfills_version_string(self):
        test_parameters = [
            ("> 1.0.0, < 15.0.0, != 14.0.1", [], False),
            ("> 1.0.0, < 15.0.0, != 14.0.1", ["1.0.0"], False),
            ("> 1.0.0, < 15.0.0, != 14.0.1", ["14.0.1"], False),
            ("> 1.0.0, < 15.0.0, != 14.0.1", ["16.0.0"], False),
            ("> 1.0.0, < 15.0.0, != 14.0.1", ["2.0.0"], True),
            (
                "> 1.0.0, < 15.0.0, != 14.0.1",
                ["1.0.0", "14.0.1", "16.0.0", "2.0.0"],
                True,
            ),
            ("> 15.0.0", [], False),
            ("> 15.0.0", ["1.0.0"], False),
            ("> 15.0.0", ["16.0.0"], True),
            ("15.0.0", [], False),
            ("15.0.0", ["15.0.0"], True),
            # No version specified, whatever version installed. This is threated like ANY version installed fulfills.
            ("", ["15.0.0"], True),
            # No version specified, no version installed.
            ("", [], False),
        ]
        for version_string, installed_versions, expected_result in test_parameters:
            msg = "version_string: {}, installed_versions: {}, expected_result: {}".format(
                version_string, installed_versions, expected_result
            )
            self.assertEqual(
                expected_result,
                pkg._fulfills_version_string(installed_versions, version_string),
                msg,
            )

    def test_fulfills_version_spec(self):
        test_parameters = [
            (["1.0.0", "14.0.1", "16.0.0", "2.0.0"], "==", "1.0.0", True),
            (["1.0.0", "14.0.1", "16.0.0", "2.0.0"], ">=", "1.0.0", True),
            (["1.0.0", "14.0.1", "16.0.0", "2.0.0"], ">", "1.0.0", True),
            (["1.0.0", "14.0.1", "16.0.0", "2.0.0"], "<", "2.0.0", True),
            (["1.0.0", "14.0.1", "16.0.0", "2.0.0"], "<=", "2.0.0", True),
            (["1.0.0", "14.0.1", "16.0.0", "2.0.0"], "!=", "1.0.0", True),
            (["1.0.0", "14.0.1", "16.0.0", "2.0.0"], "==", "17.0.0", False),
            (["1.0.0"], "!=", "1.0.0", False),
            ([], "==", "17.0.0", False),
        ]
        for installed_versions, operator, version, expected_result in test_parameters:
            msg = "installed_versions: {}, operator: {}, version: {}, expected_result: {}".format(
                installed_versions, operator, version, expected_result
            )
            self.assertEqual(
                expected_result,
                pkg._fulfills_version_spec(installed_versions, operator, version),
                msg,
            )
