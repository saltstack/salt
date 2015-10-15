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
from salt.states import smtp

smtp.__opts__ = {}
smtp.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SmtpTestCase(TestCase):
    '''
    Test cases for salt.states.smtp
    '''
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SmtpTestCase, needs_daemon=False)
