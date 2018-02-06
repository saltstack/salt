# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import random

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf

# Import Salt libs
import salt.utils.platform


class StatusModuleTest(ModuleCase):
    '''
    Test the status module
    '''
    @skipIf(salt.utils.platform.is_windows(), 'minion is windows')
    def test_status_pid(self):
        '''
        status.pid
        '''
        status_pid = self.run_function('status.pid', ['salt'])
        grab_pids = status_pid.split()[:10]
        random_pid = random.choice(grab_pids)
        grep_salt = self.run_function('cmd.run', ['ps aux | grep salt'])
        self.assertIn(random_pid, grep_salt)
