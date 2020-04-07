# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.mac_keychain as keychain

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, call, patch
from tests.support.unit import TestCase


class KeychainTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {keychain: {}}

    def test_install_cert(self):
        """
            Test installing a certificate into the macOS keychain
        """
        expected = {
            "changes": {"installed": "Friendly Name"},
            "comment": "",
            "name": "/path/to/cert.p12",
            "result": True,
        }

        list_mock = MagicMock(return_value=["Cert1"])
        friendly_mock = MagicMock(return_value="Friendly Name")
        install_mock = MagicMock(return_value="1 identity imported.")
        with patch.dict(
            keychain.__salt__,
            {
                "keychain.list_certs": list_mock,
                "keychain.get_friendly_name": friendly_mock,
                "keychain.install": install_mock,
            },
        ):
            out = keychain.installed("/path/to/cert.p12", "passw0rd")
            list_mock.assert_called_once_with("/Library/Keychains/System.keychain")
            friendly_mock.assert_called_once_with("/path/to/cert.p12", "passw0rd")
            install_mock.assert_called_once_with(
                "/path/to/cert.p12", "passw0rd", "/Library/Keychains/System.keychain"
            )
            self.assertEqual(out, expected)

    def test_installed_cert(self):
        """
            Test installing a certificate into the macOS keychain when it's
            already installed
        """
        expected = {
            "changes": {},
            "comment": "Friendly Name already installed.",
            "name": "/path/to/cert.p12",
            "result": True,
        }

        list_mock = MagicMock(return_value=["Friendly Name"])
        friendly_mock = MagicMock(return_value="Friendly Name")
        install_mock = MagicMock(return_value="1 identity imported.")
        hash_mock = MagicMock(return_value="ABCD")
        with patch.dict(
            keychain.__salt__,
            {
                "keychain.list_certs": list_mock,
                "keychain.get_friendly_name": friendly_mock,
                "keychain.install": install_mock,
                "keychain.get_hash": hash_mock,
            },
        ):
            out = keychain.installed("/path/to/cert.p12", "passw0rd")
            list_mock.assert_called_once_with("/Library/Keychains/System.keychain")
            friendly_mock.assert_called_once_with("/path/to/cert.p12", "passw0rd")
            assert not install_mock.called
            self.assertEqual(out, expected)

    def test_uninstall_cert(self):
        """
            Test uninstalling a certificate into the macOS keychain when it's
            already installed
        """
        expected = {
            "changes": {"uninstalled": "Friendly Name"},
            "comment": "",
            "name": "/path/to/cert.p12",
            "result": True,
        }

        list_mock = MagicMock(return_value=["Friendly Name"])
        friendly_mock = MagicMock(return_value="Friendly Name")
        uninstall_mock = MagicMock(return_value="1 identity imported.")
        with patch.dict(
            keychain.__salt__,
            {
                "keychain.list_certs": list_mock,
                "keychain.get_friendly_name": friendly_mock,
                "keychain.uninstall": uninstall_mock,
            },
        ):
            out = keychain.uninstalled("/path/to/cert.p12", "passw0rd")
            list_mock.assert_called_once_with("/Library/Keychains/System.keychain")
            friendly_mock.assert_called_once_with("/path/to/cert.p12", "passw0rd")
            uninstall_mock.assert_called_once_with(
                "Friendly Name", "/Library/Keychains/System.keychain", None
            )
            self.assertEqual(out, expected)

    def test_uninstalled_cert(self):
        """
            Test uninstalling a certificate into the macOS keychain when it's
            not installed
        """
        expected = {
            "changes": {},
            "comment": "Friendly Name already uninstalled.",
            "name": "/path/to/cert.p12",
            "result": True,
        }

        list_mock = MagicMock(return_value=["Cert2"])
        friendly_mock = MagicMock(return_value="Friendly Name")
        uninstall_mock = MagicMock(return_value="1 identity imported.")
        with patch.dict(
            keychain.__salt__,
            {
                "keychain.list_certs": list_mock,
                "keychain.get_friendly_name": friendly_mock,
                "keychain.uninstall": uninstall_mock,
            },
        ):
            out = keychain.uninstalled("/path/to/cert.p12", "passw0rd")
            list_mock.assert_called_once_with("/Library/Keychains/System.keychain")
            friendly_mock.assert_called_once_with("/path/to/cert.p12", "passw0rd")
            assert not uninstall_mock.called
            self.assertEqual(out, expected)

    def test_default_keychain(self):
        """
            Test setting the default keychain
        """
        with patch("os.path.exists") as exists_mock:
            expected = {
                "changes": {"default": "/path/to/chain.keychain"},
                "comment": "",
                "name": "/path/to/chain.keychain",
                "result": True,
            }

            exists_mock.return_value = True
            get_default_mock = MagicMock(return_value="/path/to/other.keychain")
            set_mock = MagicMock(return_value="")
            with patch.dict(
                keychain.__salt__,
                {
                    "keychain.get_default_keychain": get_default_mock,
                    "keychain.set_default_keychain": set_mock,
                },
            ):
                out = keychain.default_keychain(
                    "/path/to/chain.keychain", "system", "frank"
                )
                get_default_mock.assert_called_once_with("frank", "system")
                set_mock.assert_called_once_with(
                    "/path/to/chain.keychain", "system", "frank"
                )
                self.assertEqual(out, expected)

    def test_default_keychain_set_already(self):
        """
            Test setting the default keychain when it's already set
        """
        with patch("os.path.exists") as exists_mock:
            expected = {
                "changes": {},
                "comment": "/path/to/chain.keychain was already the default keychain.",
                "name": "/path/to/chain.keychain",
                "result": True,
            }

            exists_mock.return_value = True
            get_default_mock = MagicMock(return_value="/path/to/chain.keychain")
            set_mock = MagicMock(return_value="")
            with patch.dict(
                keychain.__salt__,
                {
                    "keychain.get_default_keychain": get_default_mock,
                    "keychain.set_default_keychain": set_mock,
                },
            ):
                out = keychain.default_keychain(
                    "/path/to/chain.keychain", "system", "frank"
                )
                get_default_mock.assert_called_once_with("frank", "system")
                assert not set_mock.called
                self.assertEqual(out, expected)

    def test_default_keychain_missing(self):
        """
            Test setting the default keychain when the keychain is missing
        """
        with patch("os.path.exists") as exists_mock:
            expected = {
                "changes": {},
                "comment": "Keychain not found at /path/to/cert.p12",
                "name": "/path/to/cert.p12",
                "result": False,
            }

            exists_mock.return_value = False
            out = keychain.default_keychain("/path/to/cert.p12", "system", "frank")
            self.assertEqual(out, expected)

    def test_install_cert_salt_fileserver(self):
        """
            Test installing a certificate into the macOS keychain from the salt
            fileserver
        """
        expected = {
            "changes": {"installed": "Friendly Name"},
            "comment": "",
            "name": "salt://path/to/cert.p12",
            "result": True,
        }

        list_mock = MagicMock(return_value=["Cert1"])
        friendly_mock = MagicMock(return_value="Friendly Name")
        install_mock = MagicMock(return_value="1 identity imported.")
        cp_cache_mock = MagicMock(return_value="/tmp/path/to/cert.p12")
        with patch.dict(
            keychain.__salt__,
            {
                "keychain.list_certs": list_mock,
                "keychain.get_friendly_name": friendly_mock,
                "keychain.install": install_mock,
                "cp.cache_file": cp_cache_mock,
            },
        ):
            out = keychain.installed("salt://path/to/cert.p12", "passw0rd")
            list_mock.assert_called_once_with("/Library/Keychains/System.keychain")
            friendly_mock.assert_called_once_with("/tmp/path/to/cert.p12", "passw0rd")
            install_mock.assert_called_once_with(
                "/tmp/path/to/cert.p12",
                "passw0rd",
                "/Library/Keychains/System.keychain",
            )
            self.assertEqual(out, expected)

    def test_installed_cert_hash_different(self):
        """
            Test installing a certificate into the macOS keychain when it's
            already installed but the certificate has changed
        """
        expected = {
            "changes": {"installed": "Friendly Name", "uninstalled": "Friendly Name"},
            "comment": "Found a certificate with the same name but different hash, removing it.\n",
            "name": "/path/to/cert.p12",
            "result": True,
        }

        list_mock = MagicMock(side_effect=[["Friendly Name"], []])
        friendly_mock = MagicMock(return_value="Friendly Name")
        install_mock = MagicMock(return_value="1 identity imported.")
        uninstall_mock = MagicMock(return_value="removed.")
        hash_mock = MagicMock(side_effect=["ABCD", "XYZ"])
        with patch.dict(
            keychain.__salt__,
            {
                "keychain.list_certs": list_mock,
                "keychain.get_friendly_name": friendly_mock,
                "keychain.install": install_mock,
                "keychain.uninstall": uninstall_mock,
                "keychain.get_hash": hash_mock,
            },
        ):
            out = keychain.installed("/path/to/cert.p12", "passw0rd")
            list_mock.assert_has_calls(
                calls=[
                    call("/Library/Keychains/System.keychain"),
                    call("/Library/Keychains/System.keychain"),
                ]
            )
            friendly_mock.assert_called_once_with("/path/to/cert.p12", "passw0rd")
            install_mock.assert_called_once_with(
                "/path/to/cert.p12", "passw0rd", "/Library/Keychains/System.keychain"
            )
            uninstall_mock.assert_called_once_with(
                "Friendly Name",
                "/Library/Keychains/System.keychain",
                keychain_password=None,
            )
            self.assertEqual(out, expected)
