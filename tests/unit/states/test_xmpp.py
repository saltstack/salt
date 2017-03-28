# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.states.xmpp as xmpp


@skipIf(NO_MOCK, NO_MOCK_REASON)
class XmppTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Validate the xmpp state
    '''
    def setup_loader_modules(self):
        return {xmpp: {}}

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
