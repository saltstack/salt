# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

import logging

import pytest
import salt.config
import salt.version
from tests.support.case import ModuleCase
from tests.support.helpers import slowTest
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import skipIf

log = logging.getLogger(__name__)


@pytest.mark.windows_whitelisted
class TestModuleTest(ModuleCase, AdaptedConfigurationTestCaseMixin):
    """
    Validate the test module
    """

    @slowTest
    def test_ping(self):
        """
        test.ping
        """
        self.assertTrue(self.run_function("test.ping"))

    @slowTest
    def test_echo(self):
        """
        test.echo
        """
        self.assertEqual(self.run_function("test.echo", ["text"]), "text")

    @slowTest
    def test_version(self):
        """
        test.version
        """
        self.assertEqual(
            self.run_function("test.version"), salt.version.__saltstack_version__.string
        )

    @slowTest
    def test_conf_test(self):
        """
        test.conf_test
        """
        self.assertEqual(self.run_function("test.conf_test"), "baz")

    @slowTest
    def test_get_opts(self):
        """
        test.get_opts
        """
        opts = salt.config.minion_config(self.get_config_file_path("minion"))
        self.assertEqual(
            self.run_function("test.get_opts")["cachedir"], opts["cachedir"]
        )

    @slowTest
    def test_cross_test(self):
        """
        test.cross_test
        """
        self.assertTrue(self.run_function("test.cross_test", ["test.ping"]))

    @slowTest
    def test_fib(self):
        """
        test.fib
        """
        self.assertEqual(self.run_function("test.fib", ["20"],)[0], 6765)

    @slowTest
    def test_collatz(self):
        """
        test.collatz
        """
        self.assertEqual(self.run_function("test.collatz", ["40"],)[0][-1], 2)

    @slowTest
    def test_outputter(self):
        """
        test.outputter
        """
        self.assertEqual(self.run_function("test.outputter", ["text"]), "text")

    @slowTest
    @skipIf(not salt.utils.platform.is_linux(), "linux test only")
    def test_versions_version_linux(self):
        """
        test.versions on Linux
        """

        with patch(
            "distro.linux_distribution",
            MagicMock(return_value=("Manjaro Linux", "20.0.2", "Lysia")),
        ):
            versions = self.run_function("test.versions")
            version = "version: Manjaro Linux 20.0.2 Lysia"
            self.assertIn(version, versions)

        with patch(
            "distro.linux_distribution",
            MagicMock(return_value=("Debian GNU/Linux", "9", "stretch")),
        ):
            versions = self.run_function("test.versions")
            version = "version: Debian GNU/Linux 9 stretch"
            self.assertIn(version, versions)

    @slowTest
    @skipIf(not salt.utils.platform.is_darwin(), "OS X test only")
    def test_versions_version_osx(self):
        """
        test.versions on OS X
        """

        with patch(
            "platform.mac_ver",
            MagicMock(return_value=("10.15.2", ("", "", ""), "x86_64")),
        ):
            versions = self.run_function("test.versions")
            version = "version: 10.15.2 x86_64"
            self.assertIn(version, versions)

    @slowTest
    @skipIf(not salt.utils.platform.is_windows(), "windows test only")
    def test_versions_version_windows(self):
        """
        test.versions on Windows
        """

        with patch(
            "platform.win32_ver",
            return_value=("10", "10.0.14393", "SP0", "Multiprocessor Free"),
        ), patch("win32api.RegOpenKey", MagicMock()), patch(
            "win32api.RegQueryValueEx",
            MagicMock(return_value=("Windows Server 2016 Datacenter", 1)),
        ):
            versions = self.run_function("test.versions")
            version = "version: 2016Server 10.0.14393 SP0 Multiprocessor Free"
            self.assertIn(version, versions)
