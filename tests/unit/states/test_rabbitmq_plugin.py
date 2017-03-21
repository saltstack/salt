# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt Libs
import salt.states.rabbitmq_plugin as rabbitmq_plugin

rabbitmq_plugin.__opts__ = {}
rabbitmq_plugin.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RabbitmqPluginTestCase(TestCase):
    '''
    Test cases for salt.states.rabbitmq_plugin
    '''
    # 'enabled' function tests: 1

    def test_enabled(self):
        '''
        Test to ensure the RabbitMQ plugin is enabled.
        '''
        name = 'some_plugin'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': ''}

        mock = MagicMock(side_effect=[True, False])
        with patch.dict(rabbitmq_plugin.__salt__,
                        {'rabbitmq.plugin_is_enabled': mock}):
            comment = 'Plugin \'some_plugin\' is already enabled.'
            ret.update({'comment': comment})
            self.assertDictEqual(rabbitmq_plugin.enabled(name), ret)

            with patch.dict(rabbitmq_plugin.__opts__, {'test': True}):
                comment = 'Plugin \'some_plugin\' is set to be enabled.'
                changes = {'new': 'some_plugin', 'old': ''}
                ret.update({'comment': comment, 'result': None, 'changes': changes})
                self.assertDictEqual(rabbitmq_plugin.enabled(name), ret)

    # 'disabled' function tests: 1

    def test_disabled(self):
        '''
        Test to ensure the RabbitMQ plugin is disabled.
        '''
        name = 'some_plugin'

        ret = {'name': name,
               'changes': {},
               'result': True,
               'comment': ''}

        mock = MagicMock(side_effect=[False, True])
        with patch.dict(rabbitmq_plugin.__salt__,
                        {'rabbitmq.plugin_is_enabled': mock}):
            comment = 'Plugin \'some_plugin\' is already disabled.'
            ret.update({'comment': comment})
            self.assertDictEqual(rabbitmq_plugin.disabled(name), ret)

            with patch.dict(rabbitmq_plugin.__opts__, {'test': True}):
                comment = 'Plugin \'some_plugin\' is set to be disabled.'
                changes = {'new': '', 'old': 'some_plugin'}
                ret.update({'comment': comment, 'result': None, 'changes': changes})
                self.assertDictEqual(rabbitmq_plugin.disabled(name), ret)
