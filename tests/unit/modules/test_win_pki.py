# -*- coding: utf-8 -*-
'''
    :synopsis: Unit Tests for Windows PKI Module 'module.win_pki'
    :platform: Windows
    :maturity: develop
    .. versionadded:: Nitrogen
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Libs
import salt.modules.win_pki as win_pki

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

CERTS = {
    THUMBPRINT: {
        'dnsnames': ['testdomain.local'],
        'serialnumber': '0123456789AABBCCDD',
        'subject': 'CN=testdomain.local, OU=testou, O=testorg, S=California, C=US',
        'thumbprint': THUMBPRINT,
        'version': 3
    }
}

STORES = {
    'CurrentUser': [
        'AuthRoot',
        'CA',
        'ClientAuthIssuer',
        'Disallowed',
        'MSIEHistoryJournal',
        'My',
        'Root',
        'SmartCardRoot',
        'Trust',
        'TrustedPeople',
        'TrustedPublisher',
        'UserDS'
    ],
    'LocalMachine': [
        'AuthRoot',
        'CA',
        'ClientAuthIssuer',
        'Disallowed',
        'My',
        'Remote Desktop',
        'Root',
        'SmartCardRoot',
        'Trust',
        'TrustedDevices',
        'TrustedPeople',
        'TrustedPublisher',
        'WebHosting'
    ]
}

JSON_CERTS = [{
    'DnsNameList': [{
        'Punycode': 'testdomain.local',
        'Unicode': 'testdomain.local'
    }],
    'SerialNumber': '0123456789AABBCCDD',
    'Subject': 'CN=testdomain.local, OU=testou, O=testorg, S=California, C=US',
    'Thumbprint': '9988776655443322111000AAABBBCCCDDDEEEFFF',
    'Version': 3
}]

JSON_STORES = [{
    'LocationName': 'CurrentUser',
    'StoreNames': STORES['CurrentUser']
}, {
    'LocationName': 'LocalMachine',
    'StoreNames': STORES['LocalMachine']
}]


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinPkiTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.win_pki
    '''
    def setup_loader_modules(self):
        return {win_pki: {}}

    def test_get_stores(self):
        '''
        Test - Get the certificate location contexts and their corresponding stores.
        '''
        with patch.dict(win_pki.__salt__), \
                patch('salt.modules.win_pki._cmd_run',
                      MagicMock(return_value=JSON_STORES)):
            self.assertEqual(win_pki.get_stores(), STORES)

    def test_get_certs(self):
        '''
        Test - Get the available certificates in the given store.
        '''
        with patch.dict(win_pki.__salt__), \
                patch('salt.modules.win_pki._cmd_run',
                      MagicMock(return_value=JSON_CERTS)), \
                patch('salt.modules.win_pki._validate_cert_path',
                      MagicMock(return_value=None)):
            self.assertEqual(win_pki.get_certs(), CERTS)

    def test_get_cert_file(self):
        '''
        Test - Get the details of the certificate file.
        '''
        kwargs = {'name': CERT_PATH}
        with patch.dict(win_pki.__salt__), \
                patch('os.path.isfile',
                     MagicMock(return_value=True)), \
                patch('salt.modules.win_pki._cmd_run',
                      MagicMock(return_value=JSON_CERTS)):
            self.assertEqual(win_pki.get_cert_file(**kwargs), CERTS[THUMBPRINT])

    def test_import_cert(self):
        '''
        Test - Import the certificate file into the given certificate store.
        '''
        kwargs = {'name': CERT_PATH}
        mock_value = MagicMock(return_value=CERT_PATH)
        with patch.dict(win_pki.__salt__, {'cp.cache_file': mock_value}), \
                patch('salt.modules.win_pki._cmd_run',
                      MagicMock(return_value=JSON_CERTS)), \
                patch('salt.modules.win_pki._validate_cert_path',
                      MagicMock(return_value=None)), \
                patch('salt.modules.win_pki.get_cert_file',
                      MagicMock(return_value=CERTS[THUMBPRINT])), \
                patch('salt.modules.win_pki.get_certs',
                      MagicMock(return_value=CERTS)):
            self.assertTrue(win_pki.import_cert(**kwargs))

    def test_export_cert(self):
        '''
        Test - Export the certificate to a file from the given certificate store.
        '''
        kwargs = {'name': CERT_PATH,
                  'thumbprint': THUMBPRINT}
        with patch.dict(win_pki.__salt__), \
                patch('salt.modules.win_pki._cmd_run',
                      MagicMock(return_value='True')), \
                patch('salt.modules.win_pki._validate_cert_format',
                      MagicMock(return_value=None)), \
                patch('salt.modules.win_pki._validate_cert_path',
                      MagicMock(return_value=None)):
            self.assertTrue(win_pki.export_cert(**kwargs))

    def test_test_cert(self):
        '''
        Test - Check the certificate for validity.
        '''
        with patch.dict(win_pki.__salt__), \
                patch('salt.modules.win_pki._cmd_run',
                      MagicMock(return_value='True')), \
                patch('salt.modules.win_pki._validate_cert_path',
                      MagicMock(return_value=None)):
            self.assertTrue(win_pki.test_cert(thumbprint=THUMBPRINT))

    def test_remove_cert(self):
        '''
        Test - Remove the certificate from the given certificate store.
        '''
        with patch.dict(win_pki.__salt__), \
                patch('salt.modules.win_pki._cmd_run',
                      MagicMock(return_value=None)), \
                patch('salt.modules.win_pki._validate_cert_path',
                      MagicMock(return_value=None)), \
                patch('salt.modules.win_pki.get_certs',
                      MagicMock(return_value=CERTS)):
            self.assertTrue(win_pki.remove_cert(thumbprint=THUMBPRINT[::-1]))
