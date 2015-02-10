# -*- coding: utf-8 -*-

# Import Salt Libs
from salt.utils.validate import net

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import NO_MOCK, NO_MOCK_REASON
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ValidateNetTestCase(TestCase):
    '''
    TestCase for salt.utils.validate.net module
    '''

    def test_ipv4_addr(self):
        '''
        Test IPv4 address validation
        '''
        self.assertTrue(net.ipv4_addr('127.0.0.1'))
        self.assertTrue(net.ipv4_addr('127.0.0.1'))
        self.assertTrue(net.ipv4_addr('127.0.0.19'))
        self.assertTrue(net.ipv4_addr('1.1.1.1/28'))
        self.assertTrue(net.ipv4_addr('127.0.0.11/32'))

        self.assertFalse(net.ipv4_addr('127.0.0.911'))
        self.assertFalse(net.ipv4_addr('127.0.0911'))
        self.assertFalse(net.ipv4_addr('127.0.011'))
        self.assertFalse(net.ipv4_addr('127.0.011/32'))
        self.assertFalse(net.ipv4_addr('::1'))
        self.assertFalse(net.ipv4_addr('::1/128'))
        self.assertFalse(net.ipv4_addr('::1/28'))

    def test_ipv6_addr(self):
        '''
        Test IPv6 address validation
        '''
        self.assertTrue(net.ipv6_addr('::1'))
        self.assertTrue(net.ipv6_addr('::1/32'))
        self.assertTrue(net.ipv6_addr('::1/32'))
        self.assertTrue(net.ipv6_addr('::1/128'))
        self.assertTrue(net.ipv6_addr('2a03:4000:c:10aa:1017:f00d:aaaa:a'))

        self.assertFalse(net.ipv6_addr('1.1.1.1'))
        self.assertFalse(net.ipv6_addr('::1/0'))
        self.assertFalse(net.ipv6_addr('::1/32d'))
        self.assertFalse(net.ipv6_addr('::1/129'))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ValidateNetTestCase, needs_daemon=False)
