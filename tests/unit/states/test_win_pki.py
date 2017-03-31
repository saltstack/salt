# -*- coding: utf-8 -*-
'''
    :synopsis: Unit Tests for Windows PKI Module 'state.win_pki'
    :platform: Windows
    :maturity: develop
    .. versionadded:: Nitrogen
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Libs
import salt.states.win_pki as win_pki

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON,
)

CERT_PATH = r'C:\certs\testdomain.local.cer'
THUMBPRINT = '9988776655443322111000AAABBBCCCDDDEEEFFF'
STORE_PATH = r'Cert:\LocalMachine\My'

CERTS = {
    THUMBPRINT: {
        'dnsnames': ['testdomain.local'],
        'serialnumber': '0123456789AABBCCDD',
        'subject': 'CN=testdomain.local, OU=testou, O=testorg, S=California, C=US',
        'thumbprint': THUMBPRINT,
        'version': 3
    }
}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinPkiTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.win_pki
    '''
    def setup_loader_modules(self):
        return {win_pki: {}}

    def test_import_cert(self):
        '''
        Test - Import the certificate file into the given certificate store.
        '''
        kwargs = {'name': CERT_PATH}
        ret = {
            'name': kwargs['name'],
            'changes': {
                'old': None,
                'new': THUMBPRINT
            },
            'comment': "Certificate '{0}' imported into store: {1}".format(THUMBPRINT, STORE_PATH),
            'result': True
        }
        mock_cache_file = MagicMock(return_value=CERT_PATH)
        mock_certs = MagicMock(return_value={})
        mock_cert_file = MagicMock(return_value=CERTS[THUMBPRINT])
        mock_import_cert = MagicMock(return_value=True)
        with patch.dict(win_pki.__salt__, {'cp.cache_file': mock_cache_file,
                                           'win_pki.get_certs': mock_certs,
                                           'win_pki.get_cert_file': mock_cert_file,
                                           'win_pki.import_cert': mock_import_cert}):
            with patch.dict(win_pki.__opts__, {'test': False}):
                self.assertEqual(win_pki.import_cert(**kwargs), ret)
            with patch.dict(win_pki.__opts__, {'test': True}):
                ret['comment'] = ("Certificate '{0}' will be imported into store:"
                                  " {1}").format(THUMBPRINT, STORE_PATH)
                ret['result'] = None
                self.assertEqual(win_pki.import_cert(**kwargs), ret)

    def test_remove_cert(self):
        '''
        Test - Remove the certificate from the given certificate store.
        '''
        kwargs = {'name': 'remove-cert', 'thumbprint': THUMBPRINT}
        ret = {
            'name': kwargs['name'],
            'changes': {
                'old': kwargs['thumbprint'],
                'new': None
            },
            'comment': "Certificate '{0}' removed from store: {1}".format(kwargs['thumbprint'], STORE_PATH),
            'result': True
        }
        mock_certs = MagicMock(return_value=CERTS)
        mock_remove_cert = MagicMock(return_value=True)
        with patch.dict(win_pki.__salt__, {'win_pki.get_certs': mock_certs,
                                           'win_pki.remove_cert': mock_remove_cert}):
            with patch.dict(win_pki.__opts__, {'test': False}):
                self.assertEqual(win_pki.remove_cert(**kwargs), ret)
            with patch.dict(win_pki.__opts__, {'test': True}):
                ret['comment'] = ("Certificate '{0}' will be removed from store:"
                                 " {1}").format(kwargs['thumbprint'], STORE_PATH)
                ret['result'] = None
                self.assertEqual(win_pki.remove_cert(**kwargs), ret)
