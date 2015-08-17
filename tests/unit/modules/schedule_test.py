# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

import os
import integration
SOCK_DIR = os.path.join(integration.TMP, 'test-socks')

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import schedule
from salt.utils.event import SaltEvent

# Globals
schedule.__salt__ = {}
schedule.__opts__ = {}
schedule.__pillar__ = {}

JOB1 = {'function': 'test.ping', 'maxrunning': 1, 'name': 'job1',
        'jid_include': True}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ScheduleTestCase(TestCase):
    '''
    Test cases for salt.modules.schedule
    '''
    # 'list_' function tests: 1

    def test_list(self):
        '''
        Test if it list the jobs currently scheduled on the minion.
        '''
        with patch.dict(schedule.__opts__, {'schedule': {'_seconds': []}, 'sock_dir': SOCK_DIR}):
            mock = MagicMock(return_value=True)
            with patch.dict(schedule.__salt__, {'event.fire': mock}):
                _ret_value = {'complete': True, 'schedule': {'_seconds': []}}
                with patch.object(SaltEvent, 'get_event', return_value=_ret_value):
                    self.assertEqual(schedule.list_(), 'schedule:\n  _seconds: []\n')
                    self.assertDictEqual(schedule.list_(show_all=True, return_yaml=False), {'_seconds': []})

        with patch.dict(schedule.__opts__, {'schedule': {}, 'sock_dir': SOCK_DIR}):
            mock = MagicMock(return_value=True)
            with patch.dict(schedule.__salt__, {'event.fire': mock}):
                _ret_value = {'complete': True, 'schedule': {}}
                with patch.object(SaltEvent, 'get_event', return_value=_ret_value):
                    self.assertDictEqual(schedule.list_(), {'schedule': {}})

    # 'purge' function tests: 1

    def test_purge(self):
        '''
        Test if it purge all the jobs currently scheduled on the minion.
        '''
        with patch.dict(schedule.__opts__, {'schedule': {}, 'sock_dir': SOCK_DIR}):
            mock = MagicMock(return_value=True)
            with patch.dict(schedule.__salt__, {'event.fire': mock}):
                _ret_value = {'complete': True, 'schedule': {}}
                with patch.object(SaltEvent, 'get_event', return_value=_ret_value):
                    self.assertDictEqual(schedule.purge(), {'comment': ['Deleted job: schedule from schedule.'],
                                                            'result': True})

    # 'delete' function tests: 1

    def test_delete(self):
        '''
        Test if it delete a job from the minion's schedule.
        '''
        with patch.dict(schedule.__opts__, {'schedule': {}, 'sock_dir': SOCK_DIR}):
            mock = MagicMock(return_value=True)
            with patch.dict(schedule.__salt__, {'event.fire': mock}):
                _ret_value = {'complete': True, 'schedule': {}}
                with patch.object(SaltEvent, 'get_event', return_value=_ret_value):
                    self.assertDictEqual(schedule.delete('job1'),
                                         {'comment': 'Job job1 does not exist.',
                                          'result': False})

    # 'build_schedule_item' function tests: 1

    def test_build_schedule_item(self):
        '''
        Test if it build a schedule job.
        '''
        comment = ('Unable to use "seconds", "minutes", "hours",'
                   ' or "days" with "when" or "cron" options.')
        comment1 = ('Unable to use "when" and "cron"'
                    ' options together.  Ignoring.')
        with patch.dict(schedule.__opts__, {'job1': {}}):
            self.assertDictEqual(schedule.build_schedule_item(''),
                                 {'comment': 'Job name is required.',
                                  'result': False})

            self.assertDictEqual(schedule.build_schedule_item
                                 ('job1', function='test.ping'),
                                 {'function': 'test.ping', 'maxrunning': 1,
                                  'name': 'job1', 'jid_include': True})

            self.assertDictEqual(schedule.build_schedule_item
                                 ('job1', function='test.ping', seconds=3600,
                                  when='2400'),
                                 {'comment': comment, 'result': False})

            self.assertDictEqual(schedule.build_schedule_item
                                 ('job1', function='test.ping', when='2400',
                                  cron='2'),
                                 {'comment': comment1, 'result': False})

    # 'add' function tests: 1

    def test_add(self):
        '''
        Test if it add a job to the schedule.
        '''
        comm1 = 'Job job1 already exists in schedule.'
        comm2 = ('Error: Unable to use "seconds", "minutes", "hours",'
                 ' or "days" with "when" or "cron" options.')
        comm3 = 'Unable to use "when" and "cron" options together.  Ignoring.'
        comm4 = 'Job: job2 would be added to schedule.'
        with patch.dict(schedule.__opts__, {'schedule': {'job1': 'salt'}, 'sock_dir': SOCK_DIR}):
            mock = MagicMock(return_value=True)
            with patch.dict(schedule.__salt__, {'event.fire': mock}):
                _ret_value = {'complete': True, 'schedule': {'job1': {'salt': 'salt'}}}
                with patch.object(SaltEvent, 'get_event', return_value=_ret_value):
                    self.assertDictEqual(schedule.add('job1'),
                                         {'comment': comm1, 'result': False})

                _ret_value = {'complete': True, 'schedule': {}}
                with patch.object(SaltEvent, 'get_event', return_value=_ret_value):
                    self.assertDictEqual(schedule.add('job2', function='test.ping',
                                                      seconds=3600, when='2400'),
                                         {'comment': comm2, 'result': False})

                _ret_value = {'complete': True, 'schedule': {}}
                with patch.object(SaltEvent, 'get_event', return_value=_ret_value):
                    self.assertDictEqual(schedule.add('job2', function='test.ping',
                                                      when='2400', cron='2'),
                                         {'comment': comm3, 'result': False})
                _ret_value = {'complete': True, 'schedule': {}}
                with patch.object(SaltEvent, 'get_event', return_value=_ret_value):
                    self.assertDictEqual(schedule.add('job2', function='test.ping',
                                                      test=True),
                                         {'comment': comm4, 'result': True})

    # 'modify' function tests: 1

    def test_modify(self):
        '''
        Test if it modify an existing job in the schedule.
        '''
        comm1 = ('Error: Unable to use "seconds", "minutes", "hours",'
                 ' or "days" with "when" option.')
        comm2 = 'Unable to use "when" and "cron" options together.  Ignoring.'
        comm3 = 'Job job2 does not exist in schedule.'
        comm4 = 'Job: job3 would be modified in schedule.'
        with patch.dict(schedule.__opts__, {'schedule': {'job1': JOB1,
                                                         'job3': {}},
                                            'sock_dir': SOCK_DIR}):

            mock = MagicMock(return_value=True)
            with patch.dict(schedule.__salt__, {'event.fire': mock}):
                _ret_value = {'complete': True, 'schedule': {'job1': JOB1,
                                                             'job3': {}}}
                with patch.object(SaltEvent, 'get_event', return_value=_ret_value):
                    self.assertDictEqual(schedule.modify('job1', function='test.ping',
                                                         seconds=3600, when='2400'),
                                         {'changes': {}, 'comment': comm1,
                                          'result': False})

                    self.assertDictEqual(schedule.modify('job1', function='test.ping',
                                                         when='2400', cron='2'),
                                         {'changes': {}, 'comment': comm2,
                                          'result': False})

                    self.assertDictEqual(schedule.modify('job2'), {'changes': {},
                                                                   'comment': comm3,
                                                                   'result': False})

                    self.assertDictEqual(schedule.modify('job1', function='test.ping'),
                                         {'changes': {},
                                          'comment': 'Job job1 in correct state',
                                          'result': True})

                    ret = schedule.modify('job3', function='test.ping', test=True)
                    if 'diff' in ret['changes']:
                        del ret['changes']['diff']  # difflib formatting changes between 2.6 and 2.7
                    self.assertDictEqual(ret, {'changes': {}, 'comment': comm4, 'result': True})

    # 'run_job' function tests: 1

    def test_run_job(self):
        '''
        Test if it run a scheduled job on the minion immediately.
        '''
        with patch.dict(schedule.__opts__, {'schedule': {}, 'sock_dir': SOCK_DIR}):
            mock = MagicMock(return_value=True)
            with patch.dict(schedule.__salt__, {'event.fire': mock}):
                _ret_value = {'complete': True, 'schedule': {}}
                with patch.object(SaltEvent, 'get_event', return_value=_ret_value):
                    self.assertDictEqual(schedule.run_job('job1'),
                                         {'comment': 'Job job1 does not exist.',
                                          'result': False})

    # 'enable_job' function tests: 1

    def test_enable_job(self):
        '''
        Test if it enable a job in the minion's schedule.
        '''
        with patch.dict(schedule.__opts__, {'schedule': {}, 'sock_dir': SOCK_DIR}):
            mock = MagicMock(return_value=True)
            with patch.dict(schedule.__salt__, {'event.fire': mock}):
                _ret_value = {'complete': True, 'schedule': {}}
                with patch.object(SaltEvent, 'get_event', return_value=_ret_value):
                    self.assertDictEqual(schedule.enable_job('job1'),
                                         {'comment': 'Job job1 does not exist.',
                                          'result': False})

    # 'disable_job' function tests: 1

    def test_disable_job(self):
        '''
        Test if it disable a job in the minion's schedule.
        '''
        with patch.dict(schedule.__opts__, {'schedule': {}, 'sock_dir': SOCK_DIR}):
            mock = MagicMock(return_value=True)
            with patch.dict(schedule.__salt__, {'event.fire': mock}):
                _ret_value = {'complete': True, 'schedule': {}}
                with patch.object(SaltEvent, 'get_event', return_value=_ret_value):
                    self.assertDictEqual(schedule.disable_job('job1'),
                                         {'comment': 'Job job1 does not exist.',
                                          'result': False})

    # 'save' function tests: 1

    def test_save(self):
        '''
        Test if it save all scheduled jobs on the minion.
        '''
        comm1 = 'Schedule (non-pillar items) saved.'
        with patch.dict(schedule.__opts__, {'config_dir': '', 'schedule': {},
                                            'default_include': '/tmp',
                                            'sock_dir': SOCK_DIR}):

            mock = MagicMock(return_value=True)
            with patch.dict(schedule.__salt__, {'event.fire': mock}):
                _ret_value = {'complete': True, 'schedule': {}}
                with patch.object(SaltEvent, 'get_event', return_value=_ret_value):
                    self.assertDictEqual(schedule.save(),
                                         {'comment': comm1, 'result': True})

    # 'enable' function tests: 1

    def test_enable(self):
        '''
        Test if it enable all scheduled jobs on the minion.
        '''
        self.assertDictEqual(schedule.enable(test=True),
                             {'comment': 'Schedule would be enabled.',
                              'result': True})

    # 'disable' function tests: 1

    def test_disable(self):
        '''
        Test if it disable all scheduled jobs on the minion.
        '''
        self.assertDictEqual(schedule.disable(test=True),
                             {'comment': 'Schedule would be disabled.',
                              'result': True})

    # 'reload_' function tests: 1

    def test_reload_(self):
        '''
        Test if it reload saved scheduled jobs on the minion.
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(schedule.__opts__, {'config_dir': '',
                                            'default_include': '/tmp'}):
            with patch.dict(schedule.__salt__, {'event.fire': mock}):
                self.assertDictEqual(schedule.reload_(),
                                     {'comment': [], 'result': True})

    # 'move' function tests: 1

    def test_move(self):
        '''
        Test if it move scheduled job to another minion or minions.
        '''
        comm1 = 'no servers answered the published schedule.add command'
        comm2 = 'the following minions return False'
        comm3 = 'Moved Job job1 from schedule.'
        with patch.dict(schedule.__opts__, {'schedule': {'job1': JOB1}, 'sock_dir': SOCK_DIR}):
            mock = MagicMock(return_value=True)
            with patch.dict(schedule.__salt__, {'event.fire': mock}):
                _ret_value = {'complete': True, 'schedule': {'job1': JOB1}}
                with patch.object(SaltEvent, 'get_event', return_value=_ret_value):
                    mock = MagicMock(return_value={})
                    with patch.dict(schedule.__salt__, {'publish.publish': mock}):
                        self.assertDictEqual(schedule.move('job1', 'minion1'),
                                             {'comment': comm1, 'result': True})

                    mock = MagicMock(return_value={'minion1': ''})
                    with patch.dict(schedule.__salt__, {'publish.publish': mock}):
                        self.assertDictEqual(schedule.move('job1', 'minion1'),
                                             {'comment': comm2, 'minions': ['minion1'],
                                              'result': True})

                    mock = MagicMock(return_value={'minion1': 'job1'})
                    with patch.dict(schedule.__salt__, {'publish.publish': mock}):
                        mock = MagicMock(return_value=True)
                        with patch.dict(schedule.__salt__, {'event.fire': mock}):
                            self.assertDictEqual(schedule.move('job1', 'minion1'),
                                                 {'comment': comm3,
                                                  'minions': ['minion1'],
                                                  'result': True})

                    self.assertDictEqual(schedule.move('job3', 'minion1'),
                                         {'comment': 'Job job3 does not exist.',
                                          'result': False})

        mock = MagicMock(side_effect=[{}, {'job1': {}}])
        with patch.dict(schedule.__opts__, {'schedule': mock, 'sock_dir': SOCK_DIR}):
            mock = MagicMock(return_value=True)
            with patch.dict(schedule.__salt__, {'event.fire': mock}):
                _ret_value = {'complete': True, 'schedule': {'job1': JOB1}}
                with patch.object(SaltEvent, 'get_event', return_value=_ret_value):
                    with patch.dict(schedule.__pillar__, {'schedule': {'job1': JOB1}}):
                        mock = MagicMock(return_value={})
                        with patch.dict(schedule.__salt__, {'publish.publish': mock}):
                            self.assertDictEqual(schedule.move('job1', 'minion1'),
                                                 {'comment': comm1,
                                                  'result': True})

                        mock = MagicMock(return_value={'minion1': ''})
                        with patch.dict(schedule.__salt__, {'publish.publish': mock}):
                            self.assertDictEqual(schedule.move('job1', 'minion1'),
                                                 {'comment': comm2,
                                                  'minions': ['minion1'],
                                                  'result': True})

                        mock = MagicMock(return_value={'minion1': 'job1'})
                        with patch.dict(schedule.__salt__, {'publish.publish': mock}):
                            mock = MagicMock(return_value=True)
                            with patch.dict(schedule.__salt__, {'event.fire': mock}):
                                self.assertDictEqual(schedule.move('job1', 'minion1'),
                                                     {'comment': comm3,
                                                      'minions': ['minion1'],
                                                      'result': True})

    # 'copy' function tests: 1

    def test_copy(self):
        '''
        Test if it copy scheduled job to another minion or minions.
        '''
        comm1 = 'no servers answered the published schedule.add command'
        comm2 = 'the following minions return False'
        comm3 = 'Copied Job job1 from schedule to minion(s).'
        with patch.dict(schedule.__opts__, {'schedule': {'job1': JOB1}, 'sock_dir': SOCK_DIR}):
            mock = MagicMock(return_value=True)
            with patch.dict(schedule.__salt__, {'event.fire': mock}):
                _ret_value = {'complete': True, 'schedule': {'job1': {'job1': JOB1}}}
                with patch.object(SaltEvent, 'get_event', return_value=_ret_value):
                    mock = MagicMock(return_value={})
                    with patch.dict(schedule.__salt__, {'publish.publish': mock}):
                        self.assertDictEqual(schedule.copy('job1', 'minion1'),
                                             {'comment': comm1, 'result': True})

                    mock = MagicMock(return_value={'minion1': ''})
                    with patch.dict(schedule.__salt__, {'publish.publish': mock}):
                        self.assertDictEqual(schedule.copy('job1', 'minion1'),
                                             {'comment': comm2, 'minions': ['minion1'],
                                              'result': True})

                    mock = MagicMock(return_value={'minion1': 'job1'})
                    with patch.dict(schedule.__salt__, {'publish.publish': mock}):
                        mock = MagicMock(return_value=True)
                        with patch.dict(schedule.__salt__, {'event.fire': mock}):
                            self.assertDictEqual(schedule.copy('job1', 'minion1'),
                                                 {'comment': comm3,
                                                  'minions': ['minion1'],
                                                  'result': True})

                    self.assertDictEqual(schedule.copy('job3', 'minion1'),
                                         {'comment': 'Job job3 does not exist.',
                                          'result': False})

        mock = MagicMock(side_effect=[{}, {'job1': {}}])
        with patch.dict(schedule.__opts__, {'schedule': mock, 'sock_dir': SOCK_DIR}):
            with patch.dict(schedule.__pillar__, {'schedule': {'job1': JOB1}}):
                mock = MagicMock(return_value=True)
                with patch.dict(schedule.__salt__, {'event.fire': mock}):
                    _ret_value = {'complete': True, 'schedule': {'job1': {'job1': JOB1}}}
                    with patch.object(SaltEvent, 'get_event', return_value=_ret_value):

                        mock = MagicMock(return_value={})
                        with patch.dict(schedule.__salt__, {'publish.publish': mock}):
                            self.assertDictEqual(schedule.copy('job1', 'minion1'),
                                                 {'comment': comm1, 'result': True})

                        mock = MagicMock(return_value={'minion1': ''})
                        with patch.dict(schedule.__salt__, {'publish.publish': mock}):
                            self.assertDictEqual(schedule.copy('job1', 'minion1'),
                                                 {'comment': comm2,
                                                  'minions': ['minion1'],
                                                  'result': True})

                        mock = MagicMock(return_value={'minion1': 'job1'})
                        with patch.dict(schedule.__salt__, {'publish.publish': mock}):
                            mock = MagicMock(return_value=True)
                            with patch.dict(schedule.__salt__, {'event.fire': mock}):
                                self.assertDictEqual(schedule.copy('job1', 'minion1'),
                                                     {'comment': comm3,
                                                      'minions': ['minion1'],
                                                      'result': True})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ScheduleTestCase, needs_daemon=False)
