# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Salt Libs
from salt.utils.schedule import Schedule

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.mock import MagicMock, patch
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')


class ScheduleTestCase(TestCase):
    '''
    Unit tests for salt.utils.schedule module
    '''

    def setUp(self):
        with patch('salt.utils.schedule.clean_proc_dir', MagicMock(return_value=None)):
            self.schedule = Schedule({}, {}, returners={})

    # delete_job tests

    def test_delete_job_exists(self):
        '''
        Tests ensuring the job exists and deleting it
        '''
        self.schedule.opts = {'schedule': {'foo': 'bar'}, 'pillar': ''}
        self.schedule.delete_job('foo')
        self.assertNotIn('foo', self.schedule.opts)

    def test_delete_job_in_pillar(self):
        '''
        Tests deleting job in pillar
        '''
        self.schedule.opts = {'pillar': {'schedule': {'foo': 'bar'}}, 'schedule': ''}
        self.schedule.delete_job('foo')
        self.assertNotIn('foo', self.schedule.opts)

    def test_delete_job_intervals(self):
        '''
        Tests removing job from intervals
        '''
        self.schedule.opts = {'pillar': '', 'schedule': ''}
        self.schedule.intervals = {'foo': 'bar'}
        self.schedule.delete_job('foo')
        self.assertNotIn('foo', self.schedule.intervals)

    # add_job tests

    def test_add_job_data_not_dict(self):
        '''
        Tests if data is a dictionary
        '''
        data = 'foo'
        self.assertRaises(ValueError, Schedule.add_job, self.schedule, data)

    def test_add_job_multiple_jobs(self):
        '''
        Tests if more than one job is scheduled at a time
        '''
        data = {'key1': 'value1', 'key2': 'value2'}
        self.assertRaises(ValueError, Schedule.add_job, self.schedule, data)

    # enabled_schedule tests

    def test_enable_schedule(self):
        '''
        Tests enabling the scheduler
        '''
        self.schedule.opts = {'schedule': {'enabled': 'foo'}}
        Schedule.enable_schedule(self.schedule)
        self.assertTrue(self.schedule.opts['schedule']['enabled'])

    # disable_schedule tests

    def test_disable_schedule(self):
        '''
        Tests disabling the scheduler
        '''
        self.schedule.opts = {'schedule': {'enabled': 'foo'}}
        Schedule.disable_schedule(self.schedule)
        self.assertFalse(self.schedule.opts['schedule']['enabled'])

    # reload tests

    def test_reload_update_schedule_key(self):
        '''
        Tests reloading and updating the schedule from saved schedule file that
        contains a schedule key
        '''
        saved = {'schedule': {'foo': 'bar'}}
        ret = {'schedule': {'foo': 'bar', 'hello': 'world'}}
        self.schedule.opts = {'schedule': {'hello': 'world'}}
        Schedule.reload(self.schedule, saved)
        self.assertEqual(self.schedule.opts, ret)

    def test_reload_update_schedule_no_key(self):
        '''
        Tests reloading and updating the schedule from saved schedule file that
        contains a schedule key
        '''
        saved = {'foo': 'bar'}
        ret = {'schedule': {'foo': 'bar', 'hello': 'world'}}
        self.schedule.opts = {'schedule': {'hello': 'world'}}
        Schedule.reload(self.schedule, saved)
        self.assertEqual(self.schedule.opts, ret)

    def test_reload_no_schedule_in_opts(self):
        '''
        Tests reloading the schedule
        '''
        saved = {'foo': 'bar'}
        ret = {'schedule': {'foo': 'bar'}}
        Schedule.reload(self.schedule, saved)
        self.assertEqual(self.schedule.opts, ret)

    def test_reload_schedule_in_saved_but_not_opts(self):
        '''
        Tests reloading the schedule
        '''
        saved = {'schedule': {'foo': 'bar'}}
        ret = {'schedule': {'schedule': {'foo': 'bar'}}}
        Schedule.reload(self.schedule, saved)
        self.assertEqual(self.schedule.opts, ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ScheduleTestCase, needs_daemon=False)
