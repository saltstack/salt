# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexander Schwartz <alexander.schwartz@gmx.net>`
'''

# Import python libs
from __future__ import absolute_import
import os
import tempfile

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import archive as archive
from salt.ext.six.moves import zip  # pylint: disable=import-error,redefined-builtin

# Globals
archive.__salt__ = {}
archive.__opts__ = {"cachedir": "/tmp", "test": False}
archive.__env__ = 'test'


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ArchiveTestCase(TestCase):

    def setUp(self):
        super(ArchiveTestCase, self).setUp()

    def tearDown(self):
        super(ArchiveTestCase, self).tearDown()

    def test_extracted_tar(self):
        '''
        archive.extracted tar options
        '''

        source = 'file.tar.gz'
        tmp_dir = os.path.join(tempfile.gettempdir(), 'test_archive', '')
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
        ret = {'stdout': ['saltines', 'cheese'], 'stderr': 'biscuits', 'retcode': '31337', 'pid': '1337'}
        mock_run = MagicMock(return_value=ret)
        mock_source_list = MagicMock(return_value=source)

        with patch('os.path.exists', mock_true):
            with patch.dict(archive.__opts__, {'test': False,
                                               'cachedir': tmp_dir}):
                with patch.dict(archive.__salt__, {'file.directory_exists': mock_false,
                                                   'file.file_exists': mock_false,
                                                   'file.makedirs': mock_true,
                                                   'cmd.run_all': mock_run,
                                                   'file.source_list': mock_source_list}):
                    filename = os.path.join(
                        tmp_dir,
                        'files/test/_tmp_test_archive_.tar'
                    )
                    for test_opts, ret_opts in zip(test_tar_opts, ret_tar_opts):
                        ret = archive.extracted(tmp_dir,
                                                source,
                                                'tar',
                                                tar_options=test_opts)
                        ret_opts.append(filename)
                        mock_run.assert_called_with(ret_opts, cwd=tmp_dir, python_shell=False)

    def test_tar_gnutar(self):
        '''
        Tests the call of extraction with gnutar
        '''
        gnutar = MagicMock(return_value='tar (GNU tar)')
        source = 'GNU tar'
        missing = MagicMock(return_value=False)
        nop = MagicMock(return_value=True)
        run_all = MagicMock(return_value={'retcode': 0, 'stdout': 'stdout', 'stderr': 'stderr'})
        mock_source_list = MagicMock(return_value=source)

        with patch.dict(archive.__salt__, {'cmd.run': gnutar,
                                           'file.directory_exists': missing,
                                           'file.file_exists': missing,
                                           'state.single': nop,
                                           'file.makedirs': nop,
                                           'cmd.run_all': run_all,
                                           'file.source_list': mock_source_list}):
            ret = archive.extracted('/tmp/out', '/tmp/foo.tar.gz', 'tar', tar_options='xvzf', keep=True)
            self.assertEqual(ret['changes']['extracted_files'], 'stdout')

    def test_tar_bsdtar(self):
        '''
        Tests the call of extraction with bsdtar
        '''
        bsdtar = MagicMock(return_value='tar (bsdtar)')
        source = 'bsdtar'
        missing = MagicMock(return_value=False)
        nop = MagicMock(return_value=True)
        run_all = MagicMock(return_value={'retcode': 0, 'stdout': 'stdout', 'stderr': 'stderr'})
        mock_source_list = MagicMock(return_value=source)

        with patch.dict(archive.__salt__, {'cmd.run': bsdtar,
                                           'file.directory_exists': missing,
                                           'file.file_exists': missing,
                                           'state.single': nop,
                                           'file.makedirs': nop,
                                           'cmd.run_all': run_all,
                                           'file.source_list': mock_source_list}):
            ret = archive.extracted('/tmp/out', '/tmp/foo.tar.gz', 'tar', tar_options='xvzf', keep=True)
            self.assertEqual(ret['changes']['extracted_files'], 'stderr')

if __name__ == '__main__':
    from integration import run_tests
    run_tests(ArchiveTestCase, needs_daemon=False)
