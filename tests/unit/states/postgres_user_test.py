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
from salt.states import postgres_user

postgres_user.__opts__ = {}
postgres_user.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PostgresUserTestCase(TestCase):
    '''
    Test cases for salt.states.postgres_user
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure that the named user is present
        with the specified privileges.
        '''
        name = 'frank'

        ret = {'name': name,
               'changes': {},
               'result': False,
               'comment': ''}

        mock_t = MagicMock(return_value=True)
        mock = MagicMock(return_value=None)
        with patch.dict(postgres_user.__salt__,
                        {'postgres.role_get': mock,
                         'postgres.user_create': mock_t}):
            with patch.dict(postgres_user.__opts__, {'test': True}):
                comt = ('User {0} is set to be created'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(postgres_user.present(name), ret)

            with patch.dict(postgres_user.__opts__, {'test': False}):
                comt = ('The user {0} has been created'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {name: 'Present'}})
                self.assertDictEqual(postgres_user.present(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure that the named user is absent.
        '''
        name = 'frank'

        ret = {'name': name,
               'changes': {},
               'result': False,
               'comment': ''}

        mock_t = MagicMock(return_value=True)
        mock = MagicMock(side_effect=[True, True, False])
        with patch.dict(postgres_user.__salt__,
                        {'postgres.user_exists': mock,
                         'postgres.user_remove': mock_t}):
            with patch.dict(postgres_user.__opts__, {'test': True}):
                comt = ('User {0} is set to be removed'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(postgres_user.absent(name), ret)

            with patch.dict(postgres_user.__opts__, {'test': False}):
                comt = ('User {0} has been removed'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {name: 'Absent'}})
                self.assertDictEqual(postgres_user.absent(name), ret)

            comt = ('User {0} is not present, so it cannot be removed'
                    .format(name))
            ret.update({'comment': comt, 'result': True, 'changes': {}})
            self.assertDictEqual(postgres_user.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PostgresUserTestCase, needs_daemon=False)
