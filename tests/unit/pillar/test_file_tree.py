# -*- coding: utf-8 -*-
'''
test for pillar file_tree.py
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import os
import tempfile
import shutil

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock
from tests.support.paths import TMP
from tests.support.helpers import TestsLoggingHandler

# Import Salt Libs
import salt.utils.files
import salt.utils.stringutils
import salt.pillar.file_tree as file_tree


MINION_ID = 'test-host'
NODEGROUP_PATH = os.path.join('nodegroups', 'test-group', 'files')
HOST_PATH = os.path.join('hosts', MINION_ID, 'files')

BASE_PILLAR_CONTENT = {'files': {'hostfile': b'base', 'groupfile': b'base'}}
DEV_PILLAR_CONTENT = {'files': {'hostfile': b'base', 'groupfile': b'dev2',
                                'hostfile1': b'dev1', 'groupfile1': b'dev1',
                                'hostfile2': b'dev2'}}
PARENT_PILLAR_CONTENT = {'files': {'hostfile': b'base', 'groupfile': b'base',
                                   'hostfile2': b'dev2'}}

FILE_DATA = {
    os.path.join('base', HOST_PATH, 'hostfile'): 'base',
    os.path.join('dev1', HOST_PATH, 'hostfile1'): 'dev1',
    os.path.join('dev2', HOST_PATH, 'hostfile2'): 'dev2',
    os.path.join('base', NODEGROUP_PATH, 'groupfile'): 'base',
    os.path.join('dev1', NODEGROUP_PATH, 'groupfile1'): 'dev1',
    os.path.join('dev2', NODEGROUP_PATH, 'groupfile'): 'dev2'  # test merging
}

_CHECK_MINIONS_RETURN = {'minions': [MINION_ID], 'missing': []}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class FileTreePillarTestCase(TestCase, LoaderModuleMockMixin):
    'test file_tree pillar'
    maxDiff = None

    def setup_loader_modules(self):
        self.tmpdir = tempfile.mkdtemp(dir=TMP)
        self.addCleanup(shutil.rmtree, self.tmpdir)
        cachedir = os.path.join(self.tmpdir, 'cachedir')
        os.makedirs(os.path.join(cachedir, 'file_tree'))
        self.pillar_path = self._create_pillar_files()
        return {
            file_tree: {
                '__opts__':  {
                    'cachedir': cachedir,
                    'pillar_roots': {
                        'base':   [os.path.join(self.pillar_path, 'base')],
                        'dev':    [os.path.join(self.pillar_path, 'base'),
                                   os.path.join(self.pillar_path, 'dev1'),
                                   os.path.join(self.pillar_path, 'dev2')
                                   ],
                        'parent': [os.path.join(self.pillar_path, 'base', 'sub1'),
                                   os.path.join(self.pillar_path, 'dev2', 'sub'),
                                   os.path.join(self.pillar_path, 'base', 'sub2'),
                                   ],
                    },
                    'pillarenv': 'base',
                    'nodegroups': {'test-group': [MINION_ID]},
                    'file_buffer_size': 262144,
                    'file_roots': {'base': '', 'dev': '', 'parent': ''},
                    'extension_modules': '',
                    'renderer': 'yaml_jinja',
                    'renderer_blacklist': [],
                    'renderer_whitelist': []
                }
            }
        }

    def _create_pillar_files(self):
        'create files in tempdir'
        pillar_path = os.path.join(self.tmpdir, 'file_tree')
        for filename in FILE_DATA:
            filepath = os.path.join(pillar_path, filename)
            os.makedirs(os.path.dirname(filepath))
            with salt.utils.files.fopen(filepath, 'w') as data_file:
                data_file.write(salt.utils.stringutils.to_str(FILE_DATA[filename]))
        return pillar_path

    def test_absolute_path(self):
        'check file tree is imported correctly with an absolute path'
        absolute_path = os.path.join(self.pillar_path, 'base')
        with patch('salt.utils.minions.CkMinions.check_minions', MagicMock(return_value=_CHECK_MINIONS_RETURN)):
            mypillar = file_tree.ext_pillar(MINION_ID, None, absolute_path)
            self.assertEqual(BASE_PILLAR_CONTENT, mypillar)

            with patch.dict(file_tree.__opts__, {'pillarenv': 'dev'}):
                mypillar = file_tree.ext_pillar(MINION_ID, None, absolute_path)
                self.assertEqual(BASE_PILLAR_CONTENT, mypillar)

    def test_relative_path(self):
        'check file tree is imported correctly with a relative path'
        with patch('salt.utils.minions.CkMinions.check_minions', MagicMock(return_value=_CHECK_MINIONS_RETURN)):
            mypillar = file_tree.ext_pillar(MINION_ID, None, '.')
            self.assertEqual(BASE_PILLAR_CONTENT, mypillar)

            with patch.dict(file_tree.__opts__, {'pillarenv': 'dev'}):
                mypillar = file_tree.ext_pillar(MINION_ID, None, '.')
                self.assertEqual(DEV_PILLAR_CONTENT, mypillar)

    def test_parent_path(self):
        'check if file tree is merged correctly with a .. path'
        with patch('salt.utils.minions.CkMinions.check_minions', MagicMock(return_value=_CHECK_MINIONS_RETURN)):
            with patch.dict(file_tree.__opts__, {'pillarenv': 'parent'}):
                mypillar = file_tree.ext_pillar(MINION_ID, None, '..')
                self.assertEqual(PARENT_PILLAR_CONTENT, mypillar)

    def test_no_pillarenv(self):
        'confirm that file_tree yells when pillarenv is missing for a relative path'
        with patch('salt.utils.minions.CkMinions.check_minions', MagicMock(return_value=_CHECK_MINIONS_RETURN)):
            with patch.dict(file_tree.__opts__, {'pillarenv': None}):
                with TestsLoggingHandler() as handler:
                    mypillar = file_tree.ext_pillar(MINION_ID, None, '.')
                    self.assertEqual({}, mypillar)

                    for message in handler.messages:
                        if message.startswith('ERROR:') and 'pillarenv is not set' in message:
                            break
                    else:
                        raise AssertionError('Did not find error message')
