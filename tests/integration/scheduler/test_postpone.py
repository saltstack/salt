# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import copy
import datetime
import logging
import os

import dateutil.parser as dateutil_parser

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS

# Import Salt libs
import salt.utils.schedule

from salt.modules.test import ping as ping

log = logging.getLogger(__name__)
ROOT_DIR = os.path.join(RUNTIME_VARS.TMP, 'schedule-unit-tests')
SOCK_DIR = os.path.join(ROOT_DIR, 'test-socks')

DEFAULT_CONFIG = salt.config.minion_config(None)
DEFAULT_CONFIG['conf_dir'] = ROOT_DIR
DEFAULT_CONFIG['root_dir'] = ROOT_DIR
DEFAULT_CONFIG['sock_dir'] = SOCK_DIR
DEFAULT_CONFIG['pki_dir'] = os.path.join(ROOT_DIR, 'pki')
DEFAULT_CONFIG['cachedir'] = os.path.join(ROOT_DIR, 'cache')


class SchedulerPostponeTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the pkg module
    '''
    def setUp(self):
        with patch('salt.utils.schedule.clean_proc_dir', MagicMock(return_value=None)):
            functions = {'test.ping': ping}
            self.schedule = salt.utils.schedule.Schedule(copy.deepcopy(DEFAULT_CONFIG), functions, returners={})
        self.schedule.opts['loop_interval'] = 1

    def tearDown(self):
        self.schedule.reset()

    def test_postpone(self):
        '''
        verify that scheduled job is postponed until the specified time.
        '''
        job = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'when': '11/29/2017 4pm',
            }
          }
        }

        # 11/29/2017 4pm
        run_time = dateutil_parser.parse('11/29/2017 4:00pm')

        # 5 minute delay
        delay = 300

        # Add job to schedule
        self.schedule.opts.update(job)

        # Postpone the job by 5 minutes
        self.schedule.postpone_job('job1', {'time': run_time.strftime('%Y-%m-%dT%H:%M:%S'),
                                            'new_time': (run_time + datetime.timedelta(seconds=delay)).strftime('%Y-%m-%dT%H:%M:%S')})
        # Run at the original time
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertNotIn('_last_run', ret)

        # Run 5 minutes later
        self.schedule.eval(now=run_time + datetime.timedelta(seconds=delay))
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time + datetime.timedelta(seconds=delay))

        # Run 6 minutes later
        self.schedule.eval(now=run_time + datetime.timedelta(seconds=delay + 1))
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time + datetime.timedelta(seconds=delay))
