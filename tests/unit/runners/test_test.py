# -*- coding: utf-8 -*-
'''
Unit tests for the test runner
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.unit import TestCase

# Import Salt Libs
import salt.runners.test as runnerstest


class TestTest(TestCase):
    '''
    Validate the test runner
    '''

    def test_arg(self):
        '''
        Test test.arg runner
        '''
        ret = runnerstest.arg('test4me')
        expected = {'args': ('test4me',), 'kwargs': {}}
        self.assertEqual(ret, expected)
