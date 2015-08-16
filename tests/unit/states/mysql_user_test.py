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
from salt.states import mysql_user
import salt

mysql_user.__salt__ = {}
mysql_user.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MysqlUserTestCase(TestCase):
    '''
    Test cases for salt.states.mysql_user
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure that the named user is present with
         the specified properties.
        '''
        name = 'frank'
        password = "bob@cat"

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[True, False, True, False, False, True,
                                      False, False, False, False, False, True])
        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        mock_str = MagicMock(return_value='salt')
        mock_none = MagicMock(return_value=None)
        mock_sn = MagicMock(side_effect=[None, 'salt', None, None, None])
        with patch.object(salt.utils, 'is_true', mock_f):
            comt = ('Either password or password_hash must be specified,'
                    ' unless allow_passwordless is True')
            ret.update({'comment': comt})
            self.assertDictEqual(mysql_user.present(name), ret)

        with patch.dict(mysql_user.__salt__, {'mysql.user_exists': mock,
                                              'mysql.user_chpass': mock_t}):
            with patch.object(salt.utils, 'is_true', mock_t):
                comt = ('User frank@localhost is already present'
                        ' with passwordless login')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(mysql_user.present(name), ret)

                with patch.object(mysql_user, '_get_mysql_error', mock_str):
                    ret.update({'comment': 'salt', 'result': False})
                    self.assertDictEqual(mysql_user.present(name), ret)

            with patch.object(mysql_user, '_get_mysql_error', mock_str):
                comt = ('User frank@localhost is already present'
                        ' with the desired password')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(mysql_user.present(name,
                                                        password=password), ret)

                with patch.object(mysql_user, '_get_mysql_error', mock_str):
                    ret.update({'comment': 'salt', 'result': False})
                    self.assertDictEqual(mysql_user.present(name,
                                                            password=password),
                                         ret)

                with patch.object(mysql_user, '_get_mysql_error', mock_none):
                    with patch.dict(mysql_user.__opts__, {'test': True}):
                        comt = ('Password for user frank@localhost'
                                ' is set to be changed')
                        ret.update({'comment': comt, 'result': None})
                        self.assertDictEqual(mysql_user.present
                                             (name, password=password), ret)

                with patch.object(mysql_user, '_get_mysql_error', mock_sn):
                    with patch.dict(mysql_user.__opts__, {'test': False}):
                        ret.update({'comment': 'salt', 'result': False})
                        self.assertDictEqual(mysql_user.present
                                             (name, password=password), ret)

                    with patch.dict(mysql_user.__opts__, {'test': True}):
                        comt = ('User frank@localhost is set to be added')
                        ret.update({'comment': comt, 'result': None})
                        self.assertDictEqual(mysql_user.present
                                             (name, password=password), ret)

                    with patch.dict(mysql_user.__opts__, {'test': False}):
                        comt = ('Password for user frank@localhost'
                                ' has been changed')
                        ret.update({'comment': comt, 'result': True,
                                    'changes': {name: 'Updated'}})
                        self.assertDictEqual(mysql_user.present
                                             (name, password=password), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure that the named user is absent.
        '''
        name = 'frank_exampledb'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[True, True, True, False, False, False])
        mock_t = MagicMock(side_effect=[True, False])
        mock_str = MagicMock(return_value='salt')
        mock_none = MagicMock(return_value=None)
        with patch.dict(mysql_user.__salt__, {'mysql.user_exists': mock,
                                              'mysql.user_remove': mock_t}):
            with patch.dict(mysql_user.__opts__, {'test': True}):
                comt = ('User frank_exampledb@localhost is set to be removed')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(mysql_user.absent(name), ret)

            with patch.dict(mysql_user.__opts__, {'test': False}):
                comt = ('User frank_exampledb@localhost has been removed')
                ret.update({'comment': comt, 'result': True,
                            'changes': {'frank_exampledb': 'Absent'}})
                self.assertDictEqual(mysql_user.absent(name), ret)

                with patch.object(mysql_user, '_get_mysql_error', mock_str):
                    comt = ('User frank_exampledb@localhost has been removed')
                    ret.update({'comment': 'salt', 'result': False,
                                'changes': {}})
                    self.assertDictEqual(mysql_user.absent(name), ret)

                    comt = ('User frank_exampledb@localhost has been removed')
                    ret.update({'comment': 'salt'})
                    self.assertDictEqual(mysql_user.absent(name), ret)

                with patch.object(mysql_user, '_get_mysql_error', mock_none):
                    comt = ('User frank_exampledb@localhost is not present,'
                            ' so it cannot be removed')
                    ret.update({'comment': comt, 'result': True,
                                'changes': {}})
                    self.assertDictEqual(mysql_user.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MysqlUserTestCase, needs_daemon=False)
