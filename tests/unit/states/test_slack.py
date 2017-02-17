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
from salt.states import slack

slack.__salt__ = {}
slack.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SlackTestCase(TestCase):
    '''
    Test cases for salt.states.slack
    '''
    # 'post_message' function tests: 1

    def test_post_message(self):
        '''
        Test to send a message to a Slack channel.
        '''
        name = 'slack-message'
        channel = '#general'
        from_name = 'SuperAdmin'
        message = 'This state was executed successfully.'

        ret = {'name': name,
               'changes': {},
               'result': None,
               'comment': ''}

        with patch.dict(slack.__opts__, {'test': True}):
            comt = ('The following message is to be sent to Slack: {0}'
                    .format(message))
            ret.update({'comment': comt})
            self.assertDictEqual(slack.post_message(name, channel, from_name,
                                                    message), ret)

        with patch.dict(slack.__opts__, {'test': False}):
            comt = ('Slack channel is missing: None')
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(slack.post_message(name, None, from_name,
                                                    message), ret)

            comt = ('Slack from name is missing: None')
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(slack.post_message(name, channel, None,
                                                    message), ret)

            comt = ('Slack message is missing: None')
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(slack.post_message(name, channel, from_name,
                                                    None), ret)

            mock = MagicMock(return_value=True)
            with patch.dict(slack.__salt__, {'slack.post_message': mock}):
                comt = ('Sent message: slack-message')
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(slack.post_message(name, channel,
                                                        from_name, message),
                                     ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SlackTestCase, needs_daemon=False)
