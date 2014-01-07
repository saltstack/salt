# -*- coding: utf-8 -*-
'''
    :codauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import (ensure_in_syspath, destructiveTest)
from salttesting.mock import patch, MagicMock, call, NO_MOCK, NO_MOCK_REASON
ensure_in_syspath('../')

# Import salt libs
import integration
from salt.fileserver import roots
from salt import fileclient

roots.__opts__ = {}

# Import Python libs
import os
import shutil


class RootsTest(integration.ModuleCase):
    def setUp(self):
        self.master_opts['file_roots']['base'] = [os.path.join(integration.FILES, 'file', 'base')]

    def test_file_list(self):
        with patch.dict(roots.__opts__, {'file_roots': self.master_opts['file_roots'],
                                         'fileserver_ignoresymlinks': False,
                                         'fileserver_followsymlinks': False,
                                         'file_ignore_regex': False,
                                         'file_ignore_glob': False}):
            ret = roots.file_list({'saltenv': 'base'})
            self.assertIn('testfile', ret)

    def test_find_file(self):
        with patch.dict(roots.__opts__, {'file_roots': self.master_opts['file_roots'],
                                         'fileserver_ignoresymlinks': False,
                                         'fileserver_followsymlinks': False,
                                         'file_ignore_regex': False,
                                         'file_ignore_glob': False}):

            ret = roots.find_file('testfile')
            self.assertEqual('testfile', ret['rel'])

            full_path_to_file = os.path.join(integration.FILES, 'file', 'base', 'testfile')
            self.assertEqual(full_path_to_file, ret['path'])

    def test_serve_file(self):
        with patch.dict(roots.__opts__, {'file_roots': self.master_opts['file_roots'],
                                        'fileserver_ignoresymlinks': False,
                                        'fileserver_followsymlinks': False,
                                        'file_ignore_regex': False,
                                        'file_ignore_glob': False,
                                        'file_buffer_size': 262144}):
            load = {'saltenv': 'base',
                    'path': os.path.join(integration.FILES, 'file', 'base', 'testfile'),
                    'loc': 0
                    }
            fnd = {'path': os.path.join(integration.FILES, 'file', 'base', 'testfile'),
                   'rel': 'testfile'}
            ret = roots.serve_file(load, fnd)
            self.assertDictEqual(ret,
                                 {'data': 'Scene 24\n\n \n  OLD MAN:  Ah, hee he he ha!\n  ARTHUR:  And this enchanter of whom you speak, he has seen the grail?\n  OLD MAN:  Ha ha he he he he!\n  ARTHUR:  Where does he live?  Old man, where does he live?\n  OLD MAN:  He knows of a cave, a cave which no man has entered.\n  ARTHUR:  And the Grail... The Grail is there?\n  OLD MAN:  Very much danger, for beyond the cave lies the Gorge\n      of Eternal Peril, which no man has ever crossed.\n  ARTHUR:  But the Grail!  Where is the Grail!?\n  OLD MAN:  Seek you the Bridge of Death.\n  ARTHUR:  The Bridge of Death, which leads to the Grail?\n  OLD MAN:  Hee hee ha ha!\n\n',
 'dest': 'testfile'})

    @skipIf(True, "Update test not yet implemented")
    def test_update(self):
        pass

    def test_file_hash(self):
        with patch.dict(roots.__opts__, {'file_roots': self.master_opts['file_roots'],
                                 'fileserver_ignoresymlinks': False,
                                 'fileserver_followsymlinks': False,
                                 'file_ignore_regex': False,
                                 'file_ignore_glob': False,
                                 'hash_type': self.master_opts['hash_type'],
                                 'cachedir': self.master_opts['cachedir']}):
            load = {
                    'saltenv': 'base',
                    'path': os.path.join(integration.FILES, 'file', 'base', 'testfile'),
                    }
            fnd = {
                'path': os.path.join(integration.FILES, 'file', 'base', 'testfile'),
                'rel': 'testfile'
            }
            ret = roots.file_hash(load, fnd)
            self.assertDictEqual(ret, {'hsum': '98aa509006628302ce38ce521a7f805f', 'hash_type': 'md5'})

    def test_file_list_emptydirs(self):
        with patch.dict(roots.__opts__, {'file_roots': self.master_opts['file_roots'],
                                         'fileserver_ignoresymlinks': False,
                                         'fileserver_followsymlinks': False,
                                         'file_ignore_regex': False,
                                         'file_ignore_glob': False}):
            ret = roots.file_list_emptydirs({'saltenv': 'base'})
            self.assertIn('empty_dir', ret)

    def test_dir_list(self):
        with patch.dict(roots.__opts__, {'file_roots': self.master_opts['file_roots'],
                                 'fileserver_ignoresymlinks': False,
                                 'fileserver_followsymlinks': False,
                                 'file_ignore_regex': False,
                                 'file_ignore_glob': False}):
            ret = roots.dir_list({'saltenv': 'base'})
            self.assertIn('empty_dir', ret)

    def test_symlink_list(self):
        with patch.dict(roots.__opts__, {'file_roots': self.master_opts['file_roots'],
                         'fileserver_ignoresymlinks': False,
                         'fileserver_followsymlinks': False,
                         'file_ignore_regex': False,
                         'file_ignore_glob': False}):
            ret = roots.symlink_list({'saltenv': 'base'})
            self.assertDictEqual(ret, {'dest_sym': 'source_sym'})


class RootsLimitTraversalTest(integration.ModuleCase):

    def setUp(self):
        self.master_opts['file_roots']['base'] = [os.path.join(integration.FILES, 'file', 'base')]

    # @destructiveTest
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

if __name__ == '__main__':
    from integration import run_tests
    run_tests(RootsLimitTraversalTest)
