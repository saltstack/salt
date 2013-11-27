# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place (mp@saltstack.com)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details
    :license: Apache 2.0, see LICENSE for more details.


    tests.unit.returners.smtp_return_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch, call

ensure_in_syspath('../../')

# Import salt libs
from salt.returners import smtp_return as smtp

smtp.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.returners.smtp_return.smtplib.SMTP')
class SMTPReturnerTestCase(TestCase):
    def test_returner(self, mocked_smtplib):
        '''
        Test to see if the SMTP returner sends a message
        '''
        ret = {'id': '12345',
               'fun': 'mytest.func',
               'fun_args': 'myfunc args',
               'jid': '54321',
               'return': 'The room is on fire as shes fixing her hair'
               }

        with patch.dict(smtp.__salt__, {'config.option': MagicMock()}):
            smtp.returner(ret)
            self.assertTrue(mocked_smtplib.return_value.sendmail.called)
