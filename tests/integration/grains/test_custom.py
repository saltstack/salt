# -*- coding: utf-8 -*-
"""
Test the core grains
"""

# Import python libs
from __future__ import absolute_import, unicode_literals

# Import Salt Testing libs
from tests.support.case import ModuleCase


class TestGrainsCore(ModuleCase):
    """
    Test the core grains grains
    """

    def test_grains_passed_to_custom_grain(self):
        """
        test if current grains are passed to grains module functions that have a grains argument
        """
        self.assertEqual(
            self.run_function("grains.get", ["custom_grain_test"]), "itworked"
        )
