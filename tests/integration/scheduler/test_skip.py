# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import copy
import logging
import os

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


class SchedulerSkipTest(ModuleCase, SaltReturnAssertsMixin):
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

        run_time = dateutil_parser.parse('11/29/2017 4:00pm')
        self.schedule.skip_job('job1', {'time': run_time.strftime('%Y-%m-%dT%H:%M:%S'),
                                        'time_fmt': '%Y-%m-%dT%H:%M:%S'})

        # Run 11/29/2017 at 4pm
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertNotIn('_last_run', ret)
        self.assertEqual(ret['_skip_reason'], 'skip_explicit')
        self.assertEqual(ret['_skipped_time'], run_time)

        # Run 11/29/2017 at 5pm
        run_time = dateutil_parser.parse('11/29/2017 5:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time)

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
                  'start': '11/29/2017 2pm',
                  'end': '11/29/2017 3pm'
              }
            }
          }
        }

        # Add job to schedule
        self.schedule.opts.update(job)

        # eval at 1:30pm to prime.
        run_time = dateutil_parser.parse('11/29/2017 1:30pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')

        # eval at 2:30pm, will not run during range.
        run_time = dateutil_parser.parse('11/29/2017 2:30pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertNotIn('_last_run', ret)
        self.assertEqual(ret['_skip_reason'], 'in_skip_range')
        self.assertEqual(ret['_skipped_time'], run_time)

        # eval at 3:30pm, will run.
        run_time = dateutil_parser.parse('11/29/2017 3:30pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time)

    def test_skip_during_range_invalid_datestring(self):
        '''
        verify that scheduled job is not not and returns the right error string
        '''
        run_time = dateutil_parser.parse('11/29/2017 2:30pm')

        job1 = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'hours': '1',
              '_next_fire_time': run_time,
              'skip_during_range': {
                  'start': '25pm',
                  'end': '3pm'
              }
            }
          }
        }

        job2 = {
          'schedule': {
            'job2': {
              'function': 'test.ping',
              'hours': '1',
              '_next_fire_time': run_time,
              'skip_during_range': {
                  'start': '2pm',
                  'end': '25pm'
              }
            }
          }
        }

        # Add job1 to schedule
        self.schedule.opts.update(job1)

        # Eval
        self.schedule.eval(now=run_time)

        # Check the first job
        ret = self.schedule.job_status('job1')
        _expected = ('Invalid date string for start in '
                     'skip_during_range. Ignoring '
                     'job job1.')
        self.assertEqual(ret['_error'], _expected)

        # Clear out schedule
        self.schedule.opts['schedule'] = {}

        # Add job2 to schedule
        self.schedule.opts.update(job2)

        # Eval
        self.schedule.eval(now=run_time)

        # Check the second job
        ret = self.schedule.job_status('job2')
        _expected = ('Invalid date string for end in '
                     'skip_during_range. Ignoring '
                     'job job2.')
        self.assertEqual(ret['_error'], _expected)

    def test_skip_during_range_global(self):
        '''
        verify that scheduled job is skipped during the specified range
        '''
        job = {
          'schedule': {
            'skip_during_range': {
              'start': '11/29/2017 2pm',
              'end': '11/29/2017 3pm'
            },
            'job1': {
              'function': 'test.ping',
              'hours': '1',
            }
          }
        }

        # Add job to schedule
        self.schedule.opts.update(job)

        # eval at 1:30pm to prime.
        run_time = dateutil_parser.parse('11/29/2017 1:30pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')

        # eval at 2:30pm, will not run during range.
        run_time = dateutil_parser.parse('11/29/2017 2:30pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertNotIn('_last_run', ret)
        self.assertEqual(ret['_skip_reason'], 'in_skip_range')
        self.assertEqual(ret['_skipped_time'], run_time)

        # eval at 3:30pm, will run.
        run_time = dateutil_parser.parse('11/29/2017 3:30pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time)

    def test_run_after_skip_range(self):
        '''
        verify that scheduled job is skipped during the specified range
        '''
        job = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'when': '11/29/2017 2:30pm',
              'run_after_skip_range': True,
              'skip_during_range': {
                  'start': '11/29/2017 2pm',
                  'end': '11/29/2017 3pm'
              }
            }
          }
        }

        # Add job to schedule
        self.schedule.opts.update(job)

        # eval at 2:30pm, will not run during range.
        run_time = dateutil_parser.parse('11/29/2017 2:30pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertNotIn('_last_run', ret)
        self.assertEqual(ret['_skip_reason'], 'in_skip_range')
        self.assertEqual(ret['_skipped_time'], run_time)

        # eval at 3:00:01pm, will run.
        run_time = dateutil_parser.parse('11/29/2017 3:00:01pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_last_run'], run_time)
