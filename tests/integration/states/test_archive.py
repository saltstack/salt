# -*- coding: utf-8 -*-
'''
Tests for the archive state
'''
# Import python libs
from __future__ import absolute_import
import errno
import logging
import os

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import skip_if_not_root, Webserver
from tests.support.mixins import SaltReturnAssertsMixin

# Import salt libs
import salt.utils

# Setup logging
log = logging.getLogger(__name__)

if salt.utils.is_windows():
    ARCHIVE_DIR = os.path.join('c:/', 'tmp')
else:
    ARCHIVE_DIR = '/tmp/archive'

UNTAR_FILE = os.path.join(ARCHIVE_DIR, 'custom/README')
ARCHIVE_TAR_HASH = 'md5=7643861ac07c30fe7d2310e9f25ca514'


class ArchiveTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the archive state
    '''
    @classmethod
    def setUpClass(cls):
        cls.webserver = Webserver()
        cls.webserver.start()
        cls.archive_tar_source = cls.webserver.url('custom.tar.gz')

    @classmethod
    def tearDownClass(cls):
        cls.webserver.stop()

    def setUp(self):
        self._clear_archive_dir()

    def tearDown(self):
        self._clear_archive_dir()

    @staticmethod
    def _clear_archive_dir():
        try:
            salt.utils.rm_rf(ARCHIVE_DIR)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise

    def _check_extracted(self, path):
        '''
        function to check if file was extracted
        '''
        log.debug('Checking for extracted file: %s', path)
        self.assertTrue(os.path.isfile(path))

    def test_archive_extracted_skip_verify(self):
        '''
        test archive.extracted with skip_verify
        '''
        ret = self.run_state('archive.extracted', name=ARCHIVE_DIR,
                             source=self.archive_tar_source, archive_format='tar',
                             skip_verify=True)
        log.debug('ret = %s', ret)
        if 'Timeout' in ret:
            self.skipTest('Timeout talking to local tornado server.')
        self.assertSaltTrueReturn(ret)

        self._check_extracted(UNTAR_FILE)

    def test_archive_extracted_with_source_hash(self):
        '''
        test archive.extracted without skip_verify
        only external resources work to check to
        ensure source_hash is verified correctly
        '''
        ret = self.run_state('archive.extracted', name=ARCHIVE_DIR,
                             source=self.archive_tar_source, archive_format='tar',
                             source_hash=ARCHIVE_TAR_HASH)
        log.debug('ret = %s', ret)
        if 'Timeout' in ret:
            self.skipTest('Timeout talking to local tornado server.')

        self.assertSaltTrueReturn(ret)

        self._check_extracted(UNTAR_FILE)

    @skip_if_not_root
    def test_archive_extracted_with_root_user_and_group(self):
        '''
        test archive.extracted with user and group set to "root"
        '''
        ret = self.run_state('archive.extracted', name=ARCHIVE_DIR,
                             source=self.archive_tar_source, archive_format='tar',
                             source_hash=ARCHIVE_TAR_HASH,
                             user='root', group='root')
        log.debug('ret = %s', ret)
        if 'Timeout' in ret:
            self.skipTest('Timeout talking to local tornado server.')

        self.assertSaltTrueReturn(ret)

        self._check_extracted(UNTAR_FILE)

    def test_archive_extracted_with_strip_in_options(self):
        '''
        test archive.extracted with --strip in options
        '''
        ret = self.run_state('archive.extracted', name=ARCHIVE_DIR,
                             source=self.archive_tar_source,
                             source_hash=ARCHIVE_TAR_HASH,
                             options='--strip=1',
                             enforce_toplevel=False)
        log.debug('ret = %s', ret)
        if 'Timeout' in ret:
            self.skipTest('Timeout talking to local tornado server.')

        self.assertSaltTrueReturn(ret)

        self._check_extracted(os.path.join(ARCHIVE_DIR, 'README'))

    def test_archive_extracted_with_strip_components_in_options(self):
        '''
        test archive.extracted with --strip-components in options
        '''
        ret = self.run_state('archive.extracted', name=ARCHIVE_DIR,
                             source=self.archive_tar_source,
                             source_hash=ARCHIVE_TAR_HASH,
                             options='--strip-components=1',
                             enforce_toplevel=False)
        log.debug('ret = %s', ret)
        if 'Timeout' in ret:
            self.skipTest('Timeout talking to local tornado server.')

        self.assertSaltTrueReturn(ret)

        self._check_extracted(os.path.join(ARCHIVE_DIR, 'README'))

    def test_archive_extracted_without_archive_format(self):
        '''
        test archive.extracted with no archive_format option
        '''
        ret = self.run_state('archive.extracted', name=ARCHIVE_DIR,
                             source=self.archive_tar_source,
                             source_hash=ARCHIVE_TAR_HASH)
        log.debug('ret = %s', ret)
        if 'Timeout' in ret:
            self.skipTest('Timeout talking to local tornado server.')
        self.assertSaltTrueReturn(ret)

        self._check_extracted(UNTAR_FILE)

    def test_archive_extracted_with_cmd_unzip_false(self):
        '''
        test archive.extracted using use_cmd_unzip argument as false
        '''

        ret = self.run_state('archive.extracted', name=ARCHIVE_DIR,
                             source=self.archive_tar_source,
                             source_hash=ARCHIVE_TAR_HASH,
                             use_cmd_unzip=False,
                             archive_format='tar')
        log.debug('ret = %s', ret)
        if 'Timeout' in ret:
            self.skipTest('Timeout talking to local tornado server.')
        self.assertSaltTrueReturn(ret)

        self._check_extracted(UNTAR_FILE)
