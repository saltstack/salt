# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place (mp@saltstack.com)`


    tests.unit.returners.smtp_return_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import salt libs
import salt.returners.smtp_return as smtp

try:
    import gnupg  # pylint: disable=unused-import
    HAS_GNUPG = True
except ImportError:
    HAS_GNUPG = False


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SMTPReturnerTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test SMTP returner
    '''
    def setup_loader_modules(self):
        return {smtp: {}}

    def _test_returner(self, mocked_smtplib):  # pylint: disable=unused-argument
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
        def test_returner(self):
            with patch.dict(smtp.__opts__, {'extension_modules': '',
                                            'renderer': 'jinja|yaml',
                                            'renderer_blacklist': [],
                                            'renderer_whitelist': [],
                                            'file_roots': [],
                                            'pillar_roots': [],
                                            'cachedir': '/'}), \
                    patch('salt.returners.smtp_return.gnupg'), \
                    patch('salt.returners.smtp_return.smtplib.SMTP') as mocked_smtplib:
                self._test_returner(mocked_smtplib)

    else:
        def test_returner(self):
            with patch.dict(smtp.__opts__, {'extension_modules': '',
                                            'renderer': 'jinja|yaml',
                                            'renderer_blacklist': [],
                                            'renderer_whitelist': [],
                                            'file_roots': [],
                                            'pillar_roots': [],
                                            'cachedir': '/'}), \
                    patch('salt.returners.smtp_return.smtplib.SMTP') as mocked_smtplib:
                self._test_returner(mocked_smtplib)
