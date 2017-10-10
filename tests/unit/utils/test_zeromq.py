# -*- coding: utf-8 -*-
'''
Test salt.utils.zeromq
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import salt libs
import salt.utils.zeromq


class UtilsTestCase(TestCase):
    def test_ip_bracket(self):
        test_ipv4 = '127.0.0.1'
        test_ipv6 = '::1'
        self.assertEqual(test_ipv4, salt.utils.zeromq.ip_bracket(test_ipv4))
        self.assertEqual('[{0}]'.format(test_ipv6), salt.utils.zeromq.ip_bracket(test_ipv6))
