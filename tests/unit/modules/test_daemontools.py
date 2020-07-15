# -*- coding: utf-8 -*-
"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import os

# Import Salt Libs
import salt.modules.daemontools as daemontools
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class DaemontoolsTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.daemontools
    """

    def setup_loader_modules(self):
        return {daemontools: {}}

    def test_start(self):
        """
        Test for Starts service via daemontools
        """
        mock = MagicMock(return_value=None)
        with patch.dict(daemontools.__salt__, {"file.remove": mock}):
            mock = MagicMock(return_value="")
            with patch.object(daemontools, "_service_path", mock):
                mock = MagicMock(return_value=False)
                with patch.dict(daemontools.__salt__, {"cmd.retcode": mock}):
                    self.assertTrue(daemontools.start("name"))

    def test_stop(self):
        """
        Test for Stops service via daemontools
        """
        mock = MagicMock(return_value=None)
        with patch.dict(daemontools.__salt__, {"file.touch": mock}):
            mock = MagicMock(return_value="")
            with patch.object(daemontools, "_service_path", mock):
                mock = MagicMock(return_value=False)
                with patch.dict(daemontools.__salt__, {"cmd.retcode": mock}):
                    self.assertTrue(daemontools.stop("name"))

    def test_term(self):
        """
        Test for Send a TERM to service via daemontools
        """
        mock = MagicMock(return_value="")
        with patch.object(daemontools, "_service_path", mock):
            mock = MagicMock(return_value=False)
            with patch.dict(daemontools.__salt__, {"cmd.retcode": mock}):
                self.assertTrue(daemontools.term("name"))

    def test_reload_(self):
        """
        Test for Wrapper for term()
        """
        mock = MagicMock(return_value=None)
        with patch.object(daemontools, "term", mock):
            self.assertEqual(daemontools.reload_("name"), None)

    def test_restart(self):
        """
        Test for Restart service via daemontools. This will stop/start service
        """
        mock = MagicMock(return_value=False)
        with patch.object(daemontools, "stop", mock):
            self.assertEqual(daemontools.restart("name"), "restart False")

    def test_full_restart(self):
        """
        Test for Calls daemontools.restart() function
        """
        mock = MagicMock(return_value=None)
        with patch.object(daemontools, "restart", mock):
            self.assertEqual(daemontools.restart("name"), None)

    def test_status(self):
        """
        Test for Return the status for a service via
        daemontools, return pid if running
        """
        with patch("re.search", MagicMock(return_value=1)):
            mock = MagicMock(return_value="")
            with patch.object(daemontools, "_service_path", mock):
                mock = MagicMock(return_value="name")
                with patch.dict(daemontools.__salt__, {"cmd.run_stdout": mock}):
                    self.assertEqual(daemontools.status("name"), "")

    def test_available(self):
        """
        Test for Returns ``True`` if the specified service
        is available, otherwise returns``False``.
        """
        mock = MagicMock(return_value=[])
        with patch.object(daemontools, "get_all", mock):
            self.assertFalse(daemontools.available("name"))

    def test_missing(self):
        """
        Test for The inverse of daemontools.available.
        """
        mock = MagicMock(return_value=[])
        with patch.object(daemontools, "get_all", mock):
            self.assertTrue(daemontools.missing("name"))

    def test_get_all(self):
        """
        Test for Return a list of all available services
        """
        self.assertRaises(CommandExecutionError, daemontools.get_all)

        with patch.object(daemontools, "SERVICE_DIR", "A"):
            mock = MagicMock(return_value="A")
            with patch.object(os, "listdir", mock):
                self.assertEqual(daemontools.get_all(), ["A"])
