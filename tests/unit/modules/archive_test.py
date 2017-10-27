# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.unit.modules.archive_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
from salt.ext.six.moves import zip
ensure_in_syspath('../../')

# Import salt libs
from salt.modules import archive
from salt.exceptions import CommandNotFoundError
from salt.utils import which_bin


class ZipFileMock(MagicMock):
    def __init__(self, files=None, **kwargs):  # pylint: disable=W0231
        if files is None:
            files = ['salt']
        MagicMock.__init__(self, **kwargs)
        self._files = files

    def namelist(self):
        return self._files

# Globals
archive.__salt__ = {}
archive.__pillar__ = {}
archive.__grains__ = {"id": "0"}
archive.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ArchiveTestCase(TestCase):

    @patch('salt.utils.which', lambda exe: exe)
    def test_tar(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.tar(
                '-zcvf', 'foo.tar',
                ['/tmp/something-to-compress-1',
                 '/tmp/something-to-compress-2'],
                template=None
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                ['tar', '-zcvf', 'foo.tar', '/tmp/something-to-compress-1',
                 '/tmp/something-to-compress-2'],
                runas=None, python_shell=False, template=None, cwd=None
            )

        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.tar(
                '-zcvf', 'foo.tar',
                '/tmp/something-to-compress-1,/tmp/something-to-compress-2',
                template=None
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                ['tar', '-zcvf', 'foo.tar', '/tmp/something-to-compress-1',
                 '/tmp/something-to-compress-2'],
                runas=None, python_shell=False, template=None, cwd=None
            )

    @patch('salt.utils.which', lambda exe: None)
    def test_tar_raises_exception_if_not_found(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            self.assertRaises(
                CommandNotFoundError,
                archive.tar,
                'zxvf',
                'foo.tar',
                '/tmp/something-to-compress'
            )
            self.assertFalse(mock.called)

    @patch('salt.utils.which', lambda exe: exe)
    def test_gzip(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.gzip('/tmp/something-to-compress')
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                ['gzip', '/tmp/something-to-compress'],
                runas=None, python_shell=False, template=None
            )

    @patch('salt.utils.which', lambda exe: None)
    def test_gzip_raises_exception_if_not_found(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            self.assertRaises(
                CommandNotFoundError,
                archive.gzip, '/tmp/something-to-compress'
            )
            self.assertFalse(mock.called)

    @patch('salt.utils.which', lambda exe: exe)
    def test_gunzip(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.gunzip('/tmp/something-to-decompress.tar.gz')
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                ['gunzip', '/tmp/something-to-decompress.tar.gz'],
                runas=None, python_shell=False, template=None
            )

    @patch('salt.utils.which', lambda exe: None)
    def test_gunzip_raises_exception_if_not_found(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            self.assertRaises(
                CommandNotFoundError,
                archive.gunzip,
                '/tmp/something-to-decompress.tar.gz'
            )
            self.assertFalse(mock.called)

    @patch('salt.utils.which', lambda exe: exe)
    def test_cmd_zip(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.cmd_zip(
                '/tmp/salt.{{grains.id}}.zip',
                '/tmp/tmpePe8yO,/tmp/tmpLeSw1A',
                template='jinja'
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                ['zip', '-r', '/tmp/salt.{{grains.id}}.zip',
                 '/tmp/tmpePe8yO', '/tmp/tmpLeSw1A'],
                 runas=None, python_shell=False, template='jinja', cwd=None
            )

        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.cmd_zip(
                '/tmp/salt.{{grains.id}}.zip',
                ['/tmp/tmpePe8yO', '/tmp/tmpLeSw1A'],
                template='jinja'
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                ['zip', '-r', '/tmp/salt.{{grains.id}}.zip',
                 '/tmp/tmpePe8yO', '/tmp/tmpLeSw1A'],
                runas=None, python_shell=False, template='jinja', cwd=None
            )

    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('os.path.isdir', MagicMock(return_value=False))
    @patch('zipfile.ZipFile', MagicMock())
    def test_zip(self):
        ret = archive.zip_(
            '/tmp/salt.{{grains.id}}.zip',
            '/tmp/tmpePe8yO,/tmp/tmpLeSw1A',
            template='jinja'
        )
        self.assertEqual(['tmp/tmpePe8yO', 'tmp/tmpLeSw1A'], ret)

    @patch('salt.utils.which', lambda exe: None)
    def test_zip_raises_exception_if_not_found(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            self.assertRaises(
                CommandNotFoundError,
                archive.cmd_zip,
                '/tmp/salt.{{grains.id}}.zip',
                '/tmp/tmpePe8yO,/tmp/tmpLeSw1A',
                template='jinja',
            )
            self.assertFalse(mock.called)

    @patch('salt.utils.which', lambda exe: exe)
    def test_cmd_unzip(self):
        def _get_mock():
            '''
            Create a new MagicMock for each scenario in this test, so that
            assert_called_once_with doesn't complain that the same mock object
            is called more than once.
            '''
            return MagicMock(return_value={'stdout': 'salt',
                                           'stderr': '',
                                           'pid': 12345,
                                           'retcode': 0})

        mock = _get_mock()
        with patch.dict(archive.__salt__, {'cmd.run_all': mock}):
            ret = archive.cmd_unzip(
                '/tmp/salt.{{grains.id}}.zip',
                '/tmp/dest',
                excludes='/tmp/tmpePe8yO,/tmp/tmpLeSw1A',
                template='jinja'
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                ['unzip', '/tmp/salt.{{grains.id}}.zip', '-d', '/tmp/dest',
                 '-x', '/tmp/tmpePe8yO', '/tmp/tmpLeSw1A'],
                output_loglevel='debug',
                python_shell=False,
                redirect_stderr=True,
                runas=None,
                template='jinja'
            )

        mock = _get_mock()
        with patch.dict(archive.__salt__, {'cmd.run_all': mock}):
            ret = archive.cmd_unzip(
                '/tmp/salt.{{grains.id}}.zip',
                '/tmp/dest',
                excludes=['/tmp/tmpePe8yO', '/tmp/tmpLeSw1A'],
                template='jinja'
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                ['unzip', '/tmp/salt.{{grains.id}}.zip', '-d', '/tmp/dest',
                 '-x', '/tmp/tmpePe8yO', '/tmp/tmpLeSw1A'],
                output_loglevel='debug',
                python_shell=False,
                redirect_stderr=True,
                runas=None,
                template='jinja'
            )

        mock = _get_mock()
        with patch.dict(archive.__salt__, {'cmd.run_all': mock}):
            ret = archive.cmd_unzip(
                '/tmp/salt.{{grains.id}}.zip',
                '/tmp/dest',
                excludes='/tmp/tmpePe8yO,/tmp/tmpLeSw1A',
                template='jinja',
                options='-fo'
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                ['unzip', '-fo', '/tmp/salt.{{grains.id}}.zip', '-d',
                 '/tmp/dest', '-x', '/tmp/tmpePe8yO', '/tmp/tmpLeSw1A'],
                output_loglevel='debug',
                python_shell=False,
                redirect_stderr=True,
                runas=None,
                template='jinja'
            )

        mock = _get_mock()
        with patch.dict(archive.__salt__, {'cmd.run_all': mock}):
            ret = archive.cmd_unzip(
                '/tmp/salt.{{grains.id}}.zip',
                '/tmp/dest',
                excludes=['/tmp/tmpePe8yO', '/tmp/tmpLeSw1A'],
                template='jinja',
                options='-fo'
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                ['unzip', '-fo', '/tmp/salt.{{grains.id}}.zip', '-d',
                 '/tmp/dest', '-x', '/tmp/tmpePe8yO', '/tmp/tmpLeSw1A'],
                output_loglevel='debug',
                python_shell=False,
                redirect_stderr=True,
                runas=None,
                template='jinja'
            )

        mock = _get_mock()
        with patch.dict(archive.__salt__, {'cmd.run_all': mock}):
            ret = archive.cmd_unzip(
                '/tmp/salt.{{grains.id}}.zip',
                '/tmp/dest',
                excludes=['/tmp/tmpePe8yO', '/tmp/tmpLeSw1A'],
                template='jinja',
                options='-fo',
                password='asdf',
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                ['unzip', '-P', 'asdf', '-fo', '/tmp/salt.{{grains.id}}.zip',
                 '-d', '/tmp/dest', '-x', '/tmp/tmpePe8yO', '/tmp/tmpLeSw1A'],
                output_loglevel='quiet',
                python_shell=False,
                redirect_stderr=True,
                runas=None,
                template='jinja'
            )

    def test_unzip(self):
        mock = ZipFileMock()
        with patch('zipfile.ZipFile', mock):
            ret = archive.unzip(
                '/tmp/salt.{{grains.id}}.zip',
                '/tmp/dest',
                excludes='/tmp/tmpePe8yO,/tmp/tmpLeSw1A',
                template='jinja',
                extract_perms=False
            )
            self.assertEqual(['salt'], ret)

    @patch('salt.utils.which', lambda exe: None)
    def test_unzip_raises_exception_if_not_found(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            self.assertRaises(
                CommandNotFoundError,
                archive.cmd_unzip,
                '/tmp/salt.{{grains.id}}.zip',
                '/tmp/dest',
                excludes='/tmp/tmpePe8yO,/tmp/tmpLeSw1A',
                template='jinja',
            )
            self.assertFalse(mock.called)

    @patch('salt.utils.which', lambda exe: exe)
    def test_rar(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.rar(
                '/tmp/rarfile.rar',
                '/tmp/sourcefile1,/tmp/sourcefile2'
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                ['rar', 'a', '-idp', '/tmp/rarfile.rar',
                 '/tmp/sourcefile1', '/tmp/sourcefile2'],
                runas=None, python_shell=False, template=None, cwd=None
            )

        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.rar(
                '/tmp/rarfile.rar',
                ['/tmp/sourcefile1', '/tmp/sourcefile2']
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                ['rar', 'a', '-idp', '/tmp/rarfile.rar',
                 '/tmp/sourcefile1', '/tmp/sourcefile2'],
                runas=None, python_shell=False, template=None, cwd=None
            )

    @patch('salt.utils.which', lambda exe: None)
    def test_rar_raises_exception_if_not_found(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            self.assertRaises(
                CommandNotFoundError,
                archive.rar,
                '/tmp/rarfile.rar',
                '/tmp/sourcefile1,/tmp/sourcefile2'
            )
            self.assertFalse(mock.called)

    @skipIf(which_bin(('unrar', 'rar')) is None, 'unrar not installed')
    @patch('salt.utils.which', lambda exe: exe[0] if isinstance(exe, (list, tuple)) else exe)
    @patch('salt.utils.which_bin', lambda exe: exe[0] if isinstance(exe, (list, tuple)) else exe)
    def test_unrar(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.unrar(
                '/tmp/rarfile.rar',
                '/home/strongbad/',
                excludes='file_1,file_2'
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                ['unrar', 'x', '-idp', '/tmp/rarfile.rar',
                 '-x', 'file_1', '-x', 'file_2', '/home/strongbad/'],
                runas=None, python_shell=False, template=None
            )

        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.unrar(
                '/tmp/rarfile.rar',
                '/home/strongbad/',
                excludes=['file_1', 'file_2']
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                ['unrar', 'x', '-idp', '/tmp/rarfile.rar',
                 '-x', 'file_1', '-x', 'file_2', '/home/strongbad/'],
                runas=None, python_shell=False, template=None
            )

    @patch('salt.utils.which_bin', lambda exe: None)
    def test_unrar_raises_exception_if_not_found(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            self.assertRaises(
                CommandNotFoundError,
                archive.unrar,
                '/tmp/rarfile.rar',
                '/home/strongbad/',
            )
            self.assertFalse(mock.called)

    @patch('salt.utils.which_bin', lambda exe: exe)
    def test_trim_files(self):
        source = 'file.tar.gz'
        tmp_dir = 'temp'
        files = [
            '\n'.join(['file1'] * 200),
            '\n'.join(['file2'] * 200),
            'this\nthat\nother',
            'this\nthat\nother',
            'this\nthat\nother'
        ]
        trim_opt = [
            True,
            False,
            3,
            1,
            0
        ]
        trim_100 = (['file1'] * 100)
        trim_100.append("List trimmed after 100 files.")
        expected = [
            trim_100,
            ['file2'] * 200,
            ['this', 'that', 'other'],
            ['this', 'List trimmed after 1 files.'],
            ['List trimmed after 0 files.'],
        ]

        for test_files, test_trim_opts, test_expected in zip(files, trim_opt, expected):
            with patch.dict(archive.__salt__, {'cmd.run': MagicMock(return_value=test_files)}):
                ret = archive.unrar(source, tmp_dir, trim_output=test_trim_opts)
                self.assertEqual(ret, test_expected)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ArchiveTestCase, needs_daemon=False)
