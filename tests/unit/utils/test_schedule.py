# -*- coding: utf-8 -*-
'''
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import copy
import datetime
import logging
import os

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON
import tests.integration as integration

# Import Salt Libs
import salt.config
from salt.utils.schedule import Schedule

from salt.modules.test import ping as test_ping
from salt.modules.test import true_ as test_true
from salt.modules.status import time as status_time
from salt.modules.cmdmod import run as cmd_run

# pylint: disable=import-error,unused-import
try:
    import croniter
    _CRON_SUPPORTED = True
except ImportError:
    _CRON_SUPPORTED = False
# pylint: enable=import-error

log = logging.getLogger(__name__)

ROOT_DIR = os.path.join(integration.TMP, 'schedule-unit-tests')
SOCK_DIR = os.path.join(ROOT_DIR, 'test-socks')

DEFAULT_CONFIG = salt.config.minion_config(None)
DEFAULT_CONFIG['conf_dir'] = ROOT_DIR
DEFAULT_CONFIG['root_dir'] = ROOT_DIR
DEFAULT_CONFIG['sock_dir'] = SOCK_DIR
DEFAULT_CONFIG['pki_dir'] = os.path.join(ROOT_DIR, 'pki')
DEFAULT_CONFIG['cachedir'] = os.path.join(ROOT_DIR, 'cache')


# pylint: disable=too-many-public-methods,invalid-name
@skipIf(NO_MOCK, NO_MOCK_REASON)
class ScheduleTestCase(TestCase):
    '''
    Unit tests for salt.utils.schedule module
    '''

    def setUp(self):
        with patch('salt.utils.schedule.clean_proc_dir', MagicMock(return_value=None)):
            functions = {'test.ping': test_ping,
                         'test.true': test_true,
                         'status.time': status_time,
                         'cmd.run': cmd_run}
            self.schedule = Schedule(copy.deepcopy(DEFAULT_CONFIG),
                                     functions,
                                     returners={})

    # delete_job tests

    def test_delete_job_exists(self):
        '''
        Tests ensuring the job exists and deleting it
        '''
        self.schedule.opts.update({'schedule': {'foo': 'bar'}, 'pillar': {}})
        self.assertIn('foo', self.schedule.opts['schedule'])
        self.schedule.delete_job('foo')
        self.assertNotIn('foo', self.schedule.opts['schedule'])

    def test_delete_job_in_pillar(self):
        '''
        Tests ignoring deletion job from pillar
        '''
        self.schedule.opts.update({'pillar': {'schedule': {'foo': 'bar'}}, 'schedule': {}})
        self.assertIn('foo', self.schedule.opts['pillar']['schedule'])
        self.schedule.delete_job('foo')
        self.assertIn('foo', self.schedule.opts['pillar']['schedule'])

    def test_delete_job_intervals(self):
        '''
        Tests removing job from intervals
        '''
        self.schedule.opts.update({'pillar': {}, 'schedule': {}})
        self.schedule.intervals = {'foo': 'bar'}
        self.schedule.delete_job('foo')
        self.assertNotIn('foo', self.schedule.intervals)

    def test_delete_job_prefix(self):
        '''
        Tests ensuring jobs exists and deleting them by prefix
        '''
        self.schedule.opts.update({'schedule': {'foobar': 'bar', 'foobaz': 'baz', 'fooboo': 'boo'},
                                   'pillar': {}})
        ret = copy.deepcopy(self.schedule.opts)
        del ret['schedule']['foobar']
        del ret['schedule']['foobaz']
        self.schedule.delete_job_prefix('fooba')
        self.assertEqual(self.schedule.opts, ret)

    def test_delete_job_prefix_in_pillar(self):
        '''
        Tests ignoring deletion jobs by prefix from pillar
        '''
        self.schedule.opts.update({'pillar': {'schedule': {'foobar': 'bar', 'foobaz': 'baz', 'fooboo': 'boo'}},
                                   'schedule': {}})
        ret = copy.deepcopy(self.schedule.opts)
        self.schedule.delete_job_prefix('fooba')
        self.assertEqual(self.schedule.opts, ret)

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
        data = {'foo': {'bar': 'baz'}}
        ret = copy.deepcopy(self.schedule.opts)
        ret.update({'schedule': {'foo': {'bar': 'baz', 'enabled': True},
                                 'hello': {'world': 'peace', 'enabled': True}},
                    'pillar': {}})
        self.schedule.opts.update({'schedule': {'hello': {'world': 'peace', 'enabled': True}},
                                   'pillar': {}})
        Schedule.add_job(self.schedule, data)
        self.assertEqual(self.schedule.opts, ret)

    # enable_job tests

    def test_enable_job(self):
        '''
        Tests enabling a job
        '''
        self.schedule.opts.update({'schedule': {'name': {'enabled': 'foo'}}})
        Schedule.enable_job(self.schedule, 'name')
        self.assertTrue(self.schedule.opts['schedule']['name']['enabled'])

    def test_enable_job_pillar(self):
        '''
        Tests ignoring enable a job from pillar
        '''
        self.schedule.opts.update({'pillar': {'schedule': {'name': {'enabled': False}}}})
        Schedule.enable_job(self.schedule, 'name', persist=False)
        self.assertFalse(self.schedule.opts['pillar']['schedule']['name']['enabled'])

    # disable_job tests

    def test_disable_job(self):
        '''
        Tests disabling a job
        '''
        self.schedule.opts.update({'schedule': {'name': {'enabled': 'foo'}}, 'pillar': {}})
        Schedule.disable_job(self.schedule, 'name')
        self.assertFalse(self.schedule.opts['schedule']['name']['enabled'])

    def test_disable_job_pillar(self):
        '''
        Tests ignoring disable a job in pillar
        '''
        self.schedule.opts.update({'pillar': {'schedule': {'name': {'enabled': True}}}, 'schedule': {}})
        Schedule.disable_job(self.schedule, 'name', persist=False)
        self.assertTrue(self.schedule.opts['pillar']['schedule']['name']['enabled'])

    # modify_job tests

    def test_modify_job(self):
        '''
        Tests modifying a job in the scheduler
        '''
        schedule = {'foo': 'bar'}
        self.schedule.opts.update({'schedule': {'name': 'baz'}, 'pillar': {}})
        ret = copy.deepcopy(self.schedule.opts)
        ret.update({'schedule': {'name': {'foo': 'bar'}}})
        Schedule.modify_job(self.schedule, 'name', schedule)
        self.assertEqual(self.schedule.opts, ret)

    def test_modify_job_not_exists(self):
        '''
        Tests modifying a job in the scheduler if jobs not exists
        '''
        schedule = {'foo': 'bar'}
        self.schedule.opts.update({'schedule': {}, 'pillar': {}})
        ret = copy.deepcopy(self.schedule.opts)
        ret.update({'schedule': {'name':  {'foo': 'bar'}}})
        Schedule.modify_job(self.schedule, 'name', schedule)
        self.assertEqual(self.schedule.opts, ret)

    def test_modify_job_pillar(self):
        '''
        Tests ignoring modification of job from pillar
        '''
        schedule = {'foo': 'bar'}
        self.schedule.opts.update({'schedule': {}, 'pillar': {'schedule': {'name': 'baz'}}})
        ret = copy.deepcopy(self.schedule.opts)
        Schedule.modify_job(self.schedule, 'name', schedule, persist=False)
        self.assertEqual(self.schedule.opts, ret)

    maxDiff = None

    # enable_schedule tests

    def test_enable_schedule(self):
        '''
        Tests enabling the scheduler
        '''
        self.schedule.opts.update({'schedule': {'enabled': 'foo'}, 'pillar': {}})
        Schedule.enable_schedule(self.schedule)
        self.assertTrue(self.schedule.opts['schedule']['enabled'])

    # disable_schedule tests

    def test_disable_schedule(self):
        '''
        Tests disabling the scheduler
        '''
        self.schedule.opts.update({'schedule': {'enabled': 'foo'}, 'pillar': {}})
        Schedule.disable_schedule(self.schedule)
        self.assertFalse(self.schedule.opts['schedule']['enabled'])

    # reload tests

    def test_reload_update_schedule_key(self):
        '''
        Tests reloading the schedule from saved schedule where both the
        saved schedule and self.schedule.opts contain a schedule key
        '''
        saved = {'schedule': {'foo': 'bar'}}
        ret = copy.deepcopy(self.schedule.opts)
        ret.update({'schedule': {'foo': 'bar', 'hello': 'world'}})
        self.schedule.opts.update({'schedule': {'hello': 'world'}})
        Schedule.reload(self.schedule, saved)
        self.assertEqual(self.schedule.opts, ret)

    def test_reload_update_schedule_no_key(self):
        '''
        Tests reloading the schedule from saved schedule that does not
        contain a schedule key but self.schedule.opts does
        '''
        saved = {'foo': 'bar'}
        ret = copy.deepcopy(self.schedule.opts)
        ret.update({'schedule': {'foo': 'bar', 'hello': 'world'}})
        self.schedule.opts.update({'schedule': {'hello': 'world'}})
        Schedule.reload(self.schedule, saved)
        self.assertEqual(self.schedule.opts, ret)

    def test_reload_no_schedule_in_opts(self):
        '''
        Tests reloading the schedule from saved schedule that does not
        contain a schedule key and neither does self.schedule.opts
        '''
        saved = {'foo': 'bar'}
        ret = copy.deepcopy(self.schedule.opts)
        ret['schedule'] = {'foo': 'bar'}
        self.schedule.opts.pop('schedule', None)
        Schedule.reload(self.schedule, saved)
        self.assertEqual(self.schedule.opts, ret)

    def test_reload_schedule_in_saved_but_not_opts(self):
        '''
        Tests reloading the schedule from saved schedule that contains
        a schedule key, but self.schedule.opts does not
        '''
        saved = {'schedule': {'foo': 'bar'}}
        ret = copy.deepcopy(self.schedule.opts)
        ret['schedule'] = {'foo': 'bar'}
        self.schedule.opts.pop('schedule', None)
        Schedule.reload(self.schedule, saved)
        self.assertEqual(self.schedule.opts, ret)

    # eval tests

    def test_eval_schedule_is_not_dict(self):
        '''
        Tests eval if the schedule is not a dictionary
        '''
        self.schedule.opts.update({'schedule': '', 'pillar': {'schedule': {}}})
        self.assertRaises(ValueError, Schedule.eval, self.schedule)

    def test_eval_schedule_is_not_dict_in_pillar(self):
        '''
        Tests eval if the schedule from pillar is not a dictionary
        '''
        self.schedule.opts.update({'schedule': {}, 'pillar': {'schedule': ''}})
        self.assertRaises(ValueError, Schedule.eval, self.schedule)

    def test_eval_schedule_time(self):
        '''
        Tests eval if the schedule setting time is in the future
        '''
        self.schedule.opts.update({'pillar': {'schedule': {}}})
        self.schedule.opts.update({'schedule': {'testjob': {'function': 'test.true', 'seconds': 60}}})
        now = datetime.datetime.now()
        self.schedule.eval()
        self.assertTrue(self.schedule.opts['schedule']['testjob']['_next_fire_time'] > now)

    def test_eval_schedule_time_eval(self):
        '''
        Tests eval if the schedule setting time is in the future plus splay
        '''
        self.schedule.opts.update({'pillar': {'schedule': {}}})
        self.schedule.opts.update(
            {'schedule': {'testjob': {'function': 'test.true', 'seconds': 60, 'splay': 5}}})
        now = datetime.datetime.now()
        self.schedule.eval()
        self.assertTrue(self.schedule.opts['schedule']['testjob']['_splay'] - now > datetime.timedelta(seconds=60))

    @skipIf(not _CRON_SUPPORTED, 'croniter module not installed')
    def test_eval_schedule_cron(self):
        '''
        Tests eval if the schedule is defined with cron expression
        '''
        self.schedule.opts.update({'pillar': {'schedule': {}}})
        self.schedule.opts.update({'schedule': {'testjob': {'function': 'test.true', 'cron': '* * * * *'}}})
        now = datetime.datetime.now()
        self.schedule.eval()
        self.assertTrue(self.schedule.opts['schedule']['testjob']['_next_fire_time'] > now)

    @skipIf(not _CRON_SUPPORTED, 'croniter module not installed')
    def test_eval_schedule_cron_splay(self):
        '''
        Tests eval if the schedule is defined with cron expression plus splay
        '''
        self.schedule.opts.update({'pillar': {'schedule': {}}})
        self.schedule.opts.update(
            {'schedule': {'testjob': {'function': 'test.true', 'cron': '* * * * *', 'splay': 5}}})
        self.schedule.eval()
        self.assertTrue(self.schedule.opts['schedule']['testjob']['_splay'] >
                        self.schedule.opts['schedule']['testjob']['_next_fire_time'])

    def test_handle_func_schedule_minion_blackout(self):
        '''
        Tests eval if the schedule from pillar is not a dictionary
        '''
        self.schedule.opts.update({'pillar': {'schedule': {}}})
        self.schedule.opts.update({'grains': {'minion_blackout': True}})

        self.schedule.opts.update(
            {'schedule': {'testjob': {'function': 'test.true',
                                      'seconds': 60}}})
        data = {'function': 'test.true',
                '_next_scheduled_fire_time': datetime.datetime(2018,
                                                               11,
                                                               21,
                                                               14,
                                                               9,
                                                               53,
                                                               903438),
                'run': True,
                'name': 'testjob',
                'seconds': 60,
                '_splay': None,
                '_seconds': 60,
                'jid_include': True,
                'maxrunning': 1,
                '_next_fire_time': datetime.datetime(2018,
                                                     11,
                                                     21,
                                                     14,
                                                     8,
                                                     53,
                                                     903438)}

        with patch.object(salt.utils.schedule, 'log') as log_mock:
            with patch('salt.utils.process.daemonize'), \
                patch('sys.platform', 'linux2'):
                self.schedule.handle_func(False, 'test.ping', data)
                self.assertTrue(log_mock.exception.called)

    def test_eval_schedule_compound_function(self):
        '''
        Tests eval if the schedule setting time is in the future
        '''
        self.schedule.opts.update({'pillar': {'schedule': {}}})
        self.schedule.opts.update({'schedule': {'testjob': {'function': ['cmd.run', 'status.time'],
                                                            'args': [["data"], []],
                                                            'seconds': 60}}})
        now = datetime.datetime.now()
        self.schedule.eval()
        self.assertTrue(self.schedule.opts['schedule']['testjob']['_next_fire_time'] > now)

    def test_eval_schedule_invalid_arguments(self):
        '''
        Tests eval if the schedule if data contains error
        '''
        self.schedule.opts.update({'pillar': {'schedule': {}}})
        self.schedule.opts.update({'schedule': {'testjob': {'function': ['cmd.run', 'status.time'],
                                                            'args': [["data"]],
                                                            'seconds': 60}}})
        now = datetime.datetime.now()

        # Run eval one to prime the scheduler
        self.schedule.eval()

        # Run in "60 seconds" and we should receive the error
        self.schedule.eval(now + datetime.timedelta(seconds=60))
        self.assertIn('_error', self.schedule.opts['schedule']['testjob'])
        _expected = 'Number of arguments is less than the number of functions. Ignoring job.'
        self.assertEqual(self.schedule.opts['schedule']['testjob']['_error'], _expected)
