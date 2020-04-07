# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import salt.config

# Import salt libs
import salt.version

# Import Salt Testing libs
from tests.support.case import MultimasterModuleCase
from tests.support.mixins import AdaptedConfigurationTestCaseMixin


class TestModuleTest(MultimasterModuleCase, AdaptedConfigurationTestCaseMixin):
    """
    Validate the test module
    """

    def test_ping(self):
        """
        test.ping
        """
        self.assertEqual(self.run_function_all_masters("test.ping"), [True] * 2)

    def test_echo(self):
        """
        test.echo
        """
        self.assertEqual(
            self.run_function_all_masters("test.echo", ["text"]), ["text"] * 2
        )

    def test_version(self):
        """
        test.version
        """
        self.assertEqual(
            self.run_function_all_masters("test.version"),
            [salt.version.__saltstack_version__.string] * 2,
        )

    def test_conf_test(self):
        """
        test.conf_test
        """
        self.assertEqual(self.run_function_all_masters("test.conf_test"), ["baz"] * 2)

    def test_get_opts(self):
        """
        test.get_opts
        """
        opts = salt.config.minion_config(self.get_config_file_path("mm_minion"))
        ret = self.run_function_all_masters("test.get_opts")
        self.assertEqual(ret[0]["cachedir"], opts["cachedir"])
        self.assertEqual(ret[1]["cachedir"], opts["cachedir"])

    def test_cross_test(self):
        """
        test.cross_test
        """
        self.assertTrue(self.run_function_all_masters("test.cross_test", ["test.ping"]))

    def test_fib(self):
        """
        test.fib
        """
        ret = self.run_function_all_masters("test.fib", ["20"])
        self.assertEqual(ret[0][0], 6765)
        self.assertEqual(ret[1][0], 6765)

    def test_collatz(self):
        """
        test.collatz
        """
        ret = self.run_function_all_masters("test.collatz", ["40"])
        self.assertEqual(ret[0][0][-1], 2)
        self.assertEqual(ret[1][0][-1], 2)

    def test_outputter(self):
        """
        test.outputter
        """
        self.assertEqual(
            self.run_function_all_masters("test.outputter", ["text"]), ["text"] * 2
        )
