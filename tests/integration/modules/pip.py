# Import python libs
import os

# Import salt libs
import integration

class PipModuleTest(integration.ModuleCase):
    '''
    Validate the pip module
    '''
    def test_freeze(self):
        '''
        pip.freeze
        '''
        ret = self.run_function('pip.freeze')
        self.assertIsInstance(ret, list)
        self.assertGreater(len(ret), 1)

