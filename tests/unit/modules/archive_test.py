# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.unit.modules.archive_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
ensure_in_syspath('../../')

# Import salt libs
from salt.modules import archive
from salt.exceptions import CommandNotFoundError

archive.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ArchiveTestCase(TestCase):

    @patch('salt.utils.which', lambda exe: exe)
    def test_tar(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.tar(
                'zcvf', 'foo.tar',
                ['/tmp/something-to-compress-1',
                 '/tmp/something-to-compress-2'],
                cwd=None, template=None
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                'tar -zcvf foo.tar /tmp/something-to-compress-1 '
                '/tmp/something-to-compress-2',
                cwd=None,
                template=None
            )

        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.tar(
                'zcvf', 'foo.tar',
                '/tmp/something-to-compress-1,/tmp/something-to-compress-2',
                cwd=None, template=None
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                'tar -zcvf foo.tar /tmp/something-to-compress-1 '
                '/tmp/something-to-compress-2',
                cwd=None,
                template=None
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
                'gzip /tmp/something-to-compress',
                template=None
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
                'gunzip /tmp/something-to-decompress.tar.gz',
                template=None
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
    def test_zip(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.zip_(
                '/tmp/salt.{{grains.id}}.zip',
                '/tmp/tmpePe8yO,/tmp/tmpLeSw1A',
                template='jinja'
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                'zip /tmp/salt.{{grains.id}}.zip '
                '/tmp/tmpePe8yO /tmp/tmpLeSw1A',
                template='jinja'
            )

        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.zip_(
                '/tmp/salt.{{grains.id}}.zip',
                ['/tmp/tmpePe8yO', '/tmp/tmpLeSw1A'],
                template='jinja'
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                'zip /tmp/salt.{{grains.id}}.zip '
                '/tmp/tmpePe8yO /tmp/tmpLeSw1A',
                template='jinja'
            )

    @patch('salt.utils.which', lambda exe: None)
    def test_zip_raises_exception_if_not_found(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            self.assertRaises(
                CommandNotFoundError,
                archive.zip_,
                '/tmp/salt.{{grains.id}}.zip',
                '/tmp/tmpePe8yO,/tmp/tmpLeSw1A',
                template='jinja',
            )
            self.assertFalse(mock.called)

    @patch('salt.utils.which', lambda exe: exe)
    def test_unzip(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.unzip(
                '/tmp/salt.{{grains.id}}.zip',
                '/tmp/dest',
                excludes='/tmp/tmpePe8yO,/tmp/tmpLeSw1A',
                template='jinja'
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                'unzip /tmp/salt.{{grains.id}}.zip -d /tmp/dest '
                '-x /tmp/tmpePe8yO /tmp/tmpLeSw1A',
                template='jinja'
            )

        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.unzip(
                '/tmp/salt.{{grains.id}}.zip',
                '/tmp/dest',
                excludes=['/tmp/tmpePe8yO', '/tmp/tmpLeSw1A'],
                template='jinja'
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                'unzip /tmp/salt.{{grains.id}}.zip -d /tmp/dest '
                '-x /tmp/tmpePe8yO /tmp/tmpLeSw1A',
                template='jinja'
            )

        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.unzip(
                '/tmp/salt.{{grains.id}}.zip',
                '/tmp/dest',
                excludes='/tmp/tmpePe8yO,/tmp/tmpLeSw1A',
                template='jinja',
                options='fo'
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                'unzip -fo /tmp/salt.{{grains.id}}.zip -d /tmp/dest '
                '-x /tmp/tmpePe8yO /tmp/tmpLeSw1A',
                template='jinja',
            )

        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.unzip(
                '/tmp/salt.{{grains.id}}.zip',
                '/tmp/dest',
                excludes=['/tmp/tmpePe8yO', '/tmp/tmpLeSw1A'],
                template='jinja',
                options='fo'
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                'unzip -fo /tmp/salt.{{grains.id}}.zip -d /tmp/dest '
                '-x /tmp/tmpePe8yO /tmp/tmpLeSw1A',
                template='jinja'
            )

    @patch('salt.utils.which', lambda exe: None)
    def test_unzip_raises_exception_if_not_found(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            self.assertRaises(
                CommandNotFoundError,
                archive.unzip,
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
                'rar a -idp /tmp/rarfile.rar '
                '/tmp/sourcefile1 /tmp/sourcefile2',
                template=None
            )

        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.rar(
                '/tmp/rarfile.rar',
                ['/tmp/sourcefile1', '/tmp/sourcefile2']
            )
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                'rar a -idp /tmp/rarfile.rar '
                '/tmp/sourcefile1 /tmp/sourcefile2',
                template=None
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

    @patch('salt.utils.which', lambda exe: exe)
    @patch('salt.utils.which_bin', lambda exe: exe)
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
                'unrar x -idp /tmp/rarfile.rar '
                '-x file_1 -x file_2 /home/strongbad/',
                template=None
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
                'unrar x -idp /tmp/rarfile.rar '
                '-x file_1 -x file_2 /home/strongbad/',
                template=None
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ArchiveTestCase, needs_daemon=False)
