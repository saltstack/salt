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
from salt.states import rabbitmq_user

rabbitmq_user.__opts__ = {}
rabbitmq_user.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RabbitmqUserTestCase(TestCase):
    '''
    Test cases for salt.states.rabbitmq_user
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure the RabbitMQ user exists.
        '''
        name = 'foo'
        passwd = 'password'
        tag = 'user'
        perms = [{'/': ['.*', '.*']}]

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': ''}

        mock = MagicMock(side_effect=[True, False, True, True,
                                      True, True, True])
        mock_dct = MagicMock(return_value={name: set(tag)})
        mock_pr = MagicMock(return_value=perms)
        mock_add = MagicMock(return_value={'Added': name})
        with patch.dict(rabbitmq_user.__salt__,
                        {'rabbitmq.user_exists': mock,
                         'rabbitmq.list_users': mock_dct,
                         'rabbitmq.list_user_permissions': mock_pr,
                         'rabbitmq.set_user_tags': mock_add}):
            comt = ('User foo already presents')
            ret.update({'comment': comt})
            self.assertDictEqual(rabbitmq_user.present(name), ret)

            with patch.dict(rabbitmq_user.__opts__, {'test': True}):
                comt = ('User foo is set to be created')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(rabbitmq_user.present(name), ret)

                comt = ("User foo's password is set to be updated")
                ret.update({'comment': comt})
                self.assertDictEqual(rabbitmq_user.present(name,
                                                           password=passwd,
                                                           force=True), ret)

                comt = ("User foo's password is set to be removed")
                ret.update({'comment': comt})
                self.assertDictEqual(rabbitmq_user.present(name, force=True),
                                     ret)

                comt = ('Tags for user foo is set to be changed')
                ret.update({'comment': comt})
                self.assertDictEqual(rabbitmq_user.present(name, tags=tag), ret)

                comt = ('Permissions for user foo is set to be changed')
                ret.update({'comment': comt})
                self.assertDictEqual(rabbitmq_user.present(name, perms=perms),
                                     ret)

            with patch.dict(rabbitmq_user.__opts__, {'test': False}):
                ret.update({'comment': name, 'result': True,
                            'changes': {'new': 'Set tags: user\n', 'old': ''}})
                self.assertDictEqual(rabbitmq_user.present(name, tags=tag), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure the named user is absent.
        '''
        name = 'foo'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': 'User {0} is not present'.format(name)}

        mock = MagicMock(return_value=False)
        with patch.dict(rabbitmq_user.__salt__, {'rabbitmq.user_exists': mock}):
            self.assertDictEqual(rabbitmq_user.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RabbitmqUserTestCase, needs_daemon=False)
