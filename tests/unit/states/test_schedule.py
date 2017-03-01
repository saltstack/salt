# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import schedule

schedule.__opts__ = {}
schedule.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ScheduleTestCase(TestCase):
    '''
    Test cases for salt.states.schedule
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure a job is present in the schedule.
        '''
        name = 'job1'

        ret = {'name': name,
               'changes': {},
               'result': False,
               'comment': ''}

        mock_dict = MagicMock(side_effect=[ret, []])
        mock_mod = MagicMock(return_value=ret)
        mock_lst = MagicMock(side_effect=[{name: {}}, {name: {}}, {}, {}])
        with patch.dict(schedule.__salt__,
                        {'schedule.list': mock_lst,
                         'schedule.build_schedule_item': mock_dict,
                         'schedule.modify': mock_mod,
                         'schedule.add': mock_mod}):
            self.assertDictEqual(schedule.present(name), ret)

            with patch.dict(schedule.__opts__, {'test': False}):
                self.assertDictEqual(schedule.present(name), ret)

                self.assertDictEqual(schedule.present(name), ret)

            with patch.dict(schedule.__opts__, {'test': True}):
                ret.update({'result': True})
                self.assertDictEqual(schedule.present(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure a job is absent from the schedule.
        '''
        name = 'job1'

        ret = {'name': name,
               'changes': {},
               'result': False,
               'comment': ''}

        mock_mod = MagicMock(return_value=ret)
        mock_lst = MagicMock(side_effect=[{name: {}}, {}])
        with patch.dict(schedule.__salt__,
                        {'schedule.list': mock_lst,
                         'schedule.delete': mock_mod}):
            with patch.dict(schedule.__opts__, {'test': False}):
                self.assertDictEqual(schedule.absent(name), ret)

            with patch.dict(schedule.__opts__, {'test': True}):
                comt = ('Job job1 not present in schedule')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(schedule.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ScheduleTestCase, needs_daemon=False)
