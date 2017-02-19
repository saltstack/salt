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
    patch)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import incron

incron.__salt__ = {}
incron.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class IncronTestCase(TestCase):
    '''
    Test cases for salt.states.incron
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to verifies that the specified incron job is present
        for the specified user.
        '''
        name = 'salt'
        path = '/home/user'
        mask = 'IN_MODIFY'
        cmd = 'echo "$$ $@"'

        ret = {'name': name,
               'result': None,
               'comment': '',
               'changes': {}}

        comt4 = ('Incron {0} for user root failed to commit with error \nabsent'
                 .format(name))
        mock_dict = MagicMock(return_value={'crons': [{'path': path, 'cmd': cmd,
                                                       'mask': mask}]})
        mock = MagicMock(side_effect=['present', 'new', 'updated', 'absent'])
        with patch.dict(incron.__salt__, {'incron.list_tab': mock_dict,
                                          'incron.set_job': mock}):
            with patch.dict(incron.__opts__, {'test': True}):
                comt = ('Incron {0} is set to be added'.format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(incron.present(name, path, mask, cmd), ret)

            with patch.dict(incron.__opts__, {'test': False}):
                comt = ('Incron {0} already present'.format(name))
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(incron.present(name, path, mask, cmd), ret)

                comt = ('Incron {0} added to root\'s incrontab'.format(name))
                ret.update({'comment': comt, 'changes': {'root': 'salt'}})
                self.assertDictEqual(incron.present(name, path, mask, cmd), ret)

                comt = ('Incron {0} updated'.format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(incron.present(name, path, mask, cmd), ret)

                ret.update({'comment': comt4, 'result': False, 'changes': {}})
                self.assertDictEqual(incron.present(name, path, mask, cmd), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to verifies that the specified incron job is absent
        for the specified user.
        '''
        name = 'salt'
        path = '/home/user'
        mask = 'IN_MODIFY'
        cmd = 'echo "$$ $@"'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        comt4 = (("Incron {0} for user root failed to commit with error new"
                  .format(name)))
        mock_dict = MagicMock(return_value={'crons': [{'path': path, 'cmd': cmd,
                                                       'mask': mask}]})
        mock = MagicMock(side_effect=['absent', 'removed', 'new'])
        with patch.dict(incron.__salt__, {'incron.list_tab': mock_dict,
                                          'incron.rm_job': mock}):
            with patch.dict(incron.__opts__, {'test': True}):
                comt = ('Incron {0} is absent'.format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(incron.absent(name, path, mask, cmd), ret)

            with patch.dict(incron.__opts__, {'test': False}):
                comt = ("Incron {0} already absent".format(name))
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(incron.absent(name, path, mask, cmd), ret)

                comt = (("Incron {0} removed from root's crontab".format(name)))
                ret.update({'comment': comt, 'changes': {'root': 'salt'}})
                self.assertDictEqual(incron.absent(name, path, mask, cmd), ret)

                ret.update({'comment': comt4, 'result': False, 'changes': {}})
                self.assertDictEqual(incron.absent(name, path, mask, cmd), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(IncronTestCase, needs_daemon=False)
