# -*- coding: utf-8 -*-
'''
    :codeauthor: `Anthony Shaw <anthonyshaw@apache.org>`

    tests.unit.cloud.clouds.dimensiondata_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase

# Import Salt Libs
import salt.cloud.libcloudfuncs as libcloud

# Import Salt Testing Libs
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')


class LibcloudTestCase(TestCase):
    def test_node_state_libcloud_020(self):
        state = libcloud.node_state(2)
        self.assertEqual('TERMINATED', state)

    def test_node_state_libcloud_100(self):
        state = libcloud.node_state('terminated')
        self.assertEqual('TERMINATED', state)


if __name__ == '__main__':
    from unit import run_tests
    run_tests(LibcloudTestCase, needs_daemon=False)
