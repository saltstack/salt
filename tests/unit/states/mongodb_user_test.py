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
from salt.states import mongodb_user

mongodb_user.__salt__ = {}
mongodb_user.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MongodbUserTestCase(TestCase):
    '''
    Test cases for salt.states.mongodb_user
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure that the user is present with the specified properties.
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

        mock = MagicMock(side_effect=[True, False, False])
        mock_t = MagicMock(return_value=True)
        with patch.dict(mongodb_user.__salt__,
                        {'mongodb.user_exists': mock,
                         'mongodb.user_create': mock_t}):
            comt = ('User {0} is already present'.format(name))
            ret.update({'comment': comt, 'result': True})
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

            comt = ('User {0} is not present, so it cannot be removed'
                    .format(name))
            ret.update({'comment': comt, 'result': True, 'changes': {}})
            self.assertDictEqual(mongodb_user.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MongodbUserTestCase, needs_daemon=False)
