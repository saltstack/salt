# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import slack_notify

# Globals
slack_notify.__salt__ = {}
slack_notify.__opts__ = {}
RET_DICT = {'res': False, 'message': 'invalid_auth'}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SlackNotifyTestCase(TestCase):
    '''
    Test cases for salt.modules.slack_notify
    '''
    # 'list_rooms' function tests: 1

    def test_list_rooms(self):
        '''
        Test if it list all Slack rooms.
        '''
        mock = MagicMock(return_value='fake_key')
        with patch.dict(slack_notify.__salt__, {'config.get': mock}):
            self.assertDictEqual(slack_notify.list_rooms(), RET_DICT)

    # 'list_users' function tests: 1

    def test_list_users(self):
        '''
        Test if it list all Slack users.
        '''
        mock = MagicMock(return_value='fake_key')
        with patch.dict(slack_notify.__salt__, {'config.get': mock}):
            self.assertDictEqual(slack_notify.list_users(), RET_DICT)

    # 'find_room' function tests: 1

    def test_find_room(self):
        '''
        Test if it find a room by name and return it.
        '''
        mock = MagicMock(return_value='fake_key')
        with patch.dict(slack_notify.__salt__, {'config.get': mock}):
            self.assertFalse(slack_notify.find_room(name="random"))

    # 'find_user' function tests: 1

    def test_find_user(self):
        '''
        Test if it find a user by name and return it.
        '''
        mock = MagicMock(return_value='fake_key')
        with patch.dict(slack_notify.__salt__, {'config.get': mock}):
            self.assertFalse(slack_notify.find_user(name="SALT"))

    # 'post_message' function tests: 1

    def test_post_message(self):
        '''
        Test if it send a message to a Slack channel.
        '''
        mock = MagicMock(return_value='fake_key')
        with patch.dict(slack_notify.__salt__, {'config.get': mock}):
            self.assertDictEqual(slack_notify.post_message
                                 (channel="Development Room",
                                  message="Build is done",
                                  from_name="Build Server"), RET_DICT)

    # 'call_hook' function test: 1

    def test_call_hook(self):
        '''
        Test if it send a message to Slack incoming WebHook.
        '''
        mock = MagicMock(return_value='fake/hook/identifier')
        with patch.dict(slack_notify.__salt__, {'config.get': mock}):
            self.assertDictEqual(slack_notify.call_hook
                                 (message="Message header",
                                  attachment="Extra data",
                                  color='danger',
                                  short=True),
                                 {'res': False, 'message': 404})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SlackNotifyTestCase, needs_daemon=False)
