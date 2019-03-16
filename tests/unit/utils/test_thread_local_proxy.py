# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.utils import thread_local_proxy

# Import Salt Testing Libs
from tests.support.unit import TestCase


class ThreadLocalProxyTestCase(TestCase):
    '''
    Test case for salt.utils.thread_local_proxy module.
    '''

    def test_set_reference_avoid_loop(self):
        '''
        Test that passing another proxy (or the same proxy) to set_reference
        does not results in a recursive proxy loop.
        '''
        test_obj1 = 1
        test_obj2 = 2
        proxy1 = thread_local_proxy.ThreadLocalProxy(test_obj1)
        proxy2 = thread_local_proxy.ThreadLocalProxy(proxy1)
        self.assertEqual(test_obj1, proxy1)
        self.assertEqual(test_obj1, proxy2)
        self.assertEqual(proxy1, proxy2)
        thread_local_proxy.ThreadLocalProxy.set_reference(proxy1, test_obj2)
        self.assertEqual(test_obj2, proxy1)
        self.assertEqual(test_obj2, proxy2)
        self.assertEqual(proxy1, proxy2)
        thread_local_proxy.ThreadLocalProxy.set_reference(proxy1, proxy2)
        self.assertEqual(test_obj2, proxy1)
        self.assertEqual(test_obj2, proxy2)
        self.assertEqual(proxy1, proxy2)
