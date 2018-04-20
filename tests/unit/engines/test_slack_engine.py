# -*- coding: utf-8 -*-
'''
unit tests for the slack engine
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
import salt.engines.slack as slack
import salt.config


@skipIf(slack.HAS_SLACKCLIENT is False, 'The SlackClient is not installed')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class EngineSlackTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.engine.sqs_events
    '''

    def setup_loader_modules(self):
        return {slack: {}}

    def setUp(self):
        mock_opts = salt.config.DEFAULT_MINION_OPTS
        token = 'xoxb-xxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx'

        with patch.dict(slack.__opts__, mock_opts):
            with patch('slackclient.SlackClient.rtm_connect', MagicMock(return_value=True)):
                self.client = slack.SlackClient(token)

    def test_control_message_target(self):
        '''
        Test slack engine: control_message_target
        '''
        trigger_string = '!'

        loaded_groups = {u'default': {u'targets': {},
                                      u'commands': set([u'cmd.run', u'test.ping']),
                                      u'default_target': {u'tgt_type': u'glob', u'target': u'*'},
                                      u'users': set([u'gareth']),
                                      u'aliases': {u'whoami': {u'cmd': u'cmd.run whoami'},
                                                   u'list_pillar': {u'cmd': u'pillar.items'}}
                                      }}

        slack_user_name = 'gareth'

        _expected = (True,
                     {u'tgt_type': u'glob', u'target': u'*'},
                     [u'cmd.run', u'whoami'])
        text = '!cmd.run whoami'
        target_commandline = self.client.control_message_target(slack_user_name,
                                                                text,
                                                                loaded_groups,
                                                                trigger_string)

        self.assertEqual(target_commandline, _expected)

        text = '!whoami'
        target_commandline = self.client.control_message_target(slack_user_name,
                                                                text,
                                                                loaded_groups,
                                                                trigger_string)

        self.assertEqual(target_commandline, _expected)

        _expected = (True,
                     {u'tgt_type': u'glob', u'target': u'*'},
                     [u'pillar.items', u'pillar={"hello": "world"}'])
        text = r"""!list_pillar pillar='{"hello": "world"}'"""
        target_commandline = self.client.control_message_target(slack_user_name,
                                                                text,
                                                                loaded_groups,
                                                                trigger_string)

        self.assertEqual(target_commandline, _expected)
