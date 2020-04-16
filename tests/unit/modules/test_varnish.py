# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.varnish as varnish

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf


class VarnishTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.varnish
    """

    def setup_loader_modules(self):
        return {varnish: {}}

    @skipIf(True, "FASTTEST skip")
    def test_version(self):
        """
        Test to return server version from varnishd -V
        """
        with patch.dict(
            varnish.__salt__, {"cmd.run": MagicMock(return_value="(varnish-2.0)")}
        ):
            self.assertEqual(varnish.version(), "2.0")

    @skipIf(True, "FASTTEST skip")
    def test_ban(self):
        """
        Test to add ban to the varnish cache
        """
        with patch.object(varnish, "_run_varnishadm", return_value={"retcode": 0}):
            self.assertTrue(varnish.ban("ban_expression"))

    @skipIf(True, "FASTTEST skip")
    def test_ban_list(self):
        """
        Test to list varnish cache current bans
        """
        with patch.object(varnish, "_run_varnishadm", return_value={"retcode": True}):
            self.assertFalse(varnish.ban_list())

        with patch.object(
            varnish,
            "_run_varnishadm",
            return_value={"retcode": False, "stdout": "A\nB\nC"},
        ):
            self.assertEqual(varnish.ban_list(), ["B", "C"])

    @skipIf(True, "FASTTEST skip")
    def test_purge(self):
        """
        Test to purge the varnish cache
        """
        with patch.object(varnish, "ban", return_value=True):
            self.assertTrue(varnish.purge())

    @skipIf(True, "FASTTEST skip")
    def test_param_set(self):
        """
        Test to set a param in varnish cache
        """
        with patch.object(varnish, "_run_varnishadm", return_value={"retcode": 0}):
            self.assertTrue(varnish.param_set("param", "value"))

    @skipIf(True, "FASTTEST skip")
    def test_param_show(self):
        """
        Test to show params of varnish cache
        """
        with patch.object(
            varnish,
            "_run_varnishadm",
            return_value={"retcode": True, "stdout": "A\nB\nC"},
        ):
            self.assertFalse(varnish.param_show("param"))

        with patch.object(
            varnish,
            "_run_varnishadm",
            return_value={"retcode": False, "stdout": "A .1\nB .2\n"},
        ):
            self.assertEqual(varnish.param_show("param"), {"A": ".1"})
