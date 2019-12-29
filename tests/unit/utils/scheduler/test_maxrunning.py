# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import logging

import dateutil.parser as dateutil_parser

# Import Salt Testing libs
from tests.support.mock import MagicMock, patch
from tests.unit.utils.scheduler.base import SchedulerTestsBase

log = logging.getLogger(__name__)


class SchedulerMaxRunningTest(SchedulerTestsBase):
    '''
    Validate the pkg module
    '''
    def setUp(self):
        super(SchedulerMaxRunningTest, self).setUp()
        self.schedule.opts['loop_interval'] = 1

    def test_maxrunning_minion(self):
        '''
        verify that scheduled job runs
        '''
        self.schedule.opts['__role'] = 'minion'

        job = {
          'schedule': {
            'maxrunning_minion': {
              'function': 'test.ping',
              'seconds': 10,
              'maxrunning': 1
            }
          }
        }

        job_data = {'function': 'test.ping',
                    'run': True,
                    'name': 'maxrunning_minion',
                    'seconds': 10,
                    '_seconds': 10,
                    'jid_include': True,
                    'maxrunning': 1}

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        running_data = [{'fun_args': [],
                         'jid': '20181018165923360935',
                         'schedule': 'maxrunning_minion',
                         'pid': 15338,
                         'fun': 'test.ping',
                         'id': 'host'}]

        run_time = dateutil_parser.parse('11/29/2017 4:00pm')

        with patch('salt.utils.minion.running',
                   MagicMock(return_value=running_data)):
            with patch('salt.utils.process.os_is_running',
                       MagicMock(return_value=True)):
                ret = self.schedule._check_max_running('test.ping',
                                                       job_data,
                                                       self.schedule.opts,
                                                       now=run_time)
        self.assertIn('_skip_reason', ret)
        self.assertEqual('maxrunning', ret['_skip_reason'])
        self.assertEqual(False, ret['run'])

    def test_maxrunning_master(self):
        '''
        verify that scheduled job runs
        '''
        self.schedule.opts['__role'] = 'master'

        job = {
          'schedule': {
            'maxrunning_master': {
              'function': 'state.orch',
              'args': ['test.orch_test'],
              'minutes': 1,
              'maxrunning': 1
            }
          }
        }

        job_data = {'function': 'state.orch',
                    'fun_args': ['test.orch_test'],
                    'run': True,
                    'name': 'maxrunning_master',
                    'minutes': 1,
                    'jid_include': True,
                    'maxrunning': 1}

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        running_data = [{'fun_args': ['test.orch_test'],
                         'jid': '20181018165923360935',
                         'schedule': 'maxrunning_master',
                         'pid': 15338,
                         'fun': 'state.orch',
                         'id': 'host'}]

        run_time = dateutil_parser.parse('11/29/2017 4:00pm')

        with patch('salt.utils.master.get_running_jobs',
                   MagicMock(return_value=running_data)):
            with patch('salt.utils.process.os_is_running',
                       MagicMock(return_value=True)):
                ret = self.schedule._check_max_running('state.orch',
                                                       job_data,
                                                       self.schedule.opts,
                                                       now=run_time)
        self.assertIn('_skip_reason', ret)
        self.assertEqual('maxrunning', ret['_skip_reason'])
        self.assertEqual(False, ret['run'])
