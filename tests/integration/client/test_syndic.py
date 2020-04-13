# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import SyndicCase
from tests.support.unit import skipIf


class TestSyndic(SyndicCase):
    """
    Validate the syndic interface by testing the test module
    """

    @skipIf(True, "SLOWTEST skip")
    def test_ping(self):
        """
        test.ping
        """
        self.assertTrue(self.run_function("test.ping"))

    @skipIf(True, "SLOWTEST skip")
    def test_fib(self):
        """
        test.fib
        """
        self.assertEqual(self.run_function("test.fib", ["20"],)[0], 6765)
