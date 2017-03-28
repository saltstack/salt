# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.states.influxdb08_user as influxdb08_user


@skipIf(NO_MOCK, NO_MOCK_REASON)
class InfluxdbUserTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.influxdb08_user
    '''
    def setup_loader_modules(self):
        return {influxdb08_user: {}}

    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure that the cluster admin or database user is present.
        '''
        name = 'salt'
        passwd = 'salt'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[False, False, False, True])
        mock_t = MagicMock(side_effect=[True, False])
        mock_f = MagicMock(return_value=False)
        with patch.dict(influxdb08_user.__salt__,
                        {'influxdb08.db_exists': mock_f,
                         'influxdb08.user_exists': mock,
                         'influxdb08.user_create': mock_t}):
            comt = ('Database mydb does not exist')
            ret.update({'comment': comt})
            self.assertDictEqual(influxdb08_user.present(name, passwd,
                                                       database='mydb'), ret)

            with patch.dict(influxdb08_user.__opts__, {'test': True}):
                comt = ('User {0} is not present and needs to be created'
                        .format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(influxdb08_user.present(name, passwd), ret)

            with patch.dict(influxdb08_user.__opts__, {'test': False}):
                comt = ('User {0} has been created'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {'salt': 'Present'}})
                self.assertDictEqual(influxdb08_user.present(name, passwd), ret)

                comt = ('Failed to create user {0}'.format(name))
                ret.update({'comment': comt, 'result': False, 'changes': {}})
                self.assertDictEqual(influxdb08_user.present(name, passwd), ret)

            comt = ('User {0} is already present'.format(name))
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(influxdb08_user.present(name, passwd), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure that the named cluster admin or database user is absent.
        '''
        name = 'salt'

        ret = {'name': name,
               'result': None,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[True, True, True, False])
        mock_t = MagicMock(side_effect=[True, False])
        with patch.dict(influxdb08_user.__salt__,
                        {'influxdb08.user_exists': mock,
                         'influxdb08.user_remove': mock_t}):
            with patch.dict(influxdb08_user.__opts__, {'test': True}):
                comt = ('User {0} is present and needs to be removed'
                        .format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(influxdb08_user.absent(name), ret)

            with patch.dict(influxdb08_user.__opts__, {'test': False}):
                comt = ('User {0} has been removed'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {'salt': 'Absent'}})
                self.assertDictEqual(influxdb08_user.absent(name), ret)

                comt = ('Failed to remove user {0}'.format(name))
                ret.update({'comment': comt, 'result': False, 'changes': {}})
                self.assertDictEqual(influxdb08_user.absent(name), ret)

            comt = ('User {0} is not present, so it cannot be removed'
                    .format(name))
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(influxdb08_user.absent(name), ret)
