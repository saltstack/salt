# -*- coding: utf-8 -*-
'''
tests for host state
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.case import ModuleCase


class CompileTest(ModuleCase):
    '''
    Validate the state compiler
    '''
    def test_multi_state(self):
        '''
        Test the error with multiple states of the same type
        '''
        ret = self.run_function('state.sls', mods='fuzz.multi_state')
        # Verify that the return is a list, aka, an error
        self.assertIsInstance(ret, list)

    def test_jinja_deep_error(self):
        '''
        Test when we have an error in a execution module
        called by jinja
        '''
        ret = self.run_function('state.sls', ['issue-10010'])
        self.assertTrue(
            ', in jinja_error' in ret[0].strip())
        self.assertTrue(
            ret[0].strip().endswith('Exception: hehehe'))
