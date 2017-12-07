# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import copy
import logging
import os
import time

import dateutil.parser as dateutil_parser

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin

# Import Salt Testing Libs
from tests.support.mock import MagicMock, patch
import tests.integration as integration

# Import Salt libs
import salt.utils.schedule

from salt.modules.test import ping as ping

log = logging.getLogger(__name__)
ROOT_DIR = os.path.join(integration.TMP, 'schedule-unit-tests')
SOCK_DIR = os.path.join(ROOT_DIR, 'test-socks')

DEFAULT_CONFIG = salt.config.minion_config(None)
DEFAULT_CONFIG['conf_dir'] = ROOT_DIR
DEFAULT_CONFIG['root_dir'] = ROOT_DIR
DEFAULT_CONFIG['sock_dir'] = SOCK_DIR
DEFAULT_CONFIG['pki_dir'] = os.path.join(ROOT_DIR, 'pki')
DEFAULT_CONFIG['cachedir'] = os.path.join(ROOT_DIR, 'cache')


class SchedulerEvalTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the pkg module
    '''
    def setUp(self):
        with patch('salt.utils.schedule.clean_proc_dir', MagicMock(return_value=None)):
            functions = {'test.ping': ping}
            self.schedule = salt.utils.schedule.Schedule(copy.deepcopy(DEFAULT_CONFIG), functions, returners={})

    def test_eval(self):
        '''
        verify that scheduled job runs
        '''
        job = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'when': '11/29/2017 4:00pm',
            }
          }
        }
        run_time2 = int(time.mktime(dateutil_parser.parse('11/29/2017 4:00pm').timetuple()))
        run_time1 = run_time2 - 1

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # Evaluate 1 second before the run time
        self.schedule.eval(now=run_time1)
        ret = self.schedule.job_status('job1')
        self.assertNotIn('_last_run', ret)

        # Evaluate 1 second at the run time
        self.schedule.eval(now=run_time2)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time2)
