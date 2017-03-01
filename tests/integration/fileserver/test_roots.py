# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Testing libs
import tests.integration as integration
from tests.support.unit import skipIf
from tests.support.mock import patch, NO_MOCK, NO_MOCK_REASON

# Import salt libs
from salt.fileserver import roots
from salt import fileclient
import salt.utils

roots.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RootsTest(integration.ModuleCase):

    def setUp(self):
        if integration.TMP_STATE_TREE not in self.master_opts['file_roots']['base']:
            # We need to setup the file roots
            self.master_opts['file_roots']['base'] = [os.path.join(integration.FILES, 'file', 'base')]

    def test_file_list(self):
        with patch.dict(roots.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'file_roots': self.master_opts['file_roots'],
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
            if salt.utils.is_windows():
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

            # Hashes are different in Windows. May be how git translates line
            # endings
            hsum = 'baba5791276eb99a7cc498fb1acfbc3b4bd96d24cfe984b4ed6b5be2418731df'
            if salt.utils.is_windows():
                hsum = '754aa260e1f3e70f43aaf92149c7d1bad37f708c53304c37660e628d7553f687'

            self.assertDictEqual(
                ret,
                {
                    'hsum': hsum,
                    'hash_type': 'sha256'
                }
            )

    def test_file_list_emptydirs(self):
        if integration.TMP_STATE_TREE not in self.master_opts['file_roots']['base']:
            self.skipTest('This test fails when using tests/runtests.py. salt-runtests will be available soon.')

        empty_dir = os.path.join(integration.TMP_STATE_TREE, 'empty_dir')
        if not os.path.isdir(empty_dir):
            # There's no use creating the empty-directory ourselves at this
            # point, the minions have already synced, it wouldn't get pushed to
            # them
            self.skipTest('This test fails when using tests/runtests.py. salt-runtests will be available soon.')

        with patch.dict(roots.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'file_roots': self.master_opts['file_roots'],
                                         'fileserver_ignoresymlinks': False,
                                         'fileserver_followsymlinks': False,
                                         'file_ignore_regex': False,
                                         'file_ignore_glob': False}):
            ret = roots.file_list_emptydirs({'saltenv': 'base'})
            self.assertIn('empty_dir', ret)

    def test_dir_list(self):
        empty_dir = os.path.join(integration.TMP_STATE_TREE, 'empty_dir')
        if integration.TMP_STATE_TREE not in self.master_opts['file_roots']['base']:
            self.skipTest('This test fails when using tests/runtests.py. salt-runtests will be available soon.')

        empty_dir = os.path.join(integration.TMP_STATE_TREE, 'empty_dir')
        if not os.path.isdir(empty_dir):
            # There's no use creating the empty-directory ourselves at this
            # point, the minions have already synced, it wouldn't get pushed to
            # them
            self.skipTest('This test fails when using tests/runtests.py. salt-runtests will be available soon.')

        with patch.dict(roots.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'file_roots': self.master_opts['file_roots'],
                                         'fileserver_ignoresymlinks': False,
                                         'fileserver_followsymlinks': False,
                                         'file_ignore_regex': False,
                                         'file_ignore_glob': False}):
            ret = roots.dir_list({'saltenv': 'base'})
            self.assertIn('empty_dir', ret)

    # Git doesn't handle symlinks in Windows. See the thread below:
    # http://stackoverflow.com/questions/5917249/git-symlinks-in-windows
    @skipIf(salt.utils.is_windows(),
            'Git doesn\'t handle symlinks properly on Windows')
    def test_symlink_list(self):
        with patch.dict(roots.__opts__, {'cachedir': self.master_opts['cachedir'],
                                         'file_roots': self.master_opts['file_roots'],
                                         'fileserver_ignoresymlinks': False,
                                         'fileserver_followsymlinks': False,
                                         'file_ignore_regex': False,
                                         'file_ignore_glob': False}):
            ret = roots.symlink_list({'saltenv': 'base'})
            self.assertDictEqual(ret, {'dest_sym': 'source_sym'})


class RootsLimitTraversalTest(integration.ModuleCase):

    # @destructiveTest
    def test_limit_traversal(self):
        '''
        1) Set up a deep directory structure
        2) Enable the configuration option for 'limit_directory_traversal'
        3) Ensure that we can find SLS files in a directory so long as there is an SLS file in a directory above.
        4) Ensure that we cannot find an SLS file in a directory that does not have an SLS file in a directory above.
        '''
        file_client_opts = self.get_config('master', from_scratch=True)
        file_client_opts['fileserver_limit_traversal'] = True

        ret = fileclient.Client(file_client_opts).list_states('base')
        self.assertIn('test_deep.test', ret)
        self.assertIn('test_deep.a.test', ret)
        self.assertNotIn('test_deep.b.2.test', ret)
