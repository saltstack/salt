# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import copy
import datetime
import logging
import os
import random

import dateutil.parser as dateutil_parser

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin

# Import Salt Testing Libs
from tests.support.mock import MagicMock, patch
from tests.support.unit import skipIf
import tests.integration as integration

# Import Salt libs
import salt.utils.schedule

from salt.modules.test import ping as ping

try:
    import croniter  # pylint: disable=W0611
    HAS_CRONITER = True
except ImportError:
    HAS_CRONITER = False

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
        self.schedule.opts['loop_interval'] = 1

    def tearDown(self):
        self.schedule.reset()

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
        run_time2 = dateutil_parser.parse('11/29/2017 4:00pm')
        run_time1 = run_time2 - datetime.timedelta(seconds=1)

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

    def test_eval_multiple_whens(self):
        '''
        verify that scheduled job runs
        '''
        job = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'when': [
                '11/29/2017 4:00pm',
                '11/29/2017 5:00pm',
                ]
            }
          }
        }
        run_time1 = dateutil_parser.parse('11/29/2017 4:00pm')
        run_time2 = dateutil_parser.parse('11/29/2017 5:00pm')

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # Evaluate run time1
        self.schedule.eval(now=run_time1)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time1)

        # Evaluate run time2
        self.schedule.eval(now=run_time2)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time2)

    def test_eval_loop_interval(self):
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
        # 30 second loop interval
        LOOP_INTERVAL = random.randint(30, 59)
        self.schedule.opts['loop_interval'] = LOOP_INTERVAL

        run_time2 = dateutil_parser.parse('11/29/2017 4:00pm')

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # Evaluate 1 second at the run time
        self.schedule.eval(now=run_time2 + datetime.timedelta(seconds=LOOP_INTERVAL))

        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time2 + datetime.timedelta(seconds=LOOP_INTERVAL))

    def test_eval_multiple_whens_loop_interval(self):
        '''
        verify that scheduled job runs
        '''
        job = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'when': [
                '11/29/2017 4:00pm',
                '11/29/2017 5:00pm',
                ]
            }
          }
        }
        # 30 second loop interval
        LOOP_INTERVAL = random.randint(30, 59)
        self.schedule.opts['loop_interval'] = LOOP_INTERVAL

        run_time1 = dateutil_parser.parse('11/29/2017 4:00pm') + datetime.timedelta(seconds=LOOP_INTERVAL)
        run_time2 = dateutil_parser.parse('11/29/2017 5:00pm') + datetime.timedelta(seconds=LOOP_INTERVAL)

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # Evaluate 1 second at the run time
        self.schedule.eval(now=run_time1)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time1)

        # Evaluate 1 second at the run time
        self.schedule.eval(now=run_time2)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time2)

    def test_eval_once(self):
        '''
        verify that scheduled job runs
        '''
        job = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'once': '2017-12-13T13:00:00',
            }
          }
        }
        run_time = dateutil_parser.parse('12/13/2017 1:00pm')

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # Evaluate 1 second at the run time
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time)

    def test_eval_once_loop_interval(self):
        '''
        verify that scheduled job runs
        '''
        job = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'once': '2017-12-13T13:00:00',
            }
          }
        }
        # Randomn second loop interval
        LOOP_INTERVAL = random.randint(0, 59)
        self.schedule.opts['loop_interval'] = LOOP_INTERVAL

        # Run the job at the right plus LOOP_INTERVAL
        run_time = dateutil_parser.parse('12/13/2017 1:00pm') + datetime.timedelta(seconds=LOOP_INTERVAL)

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # Evaluate at the run time
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time)

    @skipIf(not HAS_CRONITER, 'Cannot find croniter python module')
    def test_eval_cron(self):
        '''
        verify that scheduled job runs
        '''
        job = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'cron': '0 16 29 11 *'
            }
          }
        }

        # Add the job to the scheduler
        self.schedule.opts['schedule'] = {}
        self.schedule.opts.update(job)

        run_time = dateutil_parser.parse('11/29/2017 4:00pm')
        with patch('croniter.croniter.get_next', MagicMock(return_value=run_time)):
            self.schedule.eval(now=run_time)

        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time)

    @skipIf(not HAS_CRONITER, 'Cannot find croniter python module')
    def test_eval_cron_loop_interval(self):
        '''
        verify that scheduled job runs
        '''
        job = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'cron': '0 16 29 11 *'
            }
          }
        }
        # Randomn second loop interval
        LOOP_INTERVAL = random.randint(0, 59)
        self.schedule.opts['loop_interval'] = LOOP_INTERVAL

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        run_time = dateutil_parser.parse('11/29/2017 4:00pm')
        with patch('croniter.croniter.get_next', MagicMock(return_value=run_time)):
            self.schedule.eval(now=run_time)

        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time)

    def test_eval_until(self):
        '''
        verify that scheduled job is skipped once the current
        time reaches the specified until time
        '''
        job = {
          'schedule': {
            'job_eval_after': {
              'function': 'test.ping',
              'hours': '1',
              'until': '11/29/2017 5:00pm'
            }
          }
        }

        # Add job to schedule
        self.schedule.opts.update(job)

        # eval at 2:00pm to prime, simulate minion start up.
        run_time = dateutil_parser.parse('11/29/2017 2:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job_eval_after')

        # eval at 3:00pm, will run.
        run_time = dateutil_parser.parse('11/29/2017 3:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job_eval_after')
        self.assertEqual(ret['_last_run'], run_time)

        # eval at 4:00pm, will run.
        run_time = dateutil_parser.parse('11/29/2017 4:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job_eval_after')
        self.assertEqual(ret['_last_run'], run_time)

        # eval at 5:00pm, will not run
        run_time = dateutil_parser.parse('11/29/2017 5:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job_eval_after')
        self.assertEqual(ret['_skip_reason'], 'until_passed')
        self.assertEqual(ret['_skipped_time'], run_time)

    def test_eval_after(self):
        '''
        verify that scheduled job is skipped until after the specified
        time has been reached.
        '''
        job = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'hours': '1',
              'after': '11/29/2017 5:00pm'
            }
          }
        }

        # Add job to schedule
        self.schedule.opts.update(job)

        # eval at 2:00pm to prime, simulate minion start up.
        run_time = dateutil_parser.parse('11/29/2017 2:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')

        # eval at 3:00pm, will not run.
        run_time = dateutil_parser.parse('11/29/2017 3:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_skip_reason'], 'after_not_passed')
        self.assertEqual(ret['_skipped_time'], run_time)

        # eval at 4:00pm, will not run.
        run_time = dateutil_parser.parse('11/29/2017 4:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_skip_reason'], 'after_not_passed')
        self.assertEqual(ret['_skipped_time'], run_time)

        # eval at 5:00pm, will not run
        run_time = dateutil_parser.parse('11/29/2017 5:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_skip_reason'], 'after_not_passed')
        self.assertEqual(ret['_skipped_time'], run_time)

        # eval at 6:00pm, will run
        run_time = dateutil_parser.parse('11/29/2017 6:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time)
