# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import copy
import datetime
import logging
import os
import random
import time

import dateutil.parser as dateutil_parser
import datetime

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import skipIf
from tests.support.runtests import RUNTIME_VARS

# Import Salt libs
import salt.utils.schedule
import salt.utils.platform

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


class SchedulerEvalTest(ModuleCase, SaltReturnAssertsMixin):
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

    def test_eval(self):
        '''
        verify that scheduled job runs
        '''
        job_name = 'test_eval'
        job = {
          'schedule': {
            job_name: {
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
        ret = self.schedule.job_status(job_name)
        self.assertNotIn('_last_run', ret)

        # Evaluate 1 second at the run time
        self.schedule.eval(now=run_time2)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time2)

    def test_eval_multiple_whens(self):
        '''
        verify that scheduled job runs
        '''
        job_name = 'test_eval_multiple_whens'
        job = {
          'schedule': {
            job_name: {
              'function': 'test.ping',
              'when': [
                '11/29/2017 4:00pm',
                '11/29/2017 5:00pm',
                ],
            }
          }
        }
        if salt.utils.platform.is_darwin():
            job['schedule'][job_name]['dry_run'] = True

        run_time1 = dateutil_parser.parse('11/29/2017 4:00pm')
        run_time2 = dateutil_parser.parse('11/29/2017 5:00pm')

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # Evaluate run time1
        self.schedule.eval(now=run_time1)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time1)

        time.sleep(2)

        # Evaluate run time2
        self.schedule.eval(now=run_time2)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time2)

    def test_eval_whens(self):
        '''
        verify that scheduled job runs
        '''
        job_name = 'test_eval_whens'
        job = {
          'schedule': {
            job_name: {
              'function': 'test.ping',
              'when': 'tea time',
            }
          }
        }
        run_time = dateutil_parser.parse('11/29/2017 12:00pm')

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # Evaluate run time1
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)

    def test_eval_loop_interval(self):
        '''
        verify that scheduled job runs
        '''
        job_name = 'test_eval_loop_interval'
        job = {
          'schedule': {
            job_name: {
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

        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time2 + datetime.timedelta(seconds=LOOP_INTERVAL))

    def test_eval_multiple_whens_loop_interval(self):
        '''
        verify that scheduled job runs
        '''
        job_name = 'test_eval_multiple_whens_loop_interval'
        job = {
          'schedule': {
            job_name: {
              'function': 'test.ping',
              'when': [
                '11/29/2017 4:00pm',
                '11/29/2017 5:00pm',
                ],
            }
          }
        }
        if salt.utils.platform.is_darwin():
            job['schedule'][job_name]['dry_run'] = True

        # 30 second loop interval
        LOOP_INTERVAL = random.randint(30, 59)
        self.schedule.opts['loop_interval'] = LOOP_INTERVAL

        run_time1 = dateutil_parser.parse('11/29/2017 4:00pm') + datetime.timedelta(seconds=LOOP_INTERVAL)
        run_time2 = dateutil_parser.parse('11/29/2017 5:00pm') + datetime.timedelta(seconds=LOOP_INTERVAL)

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # Evaluate 1 second at the run time
        self.schedule.eval(now=run_time1)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time1)

        time.sleep(2)

        # Evaluate 1 second at the run time
        self.schedule.eval(now=run_time2)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time2)

    def test_eval_once(self):
        '''
        verify that scheduled job runs
        '''
        job_name = 'test_once'
        job = {
          'schedule': {
            job_name: {
              'function': 'test.ping',
              'once': '2017-12-13T13:00:00',
            }
          }
        }
        run_time = dateutil_parser.parse('12/13/2017 1:00pm')

        # Add the job to the scheduler
        self.schedule.opts['schedule'] = {}
        self.schedule.opts.update(job)

        # Evaluate 1 second at the run time
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)

    def test_eval_once_loop_interval(self):
        '''
        verify that scheduled job runs
        '''
        job_name = 'test_eval_once_loop_interval'
        job = {
          'schedule': {
            job_name: {
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
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)

    @skipIf(not HAS_CRONITER, 'Cannot find croniter python module')
    def test_eval_cron(self):
        '''
        verify that scheduled job runs
        '''
        job_name = 'test_eval_cron'
        job = {
          'schedule': {
            job_name: {
              'function': 'test.ping',
              'cron': '0 16 29 11 *',
            }
          }
        }

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        run_time = dateutil_parser.parse('11/29/2017 4:00pm')
        with patch('croniter.croniter.get_next', MagicMock(return_value=run_time)):
            self.schedule.eval(now=run_time)

        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)

    @skipIf(not HAS_CRONITER, 'Cannot find croniter python module')
    def test_eval_cron_loop_interval(self):
        '''
        verify that scheduled job runs
        '''
        job_name = 'test_eval_cron_loop_interval'
        job = {
          'schedule': {
            job_name: {
              'function': 'test.ping',
              'cron': '0 16 29 11 *',
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

        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)

    def test_eval_until(self):
        '''
        verify that scheduled job is skipped once the current
        time reaches the specified until time
        '''
        job_name = 'test_eval_until'
        job = {
          'schedule': {
            job_name: {
              'function': 'test.ping',
              'hours': '1',
              'until': '11/29/2017 5:00pm',
            }
          }
        }

        if salt.utils.platform.is_darwin():
            job['schedule'][job_name]['dry_run'] = True

        # Add job to schedule
        self.schedule.delete_job('test_eval_until')
        self.schedule.opts.update(job)

        # eval at 2:00pm to prime, simulate minion start up.
        run_time = dateutil_parser.parse('11/29/2017 2:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)

        # eval at 3:00pm, will run.
        run_time = dateutil_parser.parse('11/29/2017 3:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)

        time.sleep(2)

        # eval at 4:00pm, will run.
        run_time = dateutil_parser.parse('11/29/2017 4:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)

        time.sleep(2)

        # eval at 5:00pm, will not run
        run_time = dateutil_parser.parse('11/29/2017 5:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_skip_reason'], 'until_passed')
        self.assertEqual(ret['_skipped_time'], run_time)

    def test_eval_after(self):
        '''
        verify that scheduled job is skipped until after the specified
        time has been reached.
        '''
        job_name = 'test_eval_after'
        job = {
          'schedule': {
            job_name: {
              'function': 'test.ping',
              'hours': '1',
              'after': '11/29/2017 5:00pm',
            }
          }
        }

        # Add job to schedule
        self.schedule.opts.update(job)

        # eval at 2:00pm to prime, simulate minion start up.
        run_time = dateutil_parser.parse('11/29/2017 2:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)

        # eval at 3:00pm, will not run.
        run_time = dateutil_parser.parse('11/29/2017 3:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_skip_reason'], 'after_not_passed')
        self.assertEqual(ret['_skipped_time'], run_time)

        # eval at 4:00pm, will not run.
        run_time = dateutil_parser.parse('11/29/2017 4:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_skip_reason'], 'after_not_passed')
        self.assertEqual(ret['_skipped_time'], run_time)

        # eval at 5:00pm, will not run
        run_time = dateutil_parser.parse('11/29/2017 5:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_skip_reason'], 'after_not_passed')
        self.assertEqual(ret['_skipped_time'], run_time)

        # eval at 6:00pm, will run
        run_time = dateutil_parser.parse('11/29/2017 6:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)

    def test_eval_enabled(self):
        '''
        verify that scheduled job does not run
        '''
        job_name = 'test_eval_enabled'
        job = {
          'schedule': {
            'enabled': True,
            job_name: {
              'function': 'test.ping',
              'when': '11/29/2017 4:00pm',
            }
          }
        }
        run_time1 = dateutil_parser.parse('11/29/2017 4:00pm')

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # Evaluate 1 second at the run time
        self.schedule.eval(now=run_time1)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time1)

    def test_eval_enabled_key(self):
        '''
        verify that scheduled job runs
        when the enabled key is in place
        https://github.com/saltstack/salt/issues/47695
        '''
        job_name = 'test_eval_enabled_key'
        job = {
          'schedule': {
            'enabled': True,
            job_name: {
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
        ret = self.schedule.job_status('test_eval_enabled_key')
        self.assertNotIn('_last_run', ret)

        # Evaluate 1 second at the run time
        self.schedule.eval(now=run_time2)
        ret = self.schedule.job_status('test_eval_enabled_key')
        self.assertEqual(ret['_last_run'], run_time2)

    def test_eval_disabled(self):
        '''
        verify that scheduled job does not run
        '''
        job_name = 'test_eval_disabled'
        job = {
          'schedule': {
            'enabled': False,
            job_name: {
              'function': 'test.ping',
              'when': '11/29/2017 4:00pm',
            }
          }
        }
        run_time1 = dateutil_parser.parse('11/29/2017 4:00pm')

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # Evaluate 1 second at the run time
        self.schedule.eval(now=run_time1)
        ret = self.schedule.job_status(job_name)
        self.assertNotIn('_last_run', ret)
        self.assertEqual(ret['_skip_reason'], 'disabled')

        # Ensure job data still matches
        self.assertEqual(ret, job['schedule'][job_name])

    def test_eval_global_disabled_job_enabled(self):
        '''
        verify that scheduled job does not run
        '''
        job_name = 'test_eval_global_disabled'
        job = {
          'schedule': {
            'enabled': False,
            job_name: {
              'function': 'test.ping',
              'when': '11/29/2017 4:00pm',
              'enabled': True,
            }
          }
        }
        run_time1 = dateutil_parser.parse('11/29/2017 4:00pm')

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # Evaluate 1 second at the run time
        self.schedule.eval(now=run_time1)
        ret = self.schedule.job_status(job_name)
        self.assertNotIn('_last_run', ret)
        self.assertEqual(ret['_skip_reason'], 'disabled')

        # Ensure job is still enabled
        self.assertEqual(ret['enabled'], True)

    def test_eval_run_on_start(self):
        '''
        verify that scheduled job is run when minion starts
        '''
        job_name = 'test_eval_run_on_start'
        job = {
          'schedule': {
            job_name: {
              'function': 'test.ping',
              'hours': '1',
              'run_on_start': True,
            }
          }
        }

        # Add job to schedule
        self.schedule.opts.update(job)

        # eval at 2:00pm, will run.
        run_time = dateutil_parser.parse('11/29/2017 2:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)

        # eval at 3:00pm, will run.
        run_time = dateutil_parser.parse('11/29/2017 3:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)

    def test_eval_splay(self):
        '''
        verify that scheduled job runs with splayed time
        '''
        job_name = 'job_eval_splay'
        job = {
          'schedule': {
            job_name: {
              'function': 'test.ping',
              'seconds': '30',
              'splay': '10',
            }
          }
        }

        # Add job to schedule
        self.schedule.opts.update(job)

        with patch('random.randint', MagicMock(return_value=10)):
            # eval at 2:00pm to prime, simulate minion start up.
            run_time = dateutil_parser.parse('11/29/2017 2:00pm')
            self.schedule.eval(now=run_time)
            ret = self.schedule.job_status(job_name)

            # eval at 2:00:40pm, will run.
            run_time = dateutil_parser.parse('11/29/2017 2:00:40pm')
            self.schedule.eval(now=run_time)
            ret = self.schedule.job_status(job_name)
            self.assertEqual(ret['_last_run'], run_time)

    def test_eval_splay_range(self):
        '''
        verify that scheduled job runs with splayed time
        '''
        job_name = 'job_eval_splay_range'
        job = {
          'schedule': {
            job_name: {
              'function': 'test.ping',
              'seconds': '30',
              'splay': {'start': 5, 'end': 10},
            }
          }
        }

        # Add job to schedule
        self.schedule.opts.update(job)

        with patch('random.randint', MagicMock(return_value=10)):
            # eval at 2:00pm to prime, simulate minion start up.
            run_time = dateutil_parser.parse('11/29/2017 2:00pm')
            self.schedule.eval(now=run_time)
            ret = self.schedule.job_status(job_name)

            # eval at 2:00:40pm, will run.
            run_time = dateutil_parser.parse('11/29/2017 2:00:40pm')
            self.schedule.eval(now=run_time)
            ret = self.schedule.job_status(job_name)
            self.assertEqual(ret['_last_run'], run_time)

    def test_eval_splay_global(self):
        '''
        verify that scheduled job runs with splayed time
        '''
        job_name = 'job_eval_splay_global'
        job = {
          'schedule': {
            'splay': {'start': 5, 'end': 10},
            job_name: {
              'function': 'test.ping',
              'seconds': '30',
            }
          }
        }

        # Add job to schedule
        self.schedule.opts.update(job)

        with patch('random.randint', MagicMock(return_value=10)):
            # eval at 2:00pm to prime, simulate minion start up.
            run_time = dateutil_parser.parse('11/29/2017 2:00pm')
            self.schedule.eval(now=run_time)
            ret = self.schedule.job_status(job_name)

            # eval at 2:00:40pm, will run.
            run_time = dateutil_parser.parse('11/29/2017 2:00:40pm')
            self.schedule.eval(now=run_time)
            ret = self.schedule.job_status(job_name)
            self.assertEqual(ret['_last_run'], run_time)

    def test_eval_seconds(self):
        '''
        verify that scheduled job run mutiple times with seconds
        '''
        job_name = 'job_eval_seconds'
        job = {
          'schedule': {
            job_name: {
              'function': 'test.ping',
              'seconds': '30',
            }
          }
        }

        if salt.utils.platform.is_darwin():
            job['schedule'][job_name]['dry_run'] = True

        # Add job to schedule
        self.schedule.opts.update(job)

        # eval at 2:00pm to prime, simulate minion start up.
        run_time = dateutil_parser.parse('11/29/2017 2:00pm')
        next_run_time = run_time + datetime.timedelta(seconds=30)
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_next_fire_time'], next_run_time)

        # eval at 2:00:01pm, will not run.
        run_time = dateutil_parser.parse('11/29/2017 2:00:01pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertNotIn('_last_run', ret)
        self.assertEqual(ret['_next_fire_time'], next_run_time)

        # eval at 2:00:30pm, will run.
        run_time = dateutil_parser.parse('11/29/2017 2:00:30pm')
        next_run_time = run_time + datetime.timedelta(seconds=30)
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)
        self.assertEqual(ret['_next_fire_time'], next_run_time)

        time.sleep(2)

        # eval at 2:01:00pm, will run.
        run_time = dateutil_parser.parse('11/29/2017 2:01:00pm')
        next_run_time = run_time + datetime.timedelta(seconds=30)
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)
        self.assertEqual(ret['_next_fire_time'], next_run_time)

        time.sleep(2)

        # eval at 2:01:30pm, will run.
        run_time = dateutil_parser.parse('11/29/2017 2:01:30pm')
        next_run_time = run_time + datetime.timedelta(seconds=30)
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)
        self.assertEqual(ret['_next_fire_time'], next_run_time)

    def test_eval_minutes(self):
        '''
        verify that scheduled job run mutiple times with minutes
        '''
        job_name = 'job_eval_minutes'
        job = {
          'schedule': {
            job_name: {
              'function': 'test.ping',
              'minutes': '30',
            }
          }
        }

        if salt.utils.platform.is_darwin():
            job['schedule'][job_name]['dry_run'] = True

        # Add job to schedule
        self.schedule.opts.update(job)

        # eval at 2:00pm to prime, simulate minion start up.
        run_time = dateutil_parser.parse('11/29/2017 2:00pm')
        next_run_time = run_time + datetime.timedelta(minutes=30)
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_next_fire_time'], next_run_time)

        # eval at 2:00:01pm, will not run.
        run_time = dateutil_parser.parse('11/29/2017 2:00:01pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertNotIn('_last_run', ret)
        self.assertEqual(ret['_next_fire_time'], next_run_time)

        # eval at 2:30:00pm, will run.
        run_time = dateutil_parser.parse('11/29/2017 2:30:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)

        time.sleep(2)

        # eval at 3:00:00pm, will run.
        run_time = dateutil_parser.parse('11/29/2017 3:00:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)

        time.sleep(2)

        # eval at 3:30:00pm, will run.
        run_time = dateutil_parser.parse('11/29/2017 3:30:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)

    def test_eval_hours(self):
        '''
        verify that scheduled job run mutiple times with hours
        '''
        job_name = 'job_eval_hours'
        job = {
          'schedule': {
            job_name: {
              'function': 'test.ping',
              'hours': '2',
            }
          }
        }

        if salt.utils.platform.is_darwin():
            job['schedule'][job_name]['dry_run'] = True

        # Add job to schedule
        self.schedule.opts.update(job)

        # eval at 2:00pm to prime, simulate minion start up.
        run_time = dateutil_parser.parse('11/29/2017 2:00pm')
        next_run_time = run_time + datetime.timedelta(hours=2)
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_next_fire_time'], next_run_time)

        # eval at 2:00:01pm, will not run.
        run_time = dateutil_parser.parse('11/29/2017 2:00:01pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertNotIn('_last_run', ret)
        self.assertEqual(ret['_next_fire_time'], next_run_time)

        # eval at 4:00:00pm, will run.
        run_time = dateutil_parser.parse('11/29/2017 4:00:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)

        time.sleep(2)

        # eval at 6:00:00pm, will run.
        run_time = dateutil_parser.parse('11/29/2017 6:00:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)

        time.sleep(2)

        # eval at 8:00:00pm, will run.
        run_time = dateutil_parser.parse('11/29/2017 8:00:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)

    def test_eval_days(self):
        '''
        verify that scheduled job run mutiple times with days
        '''
        job_name = 'job_eval_days'
        job = {
          'schedule': {
            job_name: {
              'function': 'test.ping',
              'days': '2',
              'dry_run': True
            }
          }
        }

        if salt.utils.platform.is_darwin():
            job['schedule'][job_name]['dry_run'] = True

        # Add job to schedule
        self.schedule.opts.update(job)

        # eval at 11/23/2017 2:00pm to prime, simulate minion start up.
        run_time = dateutil_parser.parse('11/23/2017 2:00pm')
        next_run_time = run_time + datetime.timedelta(days=2)
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_next_fire_time'], next_run_time)

        # eval at 11/25/2017 2:00:00pm, will run.
        run_time = dateutil_parser.parse('11/25/2017 2:00:00pm')
        next_run_time = run_time + datetime.timedelta(days=2)
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)
        self.assertEqual(ret['_next_fire_time'], next_run_time)

        # eval at 11/26/2017 2:00:00pm, will not run.
        run_time = dateutil_parser.parse('11/26/2017 2:00:00pm')
        last_run_time = run_time - datetime.timedelta(days=1)
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], last_run_time)
        self.assertEqual(ret['_next_fire_time'], next_run_time)

        time.sleep(2)

        # eval at 11/27/2017 2:00:00pm, will run.
        run_time = dateutil_parser.parse('11/27/2017 2:00:00pm')
        next_run_time = run_time + datetime.timedelta(days=2)
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)
        self.assertEqual(ret['_next_fire_time'], next_run_time)

        time.sleep(2)

        # eval at 11/28/2017 2:00:00pm, will not run.
        run_time = dateutil_parser.parse('11/28/2017 2:00:00pm')
        last_run_time = run_time - datetime.timedelta(days=1)
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], last_run_time)
        self.assertEqual(ret['_next_fire_time'], next_run_time)

        time.sleep(2)

        # eval at 11/29/2017 2:00:00pm, will run.
        run_time = dateutil_parser.parse('11/29/2017 2:00:00pm')
        next_run_time = run_time + datetime.timedelta(days=2)
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret['_last_run'], run_time)
        self.assertEqual(ret['_next_fire_time'], next_run_time)

    def test_eval_when_splay(self):
        '''
        verify that scheduled job runs
        '''
        job_name = 'test_eval_when_splay'
        splay = 300
        job = {
          'schedule': {
            job_name: {
              'function': 'test.ping',
              'when': '11/29/2017 4:00pm',
              'splay': splay
            }
          }
        }
        run_time1 = dateutil_parser.parse('11/29/2017 4:00pm')
        run_time2 = run_time1 + datetime.timedelta(seconds=splay)

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        with patch('random.randint', MagicMock(return_value=splay)):
            # Evaluate to prime
            run_time = dateutil_parser.parse('11/29/2017 3:00pm')
            self.schedule.eval(now=run_time)
            ret = self.schedule.job_status(job_name)

            # Evaluate at expected runtime1, should not run
            self.schedule.eval(now=run_time1)
            ret = self.schedule.job_status(job_name)
            self.assertNotIn('_last_run', ret)

            # Evaluate at expected runtime2, should run
            self.schedule.eval(now=run_time2)
            ret = self.schedule.job_status(job_name)
            self.assertEqual(ret['_last_run'], run_time2)

    def test_eval_when_splay_in_past(self):
        '''
        verify that scheduled job runs
        '''
        job_name = 'test_eval_when_splay_in_past'
        splay = 300
        job = {
          'schedule': {
            job_name: {
              'function': 'test.ping',
              'when': ['11/29/2017 6:00am'],
              'splay': splay
            }
          }
        }
        run_time1 = dateutil_parser.parse('11/29/2017 4:00pm')

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # Evaluate to prime
        run_time = dateutil_parser.parse('11/29/2017 3:00pm')
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)

        # Evaluate at expected runtime1, should not run
        # and _next_fire_time should be None
        self.schedule.eval(now=run_time1)
        ret = self.schedule.job_status(job_name)
        self.assertNotIn('_last_run', ret)
        self.assertEqual(ret['_next_fire_time'], None)
