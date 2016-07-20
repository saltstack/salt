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
from salt.states import postgres_database

postgres_database.__opts__ = {}
postgres_database.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PostgresDatabaseTestCase(TestCase):
    '''
    Test cases for salt.states.postgres_database
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure that the named database is present
        with the specified properties.
        '''
        name = 'frank'

        ret = {'name': name,
               'changes': {},
               'result': False,
               'comment': ''}

        mock_t = MagicMock(return_value=True)
        mock = MagicMock(return_value={name: {}})
        with patch.dict(postgres_database.__salt__,
                        {'postgres.db_list': mock,
                         'postgres.db_alter': mock_t}):
            comt = ('Database {0} is already present'.format(name))
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(postgres_database.present(name), ret)

            comt = ("Database frank has wrong parameters "
                    "which couldn't be changed on fly.")
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(postgres_database.present(name, tablespace='A',
                                                           lc_collate=True),
                                 ret)

            with patch.dict(postgres_database.__opts__, {'test': True}):
                comt = ('Database frank exists, '
                        'but parameters need to be changed')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(postgres_database.present(name,
                                                               tablespace='A'),
                                     ret)

            with patch.dict(postgres_database.__opts__, {'test': False}):
                comt = ('Parameters for database frank have been changed')
                ret.update({'comment': comt, 'result': True,
                            'changes': {name: 'Parameters changed'}})
                self.assertDictEqual(postgres_database.present(name,
                                                               tablespace='A'),
                                     ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure that the named database is absent.
        '''
        name = 'frank'

        ret = {'name': name,
               'changes': {},
               'result': False,
               'comment': ''}

        mock_t = MagicMock(return_value=True)
        mock = MagicMock(side_effect=[True, True, False])
        with patch.dict(postgres_database.__salt__,
                        {'postgres.db_exists': mock,
                         'postgres.db_remove': mock_t}):
            with patch.dict(postgres_database.__opts__, {'test': True}):
                comt = ('Database {0} is set to be removed'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(postgres_database.absent(name), ret)

            with patch.dict(postgres_database.__opts__, {'test': False}):
                comt = ('Database {0} has been removed'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {name: 'Absent'}})
                self.assertDictEqual(postgres_database.absent(name), ret)

                comt = ('Database {0} is not present, so it cannot be removed'
                        .format(name))
                ret.update({'comment': comt, 'result': True, 'changes': {}})
                self.assertDictEqual(postgres_database.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PostgresDatabaseTestCase, needs_daemon=False)
