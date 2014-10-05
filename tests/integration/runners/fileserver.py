# -*- coding: utf-8 -*-

'''
Tests for the fileserver runner
'''

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class ManageTest(integration.ShellCase):
    '''
    Test the fileserver runner
    '''
    def test_dir_list(self):
        '''
        fileserver.dir_list
        '''
        ret = self.run_run_plus(fun='fileserver.dir_list')
        self.assertIsInstance(ret['fun'], list)

    def test_envs(self):
        '''
        fileserver.envs
        '''
        ret = self.run_run_plus(fun='fileserver.envs')
        self.assertIsInstance(ret['fun'], list)

        ret = self.run_run_plus(fun='fileserver.envs', args=['backend="{0}"'.format(['root'])])
        self.assertIsInstance(ret['fun'], list)

    def test_file_list(self):
        '''
        fileserver.file_list
        '''
        ret = self.run_run_plus(fun='fileserver.file_list')
        self.assertIsInstance(ret['fun'], list)

    def test_symlink_list(self):
        '''
        fileserver.symlink_list
        '''
        ret = self.run_run_plus(fun='fileserver.symlink_list')
        self.assertIsInstance(ret['fun'], dict)

    def test_update(self):
        '''
        fileserver.update
        '''
        ret = self.run_run_plus(fun='fileserver.update')
        self.assertTrue(ret['fun'])

if __name__ == '__main__':
    from integration import run_tests
    run_tests(ManageTest)
