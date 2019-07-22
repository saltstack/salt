# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.helpers import TstSuiteLoggingHandler, flaky

import logging
import salt.ext.six as six


@skipIf(six.PY3, 'Runtest Log Hander Disabled for PY3, #41836')
class LoggingJIDsTest(ModuleCase):
    '''
    Validate that JIDs appear in LOGs
    '''
    def setUp(self):
        '''
        Set up
        '''
        log_format = '[%(levelname)-8s] %(jid)s %(message)s'
        self.handler = TstSuiteLoggingHandler(format=log_format,
                                              level=logging.DEBUG)

    @flaky
    def test_jid_in_logs(self):
        '''
        Test JID in log_format
        '''
        with self.handler:
            self.run_function('test.ping')
            assert any('JID' in s for s in self.handler.messages) is True, 'JID not found in log messages'
