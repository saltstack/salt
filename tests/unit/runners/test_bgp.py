# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import salt libs
import salt.runners.bgp as bgp

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf


@skipIf(not bgp.HAS_NAPALM, "napalm module required for this test")
class BGPTest(TestCase, LoaderModuleMockMixin):
    """
    Test the bgp runner
    """

    def setup_loader_modules(self):
        return {
            bgp: {
                "__opts__": {
                    "optimization_order": [0, 1, 2],
                    "renderer": "yaml",
                    "renderer_blacklist": [],
                    "renderer_whitelist": [],
                }
            }
        }

    def test_neighbors(self):
        ret = bgp.neighbors()
        self.assertEqual(ret, [])
