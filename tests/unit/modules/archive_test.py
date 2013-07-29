# -*- coding: utf-8 -*-
'''
    tests.unit.modules.archive_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
from salt.modules import archive

# Import 3rd party libs
try:
    from mock import MagicMock, patch
    HAS_MOCK = True
except ImportError:
    HAS_MOCK = False

archive.__salt__ = {}


@skipIf(HAS_MOCK is False, 'mock python module is unavailable')
@patch('salt.utils.which', lambda exe: exe)
class ArchiveTestCase(TestCase):
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

    def test_gzip(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.gzip('/tmp/something-to-compress')
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                'gzip /tmp/something-to-compress',
                template=None
            )

    def test_gunzip(self):
        mock = MagicMock(return_value='salt')
        with patch.dict(archive.__salt__, {'cmd.run': mock}):
            ret = archive.gunzip('/tmp/something-to-decompress.tar.gz')
            self.assertEqual(['salt'], ret)
            mock.assert_called_once_with(
                'gunzip /tmp/something-to-decompress.tar.gz',
                template=None
            )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ArchiveTestCase, needs_daemon=False)
