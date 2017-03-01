# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.utils.validate import net

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ValidateNetTestCase(TestCase):
    '''
    TestCase for salt.utils.validate.net module
    '''

    def test_ipv4_addr(self):
        '''
        Test IPv4 address validation
        '''
        true_addrs = [
            '127.0.0.1',
            '127.0.0.1',
            '127.0.0.19',
            '1.1.1.1/28',
            '127.0.0.11/32',
        ]

        false_addrs = [
            '127.0.0.911',
            '127.0.0911',
            '127.0.011',
            '127.0.011/32',
            '::1',
            '::1/128',
            '::1/28',
        ]

        for addr in true_addrs:
            self.assertTrue(net.ipv4_addr(addr))

        for addr in false_addrs:
            self.assertFalse(net.ipv4_addr(addr))

    def test_ipv6_addr(self):
        '''
        Test IPv6 address validation
        '''
        true_addrs = [
            '::1',
            '::1/32',
            '::1/32',
            '::1/128',
            '2a03:4000:c:10aa:1017:f00d:aaaa:a',
        ]

        false_addrs = [
            '1.1.1.1',
            '::1/0',
            '::1/32d',
            '::1/129',
        ]

        for addr in true_addrs:
            self.assertTrue(net.ipv6_addr(addr))

        for addr in false_addrs:
            self.assertFalse(net.ipv6_addr(addr))
