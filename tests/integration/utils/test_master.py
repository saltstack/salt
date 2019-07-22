# -*- coding: utf-8 -*-
'''
Test master code from utils
'''
from __future__ import absolute_import

import os
import time

import setproctitle  # pylint: disable=W8410

import salt.config
import salt.utils.master as master

from tests.support.case import ShellTestCase
from tests.support.paths import TMP_ROOT_DIR
from tests.support.helpers import flaky
from tests.support.unit import skipIf

DEFAULT_CONFIG = salt.config.master_config(None)
DEFAULT_CONFIG['cachedir'] = os.path.join(TMP_ROOT_DIR, 'cache')


@skipIf(True, 'WAR ROOM TEMPORARY SKIP')
class MasterUtilJobsTestCase(ShellTestCase):

    def setUp(self):
        '''
        Necessary so that the master pid health check
        passes as it looks for salt in cmdline
        '''
        setproctitle.setproctitle('salt')

    @flaky
    def test_get_running_jobs(self):
        '''
        Test get running jobs
        '''
        ret = self.run_run_plus("test.sleep", '90', asynchronous=True)
        jid = ret['jid']

        # Ran into a problem where the async jump was not seen until
        # after the test had finished. This caused the test to fail
        # because no job was present (not proc file). This attempts
        # to wait a total of 20s before giving up.
        attempt = 0
        while attempt < 10:
            jobs = master.get_running_jobs(DEFAULT_CONFIG)
            if jobs:
                jids = [job['jid'] for job in jobs]
                assert jids.count(jid) == 1
                break
            time.sleep(2)
            attempt += attempt + 1
