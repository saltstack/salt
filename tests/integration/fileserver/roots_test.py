# -*- coding: utf-8 -*-
'''
    :codauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Salt Testing libs
from salttesting.helpers import (ensure_in_syspath, destructiveTest)
ensure_in_syspath('../')

# Import salt libs
import integration
from salt import fileclient

# Import Python libs
import os


class RootsLimitTraversalTest(integration.ModuleCase):

    @destructiveTest
    def setUp(self):
        self._create_test_deep_structure()

    @destructiveTest
    def test_limit_traversal(self):
        '''
        1) Set up a deep directory structure
        2) Enable the configuration option for 'limit_directory_traversal'
        3) Ensure that we can find SLS files in a directory so long as there is an SLS file in a directory above.
        4) Ensure that we cannot find an SLS file in a directory that does not have an SLS file in a directory above.
        '''
        file_client_opts = self.master_opts
        file_client_opts['fileserver_limit_traversal'] = True

        ret = fileclient.Client(file_client_opts).list_states('base')
        self.assertIn('test_deep.test', ret)
        self.assertIn('test_deep.a.test', ret)
        self.assertNotIn('test_deep.b.2.test', ret)

    @destructiveTest
    def _create_test_deep_structure(self):
        '''
        Create a directory structure as follows, comments indicate whether a traversal should find SLS
        files above.

        test_deep/test.sls      # True
        test_deep/a/test.sls    # True
        test_deep/b/            # True
        test_deep/b/1/          # False
        test_deep/b/2/test.sls  # False
        '''

        # Get file server root
        file_root = self.master_opts['file_roots']['base'][0]

        if os.path.exists(os.path.join(file_root, 'test_deep')):
            return

        for test_dir in ['a', 'b']:
            os.makedirs(os.path.join(file_root, 'test_deep', test_dir))

        # test_deep/test.sls
        open(os.path.join(file_root, 'test_deep', 'test.sls'), 'w').close()
        # test_deep/a/test.sls
        open(os.path.join(file_root, 'test_deep', 'a', 'test.sls'), 'w').close()
        # test_deep/b/1/
        os.mkdir(os.path.join(file_root, 'test_deep', 'b', '1'))
        # test_deep/b/2/
        os.mkdir(os.path.join(file_root, 'test_deep', 'b', '2'))
        # test_deep/b/2/test.sls
        open(os.path.join(file_root, 'test_deep', 'b', '2', 'test.sls'), 'w').close()

    @destructiveTest
    def tearDown(self):
        test_deep_dir = os.path.join(self.master_opts['file_roots']['base'][0], 'test_deep')
        if os.path.exists(test_deep_dir):
            os.rmdir(test_deep_dir)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RootsLimitTraversalTest)
