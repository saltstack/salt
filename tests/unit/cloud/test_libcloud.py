# -*- coding: utf-8 -*-
'''
    :codeauthor: `Anthony Shaw <anthonyshaw@apache.org>`

    tests.unit.cloud.clouds.dimensiondata_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.unit import TestCase

# Import Salt Libs
import salt.cloud.libcloudfuncs as libcloud


class LibcloudTestCase(TestCase):
    def test_node_state_libcloud_020(self):
        state = libcloud.node_state(2)
        self.assertEqual('TERMINATED', state)

    def test_node_state_libcloud_100(self):
        state = libcloud.node_state('terminated')
        self.assertEqual('TERMINATED', state)
