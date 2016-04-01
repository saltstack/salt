# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import xmpp

# Globals
xmpp.__salt__ = {}
xmpp.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class XmppTestCase(TestCase):
    '''
        Validate the xmpp state
    '''
    def test_send_msg(self):
        '''
            Test to send a message to an XMPP user
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': None,
               'comment': ''}
        with patch.dict(xmpp.__opts__, {"test": True}):
            ret.update({'comment': 'Need to send message to myaccount: salt'})
            self.assertDictEqual(xmpp.send_msg('salt', 'myaccount',
                                               'salt@saltstack.com'), ret)

        with patch.dict(xmpp.__opts__, {"test": False}):
            mock = MagicMock(return_value=True)
            with patch.dict(xmpp.__salt__, {'xmpp.send_msg': mock,
                                            'xmpp.send_msg_multi': mock}):
                ret.update({'result': True,
                            'comment': 'Sent message to myaccount: salt'})
                self.assertDictEqual(xmpp.send_msg('salt', 'myaccount',
                                                   'salt@saltstack.com'), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(XmppTestCase, needs_daemon=False)
