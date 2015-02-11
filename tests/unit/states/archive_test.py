# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexander Schwartz <alexander.schwartz@gmx.net>`
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

ensure_in_syspath('../../')

from salt.states import archive as archive

# Globals
archive.__salt__ = {}
archive.__opts__ = {"cachedir": "/tmp", "test": False}
archive.__env__ = 'base'


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ArchiveTestCase(TestCase):

    def setUp(self):
        super(ArchiveTestCase, self).setUp()

    def tearDown(self):
        super(ArchiveTestCase, self).tearDown()

    def test_tar_gnutar(self):
        '''
        Tests the call of extraction with gnutar
        '''
        gnutar = MagicMock(return_value='tar (GNU tar)')
        missing = MagicMock(return_value=False)
        nop = MagicMock(return_value=True)
        run_all = MagicMock(return_value={'retcode': 0, 'stdout': 'stdout', 'stderr': 'stderr'})
        with patch.dict(archive.__salt__, {'cmd.run': gnutar, 'file.directory_exists': missing, 'file.file_exists': missing, 'state.single': nop, 'file.makedirs': nop, 'cmd.run_all': run_all}):
            ret = archive.extracted('/tmp/out', '/tmp/foo.tar.gz', 'tar', tar_options='xvzf', keep=True)
            self.assertEqual(ret['changes']['extracted_files'], 'stdout')

    def test_tar_bsdtar(self):
        '''
        Tests the call of extraction with bsdtar
        '''
        bsdtar = MagicMock(return_value='tar (bsdtar)')
        missing = MagicMock(return_value=False)
        nop = MagicMock(return_value=True)
        run_all = MagicMock(return_value={'retcode': 0, 'stdout': 'stdout', 'stderr': 'stderr'})
        with patch.dict(archive.__salt__, {'cmd.run': bsdtar, 'file.directory_exists': missing, 'file.file_exists': missing, 'state.single': nop, 'file.makedirs': nop, 'cmd.run_all': run_all}):
            ret = archive.extracted('/tmp/out', '/tmp/foo.tar.gz', 'tar', tar_options='xvzf', keep=True)
            self.assertEqual(ret['changes']['extracted_files'], 'stderr')

if __name__ == '__main__':
    from integration import run_tests
    run_tests(ArchiveTestCase, needs_daemon=False)
