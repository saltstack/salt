# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.modules import mac_keychain as keychain

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
        mock = MagicMock()
        with patch.dict(keychain.__salt__, {'cmd.run': mock}):
            keychain.install('/path/to/cert.p12', 'passw0rd')
            mock.assert_called_once_with('security import /path/to/cert.p12 -P passw0rd '
                                         '-k /Library/Keychains/System.keychain')

    @patch('salt.modules.mac_keychain.unlock_keychain')
    def test_install_cert_extras(self, unlock_mock):
        '''
            Test installing a certificate into the OSX keychain with extras
        '''
        mock = MagicMock()
        with patch.dict(keychain.__salt__, {'cmd.run': mock}):
            keychain.install('/path/to/cert.p12', 'passw0rd', '/path/to/chain', allow_any=True,
                             keychain_password='passw0rd1')
            unlock_mock.assert_called_once_with('/path/to/chain', 'passw0rd1')
            mock.assert_called_once_with('security import /path/to/cert.p12 -P passw0rd -k /path/to/chain -A')

    def test_uninstall_cert(self):
        '''
            Test uninstalling a certificate from the OSX keychain
        '''
        mock = MagicMock()
        with patch.dict(keychain.__salt__, {'cmd.run': mock}):
            keychain.uninstall('/path/to/cert.p12', 'passw0rd')
            mock.assert_called_once_with('security delete-certificate -c "/path/to/cert.p12" passw0rd')

    def test_list_certs(self):
        '''
            Test listing available certificates in a keychain
        '''
        expected = ["com.apple.systemdefault", "com.apple.kerberos.kdc"]
        mock = MagicMock(return_value='"com.apple.systemdefault"\n"com.apple.kerberos.kdc"')
        with patch.dict(keychain.__salt__, {'cmd.run': mock}):
            out = keychain.list_certs('/path/to/cert.p12')
            mock.assert_called_once_with('security find-certificate -a /path/to/cert.p12 | '
                                         'grep -o "alis".*\\" | grep -o \'\\"[-A-Za-z0-9.:() ]*\\"\'',
                                         python_shell=True)

            self.assertEqual(out, expected)

    def test_get_friendly_name(self):
        '''
            Test getting the friendly name of a certificate
        '''
        expected = "ID Installer Salt"
        mock = MagicMock(return_value="friendlyName: ID Installer Salt")
        with patch.dict(keychain.__salt__, {'cmd.run': mock}):
            out = keychain.get_friendly_name('/path/to/cert.p12', 'passw0rd')
            mock.assert_called_once_with('openssl pkcs12 -in /path/to/cert.p12 -passin pass:passw0rd -info '
                                         '-nodes -nokeys 2> /dev/null | grep friendlyName:',
                                         python_shell=True)

            self.assertEqual(out, expected)

    def test_get_default_keychain(self):
        '''
            Test getting the default keychain
        '''
        mock = MagicMock()
        with patch.dict(keychain.__salt__, {'cmd.run': mock}):
            keychain.get_default_keychain('frank', 'system')
            mock.assert_called_once_with('security default-keychain -d system', runas='frank')

    def test_set_default_keychain(self):
        '''
            Test setting the default keychain
        '''
        mock = MagicMock()
        with patch.dict(keychain.__salt__, {'cmd.run': mock}):
            keychain.set_default_keychain('/path/to/chain.keychain', 'system', 'frank')
            mock.assert_called_once_with('security default-keychain -d system -s /path/to/chain.keychain',
                                         runas='frank')

    def test_unlock_keychain(self):
        '''
            Test unlocking the keychain
        '''
        mock = MagicMock()
        with patch.dict(keychain.__salt__, {'cmd.run': mock}):
            keychain.unlock_keychain('/path/to/chain.keychain', 'passw0rd')
            mock.assert_called_once_with('security unlock-keychain -p passw0rd /path/to/chain.keychain')

if __name__ == '__main__':
    from integration import run_tests
    run_tests(KeychainTestCase, needs_daemon=False)
