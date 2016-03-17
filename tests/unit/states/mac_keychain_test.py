# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.states import mac_keychain as keychain

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch
)

ensure_in_syspath('../../')

keychain.__salt__ = {}


class KeychainTestCase(TestCase):

    def test_install_cert(self):
        '''
            Test installing a certificate into the OSX keychain
        '''
        expected = {
            'changes': {'installed': 'Friendly Name'},
            'comment': '',
            'name': '/path/to/cert.p12',
            'result': True
        }

        list_mock = MagicMock(return_value=['Cert1'])
        friendly_mock = MagicMock(return_value='Friendly Name')
        install_mock = MagicMock(return_value='1 identity imported.')
        with patch.dict(keychain.__salt__, {'keychain.list_certs': list_mock,
                                            'keychain.get_friendly_name': friendly_mock,
                                            'keychain.install': install_mock}):
            out = keychain.installed('/path/to/cert.p12', 'passw0rd')
            list_mock.assert_called_once_with('/Library/Keychains/System.keychain')
            friendly_mock.assert_called_once_with('/path/to/cert.p12', 'passw0rd')
            install_mock.assert_called_once_with('/path/to/cert.p12', 'passw0rd', '/Library/Keychains/System.keychain')
            self.assertEqual(out, expected)

    def test_installed_cert(self):
        '''
            Test installing a certificate into the OSX keychain when it's already installed
        '''
        expected = {
            'changes': {},
            'comment': 'Friendly Name already installed.',
            'name': '/path/to/cert.p12',
            'result': True
        }

        list_mock = MagicMock(return_value=['Friendly Name'])
        friendly_mock = MagicMock(return_value='Friendly Name')
        install_mock = MagicMock(return_value='1 identity imported.')
        with patch.dict(keychain.__salt__, {'keychain.list_certs': list_mock,
                                            'keychain.get_friendly_name': friendly_mock,
                                            'keychain.install': install_mock}):
            out = keychain.installed('/path/to/cert.p12', 'passw0rd')
            list_mock.assert_called_once_with('/Library/Keychains/System.keychain')
            friendly_mock.assert_called_once_with('/path/to/cert.p12', 'passw0rd')
            assert not install_mock.called
            self.assertEqual(out, expected)

    def test_uninstall_cert(self):
        '''
            Test uninstalling a certificate into the OSX keychain when it's already installed
        '''
        expected = {
            'changes': {'uninstalled': 'Friendly Name'},
            'comment': '',
            'name': '/path/to/cert.p12',
            'result': True
        }

        list_mock = MagicMock(return_value=['Friendly Name'])
        friendly_mock = MagicMock(return_value='Friendly Name')
        uninstall_mock = MagicMock(return_value='1 identity imported.')
        with patch.dict(keychain.__salt__, {'keychain.list_certs': list_mock,
                                            'keychain.get_friendly_name': friendly_mock,
                                            'keychain.uninstall': uninstall_mock}):
            out = keychain.uninstalled('/path/to/cert.p12', 'passw0rd')
            list_mock.assert_called_once_with('/Library/Keychains/System.keychain')
            friendly_mock.assert_called_once_with('/path/to/cert.p12', 'passw0rd')
            uninstall_mock.assert_called_once_with('Friendly Name', '/Library/Keychains/System.keychain', None)
            self.assertEqual(out, expected)

    def test_uninstalled_cert(self):
        '''
            Test uninstalling a certificate into the OSX keychain when it's not installed
        '''
        expected = {
            'changes': {},
            'comment': 'Friendly Name already uninstalled.',
            'name': '/path/to/cert.p12',
            'result': True
        }

        list_mock = MagicMock(return_value=['Cert2'])
        friendly_mock = MagicMock(return_value='Friendly Name')
        uninstall_mock = MagicMock(return_value='1 identity imported.')
        with patch.dict(keychain.__salt__, {'keychain.list_certs': list_mock,
                                            'keychain.get_friendly_name': friendly_mock,
                                            'keychain.uninstall': uninstall_mock}):
            out = keychain.uninstalled('/path/to/cert.p12', 'passw0rd')
            list_mock.assert_called_once_with('/Library/Keychains/System.keychain')
            friendly_mock.assert_called_once_with('/path/to/cert.p12', 'passw0rd')
            assert not uninstall_mock.called
            self.assertEqual(out, expected)

    @patch('os.path.exists')
    def test_default_keychain(self, exists_mock):
        '''
            Test setting the default keychain
        '''
        expected = {
            'changes': {'default': '/path/to/chain.keychain'},
            'comment': '',
            'name': '/path/to/chain.keychain',
            'result': True
        }

        exists_mock.return_value = True
        get_default_mock = MagicMock(return_value='/path/to/other.keychain')
        set_mock = MagicMock(return_value='')
        with patch.dict(keychain.__salt__, {'keychain.get_default_keychain': get_default_mock,
                                            'keychain.set_default_keychain': set_mock}):
            out = keychain.default_keychain('/path/to/chain.keychain', 'system', 'frank')
            get_default_mock.assert_called_once_with('frank', 'system')
            set_mock.assert_called_once_with('/path/to/chain.keychain', 'system', 'frank')
            self.assertEqual(out, expected)

    @patch('os.path.exists')
    def test_default_keychain_set_already(self, exists_mock):
        '''
            Test setting the default keychain when it's already set
        '''
        expected = {
            'changes': {},
            'comment': '/path/to/chain.keychain was already the default keychain.',
            'name': '/path/to/chain.keychain',
            'result': True
        }

        exists_mock.return_value = True
        get_default_mock = MagicMock(return_value='/path/to/chain.keychain')
        set_mock = MagicMock(return_value='')
        with patch.dict(keychain.__salt__, {'keychain.get_default_keychain': get_default_mock,
                                            'keychain.set_default_keychain': set_mock}):
            out = keychain.default_keychain('/path/to/chain.keychain', 'system', 'frank')
            get_default_mock.assert_called_once_with('frank', 'system')
            assert not set_mock.called
            self.assertEqual(out, expected)

    @patch('os.path.exists')
    def test_default_keychain_missing(self, exists_mock):
        '''
            Test setting the default keychain when the keychain is missing
        '''
        expected = {
            'changes': {},
            'comment': 'Keychain not found at /path/to/cert.p12',
            'name': '/path/to/cert.p12',
            'result': False
        }

        exists_mock.return_value = False
        out = keychain.default_keychain('/path/to/cert.p12', 'system', 'frank')
        self.assertEqual(out, expected)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(KeychainTestCase, needs_daemon=False)
