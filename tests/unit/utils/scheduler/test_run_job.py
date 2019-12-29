# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import logging

# Import Salt Testing libs
from tests.unit.utils.scheduler.base import SchedulerTestsBase

log = logging.getLogger(__name__)


class SchedulerRunJobTest(SchedulerTestsBase):
    '''
    Validate the pkg module
    '''
    def setUp(self):
        super(SchedulerRunJobTest, self).setUp()
        self.schedule.opts['loop_interval'] = 1

    def test_run_job(self):
        '''
        verify that scheduled job runs
        '''
        job_name = 'test_run_job'
        job = {
          'schedule': {
            job_name: {
              'function': 'test.ping',
            }
          }
        }
        # Add the job to the scheduler
        self.schedule.opts.update(job)

        # Run job
        self.schedule.run_job(job_name)
        ret = self.schedule.job_status(job_name)
        expected = {'function': 'test.ping', 'run': True, 'name': 'test_run_job'}
        self.assertEqual(ret, expected)
