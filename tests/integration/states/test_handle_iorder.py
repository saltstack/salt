# -*- coding: utf-8 -*-
'''
tests for host state
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
import tests.integration as integration


class HandleOrderTest(integration.ModuleCase):
    '''
    Validate that ordering works correctly
    '''
    def test_handle_iorder(self):
        '''
        Test the error with multiple states of the same type
        '''
        ret = self.run_function('state.show_low_sls', mods='issue-7649-handle-iorder')

        sorted_chunks = [chunk['name'] for chunk in sorted(ret, key=lambda c: c.get('order'))]

        expected = ['./configure', 'make', 'make install']
        self.assertEqual(expected, sorted_chunks)
