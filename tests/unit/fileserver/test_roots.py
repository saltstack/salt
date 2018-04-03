# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import copy
import os
import tempfile

# Import Salt Testing libs
from tests.integration import AdaptedConfigurationTestCaseMixin
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.paths import FILES, TMP, TMP_STATE_TREE
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, NO_MOCK, NO_MOCK_REASON

# Import Salt libs
import salt.fileserver.roots as roots
import salt.fileclient
import salt.utils.files
import salt.utils.platform

try:
    import win32file
except ImportError:
    pass

UNICODE_FILENAME = 'питон.txt'
UNICODE_DIRNAME = UNICODE_ENVNAME = 'соль'


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RootsTest(TestCase, AdaptedConfigurationTestCaseMixin, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        self.tmp_cachedir = tempfile.mkdtemp(dir=TMP)
        self.opts = self.get_temp_config('master')
        self.opts['cachedir'] = self.tmp_cachedir
        empty_dir = os.path.join(TMP_STATE_TREE, 'empty_dir')
        if not os.path.isdir(empty_dir):
            os.makedirs(empty_dir)
        return {roots: {'__opts__': self.opts}}

    @classmethod
    def setUpClass(cls):
        '''
        Create special file_roots for symlink test on Windows
        '''
        if salt.utils.platform.is_windows():
            root_dir = tempfile.mkdtemp(dir=TMP)
            source_sym = os.path.join(root_dir, 'source_sym')
            with salt.utils.files.fopen(source_sym, 'w') as fp_:
                fp_.write('hello world!\n')
            cwd = os.getcwd()
            try:
                os.chdir(root_dir)
                win32file.CreateSymbolicLink('dest_sym', 'source_sym', 0)
            finally:
                os.chdir(cwd)
            cls.test_symlink_list_file_roots = {'base': [root_dir]}
        else:
            cls.test_symlink_list_file_roots = None

    @classmethod
    def tearDownClass(cls):
        '''
        Remove special file_roots for symlink test
        '''
        if salt.utils.platform.is_windows():
            try:
                salt.utils.files.rm_rf(cls.test_symlink_list_file_roots['base'][0])
            except OSError:
                pass

    def tearDown(self):
        del self.opts

    def test_file_list(self):
        ret = roots.file_list({'saltenv': 'base'})
        self.assertIn('testfile', ret)
        self.assertIn(UNICODE_FILENAME, ret)

    def test_find_file(self):
        ret = roots.find_file('testfile')
        self.assertEqual('testfile', ret['rel'])

        full_path_to_file = os.path.join(FILES, 'file', 'base', 'testfile')
        self.assertEqual(full_path_to_file, ret['path'])

    def test_serve_file(self):
        with patch.dict(roots.__opts__, {'file_buffer_size': 262144}):
            load = {'saltenv': 'base',
                    'path': os.path.join(FILES, 'file', 'base', 'testfile'),
                    'loc': 0
                    }
            fnd = {'path': os.path.join(FILES, 'file', 'base', 'testfile'),
                   'rel': 'testfile'}
            ret = roots.serve_file(load, fnd)

            data = 'Scene 24\n\n \n  OLD MAN:  Ah, hee he he ha!\n  ' \
                   'ARTHUR:  And this enchanter of whom you speak, he ' \
                   'has seen the grail?\n  OLD MAN:  Ha ha he he he ' \
                   'he!\n  ARTHUR:  Where does he live?  Old man, where ' \
                   'does he live?\n  OLD MAN:  He knows of a cave, a ' \
                   'cave which no man has entered.\n  ARTHUR:  And the ' \
                   'Grail... The Grail is there?\n  OLD MAN:  Very much ' \
                   'danger, for beyond the cave lies the Gorge\n      ' \
                   'of Eternal Peril, which no man has ever crossed.\n  ' \
                   'ARTHUR:  But the Grail!  Where is the Grail!?\n  ' \
                   'OLD MAN:  Seek you the Bridge of Death.\n  ARTHUR:  ' \
                   'The Bridge of Death, which leads to the Grail?\n  ' \
                   'OLD MAN:  Hee hee ha ha!\n\n'
            if salt.utils.platform.is_windows():
                data = 'Scene 24\r\n\r\n \r\n  OLD MAN:  Ah, hee he he ' \
                       'ha!\r\n  ARTHUR:  And this enchanter of whom you ' \
                       'speak, he has seen the grail?\r\n  OLD MAN:  Ha ha ' \
                       'he he he he!\r\n  ARTHUR:  Where does he live?  Old ' \
                       'man, where does he live?\r\n  OLD MAN:  He knows of ' \
                       'a cave, a cave which no man has entered.\r\n  ' \
                       'ARTHUR:  And the Grail... The Grail is there?\r\n  ' \
                       'OLD MAN:  Very much danger, for beyond the cave lies ' \
                       'the Gorge\r\n      of Eternal Peril, which no man ' \
                       'has ever crossed.\r\n  ARTHUR:  But the Grail!  ' \
                       'Where is the Grail!?\r\n  OLD MAN:  Seek you the ' \
                       'Bridge of Death.\r\n  ARTHUR:  The Bridge of Death, ' \
                       'which leads to the Grail?\r\n  OLD MAN:  Hee hee ha ' \
                       'ha!\r\n\r\n'

            self.assertDictEqual(
                ret,
                {'data': data,
                 'dest': 'testfile'})

    def test_envs(self):
        opts = {'file_roots': copy.copy(self.opts['file_roots'])}
        opts['file_roots'][UNICODE_ENVNAME] = opts['file_roots']['base']
        with patch.dict(roots.__opts__, opts):
            ret = roots.envs()
        self.assertIn('base', ret)
        self.assertIn(UNICODE_ENVNAME, ret)

    def test_file_hash(self):
        load = {
                'saltenv': 'base',
                'path': os.path.join(FILES, 'file', 'base', 'testfile'),
                }
        fnd = {
            'path': os.path.join(FILES, 'file', 'base', 'testfile'),
            'rel': 'testfile'
        }
        ret = roots.file_hash(load, fnd)

        # Hashes are different in Windows. May be how git translates line
        # endings
        hsum = 'baba5791276eb99a7cc498fb1acfbc3b4bd96d24cfe984b4ed6b5be2418731df'
        if salt.utils.platform.is_windows():
            hsum = '754aa260e1f3e70f43aaf92149c7d1bad37f708c53304c37660e628d7553f687'

        self.assertDictEqual(
            ret,
            {
                'hsum': hsum,
                'hash_type': 'sha256'
            }
        )

    def test_file_list_emptydirs(self):
        ret = roots.file_list_emptydirs({'saltenv': 'base'})
        self.assertIn('empty_dir', ret)

    def test_dir_list(self):
        ret = roots.dir_list({'saltenv': 'base'})
        self.assertIn('empty_dir', ret)
        self.assertIn(UNICODE_DIRNAME, ret)

    def test_symlink_list(self):
        if self.test_symlink_list_file_roots:
            self.opts['file_roots'] = self.test_symlink_list_file_roots
        ret = roots.symlink_list({'saltenv': 'base'})
        self.assertDictEqual(ret, {'dest_sym': 'source_sym'})


class RootsLimitTraversalTest(TestCase, AdaptedConfigurationTestCaseMixin):

    def test_limit_traversal(self):
        '''
        1) Set up a deep directory structure
        2) Enable the configuration option 'fileserver_limit_traversal'
        3) Ensure that we can find SLS files in a directory so long as there is
           an SLS file in a directory above.
        4) Ensure that we cannot find an SLS file in a directory that does not
           have an SLS file in a directory above.

        '''
        file_client_opts = self.get_temp_config('master')
        file_client_opts['fileserver_limit_traversal'] = True

        ret = salt.fileclient.Client(file_client_opts).list_states('base')
        self.assertIn('test_deep.test', ret)
        self.assertIn('test_deep.a.test', ret)
        self.assertNotIn('test_deep.b.2.test', ret)
