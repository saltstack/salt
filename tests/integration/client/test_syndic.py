# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

import pytest
from tests.support.case import SyndicCase
from tests.support.helpers import slowTest


@pytest.mark.windows_whitelisted
class TestSyndic(SyndicCase):
    """
    Validate the syndic interface by testing the test module
    """

    @slowTest
    def test_ping(self):
        """
        test.ping
        """
        self.assertTrue(self.run_function("test.ping"))

    @slowTest
    def test_fib(self):
        """
        test.fib
        """
        self.assertEqual(self.run_function("test.fib", ["20"],)[0], 6765)
