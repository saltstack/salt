# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import python libs
from __future__ import absolute_import
import os

# Import Salt Libs
from salt.utils.schedule import Schedule

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON
from salttesting.helpers import ensure_in_syspath

import integration

ensure_in_syspath('../../')
SOCK_DIR = os.path.join(integration.TMP, 'test-socks')


@skipIf(NO_MOCK, NO_MOCK_REASON)
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
        self.schedule.opts = {'schedule': {'foo': 'bar'}, 'pillar': '',
                              'sock_dir': SOCK_DIR}
        self.schedule.delete_job('foo')
        self.assertNotIn('foo', self.schedule.opts)

    def test_delete_job_in_pillar(self):
        '''
        Tests deleting job in pillar
        '''
        self.schedule.opts = {'pillar': {'schedule': {'foo': 'bar'}}, 'schedule': '',
                              'sock_dir': SOCK_DIR}
        self.schedule.delete_job('foo')
        self.assertNotIn('foo', self.schedule.opts)

    def test_delete_job_intervals(self):
        '''
        Tests removing job from intervals
        '''
        self.schedule.opts = {'pillar': '', 'schedule': '',
                              'sock_dir': SOCK_DIR}
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

    def test_add_job(self):
        '''
        Tests adding a job to the schedule
        '''
        data = {'foo': 'bar'}
        ret = {'schedule': {'foo': 'bar', 'hello': 'world'}}
        self.schedule.opts = {'schedule': {'hello': 'world'},
                              'sock_dir': SOCK_DIR}
        Schedule.add_job(self.schedule, data)
        del self.schedule.opts['sock_dir']
        self.assertEqual(self.schedule.opts, ret)

    # enable_job tests

    def test_enable_job(self):
        '''
        Tests enabling a job
        '''
        self.schedule.opts = {'schedule': {'name': {'enabled': 'foo'}},
                              'sock_dir': SOCK_DIR}
        Schedule.enable_job(self.schedule, 'name')
        del self.schedule.opts['sock_dir']
        self.assertTrue(self.schedule.opts['schedule']['name']['enabled'])

    def test_enable_job_pillar(self):
        '''
        Tests enabling a job in pillar
        '''
        self.schedule.opts = {'pillar': {'schedule': {'name': {'enabled': 'foo'}}},
                              'sock_dir': SOCK_DIR}
        Schedule.enable_job(self.schedule, 'name', persist=False, where='pillar')
        del self.schedule.opts['sock_dir']
        self.assertTrue(self.schedule.opts['pillar']['schedule']['name']['enabled'])

    # disable_job tests

    def test_disable_job(self):
        '''
        Tests disabling a job
        '''
        self.schedule.opts = {'schedule': {'name': {'enabled': 'foo'}},
                              'sock_dir': SOCK_DIR}
        Schedule.disable_job(self.schedule, 'name')
        del self.schedule.opts['sock_dir']
        self.assertFalse(self.schedule.opts['schedule']['name']['enabled'])

    def test_disable_job_pillar(self):
        '''
        Tests disabling a job in pillar
        '''
        self.schedule.opts = {'pillar': {'schedule': {'name': {'enabled': 'foo'}}},
                              'sock_dir': SOCK_DIR}
        Schedule.disable_job(self.schedule, 'name', persist=False, where='pillar')
        del self.schedule.opts['sock_dir']
        self.assertFalse(self.schedule.opts['pillar']['schedule']['name']['enabled'])

    # modify_job tests

    def test_modify_job(self):
        '''
        Tests modifying a job in the scheduler
        '''
        schedule = {'schedule': {'foo': 'bar'}}
        ret = {'schedule': {'foo': 'bar', 'name': {'schedule': {'foo': 'bar'}}}}
        self.schedule.opts = {'schedule': {'foo': 'bar'}}
        Schedule.modify_job(self.schedule, 'name', schedule)
        self.assertEqual(self.schedule.opts, ret)

    def test_modify_job_pillar(self):
        '''
        Tests modifying a job in the scheduler in pillar
        '''
        schedule = {'foo': 'bar'}
        ret = {'pillar': {'schedule': {'name': {'foo': 'bar'}}}}
        self.schedule.opts = {'pillar': {'schedule': {'name': {'foo': 'bar'}}},
                              'sock_dir': SOCK_DIR}
        Schedule.modify_job(self.schedule, 'name', schedule, persist=False, where='pillar')
        del self.schedule.opts['sock_dir']
        self.assertEqual(self.schedule.opts, ret)

    # enable_schedule tests

    def test_enable_schedule(self):
        '''
        Tests enabling the scheduler
        '''
        self.schedule.opts = {'schedule': {'enabled': 'foo'},
                              'sock_dir': SOCK_DIR}
        Schedule.enable_schedule(self.schedule)
        del self.schedule.opts['sock_dir']
        self.assertTrue(self.schedule.opts['schedule']['enabled'])

    # disable_schedule tests

    def test_disable_schedule(self):
        '''
        Tests disabling the scheduler
        '''
        self.schedule.opts = {'schedule': {'enabled': 'foo'},
                              'sock_dir': SOCK_DIR}
        Schedule.disable_schedule(self.schedule)
        del self.schedule.opts['sock_dir']
        self.assertFalse(self.schedule.opts['schedule']['enabled'])

    # reload tests

    def test_reload_update_schedule_key(self):
        '''
        Tests reloading the schedule from saved schedule where both the
        saved schedule and self.schedule.opts contain a schedule key
        '''
        saved = {'schedule': {'foo': 'bar'}}
        ret = {'schedule': {'foo': 'bar', 'hello': 'world'}}
        self.schedule.opts = {'schedule': {'hello': 'world'}}
        Schedule.reload(self.schedule, saved)
        self.assertEqual(self.schedule.opts, ret)

    def test_reload_update_schedule_no_key(self):
        '''
        Tests reloading the schedule from saved schedule that does not
        contain a schedule key but self.schedule.opts does not
        '''
        saved = {'foo': 'bar'}
        ret = {'schedule': {'foo': 'bar', 'hello': 'world'}}
        self.schedule.opts = {'schedule': {'hello': 'world'}}
        Schedule.reload(self.schedule, saved)
        self.assertEqual(self.schedule.opts, ret)

    def test_reload_no_schedule_in_opts(self):
        '''
        Tests reloading the schedule from saved schedule that does not
        contain a schedule key and neither does self.schedule.opts
        '''
        saved = {'foo': 'bar'}
        ret = {'schedule': {'foo': 'bar'}}
        Schedule.reload(self.schedule, saved)
        self.assertEqual(self.schedule.opts, ret)

    def test_reload_schedule_in_saved_but_not_opts(self):
        '''
        Tests reloading the schedule from saved schedule that contains
        a schedule key, but self.schedule.opts does not
        '''
        saved = {'schedule': {'foo': 'bar'}}
        ret = {'schedule': {'schedule': {'foo': 'bar'}}}
        Schedule.reload(self.schedule, saved)
        self.assertEqual(self.schedule.opts, ret)

    # eval tests

    def test_eval_schedule_is_not_dict(self):
        '''
        Tests if the schedule is a dictionary
        '''
        self.schedule.opts = {'schedule': ''}
        self.assertRaises(ValueError, Schedule.eval, self.schedule)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ScheduleTestCase, needs_daemon=False)
