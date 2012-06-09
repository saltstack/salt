'''
tests for host state
'''

# Import python libs
import os
#
# Import salt libs
from saltunittest import TestLoader, TextTestRunner
import integration
from integration import TestDaemon


class CompileTest(integration.ModuleCase):
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
