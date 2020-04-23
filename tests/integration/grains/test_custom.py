# -*- coding: utf-8 -*-
"""
Test the core grains
"""

from __future__ import absolute_import, unicode_literals

import pytest
from tests.support.case import ModuleCase


@pytest.mark.windows_whitelisted
class TestGrainsCore(ModuleCase):
    """
    Test the core grains grains
    """

    @pytest.mark.slow_test(seconds=30)  # Test takes >10 and <=30 seconds
    def test_grains_passed_to_custom_grain(self):
        """
        test if current grains are passed to grains module functions that have a grains argument
        """
        self.assertEqual(
            self.run_function("grains.get", ["custom_grain_test"]), "itworked"
        )
