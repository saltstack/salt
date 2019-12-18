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
from tests.support.mock import MagicMock, patch
from tests.support.unit import skipIf
from tests.support.runtests import RUNTIME_VARS

# Import Salt libs
import salt.utils.schedule

from salt.modules.test import ping as ping

try:
    import croniter  # pylint: disable=W0611
    HAS_CRONITER = True
except ImportError:
    HAS_CRONITER = False

log = logging.getLogger(__name__)
ROOT_DIR = os.path.join(RUNTIME_VARS.TMP, 'schedule-unit-tests')
SOCK_DIR = os.path.join(ROOT_DIR, 'test-socks')

DEFAULT_CONFIG = salt.config.minion_config(None)
DEFAULT_CONFIG['conf_dir'] = ROOT_DIR
DEFAULT_CONFIG['root_dir'] = ROOT_DIR
DEFAULT_CONFIG['sock_dir'] = SOCK_DIR
DEFAULT_CONFIG['pki_dir'] = os.path.join(ROOT_DIR, 'pki')
DEFAULT_CONFIG['cachedir'] = os.path.join(ROOT_DIR, 'cache')


class SchedulerErrorTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    Validate the pkg module
    '''
    def setUp(self):
        with patch('salt.utils.schedule.clean_proc_dir', MagicMock(return_value=None)):
            functions = {'test.ping': ping}
            self.schedule = salt.utils.schedule.Schedule(copy.deepcopy(DEFAULT_CONFIG), functions, returners={})
        self.schedule.opts['loop_interval'] = 1

        self.schedule.opts['grains']['whens'] = {'tea time': '11/29/2017 12:00pm'}

    def tearDown(self):
        self.schedule.reset()

    @skipIf(not HAS_CRONITER, 'Cannot find croniter python module')
    def test_eval_cron_invalid(self):
        '''
        verify that scheduled job runs
        '''
        job = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'cron': '0 16 29 13 *'
            }
          }
        }

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        run_time = dateutil_parser.parse('11/29/2017 4:00pm')
        with patch('croniter.croniter.get_next', MagicMock(return_value=run_time)):
            self.schedule.eval(now=run_time)

        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_error'],
                         'Invalid cron string. Ignoring job job1.')

    def test_eval_when_invalid_date(self):
        '''
        verify that scheduled job does not run
        and returns the right error
        '''
        run_time = dateutil_parser.parse('11/29/2017 4:00pm')

        job = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'when': '13/29/2017 1:00pm',
            }
          }
        }

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # Evaluate 1 second before the run time
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_error'],
                         'Invalid date string. Ignoring job job1.')

    def test_eval_whens_grain_not_dict(self):
        '''
        verify that scheduled job does not run
        and returns the right error
        '''
        run_time = dateutil_parser.parse('11/29/2017 4:00pm')

        job = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'when': 'tea time',
            }
          }
        }

        self.schedule.opts['grains']['whens'] = ['tea time']

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # Evaluate 1 second before the run time
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        self.assertEqual(ret['_error'],
                         'Grain "whens" must be a dict. Ignoring job job1.')

    def test_eval_once_invalid_datestring(self):
        '''
        verify that scheduled job does not run
        and returns the right error
        '''
        job = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'once': '2017-13-13T13:00:00',
            }
          }
        }
        run_time = dateutil_parser.parse('12/13/2017 1:00pm')

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # Evaluate 1 second at the run time
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        _expected = ('Date string could not be parsed: '
                     '2017-13-13T13:00:00, %Y-%m-%dT%H:%M:%S. '
                     'Ignoring job job1.')
        self.assertEqual(ret['_error'], _expected)

    def test_eval_skip_during_range_invalid_date(self):
        '''
        verify that scheduled job does not run
        and returns the right error
        '''

        job = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'hours': 1,
              'skip_during_range': {'start': '1:00pm', 'end': '25:00pm'}

            }
          }
        }

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # eval at 3:00pm to prime, simulate minion start up.
        run_time = dateutil_parser.parse('11/29/2017 3:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')

        # eval at 4:00pm to prime
        run_time = dateutil_parser.parse('11/29/2017 4:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        _expected = ('Invalid date string for end in '
                     'skip_during_range. Ignoring '
                     'job job1.')
        self.assertEqual(ret['_error'], _expected)

    def test_eval_skip_during_range_end_before_start(self):
        '''
        verify that scheduled job does not run
        and returns the right error
        '''

        job = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'hours': 1,
              'skip_during_range': {'start': '1:00pm', 'end': '12:00pm'}

            }
          }
        }

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # eval at 3:00pm to prime, simulate minion start up.
        run_time = dateutil_parser.parse('11/29/2017 3:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')

        # eval at 4:00pm to prime
        run_time = dateutil_parser.parse('11/29/2017 4:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        _expected = ('schedule.handle_func: Invalid '
                     'range, end must be larger than '
                     'start. Ignoring job job1.')
        self.assertEqual(ret['_error'], _expected)

    def test_eval_skip_during_range_not_dict(self):
        '''
        verify that scheduled job does not run
        and returns the right error
        '''

        job = {
          'schedule': {
            'job1': {
              'function': 'test.ping',
              'hours': 1,
              'skip_during_range': ['start', '1:00pm', 'end', '12:00pm']

            }
          }
        }

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # eval at 3:00pm to prime, simulate minion start up.
        run_time = dateutil_parser.parse('11/29/2017 3:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')

        # eval at 4:00pm to prime
        run_time = dateutil_parser.parse('11/29/2017 4:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status('job1')
        _expected = ('schedule.handle_func: Invalid, '
                     'range must be specified as a '
                     'dictionary. Ignoring job job1.')
        self.assertEqual(ret['_error'], _expected)
