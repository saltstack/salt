"""
Test cases for keystore state
"""

import salt.states.keystore as keystore
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class KeystoreTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.keystore
    """

    def setup_loader_modules(self):
        return {keystore: {"__opts__": {"test": False}}}

    @patch("os.path.exists", MagicMock(return_value=True))
    def test_cert_already_present(self):
        """
        Test for existing value_present
        """

        cert_return = [
            {
                "valid_until": "August 21 2017",
                "sha1": "07:1C:B9:4F:0C:C8:51:4D:02:41:24:70:8E:E8:B2:68:7B:D7:D9:D5",
                "valid_start": "August 22 2012",
                "type": "TrustedCertEntry",
                "alias": "stringhost",
                "expired": True,
            }
        ]
        x509_return = {
            "Not After": "2017-08-21 05:26:54",
            "Subject Hash": "97:95:14:4F",
            "Serial Number": "0D:FA",
            "SHA1 Finger Print": (
                "07:1C:B9:4F:0C:C8:51:4D:02:41:24:70:8E:E8:B2:68:7B:D7:D9:D5"
            ),
            "SHA-256 Finger Print": "5F:0F:B5:16:65:81:AA:E6:4A:10:1C:15:83:B1:BE:BE:74:E8:14:A9:1E:7A:8A:14:BA:1E:83:5D:78:F6:E9:E7",
            "MD5 Finger Print": "80:E6:17:AF:78:D8:E4:B8:FB:5F:41:3A:27:1D:CC:F2",
            "Version": 1,
            "Key Size": 512,
            "Public Key": (
                "-----BEGIN PUBLIC"
                " KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAJv8ZpB5hEK7qxP9K3v43hUS5fGT4waK\ne7ix4Z4mu5UBv+cw7WSFAt0Vaag0sAbsPzU8Hhsrj/qPABvfB8asUwcCAwEAAQ==\n-----END"
                " PUBLIC KEY-----\n"
            ),
            "Issuer": {
                "C": "JP",
                "organizationName": "Frank4DD",
                "CN": "Frank4DD Web CA",
                "SP": "Tokyo",
                "L": "Chuo-ku",
                "emailAddress": "support@frank4dd.com",
                "OU": "WebCert Support",
            },
            "Issuer Hash": "92:DA:45:6B",
            "Not Before": "2012-08-22 05:26:54",
            "Subject": {
                "C": "JP",
                "SP": "Tokyo",
                "organizationName": "Frank4DD",
                "CN": "www.example.com",
            },
        }

        name = "keystore.jks"
        passphrase = "changeit"
        entries = [
            {
                "alias": "stringhost",
                "certificate": """-----BEGIN CERTIFICATE-----
                   MIICEjCCAXsCAg36MA0GCSqGSIb3DQEBBQUAMIGbMQswCQYDVQQGEwJKUDEOMAwG
                   A1UECBMFVG9reW8xEDAOBgNVBAcTB0NodW8ta3UxETAPBgNVBAoTCEZyYW5rNERE
                   MRgwFgYDVQQLEw9XZWJDZXJ0IFN1cHBvcnQxGDAWBgNVBAMTD0ZyYW5rNEREIFdl
                   YiBDQTEjMCEGCSqGSIb3DQEJARYUc3VwcG9ydEBmcmFuazRkZC5jb20wHhcNMTIw
                   ODIyMDUyNjU0WhcNMTcwODIxMDUyNjU0WjBKMQswCQYDVQQGEwJKUDEOMAwGA1UE
                   CAwFVG9reW8xETAPBgNVBAoMCEZyYW5rNEREMRgwFgYDVQQDDA93d3cuZXhhbXBs
                   ZS5jb20wXDANBgkqhkiG9w0BAQEFAANLADBIAkEAm/xmkHmEQrurE/0re/jeFRLl
                   8ZPjBop7uLHhnia7lQG/5zDtZIUC3RVpqDSwBuw/NTweGyuP+o8AG98HxqxTBwID
                   AQABMA0GCSqGSIb3DQEBBQUAA4GBABS2TLuBeTPmcaTaUW/LCB2NYOy8GMdzR1mx
                   8iBIu2H6/E2tiY3RIevV2OW61qY2/XRQg7YPxx3ffeUugX9F4J/iPnnu1zAxxyBy
                   2VguKv4SWjRFoRkIfIlHX0qVviMhSlNy2ioFLy7JcPZb+v3ftDGywUqcBiVDoea0
                   Hn+GmxZA\n-----END CERTIFICATE-----""",
            }
        ]

        state_return = {
            "name": name,
            "changes": {},
            "result": True,
            "comment": "No changes made.\n",
        }

        # with patch.dict(keystore.__opts__, {'test': False}):
        with patch.dict(
            keystore.__salt__, {"keystore.list": MagicMock(return_value=cert_return)}
        ):
            with patch.dict(
                keystore.__salt__,
                {"x509.read_certificate": MagicMock(return_value=x509_return)},
            ):
                self.assertDictEqual(
                    keystore.managed(name, passphrase, entries), state_return
                )

        with patch.dict(keystore.__opts__, {"test": True}):
            with patch.dict(
                keystore.__salt__,
                {"keystore.list": MagicMock(return_value=cert_return)},
            ):
                with patch.dict(
                    keystore.__salt__,
                    {"x509.read_certificate": MagicMock(return_value=x509_return)},
                ):
                    self.assertDictEqual(
                        keystore.managed(name, passphrase, entries), state_return
                    )

    @patch("os.path.exists", MagicMock(return_value=True))
    def test_cert_update(self):
        """
        Test for existing value_present
        """

        cert_return = [
            {
                "valid_until": "August 21 2017",
                "sha1": "07:1C:B9:4F:0C:C8:51:4D:02:41:24:70:8E:E8:B2:68:7B:D7:D9:D5",
                "valid_start": "August 22 2012",
                "type": "TrustedCertEntry",
                "alias": "stringhost",
                "expired": True,
            }
        ]
        x509_return = {
            "Not After": "2017-08-21 05:26:54",
            "Subject Hash": "97:95:14:4F",
            "Serial Number": "0D:FA",
            "SHA1 Finger Print": (
                "07:1C:B9:4F:0C:C8:51:4D:02:41:24:70:8E:E8:B2:68:7B:D7:D9:D6"
            ),
            "SHA-256 Finger Print": "5F:0F:B5:16:65:81:AA:E6:4A:10:1C:15:83:B1:BE:BE:74:E8:14:A9:1E:7A:8A:14:BA:1E:83:5D:78:F6:E9:E7",
            "MD5 Finger Print": "80:E6:17:AF:78:D8:E4:B8:FB:5F:41:3A:27:1D:CC:F2",
            "Version": 1,
            "Key Size": 512,
            "Public Key": (
                "-----BEGIN PUBLIC"
                " KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAJv8ZpB5hEK7qxP9K3v43hUS5fGT4waK\ne7ix4Z4mu5UBv+cw7WSFAt0Vaag0sAbsPzU8Hhsrj/qPABvfB8asUwcCAwEAAQ==\n-----END"
                " PUBLIC KEY-----\n"
            ),
            "Issuer": {
                "C": "JP",
                "organizationName": "Frank4DD",
                "CN": "Frank4DD Web CA",
                "SP": "Tokyo",
                "L": "Chuo-ku",
                "emailAddress": "support@frank4dd.com",
                "OU": "WebCert Support",
            },
            "Issuer Hash": "92:DA:45:6B",
            "Not Before": "2012-08-22 05:26:54",
            "Subject": {
                "C": "JP",
                "SP": "Tokyo",
                "organizationName": "Frank4DD",
                "CN": "www.example.com",
            },
        }

        name = "keystore.jks"
        passphrase = "changeit"
        entries = [
            {
                "alias": "stringhost",
                "certificate": """-----BEGIN CERTIFICATE-----
                   MIICEjCCAXsCAg36MA0GCSqGSIb3DQEBBQUAMIGbMQswCQYDVQQGEwJKUDEOMAwG
                   A1UECBMFVG9reW8xEDAOBgNVBAcTB0NodW8ta3UxETAPBgNVBAoTCEZyYW5rNERE
                   MRgwFgYDVQQLEw9XZWJDZXJ0IFN1cHBvcnQxGDAWBgNVBAMTD0ZyYW5rNEREIFdl
                   YiBDQTEjMCEGCSqGSIb3DQEJARYUc3VwcG9ydEBmcmFuazRkZC5jb20wHhcNMTIw
                   ODIyMDUyNjU0WhcNMTcwODIxMDUyNjU0WjBKMQswCQYDVQQGEwJKUDEOMAwGA1UE
                   CAwFVG9reW8xETAPBgNVBAoMCEZyYW5rNEREMRgwFgYDVQQDDA93d3cuZXhhbXBs
                   ZS5jb20wXDANBgkqhkiG9w0BAQEFAANLADBIAkEAm/xmkHmEQrurE/0re/jeFRLl
                   8ZPjBop7uLHhnia7lQG/5zDtZIUC3RVpqDSwBuw/NTweGyuP+o8AG98HxqxTBwID
                   AQABMA0GCSqGSIb3DQEBBQUAA4GBABS2TLuBeTPmcaTaUW/LCB2NYOy8GMdzR1mx
                   8iBIu2H6/E2tiY3RIevV2OW61qY2/XRQg7YPxx3ffeUugX9F4J/iPnnu1zAxxyBy
                   2VguKv4SWjRFoRkIfIlHX0qVviMhSlNy2ioFLy7JcPZb+v3ftDGywUqcBiVDoea0
                   Hn+GmxZA\n-----END CERTIFICATE-----""",
            }
        ]

        test_return = {
            "name": name,
            "changes": {},
            "result": None,
            "comment": "Alias stringhost would have been updated\n",
        }
        state_return = {
            "name": name,
            "changes": {"stringhost": "Updated"},
            "result": True,
            "comment": "Alias stringhost updated.\n",
        }

        with patch.dict(keystore.__opts__, {"test": True}):
            with patch.dict(
                keystore.__salt__,
                {"keystore.list": MagicMock(return_value=cert_return)},
            ):
                with patch.dict(
                    keystore.__salt__,
                    {"x509.read_certificate": MagicMock(return_value=x509_return)},
                ):
                    self.assertDictEqual(
                        keystore.managed(name, passphrase, entries), test_return
                    )

        with patch.dict(
            keystore.__salt__, {"keystore.list": MagicMock(return_value=cert_return)}
        ):
            with patch.dict(
                keystore.__salt__,
                {"x509.read_certificate": MagicMock(return_value=x509_return)},
            ):
                with patch.dict(
                    keystore.__salt__, {"keystore.remove": MagicMock(return_value=True)}
                ):
                    with patch.dict(
                        keystore.__salt__,
                        {"keystore.add": MagicMock(return_value=True)},
                    ):
                        self.assertDictEqual(
                            keystore.managed(name, passphrase, entries), state_return
                        )

    @patch("os.path.exists", MagicMock(return_value=False))
    def test_new_file(self):
        """
        Test for existing value_present
        """
        name = "keystore.jks"
        passphrase = "changeit"
        entries = [
            {
                "alias": "stringhost",
                "certificate": """-----BEGIN CERTIFICATE-----
                   MIICEjCCAXsCAg36MA0GCSqGSIb3DQEBBQUAMIGbMQswCQYDVQQGEwJKUDEOMAwG
                   A1UECBMFVG9reW8xEDAOBgNVBAcTB0NodW8ta3UxETAPBgNVBAoTCEZyYW5rNERE
                   MRgwFgYDVQQLEw9XZWJDZXJ0IFN1cHBvcnQxGDAWBgNVBAMTD0ZyYW5rNEREIFdl
                   YiBDQTEjMCEGCSqGSIb3DQEJARYUc3VwcG9ydEBmcmFuazRkZC5jb20wHhcNMTIw
                   ODIyMDUyNjU0WhcNMTcwODIxMDUyNjU0WjBKMQswCQYDVQQGEwJKUDEOMAwGA1UE
                   CAwFVG9reW8xETAPBgNVBAoMCEZyYW5rNEREMRgwFgYDVQQDDA93d3cuZXhhbXBs
                   ZS5jb20wXDANBgkqhkiG9w0BAQEFAANLADBIAkEAm/xmkHmEQrurE/0re/jeFRLl
                   8ZPjBop7uLHhnia7lQG/5zDtZIUC3RVpqDSwBuw/NTweGyuP+o8AG98HxqxTBwID
                   AQABMA0GCSqGSIb3DQEBBQUAA4GBABS2TLuBeTPmcaTaUW/LCB2NYOy8GMdzR1mx
                   8iBIu2H6/E2tiY3RIevV2OW61qY2/XRQg7YPxx3ffeUugX9F4J/iPnnu1zAxxyBy
                   2VguKv4SWjRFoRkIfIlHX0qVviMhSlNy2ioFLy7JcPZb+v3ftDGywUqcBiVDoea0
                   Hn+GmxZA\n-----END CERTIFICATE-----""",
            }
        ]

        test_return = {
            "name": name,
            "changes": {},
            "result": None,
            "comment": "Alias stringhost would have been added\n",
        }
        state_return = {
            "name": name,
            "changes": {"stringhost": "Added"},
            "result": True,
            "comment": "Alias stringhost added.\n",
        }

        with patch.dict(keystore.__opts__, {"test": True}):
            self.assertDictEqual(
                keystore.managed(name, passphrase, entries), test_return
            )

        with patch.dict(
            keystore.__salt__, {"keystore.remove": MagicMock(return_value=True)}
        ):
            with patch.dict(
                keystore.__salt__, {"keystore.add": MagicMock(return_value=True)}
            ):
                self.assertDictEqual(
                    keystore.managed(name, passphrase, entries), state_return
                )

    @patch("os.path.exists", MagicMock(return_value=True))
    def test_force_remove(self):
        """
        Test for existing value_present
        """

        cert_return = [
            {
                "valid_until": "August 21 2017",
                "sha1": "07:1C:B9:4F:0C:C8:51:4D:02:41:24:70:8E:E8:B2:68:7B:D7:D9:D5",
                "valid_start": "August 22 2012",
                "type": "TrustedCertEntry",
                "alias": "oldhost",
                "expired": True,
            }
        ]
        x509_return = {
            "Not After": "2017-08-21 05:26:54",
            "Subject Hash": "97:95:14:4F",
            "Serial Number": "0D:FA",
            "SHA1 Finger Print": (
                "07:1C:B9:4F:0C:C8:51:4D:02:41:24:70:8E:E8:B2:68:7B:D7:D9:D6"
            ),
            "SHA-256 Finger Print": "5F:0F:B5:16:65:81:AA:E6:4A:10:1C:15:83:B1:BE:BE:74:E8:14:A9:1E:7A:8A:14:BA:1E:83:5D:78:F6:E9:E7",
            "MD5 Finger Print": "80:E6:17:AF:78:D8:E4:B8:FB:5F:41:3A:27:1D:CC:F2",
            "Version": 1,
            "Key Size": 512,
            "Public Key": (
                "-----BEGIN PUBLIC"
                " KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAJv8ZpB5hEK7qxP9K3v43hUS5fGT4waK\ne7ix4Z4mu5UBv+cw7WSFAt0Vaag0sAbsPzU8Hhsrj/qPABvfB8asUwcCAwEAAQ==\n-----END"
                " PUBLIC KEY-----\n"
            ),
            "Issuer": {
                "C": "JP",
                "organizationName": "Frank4DD",
                "CN": "Frank4DD Web CA",
                "SP": "Tokyo",
                "L": "Chuo-ku",
                "emailAddress": "support@frank4dd.com",
                "OU": "WebCert Support",
            },
            "Issuer Hash": "92:DA:45:6B",
            "Not Before": "2012-08-22 05:26:54",
            "Subject": {
                "C": "JP",
                "SP": "Tokyo",
                "organizationName": "Frank4DD",
                "CN": "www.example.com",
            },
        }

        name = "keystore.jks"
        passphrase = "changeit"
        entries = [
            {
                "alias": "stringhost",
                "certificate": """-----BEGIN CERTIFICATE-----
                   MIICEjCCAXsCAg36MA0GCSqGSIb3DQEBBQUAMIGbMQswCQYDVQQGEwJKUDEOMAwG
                   A1UECBMFVG9reW8xEDAOBgNVBAcTB0NodW8ta3UxETAPBgNVBAoTCEZyYW5rNERE
                   MRgwFgYDVQQLEw9XZWJDZXJ0IFN1cHBvcnQxGDAWBgNVBAMTD0ZyYW5rNEREIFdl
                   YiBDQTEjMCEGCSqGSIb3DQEJARYUc3VwcG9ydEBmcmFuazRkZC5jb20wHhcNMTIw
                   ODIyMDUyNjU0WhcNMTcwODIxMDUyNjU0WjBKMQswCQYDVQQGEwJKUDEOMAwGA1UE
                   CAwFVG9reW8xETAPBgNVBAoMCEZyYW5rNEREMRgwFgYDVQQDDA93d3cuZXhhbXBs
                   ZS5jb20wXDANBgkqhkiG9w0BAQEFAANLADBIAkEAm/xmkHmEQrurE/0re/jeFRLl
                   8ZPjBop7uLHhnia7lQG/5zDtZIUC3RVpqDSwBuw/NTweGyuP+o8AG98HxqxTBwID
                   AQABMA0GCSqGSIb3DQEBBQUAA4GBABS2TLuBeTPmcaTaUW/LCB2NYOy8GMdzR1mx
                   8iBIu2H6/E2tiY3RIevV2OW61qY2/XRQg7YPxx3ffeUugX9F4J/iPnnu1zAxxyBy
                   2VguKv4SWjRFoRkIfIlHX0qVviMhSlNy2ioFLy7JcPZb+v3ftDGywUqcBiVDoea0
                   Hn+GmxZA\n-----END CERTIFICATE-----""",
            }
        ]

        test_return = {
            "name": name,
            "changes": {},
            "result": None,
            "comment": (
                "Alias stringhost would have been updated\nAlias oldhost would have"
                " been removed"
            ),
        }
        state_return = {
            "name": name,
            "changes": {"oldhost": "Removed", "stringhost": "Updated"},
            "result": True,
            "comment": "Alias stringhost updated.\nAlias oldhost removed.\n",
        }

        with patch.dict(keystore.__opts__, {"test": True}):
            with patch.dict(
                keystore.__salt__,
                {"keystore.list": MagicMock(return_value=cert_return)},
            ):
                with patch.dict(
                    keystore.__salt__,
                    {"x509.read_certificate": MagicMock(return_value=x509_return)},
                ):
                    self.assertDictEqual(
                        keystore.managed(name, passphrase, entries, force_remove=True),
                        test_return,
                    )

        with patch.dict(
            keystore.__salt__, {"keystore.list": MagicMock(return_value=cert_return)}
        ):
            with patch.dict(
                keystore.__salt__,
                {"x509.read_certificate": MagicMock(return_value=x509_return)},
            ):
                with patch.dict(
                    keystore.__salt__, {"keystore.remove": MagicMock(return_value=True)}
                ):
                    with patch.dict(
                        keystore.__salt__,
                        {"keystore.add": MagicMock(return_value=True)},
                    ):
                        self.assertDictEqual(
                            keystore.managed(
                                name, passphrase, entries, force_remove=True
                            ),
                            state_return,
                        )
