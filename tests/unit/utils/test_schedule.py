# -*- coding: utf-8 -*-
'''
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import copy
import datetime
import os

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON
import tests.integration as integration

# Import Salt Libs
import salt.config
from salt.ext.six import moves
from salt.utils.schedule import Schedule

# pylint: disable=import-error,unused-import
try:
    import croniter
    _CRON_SUPPORTED = True
except ImportError:
    _CRON_SUPPORTED = False
# pylint: enable=import-error

# pylint: disable=import-error,unused-import
try:
    import dateutil
    _DATEUTIL_SUPPORTED = True
except ImportError:
    _DATEUTIL_SUPPORTED = False
# pylint: enable=import-error


ROOT_DIR = os.path.join(integration.TMP, 'schedule-unit-tests')
SOCK_DIR = os.path.join(ROOT_DIR, 'test-socks')

DEFAULT_CONFIG = salt.config.minion_config(None)
DEFAULT_CONFIG['conf_dir'] = ROOT_DIR
DEFAULT_CONFIG['root_dir'] = ROOT_DIR
DEFAULT_CONFIG['sock_dir'] = SOCK_DIR
DEFAULT_CONFIG['pki_dir'] = os.path.join(ROOT_DIR, 'pki')
DEFAULT_CONFIG['cachedir'] = os.path.join(ROOT_DIR, 'cache')

ZERO = datetime.timedelta(0)


class UTC(datetime.tzinfo):
    """UTC Class, not included in Python 2 by default"""

    def utcoffset(self, dt):
        return ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return ZERO


# pylint: disable=too-many-public-methods,invalid-name
@skipIf(NO_MOCK, NO_MOCK_REASON)
class ScheduleTestCase(TestCase):
    '''
    Unit tests for salt.utils.schedule module
    '''

    def setUp(self):
        self.utc = UTC()
        with patch('salt.utils.schedule.clean_proc_dir', MagicMock(return_value=None)):
            self.schedule = Schedule(copy.deepcopy(DEFAULT_CONFIG), {}, returners={})

    # delete_job tests

    @staticmethod
    def replace_dt(dt, dtrange, key):
        dt = dt.replace(
            hour=dtrange[key].hour,
            minute=dtrange[key].minute,
            second=dtrange[key].second,
            microsecond=dtrange[key].microsecond
        )
        return dt

    @classmethod
    def increment_range(cls, next_fire, dtrange):
        if next_fire.day != dtrange['end'].day:
            dtrange['start'] = cls.replace_dt(next_fire, dtrange, 'start')
            dtrange['end'] = cls.replace_dt(next_fire, dtrange, 'end')

    def calculate_future_runs(self, schedule_data, now=None, end=None):
        '''
        Approximation of how SaltEnterprise calculates future runs
        '''
        if now is None:
            now = datetime.datetime.now(self.utc)

        sched_id = 'narf'
        last_fire = None
        runs = []
        fake_functions = {
            'job.run': lambda: True,
            'job.skip': lambda: True,
            'test.pass': lambda: True,
        }

        opts = {
            'schedule': {sched_id: schedule_data},
            '__role': 'raas',
            'grains': {},
            'pillar': {},
            'loop_interval': 1,
            'extension_modules': '',
        }

        schedule = Schedule(opts, fake_functions, standalone=True, new_instance=True)

        for i in moves.range(0, 1000):
            if i == 1000 - 1:
                raise Exception('Future runs loop limit reached')

            schedule.eval(now=now)
            if '_next_fire_time' in opts['schedule'][sched_id]:
                next_fire = opts['schedule'][sched_id]['_next_fire_time']

                if 'range' in schedule_data:
                    self.increment_range(next_fire, schedule_data['range'])
                    if '_skip_reason' in schedule_data:
                        if next_fire in (None, last_fire) or (end is not None and next_fire > end):
                            break

                        last_fire = next_fire
                        now = next_fire
                        continue

                elif 'cron' in schedule_data:
                    next_fire = schedule_data['_next_scheduled_fire_time']

                if next_fire in (None, last_fire) or (end is not None and next_fire > end):
                    break

                elif next_fire >= now:
                    if 'range' in schedule_data:
                        drange = schedule_data['range']
                        if drange['invert'] and now >= drange['start'] and now <= drange['end']:
                            last_fire = next_fire
                            now = next_fire
                            continue

                        elif not drange['invert'] and (now < drange['start'] or now > drange['end']):
                            last_fire = next_fire
                            now = next_fire
                            continue

                    runs.append(next_fire)
                    last_fire = next_fire
                    now = next_fire

                    if 'cron' in schedule_data:
                        schedule_data['_next_fire_time'] = None

                    elif 'once' in schedule_data:
                        break

                else:
                    break

                continue

            break

        return runs

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

    def test_once(self):
        '''
        Test once schedule
        '''
        once = datetime.datetime.now(self.utc) + datetime.timedelta(minutes=20)
        schedule = {'once': once}

        runs = self.calculate_future_runs(schedule)
        self.assertEqual(len(runs), 1)

    def test_recurring_seconds(self):
        '''
        Test schedule with seconds option
        '''
        start = datetime.datetime.now(self.utc) + datetime.timedelta(seconds=30)
        end = start + datetime.timedelta(minutes=10)
        schedule = {'seconds': 60}

        runs = self.calculate_future_runs(schedule, now=start, end=end)
        self.assertEqual(len(runs), 10)

    def test_recurring_minutes(self):
        '''
        Test schedule with minutes option
        '''
        start = datetime.datetime.now(self.utc) + datetime.timedelta(seconds=30)
        end = start + datetime.timedelta(minutes=10)
        schedule = {'minutes': 1}

        runs = self.calculate_future_runs(schedule, now=start, end=end)
        self.assertEqual(len(runs), 10)

    def test_recurring_hours(self):
        '''
        Test schedule with hours option
        '''
        start = datetime.datetime.now(self.utc) + datetime.timedelta(seconds=30)
        end = start + datetime.timedelta(hours=10)
        schedule = {'hours': 2}

        runs = self.calculate_future_runs(schedule, now=start, end=end)
        self.assertEqual(len(runs), 5)

    @skipIf(not _DATEUTIL_SUPPORTED, 'dateutil module not installed')
    def test_recurring_hours_inside_range(self):
        '''
        Test schedule with hours option inside a range
        '''
        now = datetime.datetime.now(self.utc)
        end = now + datetime.timedelta(days=8)

        range_start = now + datetime.timedelta(days=1)
        range_start = range_start.replace(hour=1, minute=0, second=0, microsecond=0)
        range_end = range_start + datetime.timedelta(hours=2)
        schedule = {
            'hours': 1,
            'range': {
                'start': range_start,
                'end': range_end,
                'invert': False,
            }
        }

        runs = self.calculate_future_runs(schedule, now=now, end=end)
        self.assertEqual(len(runs), 16)

    @skipIf(not _DATEUTIL_SUPPORTED, 'dateutil module not installed')
    def test_recurring_hours_outside_range(self):
        '''
        Test schedule with hours option outside a range
        '''
        now = datetime.datetime.now(self.utc)
        end = now + datetime.timedelta(days=8)

        range_start = now + datetime.timedelta(days=1)
        range_start = range_start.replace(hour=1, minute=0, second=0, microsecond=0)
        range_end = range_start + datetime.timedelta(hours=2)
        schedule = {
            'hours': 1,
            'range': {
                'start': range_start,
                'end': range_end,
                'invert': True,
            }
        }

        runs = self.calculate_future_runs(schedule, now=now, end=end)
        self.assertEqual(len(runs), 176)

    def test_recurring_days(self):
        '''
        Test schedule with days option
        '''
        start = datetime.datetime.now(self.utc) + datetime.timedelta(seconds=30)
        end = start + datetime.timedelta(days=10)
        schedule = {'days': 3}

        runs = self.calculate_future_runs(schedule, now=start, end=end)
        self.assertEqual(len(runs), 3)

    @skipIf(not _CRON_SUPPORTED, 'croniter module not installed')
    def test_cron(self):
        '''
        Test schedule with cron option
        '''
        start = datetime.datetime.now(self.utc) + datetime.timedelta(seconds=30)
        end = start + datetime.timedelta(days=28)
        schedule = {"cron": "0 0 * * *"}

        runs = self.calculate_future_runs(schedule, now=start, end=end)
        self.assertEqual(len(runs), 28)

    @skipIf(not _DATEUTIL_SUPPORTED, 'dateutil module not installed')
    def test_repeat_when(self):
        '''
        Test schedule with when option
        '''
        start = datetime.datetime.now(self.utc) + datetime.timedelta(seconds=30)
        end = start + datetime.timedelta(days=10)
        schedule = {'when': start.isoformat()}

        runs = self.calculate_future_runs(schedule, end=end)
        self.assertEqual(len(runs), 1)
