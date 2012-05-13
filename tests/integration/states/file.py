'''
Tests for the file state
'''
# Import python libs
import os
#
# Import salt libs
from saltunittest import TestLoader, TextTestRunner
import integration
from integration import TestDaemon

class FileTest(integration.ModuleCase):
    '''
    Validate the file state
    '''
    def test_symlink(self):
        '''
        file.symlink
        '''
        name = os.path.join(integration.TMP, 'symlink')
        tgt = os.path.join(integration.TMP, 'target')
        ret = self.run_state('file.symlink', name=name, target=tgt)
        result = ret[ret.keys()[0]]['result']
        self.assertTrue(result)

    def test_test_symlink(self):
        '''
        file.symlink test interface
        '''
        name = os.path.join(integration.TMP, 'symlink')
        tgt = os.path.join(integration.TMP, 'target')
        ret = self.run_state('file.symlink', test=True, name=name, target=tgt)
        result = ret[ret.keys()[0]]['result']
        self.assertIsNone(result)

