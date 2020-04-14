# -*- coding: utf-8 -*-
#
# Author: Bo Maryniuk <bo@suse.de>
#
# Copyright 2018 SUSE LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Import Salt Testing Libs
from __future__ import absolute_import, print_function, unicode_literals

import os
import tempfile

import salt.utils.files
import salt.utils.stringutils
from salt.modules import x509
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

try:
    import pytest
except ImportError as import_error:
    pytest = None


try:
    import M2Crypto  # pylint: disable=unused-import

    HAS_M2CRYPTO = True
except ImportError:
    HAS_M2CRYPTO = False


@skipIf(not bool(pytest), False)
class X509TestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {x509: {}}

    @patch("salt.modules.x509.log", MagicMock())
    def test_private_func__parse_subject(self):
        """
        Test private function _parse_subject(subject) it handles a missing fields
        :return:
        """

        class FakeSubject(object):
            """
            Class for faking x509'th subject.
            """

            def __init__(self):
                self.nid = {"Darth Vader": 1}

            def __getattr__(self, item):
                if item != "nid":
                    raise TypeError(
                        "A star wars satellite accidentally blew up the WAN."
                    )

        subj = FakeSubject()
        x509._parse_subject(subj)
        assert x509.log.trace.call_args[0][0] == "Missing attribute '%s'. Error: %s"
        assert x509.log.trace.call_args[0][1] == list(subj.nid.keys())[0]
        assert isinstance(x509.log.trace.call_args[0][2], TypeError)

    @skipIf(not HAS_M2CRYPTO, "Skipping, M2Crypto is unavailble")
    def test_get_pem_entry(self):
        """
        Test private function _parse_subject(subject) it handles a missing fields
        :return:
        """
        ca_key = b"""-----BEGIN RSA PRIVATE KEY-----
MIICWwIBAAKBgQCjdjbgL4kQ8Lu73xeRRM1q3C3K3ptfCLpyfw38LRnymxaoJ6ls
pNSx2dU1uJ89YKFlYLo1QcEk4rJ2fdIjarV0kuNCY3rC8jYUp9BpAU5Z6p9HKeT1
2rTPH81JyjbQDR5PyfCyzYOQtpwpB4zIUUK/Go7tTm409xGKbbUFugJNgQIDAQAB
AoGAF24we34U1ZrMLifSRv5nu3OIFNZHyx2DLDpOFOGaII5edwgIXwxZeIzS5Ppr
yO568/8jcdLVDqZ4EkgCwRTgoXRq3a1GLHGFmBdDNvWjSTTMLoozuM0t2zjRmIsH
hUd7tnai9Lf1Bp5HlBEhBU2gZWk+SXqLvxXe74/+BDAj7gECQQDRw1OPsrgTvs3R
3MNwX6W8+iBYMTGjn6f/6rvEzUs/k6rwJluV7n8ISNUIAxoPy5g5vEYK6Ln/Ttc7
u0K1KNlRAkEAx34qcxjuswavL3biNGE+8LpDJnJx1jaNWoH+ObuzYCCVMusdT2gy
kKuq9ytTDgXd2qwZpIDNmscvReFy10glMQJAXebMz3U4Bk7SIHJtYy7OKQzn0dMj
35WnRV81c2Jbnzhhu2PQeAvt/i1sgEuzLQL9QEtSJ6wLJ4mJvImV0TdaIQJAAYyk
TcKK0A8kOy0kMp3yvDHmJZ1L7wr7bBGIZPBlQ0Ddh8i1sJExm1gJ+uN2QKyg/XrK
tDFf52zWnCdVGgDwcQJALW/WcbSEK+JVV6KDJYpwCzWpKIKpBI0F6fdCr1G7Xcwj
c9bcgp7D7xD+TxWWNj4CSXEccJgGr91StV+gFg4ARQ==
-----END RSA PRIVATE KEY-----
"""

        ret = x509.get_pem_entry(ca_key)
        self.assertEqual(ret, ca_key)

    @skipIf(not HAS_M2CRYPTO, "Skipping, M2Crypto is unavailble")
    def test_get_private_key_size(self):
        """
        Test private function _parse_subject(subject) it handles a missing fields
        :return:
        """
        ca_key = """
-----BEGIN RSA PRIVATE KEY-----
MIICWwIBAAKBgQCjdjbgL4kQ8Lu73xeRRM1q3C3K3ptfCLpyfw38LRnymxaoJ6ls
pNSx2dU1uJ89YKFlYLo1QcEk4rJ2fdIjarV0kuNCY3rC8jYUp9BpAU5Z6p9HKeT1
2rTPH81JyjbQDR5PyfCyzYOQtpwpB4zIUUK/Go7tTm409xGKbbUFugJNgQIDAQAB
AoGAF24we34U1ZrMLifSRv5nu3OIFNZHyx2DLDpOFOGaII5edwgIXwxZeIzS5Ppr
yO568/8jcdLVDqZ4EkgCwRTgoXRq3a1GLHGFmBdDNvWjSTTMLoozuM0t2zjRmIsH
hUd7tnai9Lf1Bp5HlBEhBU2gZWk+SXqLvxXe74/+BDAj7gECQQDRw1OPsrgTvs3R
3MNwX6W8+iBYMTGjn6f/6rvEzUs/k6rwJluV7n8ISNUIAxoPy5g5vEYK6Ln/Ttc7
u0K1KNlRAkEAx34qcxjuswavL3biNGE+8LpDJnJx1jaNWoH+ObuzYCCVMusdT2gy
kKuq9ytTDgXd2qwZpIDNmscvReFy10glMQJAXebMz3U4Bk7SIHJtYy7OKQzn0dMj
35WnRV81c2Jbnzhhu2PQeAvt/i1sgEuzLQL9QEtSJ6wLJ4mJvImV0TdaIQJAAYyk
TcKK0A8kOy0kMp3yvDHmJZ1L7wr7bBGIZPBlQ0Ddh8i1sJExm1gJ+uN2QKyg/XrK
tDFf52zWnCdVGgDwcQJALW/WcbSEK+JVV6KDJYpwCzWpKIKpBI0F6fdCr1G7Xcwj
c9bcgp7D7xD+TxWWNj4CSXEccJgGr91StV+gFg4ARQ==
-----END RSA PRIVATE KEY-----
"""

        ret = x509.get_private_key_size(ca_key)
        self.assertEqual(ret, 1024)

    @skipIf(not HAS_M2CRYPTO, "Skipping, M2Crypto is unavailble")
    def test_create_key(self):
        """
        Test that x509.create_key returns a private key
        :return:
        """
        ret = x509.create_private_key(text=True, passphrase="super_secret_passphrase")
        self.assertIn("BEGIN RSA PRIVATE KEY", ret)

    @skipIf(not HAS_M2CRYPTO, "Skipping, M2Crypto is unavailble")
    def test_create_certificate(self):
        """
        Test private function _parse_subject(subject) it handles a missing fields
        :return:
        """
        ca_key = """
-----BEGIN RSA PRIVATE KEY-----
MIICWwIBAAKBgQCjdjbgL4kQ8Lu73xeRRM1q3C3K3ptfCLpyfw38LRnymxaoJ6ls
pNSx2dU1uJ89YKFlYLo1QcEk4rJ2fdIjarV0kuNCY3rC8jYUp9BpAU5Z6p9HKeT1
2rTPH81JyjbQDR5PyfCyzYOQtpwpB4zIUUK/Go7tTm409xGKbbUFugJNgQIDAQAB
AoGAF24we34U1ZrMLifSRv5nu3OIFNZHyx2DLDpOFOGaII5edwgIXwxZeIzS5Ppr
yO568/8jcdLVDqZ4EkgCwRTgoXRq3a1GLHGFmBdDNvWjSTTMLoozuM0t2zjRmIsH
hUd7tnai9Lf1Bp5HlBEhBU2gZWk+SXqLvxXe74/+BDAj7gECQQDRw1OPsrgTvs3R
3MNwX6W8+iBYMTGjn6f/6rvEzUs/k6rwJluV7n8ISNUIAxoPy5g5vEYK6Ln/Ttc7
u0K1KNlRAkEAx34qcxjuswavL3biNGE+8LpDJnJx1jaNWoH+ObuzYCCVMusdT2gy
kKuq9ytTDgXd2qwZpIDNmscvReFy10glMQJAXebMz3U4Bk7SIHJtYy7OKQzn0dMj
35WnRV81c2Jbnzhhu2PQeAvt/i1sgEuzLQL9QEtSJ6wLJ4mJvImV0TdaIQJAAYyk
TcKK0A8kOy0kMp3yvDHmJZ1L7wr7bBGIZPBlQ0Ddh8i1sJExm1gJ+uN2QKyg/XrK
tDFf52zWnCdVGgDwcQJALW/WcbSEK+JVV6KDJYpwCzWpKIKpBI0F6fdCr1G7Xcwj
c9bcgp7D7xD+TxWWNj4CSXEccJgGr91StV+gFg4ARQ==
-----END RSA PRIVATE KEY-----
"""

        ret = x509.create_certificate(
            text=True,
            signing_private_key=ca_key,
            CN="Redacted Root CA",
            O="Redacted",
            C="BE",
            ST="Antwerp",
            L="Local Town",
            Email="certadm@example.org",
            basicConstraints="critical CA:true",
            keyUsage="critical cRLSign, keyCertSign",
            subjectKeyIdentifier="hash",
            authorityKeyIdentifier="keyid,issuer:always",
            days_valid=3650,
            days_remaining=0,
        )
        self.assertIn("BEGIN CERTIFICATE", ret)

    @skipIf(not HAS_M2CRYPTO, "Skipping, M2Crypto is unavailble")
    def test_create_crl(self):
        ca_key = """
-----BEGIN RSA PRIVATE KEY-----
MIICWwIBAAKBgQCjdjbgL4kQ8Lu73xeRRM1q3C3K3ptfCLpyfw38LRnymxaoJ6ls
pNSx2dU1uJ89YKFlYLo1QcEk4rJ2fdIjarV0kuNCY3rC8jYUp9BpAU5Z6p9HKeT1
2rTPH81JyjbQDR5PyfCyzYOQtpwpB4zIUUK/Go7tTm409xGKbbUFugJNgQIDAQAB
AoGAF24we34U1ZrMLifSRv5nu3OIFNZHyx2DLDpOFOGaII5edwgIXwxZeIzS5Ppr
yO568/8jcdLVDqZ4EkgCwRTgoXRq3a1GLHGFmBdDNvWjSTTMLoozuM0t2zjRmIsH
hUd7tnai9Lf1Bp5HlBEhBU2gZWk+SXqLvxXe74/+BDAj7gECQQDRw1OPsrgTvs3R
3MNwX6W8+iBYMTGjn6f/6rvEzUs/k6rwJluV7n8ISNUIAxoPy5g5vEYK6Ln/Ttc7
u0K1KNlRAkEAx34qcxjuswavL3biNGE+8LpDJnJx1jaNWoH+ObuzYCCVMusdT2gy
kKuq9ytTDgXd2qwZpIDNmscvReFy10glMQJAXebMz3U4Bk7SIHJtYy7OKQzn0dMj
35WnRV81c2Jbnzhhu2PQeAvt/i1sgEuzLQL9QEtSJ6wLJ4mJvImV0TdaIQJAAYyk
TcKK0A8kOy0kMp3yvDHmJZ1L7wr7bBGIZPBlQ0Ddh8i1sJExm1gJ+uN2QKyg/XrK
tDFf52zWnCdVGgDwcQJALW/WcbSEK+JVV6KDJYpwCzWpKIKpBI0F6fdCr1G7Xcwj
c9bcgp7D7xD+TxWWNj4CSXEccJgGr91StV+gFg4ARQ==
-----END RSA PRIVATE KEY-----
"""

        ca_cert = x509.create_certificate(
            text=True,
            signing_private_key=ca_key,
            CN="Redacted Root CA",
            O="Redacted",
            C="BE",
            ST="Antwerp",
            L="Local Town",
            Email="certadm@example.org",
            basicConstraints="critical CA:true",
            keyUsage="critical cRLSign, keyCertSign",
            subjectKeyIdentifier="hash",
            authorityKeyIdentifier="keyid,issuer:always",
            days_valid=3650,
            days_remaining=0,
        )

        with tempfile.NamedTemporaryFile("w+", delete=False) as ca_key_file:
            ca_key_file.write(ca_key)
            ca_key_file.flush()

        with tempfile.NamedTemporaryFile("w+", delete=False) as ca_cert_file:
            ca_cert_file.write(salt.utils.stringutils.to_str(ca_cert))
            ca_cert_file.flush()

        with tempfile.NamedTemporaryFile("w+", delete=False) as ca_crl_file:
            x509.create_crl(
                path=ca_crl_file.name,
                text=False,
                signing_private_key=ca_key_file.name,
                signing_private_key_passphrase=None,
                signing_cert=ca_cert_file.name,
                revoked=None,
                include_expired=False,
                days_valid=100,
                digest="sha512",
            )

        with salt.utils.files.fopen(ca_crl_file.name, "r") as crl_file:
            crl = crl_file.read()

        os.remove(ca_key_file.name)
        os.remove(ca_cert_file.name)
        os.remove(ca_crl_file.name)

        # Ensure that a CRL was actually created
        self.assertIn("BEGIN X509 CRL", crl)

    @skipIf(not HAS_M2CRYPTO, "Skipping, M2Crypto is unavailble")
    def test_revoke_certificate_with_crl(self):
        ca_key = """
-----BEGIN RSA PRIVATE KEY-----
MIICWwIBAAKBgQCjdjbgL4kQ8Lu73xeRRM1q3C3K3ptfCLpyfw38LRnymxaoJ6ls
pNSx2dU1uJ89YKFlYLo1QcEk4rJ2fdIjarV0kuNCY3rC8jYUp9BpAU5Z6p9HKeT1
2rTPH81JyjbQDR5PyfCyzYOQtpwpB4zIUUK/Go7tTm409xGKbbUFugJNgQIDAQAB
AoGAF24we34U1ZrMLifSRv5nu3OIFNZHyx2DLDpOFOGaII5edwgIXwxZeIzS5Ppr
yO568/8jcdLVDqZ4EkgCwRTgoXRq3a1GLHGFmBdDNvWjSTTMLoozuM0t2zjRmIsH
hUd7tnai9Lf1Bp5HlBEhBU2gZWk+SXqLvxXe74/+BDAj7gECQQDRw1OPsrgTvs3R
3MNwX6W8+iBYMTGjn6f/6rvEzUs/k6rwJluV7n8ISNUIAxoPy5g5vEYK6Ln/Ttc7
u0K1KNlRAkEAx34qcxjuswavL3biNGE+8LpDJnJx1jaNWoH+ObuzYCCVMusdT2gy
kKuq9ytTDgXd2qwZpIDNmscvReFy10glMQJAXebMz3U4Bk7SIHJtYy7OKQzn0dMj
35WnRV81c2Jbnzhhu2PQeAvt/i1sgEuzLQL9QEtSJ6wLJ4mJvImV0TdaIQJAAYyk
TcKK0A8kOy0kMp3yvDHmJZ1L7wr7bBGIZPBlQ0Ddh8i1sJExm1gJ+uN2QKyg/XrK
tDFf52zWnCdVGgDwcQJALW/WcbSEK+JVV6KDJYpwCzWpKIKpBI0F6fdCr1G7Xcwj
c9bcgp7D7xD+TxWWNj4CSXEccJgGr91StV+gFg4ARQ==
-----END RSA PRIVATE KEY-----
"""
        # Issue the CA certificate (self-signed)
        ca_cert = x509.create_certificate(
            text=True,
            signing_private_key=ca_key,
            CN="Redacted Root CA",
            O="Redacted",
            C="BE",
            ST="Antwerp",
            L="Local Town",
            Email="certadm@example.org",
            basicConstraints="critical CA:true",
            keyUsage="critical cRLSign, keyCertSign",
            subjectKeyIdentifier="hash",
            authorityKeyIdentifier="keyid,issuer:always",
            days_valid=3650,
            days_remaining=0,
        )

        # Sign a client certificate with the CA
        server_cert = x509.create_certificate(
            text=True,
            signing_private_key=ca_key,
            signing_cert=ca_cert,
            CN="Redacted Normal Certificate",
            O="Redacted",
            C="BE",
            ST="Antwerp",
            L="Local Town",
            Email="certadm@example.org",
            basicConstraints="critical CA:false",
            keyUsage="critical keyEncipherment",
            subjectKeyIdentifier="hash",
            authorityKeyIdentifier="keyid,issuer:always",
            days_valid=365,
            days_remaining=0,
        )

        # Save CA cert + key and server cert to disk as PEM files
        with tempfile.NamedTemporaryFile("w+", delete=False) as ca_key_file:
            ca_key_file.write(ca_key)
            ca_key_file.flush()

        with tempfile.NamedTemporaryFile("w+", delete=False) as ca_cert_file:
            ca_cert_file.write(salt.utils.stringutils.to_str(ca_cert))
            ca_cert_file.flush()

        with tempfile.NamedTemporaryFile("w+", delete=False) as server_cert_file:
            server_cert_file.write(salt.utils.stringutils.to_str(server_cert))
            server_cert_file.flush()

        # Revoke server CRL
        revoked = [
            {
                "certificate": server_cert_file.name,
                "revocation_date": "2015-03-01 00:00:00",
            }
        ]
        with tempfile.NamedTemporaryFile("w+", delete=False) as ca_crl_file:
            x509.create_crl(
                path=ca_crl_file.name,
                text=False,
                signing_private_key=ca_key_file.name,
                signing_private_key_passphrase=None,
                signing_cert=ca_cert_file.name,
                revoked=revoked,
                include_expired=False,
                days_valid=100,
                digest="sha512",
            )

        # Retrieve serial number from server certificate
        server_cert_details = x509.read_certificate(server_cert_file.name)
        serial_number = server_cert_details["Serial Number"].replace(":", "")
        serial_number = salt.utils.stringutils.to_str(serial_number)

        # Retrieve CRL as text
        crl = M2Crypto.X509.load_crl(ca_crl_file.name).as_text()

        # Cleanup
        os.remove(ca_key_file.name)
        os.remove(ca_cert_file.name)
        os.remove(ca_crl_file.name)
        os.remove(server_cert_file.name)

        # Ensure that the correct server cert serial is amongst
        # the revoked certificates
        self.assertIn(serial_number, crl)
