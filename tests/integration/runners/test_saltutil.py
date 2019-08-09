# -*- coding: utf-8 -*-
'''
Tests for the state runner
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os

# Import Salt Testing Libs
from tests.support.case import ShellCase
from tests.support.unit import skipIf, WAR_ROOM_SKIP

log = logging.getLogger(__name__)


class SyncRunnerTest(ShellCase):
    '''
    Test the sync runner.
    '''
    def test_sync_auth_includes_auth(self):
        '''
        '''
        ret_output = self.run_run('saltutil.sync_auth')
        assert '- auth.nullauth' in [ret_entry.strip() for ret_entry in ret_output]
        # Clean up?
        os.unlink(os.path.join(self.master_opts['root_dir'], 'extension_modules', 'auth', 'nullauth.py'))

    @skipIf(WAR_ROOM_SKIP, 'WAR ROOM - this test is causing slow downs, skip until we find out why')
    def test_sync_all_includes_auth(self):
        '''
        '''
        ret_output = self.run_run('saltutil.sync_all')
        assert '- auth.nullauth' in [ret_entry.strip() for ret_entry in ret_output]
        # Clean up?
        os.unlink(os.path.join(self.master_opts['root_dir'], 'extension_modules', 'auth', 'nullauth.py'))
