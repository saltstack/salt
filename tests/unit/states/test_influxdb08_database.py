# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch)

# Import Salt Libs
import salt.states.influxdb08_database as influxdb08_database


class InfluxdbDatabaseTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.influxdb08_database
    '''
    def setup_loader_modules(self):
        return {influxdb08_database: {}}

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
        with patch.dict(influxdb08_database.__salt__,
                        {'influxdb08.db_exists': mock,
                         'influxdb08.db_create': mock_t}):
            with patch.dict(influxdb08_database.__opts__, {'test': True}):
                comt = ('Database {0} is absent and needs to be created'
                        .format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(influxdb08_database.present(name), ret)

            with patch.dict(influxdb08_database.__opts__, {'test': False}):
                comt = ('Database {0} has been created'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {'salt': 'Present'}})
                self.assertDictEqual(influxdb08_database.present(name), ret)

                comt = ('Failed to create database {0}'.format(name))
                ret.update({'comment': comt, 'result': False, 'changes': {}})
                self.assertDictEqual(influxdb08_database.present(name), ret)

            comt = ('Database {0} is already present, so cannot be created'
                    .format(name))
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(influxdb08_database.present(name), ret)

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
        with patch.dict(influxdb08_database.__salt__,
                        {'influxdb08.db_exists': mock,
                         'influxdb08.db_remove': mock_t}):
            with patch.dict(influxdb08_database.__opts__, {'test': True}):
                comt = ('Database {0} is present and needs to be removed'
                        .format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(influxdb08_database.absent(name), ret)

            with patch.dict(influxdb08_database.__opts__, {'test': False}):
                comt = ('Database {0} has been removed'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {'salt': 'Absent'}})
                self.assertDictEqual(influxdb08_database.absent(name), ret)

                comt = ('Failed to remove database {0}'.format(name))
                ret.update({'comment': comt, 'result': False, 'changes': {}})
                self.assertDictEqual(influxdb08_database.absent(name), ret)

            comt = ('Database {0} is not present, so it cannot be removed'
                    .format(name))
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(influxdb08_database.absent(name), ret)
