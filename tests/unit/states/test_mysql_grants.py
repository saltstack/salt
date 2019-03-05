# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.states.mysql_grants as mysql_grants


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MysqlGrantsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.mysql_grants
    '''
    def setup_loader_modules(self):
        return {mysql_grants: {}}

    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure that the grant is present with the specified properties.
        '''
        name = 'frank_exampledb'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[True, False, False, False])
        mock_t = MagicMock(return_value=True)
        mock_str = MagicMock(return_value='salt')
        mock_none = MagicMock(return_value=None)
        with patch.dict(mysql_grants.__salt__, {'mysql.grant_exists': mock,
                                                'mysql.grant_add': mock_t}):
            comt = ('Grant None on None to None@localhost is already present')
            ret.update({'comment': comt})
            self.assertDictEqual(mysql_grants.present(name), ret)

            with patch.object(mysql_grants, '_get_mysql_error', mock_str):
                ret.update({'comment': 'salt', 'result': False})
                self.assertDictEqual(mysql_grants.present(name), ret)

            with patch.object(mysql_grants, '_get_mysql_error', mock_none):
                with patch.dict(mysql_grants.__opts__, {'test': True}):
                    comt = ('MySQL grant frank_exampledb is set to be created')
                    ret.update({'comment': comt, 'result': None})
                    self.assertDictEqual(mysql_grants.present(name), ret)

                with patch.dict(mysql_grants.__opts__, {'test': False}):
                    comt = ('Grant None on None to None@localhost'
                            ' has been added')
                    ret.update({'comment': comt, 'result': True,
                                'changes': {name: 'Present'}})
                    self.assertDictEqual(mysql_grants.present(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure that the grant is absent.
        '''
        name = 'frank_exampledb'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[True, False])
        mock_t = MagicMock(side_effect=[True, True, True, False, False])
        mock_str = MagicMock(return_value='salt')
        mock_none = MagicMock(return_value=None)
        with patch.dict(mysql_grants.__salt__, {'mysql.grant_exists': mock_t,
                                                'mysql.grant_revoke': mock}):
            with patch.dict(mysql_grants.__opts__, {'test': True}):
                comt = ('MySQL grant frank_exampledb is set to be revoked')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(mysql_grants.absent(name), ret)

            with patch.dict(mysql_grants.__opts__, {'test': False}):
                comt = ('Grant None on None for None@localhost'
                        ' has been revoked')
                ret.update({'comment': comt, 'result': True,
                            'changes': {name: 'Absent'}})
                self.assertDictEqual(mysql_grants.absent(name), ret)

                with patch.object(mysql_grants, '_get_mysql_error', mock_str):
                    comt = ('Unable to revoke grant None on None'
                            ' for None@localhost (salt)')
                    ret.update({'comment': comt, 'result': False,
                                'changes': {}})
                    self.assertDictEqual(mysql_grants.absent(name), ret)

                    comt = ('Unable to determine if grant None on '
                            'None for None@localhost exists (salt)')
                    ret.update({'comment': comt})
                    self.assertDictEqual(mysql_grants.absent(name), ret)

            with patch.object(mysql_grants, '_get_mysql_error', mock_none):
                comt = ('Grant None on None to None@localhost is not present,'
                        ' so it cannot be revoked')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(mysql_grants.absent(name), ret)
