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

rabbitmq_user.__opts__ = {'test': False}
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
        existing_perms = {'/': ['.*', '.*']}
        perms = [existing_perms]

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': ''}

        mock = MagicMock(side_effect=[True, False, True, True,
                                      True, True, True, True, True])
        mock_cp = MagicMock(side_effect=[False, True])
        mock_dct = MagicMock(return_value={name: set(tag)})
        mock_pr = MagicMock(return_value=existing_perms)
        mock_add = MagicMock(return_value={'Added': name})
        with patch.dict(rabbitmq_user.__salt__,
                        {'rabbitmq.user_exists': mock,
                         'rabbitmq.check_password': mock_cp,
                         'rabbitmq.list_users': mock_dct,
                         'rabbitmq.list_user_permissions': mock_pr,
                         'rabbitmq.set_user_tags': mock_add}):
            comment = 'User \'foo\' is already present.'
            ret.update({'comment': comment})
            self.assertDictEqual(rabbitmq_user.present(name), ret)

            with patch.dict(rabbitmq_user.__opts__, {'test': True}):
                comment = 'User \'foo\' is set to be created.'
                changes = {'user': {'new': 'foo', 'old': ''}}
                ret.update({'comment': comment, 'result': None, 'changes': changes})
                self.assertDictEqual(rabbitmq_user.present(name), ret)

                comment = 'Configuration for \'foo\' will change.'
                changes = {'password': {'new': 'Set password.', 'old': ''}}
                ret.update({'comment': comment, 'changes': changes, 'result': None})
                self.assertDictEqual(rabbitmq_user.present(name,
                                                           password=passwd,
                                                           force=False), ret)
                comment = 'Configuration for \'foo\' will change.'
                changes = {'password': {'new': 'Set password.', 'old': ''}}
                ret.update({'comment': comment, 'changes': changes, 'result': None})
                self.assertDictEqual(rabbitmq_user.present(name,
                                                           password=passwd,
                                                           force=True), ret)

                changes = {'password': {'new': '', 'old': 'Removed password.'}}
                ret.update({'changes': changes})
                self.assertDictEqual(rabbitmq_user.present(name, force=True),
                                     ret)

                changes = {'tags': {'new': ['u', 's', 'r', 'e'], 'old': 'user'}}
                ret.update({'changes': changes})
                self.assertDictEqual(rabbitmq_user.present(name, tags=tag), ret)

                comment = '\'foo\' is already in the desired state.'
                ret.update({'changes': {}, 'comment': comment, 'result': True})
                self.assertDictEqual(rabbitmq_user.present(name, perms=perms),
                                     ret)

            with patch.dict(rabbitmq_user.__opts__, {'test': False}):
                ret.update({'comment': '\'foo\' was configured.', 'result': True,
                            'changes': {'tags': {'new': ['u', 's', 'r', 'e'], 'old': 'user'}}})
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
               'comment': 'The user \'foo\' is not present.'}

        mock = MagicMock(return_value=False)
        with patch.dict(rabbitmq_user.__salt__, {'rabbitmq.user_exists': mock}):
            self.assertDictEqual(rabbitmq_user.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RabbitmqUserTestCase, needs_daemon=False)
