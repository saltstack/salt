# -*- coding: utf-8 -*-
'''
unit tests for the archive state
'''

# Import Python Libs
import os
import tempfile

# Import Salt Libs
from salt.states import archive

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

ensure_in_syspath('../../')

archive.__opts__ = {}
archive.__salt__ = {}
archive.__env__ = 'test'


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ArchiveTest(TestCase):
    '''
    Validate the archive state
    '''

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

        with patch('os.path.exists', mock_true):
            with patch.dict(archive.__opts__, {'test': False,
                                               'cachedir': tmp_dir}):
                with patch.dict(archive.__salt__, {'file.directory_exists': mock_false,
                                                   'file.file_exists': mock_false,
                                                   'file.makedirs': mock_true,
                                                   'cmd.run_all': mock_run}):
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ArchiveTest)
