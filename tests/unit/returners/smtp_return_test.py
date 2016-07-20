# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place (mp@saltstack.com)`


    tests.unit.returners.smtp_return_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

ensure_in_syspath('../../')

# Import salt libs
from salt.returners import smtp_return as smtp

smtp.__salt__ = {}
smtp.__opts__ = {}

try:
    import gnupg  # pylint: disable=unused-import
    HAS_GNUPG = True
except ImportError:
    HAS_GNUPG = False


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SMTPReturnerTestCase(TestCase):
    '''
    Test SMTP returner
    '''
    def _test_returner(self, mocked_smtplib, *args):  # pylint: disable=unused-argument
        '''
        Test to see if the SMTP returner sends a message
        '''
        ret = {'id': '12345',
               'fun': 'mytest.func',
               'fun_args': 'myfunc args',
               'jid': '54321',
               'return': 'The room is on fire as shes fixing her hair'}
        options = {'username': '',
                   'tls': '',
                   'from': '',
                   'fields': 'id,fun,fun_args,jid,return',
                   'to': '',
                   'host': '',
                   'renderer': 'jinja|yaml',
                   'template': '',
                   'password': '',
                   'gpgowner': '',
                   'subject': ''}

        with patch('salt.returners.smtp_return._get_options', MagicMock(return_value=options)):
            smtp.returner(ret)
            self.assertTrue(mocked_smtplib.return_value.sendmail.called)

if HAS_GNUPG:
    @patch('salt.returners.smtp_return.gnupg')
    @patch('salt.returners.smtp_return.smtplib.SMTP')
    def test_returner(self, mocked_smtplib, *args):
        with patch.dict(smtp.__opts__, {'extension_modules': '',
                                        'renderer': 'jinja|yaml',
                                        'file_roots': [],
                                        'pillar_roots': [],
                                        'cachedir': '/'}):
            self._test_returner(mocked_smtplib, *args)

else:
    @patch('salt.returners.smtp_return.smtplib.SMTP')
    def test_returner(self, mocked_smtplib, *args):
        with patch.dict(smtp.__opts__, {'extension_modules': '',
                                        'renderer': 'jinja|yaml',
                                        'file_roots': [],
                                        'pillar_roots': [],
                                        'cachedir': '/'}):
            self._test_returner(mocked_smtplib, *args)

SMTPReturnerTestCase.test_returner = test_returner
if __name__ == '__main__':
    from integration import run_tests
    run_tests(SMTPReturnerTestCase, needs_daemon=False)
