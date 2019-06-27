# -*- coding: utf-8 -*-
'''
Unit tests for the test runner
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

# Import Salt Libs
import salt.runners.test as runnerstest
import salt.utils.master


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestTest(TestCase, LoaderModuleMockMixin):
    '''
    Validate the test runner
    '''

    def test_arg(self):
        '''
        Test test.arg runner
        '''
        ret = runnerstest.get_opts('test4me')
        self.assertEqual(masterconfig, {args: ('test4me')})


    def test_get_opts(self):
        '''
        Test test.get_opts runner
        '''
        masterconfig = runnerstest.get_opts()   # configuration options of the master
        self.assertIsNot(masterconfig, None)
        self.assertIsNot(masterconfig, {})
