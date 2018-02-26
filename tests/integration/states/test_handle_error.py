# -*- coding: utf-8 -*-
'''
tests for host state
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.case import ModuleCase


class HandleErrorTest(ModuleCase):
    '''
    Validate that ordering works correctly
    '''
    def test_handle_error(self):
        '''
        Test how an error can be recovered
        '''
        # without sync_states, the custom state may not be installed
        # (resulting in :
        # State salttest.hello found in sls issue-... is unavailable
        ret = self.run_function('state.sls', ['issue-9983-handleerror'])
        self.assertTrue(
            'An exception occurred in this state: Traceback'
            in ret[[a for a in ret][0]]['comment'])
