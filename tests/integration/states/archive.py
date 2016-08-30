# -*- coding: utf-8 -*-
'''
Tests for the archive state
'''
# Import python libs
from __future__ import absolute_import
import os
import shutil
import threading
import tornado.ioloop
import tornado.web

# Import Salt Testing libs
from salttesting import TestCase
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

PORT = 9999
ARCHIVE_TAR_SOURCE = 'http://localhost:{0}/custom.tar.gz'.format(PORT)
UNTAR_FILE = ARCHIVE_DIR + 'custom/README'
ARCHIVE_TAR_HASH = 'md5=7643861ac07c30fe7d2310e9f25ca514'
STATE_DIR = os.path.join(integration.FILES, 'file', 'base')


class SetupWebServer(TestCase):
    '''
    Setup and Teardown of Web Server
    Only need to set this up once not
    before all tests
    '''
    @classmethod
    def webserver(cls):
        '''
        method to start tornado
        static web app
        '''
        application = tornado.web.Application([(r"/(.*)", tornado.web.StaticFileHandler,
                                              {"path": STATE_DIR})])
        application.listen(PORT)
        tornado.ioloop.IOLoop.instance().start()

    @classmethod
    def setUpClass(cls):
        cls.server_thread = threading.Thread(target=cls.webserver)
        cls.server_thread.daemon = True
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        tornado.ioloop.IOLoop.instance().stop()
        cls.server_thread.join()


class ArchiveTest(SetupWebServer,
                  integration.ModuleCase,
                  integration.SaltReturnAssertsMixIn):
    '''
    Validate the archive state
    '''
    def _check_ext_remove(self, dir, file):
        '''
        function to check if file was extracted
        and remove the directory.
        '''
        # check to see if it extracted
        check_dir = os.path.isfile(file)
        self.assertTrue(check_dir)

        # wipe away dir. Can't do this in teardown
        # because it needs to be wiped before each test
        shutil.rmtree(dir)

    def test_archive_extracted_skip_verify(self):
        '''
        test archive.extracted with skip_verify
        '''
        ret = self.run_state('archive.extracted', name=ARCHIVE_DIR,
                             source=ARCHIVE_TAR_SOURCE, archive_format='tar',
                             skip_verify=True)
        self.assertSaltTrueReturn(ret)

        self._check_ext_remove(ARCHIVE_DIR, UNTAR_FILE)

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
