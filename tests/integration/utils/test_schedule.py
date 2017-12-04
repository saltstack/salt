# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import copy
import logging
import os

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.helpers import (
    destructiveTest,
    requires_network,
    requires_salt_modules,
)
from tests.support.unit import skipIf

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON
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


class SchedulerTest(ModuleCase, SaltReturnAssertsMixin):
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
              'when': '11/29/2017 4pm',
            }
          }
        }
        run_time1 = 1512000000 - 1
        run_time2 = 1512000000

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

    def test_skip(self):
        '''
        verify that scheduled job is skipped at the specified time
        '''
        job = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'when': ['11/29/2017 4pm', '11/29/2017 5pm'],
            }
          }
        }

        # Add job to schedule
        self.schedule.opts.update(job)

        run_time = 1512000000
        self.schedule.skip_job('job1', {'time': run_time})

        # Run 11/29/2017 at 4pm
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertNotIn('_last_run', ret)

        # Run 11/29/2017 at 5pm
        run_time = 1512003600
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time)

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
        run_time = 1512000000

        # 5 minute delay
        delay = 300

        # Add job to schedule
        self.schedule.opts.update(job)

        # Postpone the job by 5 minutes
        self.schedule.postpone_job('job1', {'time': run_time,
                                            'new_time': run_time + delay})

        # Run at the original time
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertNotIn('_last_run', ret)

        # Run 5 minutes later
        self.schedule.eval(now=run_time + delay)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time + delay)

        # Run 6 minutes later
        self.schedule.eval(now=run_time + delay + 1)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time + delay)

    def test_skip_during_range(self):
        '''
        verify that scheduled job is skipped during the specified range
        '''
        job = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'hours': '1',
              'skip_during_range': {
                  'start': '2pm',
                  'end': '3pm'
              }
            }
          }
        }

        # Add job to schedule
        self.schedule.opts.update(job)

        # eval at 2:30pm, will not run during range.
        run_time = 148045860
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertNotIn('_last_run', ret)

        # eval at 3:30pm, will run.
        run_time = 1480462200
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time)
