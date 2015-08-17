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
from salt.states import rabbitmq_policy

rabbitmq_policy.__opts__ = {}
rabbitmq_policy.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RabbitmqPolicyTestCase(TestCase):
    '''
    Test cases for salt.states.rabbitmq_policy
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure the RabbitMQ policy exists.
        '''
        name = 'HA'
        pattern = '.*'
        definition = '{"ha-mode":"all"}'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': ''}

        mock = MagicMock(side_effect=[{'/': {name: {'pattern': pattern,
                                                    'definition': definition,
                                                    'priority': 0}}}, {}])
        with patch.dict(rabbitmq_policy.__salt__,
                        {'rabbitmq.list_policies': mock}):
            comt = ('Policy / HA is already present')
            ret.update({'comment': comt})
            self.assertDictEqual(rabbitmq_policy.present(name, pattern,
                                                         definition), ret)

            with patch.dict(rabbitmq_policy.__opts__, {'test': True}):
                comt = ('Policy / HA is set to be created')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(rabbitmq_policy.present(name, pattern,
                                                             definition), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure the named policy is absent.
        '''
        name = 'HA'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': ''}

        mock = MagicMock(side_effect=[False, True])
        with patch.dict(rabbitmq_policy.__salt__,
                        {'rabbitmq.policy_exists': mock}):
            comt = ('Policy / HA is not present')
            ret.update({'comment': comt})
            self.assertDictEqual(rabbitmq_policy.absent(name), ret)

            with patch.dict(rabbitmq_policy.__opts__, {'test': True}):
                comt = ('Removing policy / HA')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(rabbitmq_policy.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RabbitmqPolicyTestCase, needs_daemon=False)
