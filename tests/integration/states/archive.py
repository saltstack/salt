# -*- coding: utf-8 -*-
'''
Tests for the file state
'''
# Import python libs
from __future__ import absolute_import
import os
import shutil

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils

STATE_DIR = os.path.join(integration.FILES, 'file', 'base')
if salt.utils.is_windows():
    ARCHIVE_DIR = os.path.join("c:/", "tmp")
else:
    ARCHIVE_DIR = '/tmp/archive/'

#local tar file
LOCAL_ARCHIVE_TAR_SOURCE = 'salt://custom.tar.gz'
LOCAL_UNTAR_FILE = os.path.join(ARCHIVE_DIR, 'custom', 'README')

#external sources. Only external sources verify source_hash.
#Therefore need to keep to verify source_hash test
ARCHIVE_TAR_SOURCE = 'https://github.com/downloads/Graylog2/'\
                     'graylog2-server/graylog2-server-0.9.6p1.tar.gz'
UNTAR_FILE = ARCHIVE_DIR + 'graylog2-server-0.9.6p1/README'
ARCHIVE_TAR_HASH = 'md5=499ae16dcae71eeb7c3a30c75ea7a1a6'


class ArchiveTest(integration.ModuleCase,
                  integration.SaltReturnAssertsMixIn):
    '''
    Validate the archive state
    '''
    def _check_ext_remove(self, dir, file):
        '''
        function to check if file was extracted
        and remove the directory.
        '''

        #check to see if it extracted
        check_dir = os.path.isfile(file)
        self.assertTrue(check_dir)

        #wipe away dir. Can't do this in teardown
        #because it needs to be wiped before each test
        shutil.rmtree(dir)

    def test_archive_extracted_skip_verify(self):
        '''
        test archive.extracted with skip_verify
        '''
        ret = self.run_state('archive.extracted', name=ARCHIVE_DIR,
                             source=LOCAL_ARCHIVE_TAR_SOURCE, archive_format='tar',
                             skip_verify=True)
        self.assertSaltTrueReturn(ret)

        self._check_ext_remove(ARCHIVE_DIR, LOCAL_UNTAR_FILE)

    def test_archive_extracted_with_source_hash(self):
        '''
        test archive.extracted without skip_verify
        only external resources work to check to
        ensure source_hash is verified correctly
        '''
        ret = self.run_state('archive.extracted', name=ARCHIVE_DIR,
                             source=ARCHIVE_TAR_SOURCE, archive_format='tar',
                             source_hash=ARCHIVE_TAR_HASH)
        self.assertSaltTrueReturn(ret)

        self._check_ext_remove(ARCHIVE_DIR, UNTAR_FILE)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ArchiveTest)
