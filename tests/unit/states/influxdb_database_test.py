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
from salt.states import influxdb_database

influxdb_database.__salt__ = {}
influxdb_database.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class InfluxdbDatabaseTestCase(TestCase):
    '''
    Test cases for salt.states.influxdb_database
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure that the named database is present.
        '''
        name = 'salt'

        ret = {'name': name,
               'result': None,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[False, False, False, True])
        mock_t = MagicMock(side_effect=[True, False])
        with patch.dict(influxdb_database.__salt__,
                        {'influxdb.db_exists': mock,
                         'influxdb.db_create': mock_t}):
            with patch.dict(influxdb_database.__opts__, {'test': True}):
                comt = ('Database {0} is absent and needs to be created'
                        .format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(influxdb_database.present(name), ret)

            with patch.dict(influxdb_database.__opts__, {'test': False}):
                comt = ('Database {0} has been created'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {'salt': 'Present'}})
                self.assertDictEqual(influxdb_database.present(name), ret)

                comt = ('Failed to create database {0}'.format(name))
                ret.update({'comment': comt, 'result': False, 'changes': {}})
                self.assertDictEqual(influxdb_database.present(name), ret)

            comt = ('Database {0} is already present, so cannot be created'
                    .format(name))
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(influxdb_database.present(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure that the named database is absent.
        '''
        name = 'salt'

        ret = {'name': name,
               'result': None,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[True, True, True, False])
        mock_t = MagicMock(side_effect=[True, False])
        with patch.dict(influxdb_database.__salt__,
                        {'influxdb.db_exists': mock,
                         'influxdb.db_remove': mock_t}):
            with patch.dict(influxdb_database.__opts__, {'test': True}):
                comt = ('Database {0} is present and needs to be removed'
                        .format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(influxdb_database.absent(name), ret)

            with patch.dict(influxdb_database.__opts__, {'test': False}):
                comt = ('Database {0} has been removed'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {'salt': 'Absent'}})
                self.assertDictEqual(influxdb_database.absent(name), ret)

                comt = ('Failed to remove database {0}'.format(name))
                ret.update({'comment': comt, 'result': False, 'changes': {}})
                self.assertDictEqual(influxdb_database.absent(name), ret)

            comt = ('Database {0} is not present, so it cannot be removed'
                    .format(name))
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(influxdb_database.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(InfluxdbDatabaseTestCase, needs_daemon=False)
