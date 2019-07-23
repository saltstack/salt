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
import salt.states.mongodb_user as mongodb_user


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MongodbUserTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.mongodb_user
    '''
    def setup_loader_modules(self):
        return {mongodb_user: {'__opts__': {'test': True}}}

    # 'present' function tests: 2

    def test_present_new_user(self):
        '''
        Test to ensure that the user is present with the specified properties for a new account.
        '''
        name = 'myapp'
        passwd = 'password-of-myapp'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        comt = ('Port ({}) is not an integer.')
        ret.update({'comment': comt})
        self.assertDictEqual(mongodb_user.present(name, passwd, port={}), ret)

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=[])
        with patch.dict(mongodb_user.__salt__,
                        {
                         'mongodb.user_create': mock_t,
                         'mongodb.user_find': mock_f
                        }):
            comt = ('User {0} is not present and needs to be created'
                ).format(name)
            ret.update({'comment': comt, 'result': None})
            self.assertDictEqual(mongodb_user.present(name, passwd), ret)

            with patch.dict(mongodb_user.__opts__, {'test': True}):
                comt = ('User {0} is not present and needs to be created'
                        .format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(mongodb_user.present(name, passwd), ret)

            with patch.dict(mongodb_user.__opts__, {'test': False}):
                comt = ('User {0} has been created'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {name: 'Present'}})
                self.assertDictEqual(mongodb_user.present(name, passwd), ret)

    def test_present_existing_user(self):
        '''
        Test to ensure that the user is present with the specified properties for an existing account.
        '''
        name = 'myapp'
        passwd = 'password-of-myapp'
        db = 'myapp-database'
        current_role = 'mongodb-role'
        current_role_as_dict = ['mongodb-role']
        new_role = 'new-mongodb-role'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        comt = ('Port ({}) is not an integer.')
        ret.update({'comment': comt})
        self.assertDictEqual(mongodb_user.present(name, passwd, port={}), ret)

        mock_t = MagicMock(return_value=True)
        mock = MagicMock(return_value=[{'user': name, 'roles':[{'db':db,'role': current_role}]}])
        with patch.dict(mongodb_user.__salt__,
                        {
                         'mongodb.user_create': mock_t,
                         'mongodb.user_find': mock
                        }):
            comt = ('User {0} is already present and should be updated if neccesary.'
                ).format(name)
            ret.update({'comment': comt, 'result': None})
            self.assertDictEqual(mongodb_user.present(name, passwd, database=db,roles=new_role), ret)

            with patch.dict(mongodb_user.__opts__, {'test': True}):
                comt = ('User {0} is already present and should be updated if neccesary.'
                        .format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(mongodb_user.present(name, passwd, database=db,roles=new_role), ret)

            with patch.dict(mongodb_user.__opts__, {'test': False}):
                comt = ('User {0} is already present'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {name: {'database': db, 'roles': {'old': current_role_as_dict, 'new': new_role}}}})
                self.assertDictEqual(mongodb_user.present(name, passwd, database=db,roles=new_role), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure that the named user is absent.
        '''
        name = 'myapp'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[True, True, False])
        mock_t = MagicMock(return_value=True)
        with patch.dict(mongodb_user.__salt__,
                        {'mongodb.user_exists': mock,
                         'mongodb.user_remove': mock_t}):
            with patch.dict(mongodb_user.__opts__, {'test': True}):
                comt = ('User {0} is present and needs to be removed'
                        .format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(mongodb_user.absent(name), ret)

            with patch.dict(mongodb_user.__opts__, {'test': False}):
                comt = ('User {0} has been removed'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {name: 'Absent'}})
                self.assertDictEqual(mongodb_user.absent(name), ret)

            comt = 'User {0} is not present'.format(name)
            ret.update({'comment': comt, 'result': True, 'changes': {}})
            self.assertDictEqual(mongodb_user.absent(name), ret)
