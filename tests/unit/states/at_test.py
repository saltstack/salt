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
from salt.states import at

at.__salt__ = {}
at.__opts__ = {}
at.__grains__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class AtTestCase(TestCase):
    '''
    Test cases for salt.states.at
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to add a job to queue.
        '''
        name = 'jboss'
        timespec = '9:09 11/04/15'
        tag = 'love'
        user = 'jam'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        mock = MagicMock(return_value=False)
        with patch.dict(at.__opts__, {'test': False}):
            with patch.dict(at.__grains__, {'os_family': 'Redhat'}):
                with patch.dict(at.__salt__, {'cmd.run': mock}):
                    ret.update({'comment': False})
                    self.assertDictEqual(at.present(name, timespec, tag),
                                         ret)

                with patch.dict(at.__salt__, {'user.info': mock}):
                    comt = 'User: {0} is not exists'.format(user)
                    ret.update({'comment': comt, 'result': False})
                    self.assertDictEqual(at.present(name, timespec, tag, user),
                                         ret)

        with patch.dict(at.__opts__, {'test': True}):
            comt = 'job {0} is add and will run on {1}'.format(name, timespec)
            ret.update({'comment': comt, 'result': None})
            self.assertDictEqual(at.present(name, timespec, tag, user), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to remove a job from queue
        '''
        name = 'jboss'

        ret = {'name': name,
               'result': None,
               'changes': {},
               'comment': ''}

        with patch.dict(at.__opts__, {'test': True}):
            ret.update({'comment': 'Remove jobs()'})
            self.assertDictEqual(at.absent(name), ret)

        with patch.dict(at.__opts__, {'test': False}):
            comt = 'limit parameter not supported {0}'.format(name)
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(at.absent(name), ret)

            mock = MagicMock(return_value={'jobs': []})
            mock_bool = MagicMock(return_value=False)
            with patch.dict(at.__salt__, {'at.atq': mock,
                                          'cmd.run': mock_bool}):
                comt = 'No match jobs or time format error'
                ret.update({'comment': comt, 'result': False, 'name': 'all'})
                self.assertDictEqual(at.absent('all'), ret)

            mock = MagicMock(return_value={'jobs': [{'job': 'rose'}]})
            mock_bool = MagicMock(return_value=False)
            with patch.dict(at.__salt__, {'at.atq': mock,
                                          'cmd.run': mock_bool}):
                comt = "Remove job(rose) from queue but (['rose']) fail"
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(at.absent('all'), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(AtTestCase, needs_daemon=False)
