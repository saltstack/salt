# -*- coding: utf-8 -*-
"""
    tests.unit.cloud.test_libcloudfuncs
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.cloud.libcloudfuncs as libcloud

# Import Salt Testing Libs
from tests.support.unit import TestCase


class LibcloudTestCase(TestCase):
    def test_node_state_libcloud_020(self):
        state = libcloud.node_state(2)
        self.assertEqual("TERMINATED", state)

    def test_node_state_libcloud_100(self):
        state = libcloud.node_state("terminated")
        self.assertEqual("TERMINATED", state)
