# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt Libs
from salt.states import smtp


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SmtpTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.smtp
    '''
    loader_module = smtp
    # 'send_msg' function tests: 1

    def test_send_msg(self):
        '''
        Test to send a message via SMTP
        '''
        name = 'This is a salt states module'

        comt = ('Need to send message to admin@example.com:'
                ' This is a salt states module')

        ret = {'name': name,
               'changes': {},
               'result': None,
               'comment': comt}

        with patch.dict(smtp.__opts__, {'test': True}):
            self.assertDictEqual(smtp.send_msg(name,
                                               'admin@example.com',
                                               'Message from Salt',
                                               'admin@example.com',
                                               'my-smtp-account'), ret)

        comt = ('Sent message to admin@example.com: '
                'This is a salt states module')

        with patch.dict(smtp.__opts__, {'test': False}):
            mock = MagicMock(return_value=True)
            with patch.dict(smtp.__salt__, {'smtp.send_msg': mock}):
                ret['comment'] = comt
                ret['result'] = True
                self.assertDictEqual(smtp.send_msg(name,
                                                   'admin@example.com',
                                                   'Message from Salt',
                                                   'admin@example.com',
                                                   'my-smtp-account'), ret)
