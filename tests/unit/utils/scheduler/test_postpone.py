# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import datetime
import logging

import dateutil.parser as dateutil_parser

# Import Salt Testing libs
from tests.unit.utils.scheduler.base import SchedulerTestsBase


log = logging.getLogger(__name__)


class SchedulerPostponeTest(SchedulerTestsBase):
    '''
    Validate the pkg module
    '''
    def setUp(self):
        super(SchedulerPostponeTest, self).setUp()
        self.schedule.opts['loop_interval'] = 1

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
