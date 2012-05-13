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

    def test_absent_file(self):
        '''
        file.absent
        '''
        name = os.path.join(integration.TMP, 'file_to_kill')
        with open(name, 'w+') as fp_:
            fp_.write('killme')
        ret = self.run_state('file.absent', name=name)
        result = ret[ret.keys()[0]]['result']
        self.assertTrue(result)
        self.assertFalse(os.path.isfile(name))

    def test_absent_dir(self):
        '''
        file.absent
        '''
        name = os.path.join(integration.TMP, 'dir_to_kill')
        os.makedirs(name)
        ret = self.run_state('file.absent', name=name)
        result = ret[ret.keys()[0]]['result']
        self.assertTrue(result)
        self.assertFalse(os.path.isdir(name))
    
    def test_absent_link(self):
        '''
        file.absent
        '''
        name = os.path.join(integration.TMP, 'link_to_kill')
        os.symlink(name, '{0}.tgt'.format(name))
        ret = self.run_state('file.absent', name=name)
        result = ret[ret.keys()[0]]['result']
        self.assertTrue(result)
        self.assertFalse(os.path.islink(name))

    def test_test_abset(self):
        '''
        file.absent test interface
        '''
        name = os.path.join(integration.TMP, 'file_to_kill')
        with open(name, 'w+') as fp_:
            fp_.write('killme')
        ret = self.run_state('file.absent', test=True, name=name)
        result = ret[ret.keys()[0]]['result']
        self.assertIsNone(result)
        self.assertTrue(os.path.isfile(name))
