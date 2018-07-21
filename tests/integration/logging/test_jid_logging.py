# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import TestsLoggingHandler


class LoggingJIDsTest(ModuleCase):
    '''
    Validate that JIDs appear in LOGs
    '''
    def test_jid_in_logs(self):
        '''
        Test JID in log_format
        '''
        log_format = "[%(levelname)-8s] %(jid)s %(message)s"
        handler = TestsLoggingHandler(format=log_format, level="INFO")
        with handler:
            self.assertTrue(self.run_function('test.ping'))
            self.assertTrue(any("JID" in s for s in handler.messages))
