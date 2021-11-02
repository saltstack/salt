"""
Unit tests for salt.utils.color.py
"""


import salt.utils.color
from tests.support.unit import TestCase


class ColorUtilsTestCase(TestCase):
    def test_get_colors(self):
        ret = salt.utils.color.get_colors()
        self.assertEqual("\x1b[0;37m", str(ret["LIGHT_GRAY"]))

        ret = salt.utils.color.get_colors(use=False)
        self.assertDictContainsSubset({"LIGHT_GRAY": ""}, ret)

        ret = salt.utils.color.get_colors(use="LIGHT_GRAY")
        # LIGHT_YELLOW now == LIGHT_GRAY
        self.assertEqual(str(ret["LIGHT_YELLOW"]), str(ret["LIGHT_GRAY"]))
