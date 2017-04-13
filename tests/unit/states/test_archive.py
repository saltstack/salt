# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexander Schwartz <alexander.schwartz@gmx.net>`
'''

# Import python libs
from __future__ import absolute_import
import os

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.paths import TMP
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt Libs
import salt.states.archive as archive
from salt.ext.six.moves import zip  # pylint: disable=import-error,redefined-builtin


def _isfile_side_effect(path):
    '''
    MagicMock side_effect for os.path.isfile(). We don't want to use dict.get
    here because we want the test to fail if there's a path we haven't
    accounted for, so that we can add it.

    NOTE: This may fall over on some platforms if /usr/bin/tar does not exist.
    If so, just add an entry in the dictionary for the path being used for tar.
    '''
    return {
        '/tmp/foo.tar.gz': True,
        '/tmp/out': False,
        '/usr/bin/tar': True,
        '/bin/tar': True,
        '/tmp/test_extracted_tar': False,
    }[path]


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ArchiveTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {
            archive: {
                '__grains__': {'os': 'FooOS!'},
                '__opts__': {'cachedir': '/tmp',
                             'test': False,
                             'hash_type': 'sha256'},
                '__env__': 'test'
            }
        }

    def test_extracted_tar(self):
        '''
        archive.extracted tar options
        '''

        source = '/tmp/foo.tar.gz'
        tmp_dir = '/tmp/test_extracted_tar'
        test_tar_opts = [
            '--no-anchored foo',
            'v -p --opt',
            '-v -p',
            '--long-opt -z',
            'z -v -weird-long-opt arg',
        ]
        ret_tar_opts = [
            ['tar', 'x', '--no-anchored', 'foo', '-f'],
            ['tar', 'xv', '-p', '--opt', '-f'],
            ['tar', 'x', '-v', '-p', '-f'],
            ['tar', 'x', '--long-opt', '-z', '-f'],
            ['tar', 'xz', '-v', '-weird-long-opt', 'arg', '-f'],
        ]

        mock_true = MagicMock(return_value=True)
        mock_false = MagicMock(return_value=False)
        ret = {'stdout': ['cheese', 'ham', 'saltines'], 'stderr': 'biscuits', 'retcode': '31337', 'pid': '1337'}
        mock_run = MagicMock(return_value=ret)
        mock_source_list = MagicMock(return_value=(source, None))
        state_single_mock = MagicMock(return_value={'local': {'result': True}})
        list_mock = MagicMock(return_value={
            'dirs': [],
            'files': ['cheese', 'saltines'],
            'links': ['ham'],
            'top_level_dirs': [],
            'top_level_files': ['cheese', 'saltines'],
            'top_level_links': ['ham'],
        })
        isfile_mock = MagicMock(side_effect=_isfile_side_effect)

        with patch.dict(archive.__opts__, {'test': False,
                                           'cachedir': tmp_dir,
                                           'hash_type': 'sha256'}):
            with patch.dict(archive.__salt__, {'file.directory_exists': mock_false,
                                               'file.file_exists': mock_false,
                                               'state.single': state_single_mock,
                                               'file.makedirs': mock_true,
                                               'cmd.run_all': mock_run,
                                               'archive.list': list_mock,
                                               'file.source_list': mock_source_list}):
                with patch.object(os.path, 'isfile', isfile_mock):
                    for test_opts, ret_opts in zip(test_tar_opts, ret_tar_opts):
                        ret = archive.extracted(tmp_dir,
                                                source,
                                                options=test_opts,
                                                enforce_toplevel=False)
                        ret_opts.append(source)
                        mock_run.assert_called_with(ret_opts,
                                                    cwd=tmp_dir + os.sep,
                                                    python_shell=False)

    def test_tar_gnutar(self):
        '''
        Tests the call of extraction with gnutar
        '''
        gnutar = MagicMock(return_value='tar (GNU tar)')
        source = '/tmp/foo.tar.gz'
        mock_false = MagicMock(return_value=False)
        mock_true = MagicMock(return_value=True)
        state_single_mock = MagicMock(return_value={'local': {'result': True}})
        run_all = MagicMock(return_value={'retcode': 0, 'stdout': 'stdout', 'stderr': 'stderr'})
        mock_source_list = MagicMock(return_value=(source, None))
        list_mock = MagicMock(return_value={
            'dirs': [],
            'files': ['stdout'],
            'links': [],
            'top_level_dirs': [],
            'top_level_files': ['stdout'],
            'top_level_links': [],
        })
        isfile_mock = MagicMock(side_effect=_isfile_side_effect)

        with patch.dict(archive.__salt__, {'cmd.run': gnutar,
                                           'file.directory_exists': mock_false,
                                           'file.file_exists': mock_false,
                                           'state.single': state_single_mock,
                                           'file.makedirs': mock_true,
                                           'cmd.run_all': run_all,
                                           'archive.list': list_mock,
                                           'file.source_list': mock_source_list}):
            with patch.object(os.path, 'isfile', isfile_mock):
                ret = archive.extracted('/tmp/out',
                                        source,
                                        options='xvzf',
                                        enforce_toplevel=False,
                                        keep=True)
                self.assertEqual(ret['changes']['extracted_files'], 'stdout')

    def test_tar_bsdtar(self):
        '''
        Tests the call of extraction with bsdtar
        '''
        bsdtar = MagicMock(return_value='tar (bsdtar)')
        source = '/tmp/foo.tar.gz'
        mock_false = MagicMock(return_value=False)
        mock_true = MagicMock(return_value=True)
        state_single_mock = MagicMock(return_value={'local': {'result': True}})
        run_all = MagicMock(return_value={'retcode': 0, 'stdout': 'stdout', 'stderr': 'stderr'})
        mock_source_list = MagicMock(return_value=(source, None))
        list_mock = MagicMock(return_value={
            'dirs': [],
            'files': ['stderr'],
            'links': [],
            'top_level_dirs': [],
            'top_level_files': ['stderr'],
            'top_level_links': [],
        })
        isfile_mock = MagicMock(side_effect=_isfile_side_effect)

        with patch.dict(archive.__salt__, {'cmd.run': bsdtar,
                                           'file.directory_exists': mock_false,
                                           'file.file_exists': mock_false,
                                           'state.single': state_single_mock,
                                           'file.makedirs': mock_true,
                                           'cmd.run_all': run_all,
                                           'archive.list': list_mock,
                                           'file.source_list': mock_source_list}):
            with patch.object(os.path, 'isfile', isfile_mock):
                ret = archive.extracted('/tmp/out',
                                        source,
                                        options='xvzf',
                                        enforce_toplevel=False,
                                        keep=True)
                self.assertEqual(ret['changes']['extracted_files'], 'stderr')
