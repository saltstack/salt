# -*- coding: utf-8 -*-
'''
tests for host state
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ModuleCase


class HandleErrorTest(ModuleCase):
    '''
    Validate that ordering works correctly
    '''
    def test_function_do_not_return_dictionary_type(self):
        '''
        Handling a case when function returns anything but a dictionary type
        '''
        ret = self.run_function('state.sls', ['issue-9983-handleerror'])
        assert 'Data must be a dictionary type' in ret[[a for a in ret][0]]['comment']
        assert not ret[[a for a in ret][0]]['result']
        assert ret[[a for a in ret][0]]['changes'] == {}
