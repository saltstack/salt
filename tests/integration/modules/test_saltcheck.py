# -*- coding: utf-8 -*-
'''
Test the saltcheck module
'''
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.case import ModuleCase

class SaltcheckModuleTest(ModuleCase):
    '''
    Test the saltcheck module
    '''
    def test_saltcheck_run(self):
        '''
        saltcheck.run_test
        '''
        saltcheck_test = {"module_and_function": "test.echo",
                        "assertion": "assertEqual",
                        "expected-return": "This works!",
                        "args":["This works!"] }
        ret = self.run_function('saltcheck.run_test', test=saltcheck_test)
        self.assertDictContainsSubset({'status': 'Pass'}, ret)

    def test_saltcheck_state(self):
        '''
        saltcheck.run_state_tests
        '''
        saltcheck_test = 'validate-saltcheck'
        ret = self.run_function('saltcheck.run_state_tests', [saltcheck_test])
        #self.assertEqual(ret[0], "stuff")
        self.assertDictContainsSubset({'status': 'Pass'}, ret[0]['validate-saltcheck']['echo_test_hello'])
