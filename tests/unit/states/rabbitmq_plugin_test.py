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
from salt.states import rabbitmq_plugin

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
            comt = ('Plugin some_plugin is already enabled')
            ret.update({'comment': comt})
            self.assertDictEqual(rabbitmq_plugin.enabled(name), ret)

            with patch.dict(rabbitmq_plugin.__opts__, {'test': True}):
                comt = ('Plugin some_plugin is set to be enabled')
                ret.update({'comment': comt, 'result': None})
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
            comt = ('Plugin some_plugin is not enabled')
            ret.update({'comment': comt})
            self.assertDictEqual(rabbitmq_plugin.disabled(name), ret)

            with patch.dict(rabbitmq_plugin.__opts__, {'test': True}):
                comt = ('Plugin some_plugin is set to be disabled')
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(rabbitmq_plugin.disabled(name), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RabbitmqPluginTestCase, needs_daemon=False)
