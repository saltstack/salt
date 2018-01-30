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

    def test_unproxy_recursive_dict_with_proxy(self):
        '''
        Test that recursively unproxying a proxy that references a dict that
        points back to that proxy results in a dict that points back to itself.
        '''
        test_obj = {}
        proxy = thread_local_proxy.ThreadLocalProxy(test_obj)
        test_obj['x'] = proxy
        unproxied = thread_local_proxy.ThreadLocalProxy.unproxy_recursive(proxy)
        self.assertIs(unproxied, unproxied['x'])

    def test_unproxy_recursive_dict_without_proxy(self):
        '''
        Test that unproxying a dict that contains a reference to itself works
        and results in the same object being returned.
        '''
        test_obj = {}
        test_obj['x'] = test_obj
        unproxied = thread_local_proxy.ThreadLocalProxy.unproxy_recursive(
            test_obj)
        self.assertIs(test_obj, unproxied)

    def test_unproxy_recursive_list_with_proxy(self):
        '''
        Test that recursively unproxying a proxy that references a list that
        points back to that proxy results in a list that points back to itself.
        '''
        test_obj = ['abc', 123]
        proxy = thread_local_proxy.ThreadLocalProxy(test_obj)
        # Append to the list (through the proxy).
        proxy += [proxy]
        unproxied = thread_local_proxy.ThreadLocalProxy.unproxy_recursive(proxy)
        self.assertIs(unproxied, unproxied[2])
