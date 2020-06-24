# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.cpan as cpan

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class CpanTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.cpan
    """

    # 'install' function tests: 2

    def setup_loader_modules(self):
        return {cpan: {}}

    def test_install(self):
        """
        Test if it install a module from cpan
        """
        mock = MagicMock(return_value="")
        with patch.dict(cpan.__salt__, {"cmd.run": mock}):
            mock = MagicMock(
                side_effect=[{"installed version": None}, {"installed version": "3.1"}]
            )
            with patch.object(cpan, "show", mock):
                self.assertDictEqual(cpan.install("Alloy"), {"new": "3.1", "old": None})

    def test_install_error(self):
        """
        Test if it install a module from cpan
        """
        mock = MagicMock(return_value="don't know what it is")
        with patch.dict(cpan.__salt__, {"cmd.run": mock}):
            self.assertDictEqual(
                cpan.install("Alloy"),
                {
                    "error": "CPAN cannot identify this package",
                    "new": None,
                    "old": None,
                },
            )

    # 'remove' function tests: 4

    def test_remove(self):
        """
        Test if it remove a module using cpan
        """
        with patch("os.listdir", MagicMock(return_value=[""])):
            mock = MagicMock(return_value="")
            with patch.dict(cpan.__salt__, {"cmd.run": mock}):
                mock = MagicMock(
                    return_value={
                        "installed version": "2.1",
                        "cpan build dirs": [""],
                        "installed file": "/root",
                    }
                )
                with patch.object(cpan, "show", mock):
                    self.assertDictEqual(
                        cpan.remove("Alloy"), {"new": None, "old": "2.1"}
                    )

    def test_remove_unexist_error(self):
        """
        Test if it try to remove an unexist module using cpan
        """
        mock = MagicMock(return_value="don't know what it is")
        with patch.dict(cpan.__salt__, {"cmd.run": mock}):
            self.assertDictEqual(
                cpan.remove("Alloy"), {"error": "This package does not seem to exist"}
            )

    def test_remove_noninstalled_error(self):
        """
        Test if it remove non installed module using cpan
        """
        mock = MagicMock(return_value={"installed version": None})
        with patch.object(cpan, "show", mock):
            self.assertDictEqual(cpan.remove("Alloy"), {"new": None, "old": None})

    def test_remove_nopan_error(self):
        """
        Test if it gives no cpan error while removing
        """
        ret = {"error": "No CPAN data available to use for uninstalling"}
        mock = MagicMock(return_value={"installed version": "2.1"})
        with patch.object(cpan, "show", mock):
            self.assertDictEqual(cpan.remove("Alloy"), ret)

    # 'list' function tests: 1

    def test_list(self):
        """
        Test if it list installed Perl module
        """
        mock = MagicMock(return_value="")
        with patch.dict(cpan.__salt__, {"cmd.run": mock}):
            self.assertDictEqual(cpan.list_(), {})

    # 'show' function tests: 2

    def test_show(self):
        """
        Test if it show information about a specific Perl module
        """
        mock = MagicMock(return_value="")
        with patch.dict(cpan.__salt__, {"cmd.run": mock}):
            self.assertDictEqual(
                cpan.show("Alloy"),
                {"error": "This package does not seem to exist", "name": "Alloy"},
            )

    def test_show_mock(self):
        """
        Test if it show information about a specific Perl module
        """
        with patch("salt.modules.cpan.show", MagicMock(return_value={"Salt": "salt"})):
            mock = MagicMock(return_value="Salt module installed")
            with patch.dict(cpan.__salt__, {"cmd.run": mock}):
                self.assertDictEqual(cpan.show("Alloy"), {"Salt": "salt"})

    # 'show_config' function tests: 1

    def test_show_config(self):
        """
        Test if it return a dict of CPAN configuration values
        """
        mock = MagicMock(return_value="")
        with patch.dict(cpan.__salt__, {"cmd.run": mock}):
            self.assertDictEqual(cpan.show_config(), {})
