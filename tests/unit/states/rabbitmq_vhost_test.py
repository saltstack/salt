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
from salt.states import rabbitmq_vhost

rabbitmq_vhost.__opts__ = {}
rabbitmq_vhost.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RabbitmqVhostTestCase(TestCase):
    '''
    Test cases for salt.states.rabbitmq_vhost
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure the RabbitMQ VHost exists.
        '''
        name = 'virtual_host'

        ret = {'name': name,
               'changes': {'old': '', 'new': name},
               'result': None,
               'comment': 'Creating VHost virtual_host'}

        mock = MagicMock(return_value=False)
        with patch.dict(rabbitmq_vhost.__salt__,
                        {'rabbitmq.vhost_exists': mock}):
            with patch.dict(rabbitmq_vhost.__opts__, {'test': True}):
                self.assertDictEqual(rabbitmq_vhost.present(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure the named user is absent.
        '''
        name = 'myqueue'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': 'Virtual Host {0} is not present'.format(name)}

        mock = MagicMock(return_value=False)
        with patch.dict(rabbitmq_vhost.__salt__,
                        {'rabbitmq.vhost_exists': mock}):
            self.assertDictEqual(rabbitmq_vhost.absent(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RabbitmqVhostTestCase, needs_daemon=False)
