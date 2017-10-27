# -*- coding: utf-8 -*-
'''
Tests for the archive state
'''
# Import python libs
from __future__ import absolute_import
import errno
import logging
import os
import platform
import socket
import threading
import tornado.httpserver
import tornado.ioloop
import tornado.web

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils

# Setup logging
log = logging.getLogger(__name__)

STATE_DIR = os.path.join(integration.FILES, 'file', 'base')
if salt.utils.is_windows():
    ARCHIVE_DIR = os.path.join("c:/", "tmp")
else:
    ARCHIVE_DIR = '/tmp/archive'

PORT = 9999
ARCHIVE_NAME = 'custom.tar.gz'
ARCHIVE_TAR_SOURCE = 'http://localhost:{0}/{1}'.format(PORT, ARCHIVE_NAME)
ARCHIVE_LOCAL_TAR_SOURCE = 'file://{0}'.format(os.path.join(STATE_DIR, ARCHIVE_NAME))
UNTAR_FILE = os.path.join(ARCHIVE_DIR, 'custom/README')
ARCHIVE_TAR_HASH = 'md5=7643861ac07c30fe7d2310e9f25ca514'
ARCHIVE_TAR_BAD_HASH = 'md5=d41d8cd98f00b204e9800998ecf8427e'

REDHAT7 = False
QUERY_OS = platform.dist()
OS_VERSION = QUERY_OS[1]
OS_FAMILY = QUERY_OS[0]
if '7' in OS_VERSION and 'centos' in OS_FAMILY:
    REDHAT7 = True


@skipIf(not REDHAT7, 'Only run on redhat7 for now due to hanging issues on other OS')
class ArchiveTest(integration.ModuleCase,
                  integration.SaltReturnAssertsMixIn):
    '''
    Validate the archive state
    '''
    @classmethod
    def webserver(cls):
        '''
        method to start tornado
        static web app
        '''
        application = tornado.web.Application([(r"/(.*)", tornado.web.StaticFileHandler,
                                              {"path": STATE_DIR})])
        cls.server = tornado.httpserver.HTTPServer(application)
        cls.server.listen(PORT)
        tornado.ioloop.IOLoop.instance().start()

    @classmethod
    def setUpClass(cls):
        '''
        start tornado app on thread
        and wait till its running
        '''
        cls.server_thread = threading.Thread(target=cls.webserver)
        cls.server_thread.daemon = True
        cls.server_thread.start()
        # check if tornado app is up
        port_closed = True
        while port_closed:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', PORT))
            if result == 0:
                port_closed = False

    @classmethod
    def tearDownClass(cls):
        tornado.ioloop.IOLoop.instance().stop()
        cls.server_thread.join()
        cls.server.stop()

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
                             source=ARCHIVE_TAR_SOURCE, archive_format='tar',
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
                             source=ARCHIVE_TAR_SOURCE, archive_format='tar',
                             source_hash=ARCHIVE_TAR_HASH)
        log.debug('ret = %s', ret)
        if 'Timeout' in ret:
            self.skipTest('Timeout talking to local tornado server.')

        self.assertSaltTrueReturn(ret)

        self._check_extracted(UNTAR_FILE)

    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_archive_extracted_with_root_user_and_group(self):
        '''
        test archive.extracted with user and group set to "root"
        '''
        ret = self.run_state('archive.extracted', name=ARCHIVE_DIR,
                             source=ARCHIVE_TAR_SOURCE, archive_format='tar',
                             source_hash=ARCHIVE_TAR_HASH,
                             user='root', group='root')
        log.debug('ret = %s', ret)
        if 'Timeout' in ret:
            self.skipTest('Timeout talking to local tornado server.')

        self.assertSaltTrueReturn(ret)

        self._check_extracted(UNTAR_FILE)

    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_archive_extracted_with_strip_in_options(self):
        '''
        test archive.extracted with --strip in options
        '''
        ret = self.run_state('archive.extracted', name=ARCHIVE_DIR,
                             source=ARCHIVE_TAR_SOURCE,
                             source_hash=ARCHIVE_TAR_HASH,
                             options='--strip=1',
                             enforce_toplevel=False)
        log.debug('ret = %s', ret)
        if 'Timeout' in ret:
            self.skipTest('Timeout talking to local tornado server.')

        self.assertSaltTrueReturn(ret)

        self._check_extracted(os.path.join(ARCHIVE_DIR, 'README'))

    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_archive_extracted_with_strip_components_in_options(self):
        '''
        test archive.extracted with --strip-components in options
        '''
        ret = self.run_state('archive.extracted', name=ARCHIVE_DIR,
                             source=ARCHIVE_TAR_SOURCE,
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
                             source=ARCHIVE_TAR_SOURCE,
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
                             source=ARCHIVE_TAR_SOURCE,
                             source_hash=ARCHIVE_TAR_HASH,
                             use_cmd_unzip=False,
                             archive_format='tar')
        log.debug('ret = %s', ret)
        if 'Timeout' in ret:
            self.skipTest('Timeout talking to local tornado server.')
        self.assertSaltTrueReturn(ret)

        self._check_extracted(UNTAR_FILE)

    def test_local_archive_extracted(self):
        '''
        test archive.extracted with local file
        '''
        ret = self.run_state('archive.extracted', name=ARCHIVE_DIR,
                             source=ARCHIVE_LOCAL_TAR_SOURCE, archive_format='tar')
        log.debug('ret = %s', ret)

        self.assertSaltTrueReturn(ret)

        self._check_extracted(UNTAR_FILE)

    def test_local_archive_extracted_skip_verify(self):
        '''
        test archive.extracted with local file, bad hash and skip_verify
        '''
        ret = self.run_state('archive.extracted', name=ARCHIVE_DIR,
                             source=ARCHIVE_LOCAL_TAR_SOURCE, archive_format='tar',
                             source_hash=ARCHIVE_TAR_BAD_HASH, skip_verify=True)
        log.debug('ret = %s', ret)

        self.assertSaltTrueReturn(ret)

        self._check_extracted(UNTAR_FILE)

    def test_local_archive_extracted_with_source_hash(self):
        '''
        test archive.extracted with local file and valid hash
        '''
        ret = self.run_state('archive.extracted', name=ARCHIVE_DIR,
                             source=ARCHIVE_LOCAL_TAR_SOURCE, archive_format='tar',
                             source_hash=ARCHIVE_TAR_HASH)
        log.debug('ret = %s', ret)

        self.assertSaltTrueReturn(ret)

        self._check_extracted(UNTAR_FILE)

    def test_local_archive_extracted_with_bad_source_hash(self):
        '''
        test archive.extracted with local file and bad hash
        '''
        ret = self.run_state('archive.extracted', name=ARCHIVE_DIR,
                             source=ARCHIVE_LOCAL_TAR_SOURCE, archive_format='tar',
                             source_hash=ARCHIVE_TAR_BAD_HASH)
        log.debug('ret = %s', ret)

        self.assertSaltFalseReturn(ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ArchiveTest)
