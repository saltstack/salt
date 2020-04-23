# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

import pytest
import salt.config
import salt.version
from tests.support.case import ModuleCase
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.unit import skipIf


@pytest.mark.windows_whitelisted
class TestModuleTest(ModuleCase, AdaptedConfigurationTestCaseMixin):
    """
    Validate the test module
    """

    @skipIf(True, "SLOWTEST skip")
    def test_ping(self):
        """
        test.ping
        """
        self.assertTrue(self.run_function("test.ping"))

    @skipIf(True, "SLOWTEST skip")
    def test_echo(self):
        """
        test.echo
        """
        self.assertEqual(self.run_function("test.echo", ["text"]), "text")

    @skipIf(True, "SLOWTEST skip")
    def test_version(self):
        """
        test.version
        """
        self.assertEqual(
            self.run_function("test.version"), salt.version.__saltstack_version__.string
        )

    @skipIf(True, "SLOWTEST skip")
    def test_conf_test(self):
        """
        test.conf_test
        """
        self.assertEqual(self.run_function("test.conf_test"), "baz")

    @skipIf(True, "SLOWTEST skip")
    def test_get_opts(self):
        """
        test.get_opts
        """
        opts = salt.config.minion_config(self.get_config_file_path("minion"))
        self.assertEqual(
            self.run_function("test.get_opts")["cachedir"], opts["cachedir"]
        )

    @skipIf(True, "SLOWTEST skip")
    def test_cross_test(self):
        """
        test.cross_test
        """
        self.assertTrue(self.run_function("test.cross_test", ["test.ping"]))

    @skipIf(True, "SLOWTEST skip")
    def test_fib(self):
        """
        test.fib
        """
        self.assertEqual(self.run_function("test.fib", ["20"],)[0], 6765)

    @skipIf(True, "SLOWTEST skip")
    def test_collatz(self):
        """
        test.collatz
        """
        self.assertEqual(self.run_function("test.collatz", ["40"],)[0][-1], 2)

    @skipIf(True, "SLOWTEST skip")
    def test_outputter(self):
        """
        test.outputter
        """
        self.assertEqual(self.run_function("test.outputter", ["text"]), "text")
