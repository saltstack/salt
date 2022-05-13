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


import datetime
import os
import tempfile

import salt.utils.files
import salt.utils.stringutils
from salt.modules import x509
from tests.support.helpers import dedent
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

try:
    import M2Crypto  # pylint: disable=unused-import

    HAS_M2CRYPTO = True
except ImportError:
    HAS_M2CRYPTO = False


default_values = {
    "ca_key": b"""-----BEGIN RSA PRIVATE KEY-----
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
""",
    "x509_args_ca": {
        "text": True,
        "CN": "Redacted Root CA",
        "O": "Redacted",
        "C": "BE",
        "ST": "Antwerp",
        "L": "Local Town",
        "Email": "certadm@example.org",
        "basicConstraints": "critical CA:true",
        "keyUsage": "critical cRLSign, keyCertSign",
        "subjectKeyIdentifier": "hash",
        "authorityKeyIdentifier": "keyid,issuer:always",
        "days_valid": 3650,
        "days_remaining": 0,
    },
    "x509_args_cert": {
        "text": True,
        "CN": "Redacted Normal Certificate",
        "O": "Redacted",
        "C": "BE",
        "ST": "Antwerp",
        "L": "Local Town",
        "Email": "certadm@example.org",
        "basicConstraints": "critical CA:false",
        "keyUsage": "critical keyEncipherment",
        "subjectKeyIdentifier": "hash",
        "authorityKeyIdentifier": "keyid,issuer:always",
    },
    "crl_args": {
        "text": False,
        "signing_private_key_passphrase": None,
        "revoked": None,
        "include_expired": False,
        "days_valid": 100,
        "digest": "sha512",
    },
}


class X509TestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {x509: {"__opts__": {"fips_mode": False}}}

    @patch("salt.modules.x509.log", MagicMock())
    def test_private_func__parse_subject(self):
        """
        Test private function _parse_subject(subject) it handles a missing fields
        :return:
        """

        class FakeSubject:
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

    @skipIf(not HAS_M2CRYPTO, "Skipping, M2Crypto is unavailable")
    def test_get_pem_entry(self):
        """
        Test private function _parse_subject(subject) it handles a missing fields
        :return:
        """
        ca_key = default_values["ca_key"]
        ret = x509.get_pem_entry(ca_key)
        self.assertEqual(ret, ca_key)

    @skipIf(not HAS_M2CRYPTO, "Skipping, M2Crypto is unavailable")
    def test_get_private_key_size(self):
        """
        Test private function _parse_subject(subject) it handles a missing fields
        :return:
        """
        ca_key = default_values["ca_key"]
        ret = x509.get_private_key_size(ca_key)
        self.assertEqual(ret, 1024)

    @skipIf(not HAS_M2CRYPTO, "Skipping, M2Crypto is unavailable")
    def test_create_key(self):
        """
        Test that x509.create_key returns a private key
        :return:
        """
        ret = x509.create_private_key(text=True, passphrase="super_secret_passphrase")
        self.assertIn("BEGIN RSA PRIVATE KEY", ret)

    @skipIf(not HAS_M2CRYPTO, "Skipping, M2Crypto is unavailable")
    def test_create_certificate(self):
        """
        Test private function _parse_subject(subject) it handles a missing fields
        :return:
        """
        ca_key = default_values["ca_key"]
        ca_kwargs = default_values["x509_args_ca"].copy()
        ca_kwargs["signing_private_key"] = ca_key
        ret = x509.create_certificate(**ca_kwargs)
        self.assertIn("BEGIN CERTIFICATE", ret)

    @skipIf(not HAS_M2CRYPTO, "Skipping, M2Crypto is unavailable")
    def test_create_certificate_with_not_after(self):
        ca_key = default_values["ca_key"]
        ca_kwargs = default_values["x509_args_ca"].copy()
        ca_kwargs["signing_private_key"] = ca_key

        # Issue the CA certificate (self-signed)
        ca_cert = x509.create_certificate(**ca_kwargs)

        fmt = "%Y-%m-%d %H:%M:%S"
        # We also gonna use the current date in UTC format for verification
        not_after = datetime.datetime.utcnow()
        # And set the UTC timezone to the naive datetime resulting from parsing
        not_after = not_after.replace(tzinfo=M2Crypto.ASN1.UTC)
        not_after_str = datetime.datetime.strftime(not_after, fmt)

        # Sign a new server certificate with the CA
        ca_key = default_values["ca_key"]
        cert_kwargs = default_values["x509_args_cert"].copy()
        cert_kwargs["signing_private_key"] = ca_key
        cert_kwargs["signing_cert"] = ca_cert
        cert_kwargs["not_after"] = not_after_str
        server_cert = x509.create_certificate(**cert_kwargs)

        not_after_from_cert = ""
        # Save server certificate to disk so we can check its properties
        with tempfile.NamedTemporaryFile("w+") as server_cert_file:
            server_cert_file.write(salt.utils.stringutils.to_str(server_cert))
            server_cert_file.flush()

            # Retrieve not_after property from server certificate
            server_cert_details = x509.read_certificate(server_cert_file.name)
            not_after_from_cert = server_cert_details["Not After"]

        # Check if property is the one we've added to the certificate. The
        # property from the certificate will come as a string with no timezone
        # information in it.
        self.assertIn(not_after_str, not_after_from_cert)

    @skipIf(not HAS_M2CRYPTO, "Skipping, M2Crypto is unavailable")
    def test_create_certificate_with_not_before(self):
        ca_key = default_values["ca_key"]
        ca_kwargs = default_values.get("x509_args_ca").copy()
        ca_kwargs["signing_private_key"] = ca_key

        # Issue the CA certificate (self-signed)
        ca_cert = x509.create_certificate(**ca_kwargs)

        fmt = "%Y-%m-%d %H:%M:%S"
        # We also gonna use the current date in UTC format for verification
        not_before = datetime.datetime.utcnow()
        # And set the UTC timezone to the naive datetime resulting from parsing
        not_before = not_before.replace(tzinfo=M2Crypto.ASN1.UTC)
        not_before_str = datetime.datetime.strftime(not_before, fmt)

        # Sign a new server certificate with the CA
        ca_key = default_values["ca_key"]
        cert_kwargs = default_values["x509_args_cert"].copy()
        cert_kwargs["signing_private_key"] = ca_key
        cert_kwargs["signing_cert"] = ca_cert
        cert_kwargs["not_before"] = not_before_str
        server_cert = x509.create_certificate(**cert_kwargs)

        not_before_from_cert = ""
        # Save server certificate to disk so we can check its properties
        with tempfile.NamedTemporaryFile("w+") as server_cert_file:
            server_cert_file.write(salt.utils.stringutils.to_str(server_cert))
            server_cert_file.flush()
            # Retrieve not_after property from server certificate
            server_cert_details = x509.read_certificate(server_cert_file.name)
            not_before_from_cert = server_cert_details["Not Before"]

        # Check if property is the one we've added to the certificate. The
        # property will come from the certificate as a string with no timezone
        # information in it.
        self.assertIn(not_before_str, not_before_from_cert)

    @skipIf(not HAS_M2CRYPTO, "Skipping, M2Crypto is unavailable")
    def test_create_certificate_with_not_before_wrong_date(self):
        ca_key = default_values["ca_key"]
        ca_kwargs = default_values.get("x509_args_ca").copy()
        ca_kwargs["signing_private_key"] = ca_key

        # Issue the CA certificate (self-signed)
        ca_cert = x509.create_certificate(**ca_kwargs)

        not_before_str = "this is an intentionally wrong format"

        # Try to sign a new server certificate with the wrong date
        msg = (
            "not_before: this is an intentionally wrong format is not in required"
            " format %Y-%m-%d %H:%M:%S"
        )
        with self.assertRaisesRegex(salt.exceptions.SaltInvocationError, msg):
            ca_key = default_values["ca_key"]
            cert_kwargs = default_values["x509_args_cert"].copy()
            cert_kwargs["signing_private_key"] = ca_key
            cert_kwargs["signing_cert"] = ca_cert
            cert_kwargs["not_before"] = not_before_str
            x509.create_certificate(**cert_kwargs)

    @skipIf(not HAS_M2CRYPTO, "Skipping, M2Crypto is unavailable")
    def test_create_certificate_with_not_after_wrong_date(self):
        ca_key = default_values["ca_key"]
        ca_kwargs = default_values.get("x509_args_ca").copy()
        ca_kwargs["signing_private_key"] = ca_key

        # Issue the CA certificate (self-signed)
        ca_cert = x509.create_certificate(**ca_kwargs)

        not_after_str = "this is an intentionally wrong format"

        # Try to sign a new server certificate with the wrong date
        msg = (
            "not_after: this is an intentionally wrong format is not in required format"
            " %Y-%m-%d %H:%M:%S"
        )
        with self.assertRaisesRegex(salt.exceptions.SaltInvocationError, msg):
            ca_key = default_values["ca_key"]
            cert_kwargs = default_values["x509_args_cert"].copy()
            cert_kwargs["signing_private_key"] = ca_key
            cert_kwargs["signing_cert"] = ca_cert
            cert_kwargs["not_after"] = not_after_str
            x509.create_certificate(**cert_kwargs)

    @skipIf(not HAS_M2CRYPTO, "Skipping, M2Crypto is unavailable")
    def test_create_certificate_with_not_before_and_not_after(self):
        ca_key = default_values["ca_key"]
        ca_kwargs = default_values.get("x509_args_ca").copy()
        ca_kwargs["signing_private_key"] = ca_key

        # Issue the CA certificate (self-signed)
        ca_cert = x509.create_certificate(**ca_kwargs)

        fmt = "%Y-%m-%d %H:%M:%S"
        # Here we gonna use the current date as the not_before date
        # First we again take the UTC for verification
        not_before = datetime.datetime.utcnow()
        # And set the UTC timezone to the naive datetime resulting from parsing
        not_before = not_before.replace(tzinfo=M2Crypto.ASN1.UTC)
        not_before_str = datetime.datetime.strftime(not_before, fmt)
        # And we use the same logic to generate a not_after 5 days in the
        # future
        not_after = not_before + datetime.timedelta(days=5)
        # And set the UTC timezone to the naive datetime resulting from parsing
        not_after = not_after.replace(tzinfo=M2Crypto.ASN1.UTC)
        not_after_str = datetime.datetime.strftime(not_after, fmt)

        # Sign a new server certificate with the CA
        ca_key = default_values["ca_key"]
        cert_kwargs = default_values["x509_args_cert"].copy()
        cert_kwargs["signing_private_key"] = ca_key
        cert_kwargs["signing_cert"] = ca_cert
        cert_kwargs["not_after"] = not_after_str
        cert_kwargs["not_before"] = not_before_str
        server_cert = x509.create_certificate(**cert_kwargs)

        not_after_from_cert = ""
        not_before_from_cert = ""
        # Save server certificate to disk so we can check its properties
        with tempfile.NamedTemporaryFile("w+") as server_cert_file:
            server_cert_file.write(salt.utils.stringutils.to_str(server_cert))
            server_cert_file.flush()

            # Retrieve not_after property from server certificate
            server_cert_details = x509.read_certificate(server_cert_file.name)
            not_before_from_cert = server_cert_details["Not Before"]
            not_after_from_cert = server_cert_details["Not After"]

        # Check if property values are the ones we've added to the certificate.
        # The values will come as strings containing no timezone information in
        # them.
        self.assertIn(not_before_str, not_before_from_cert)
        self.assertIn(not_after_str, not_after_from_cert)

    @skipIf(not HAS_M2CRYPTO, "Skipping, M2Crypto is unavailable")
    def test_create_crl(self):
        ca_key = default_values["ca_key"]
        ca_kwargs = default_values.get("x509_args_ca").copy()
        ca_kwargs["signing_private_key"] = ca_key

        ca_cert = x509.create_certificate(**ca_kwargs)

        with tempfile.NamedTemporaryFile("w+", delete=False) as ca_key_file:
            ca_key_file.write(salt.utils.stringutils.to_str(ca_key))
            ca_key_file.flush()

        with tempfile.NamedTemporaryFile("w+", delete=False) as ca_cert_file:
            ca_cert_file.write(salt.utils.stringutils.to_str(ca_cert))
            ca_cert_file.flush()

        with tempfile.NamedTemporaryFile("w+", delete=False) as ca_crl_file:
            crl_kwargs = default_values.get("crl_args").copy()
            crl_kwargs["path"] = ca_crl_file.name
            crl_kwargs["signing_private_key"] = ca_key_file.name
            crl_kwargs["signing_cert"] = ca_cert_file.name
            x509.create_crl(**crl_kwargs)

        with salt.utils.files.fopen(ca_crl_file.name, "r") as crl_file:
            crl = crl_file.read()

        os.remove(ca_key_file.name)
        os.remove(ca_cert_file.name)
        os.remove(ca_crl_file.name)

        # Ensure that a CRL was actually created
        self.assertIn("BEGIN X509 CRL", crl)

    @skipIf(not HAS_M2CRYPTO, "Skipping, M2Crypto is unavailable")
    def test_revoke_certificate_with_crl(self):
        ca_key = default_values["ca_key"]
        ca_kwargs = default_values.get("x509_args_ca").copy()
        ca_kwargs["signing_private_key"] = ca_key

        # Issue the CA certificate (self-signed)
        ca_cert = x509.create_certificate(**ca_kwargs)

        # Sign a new server certificate with the CA
        ca_key = default_values["ca_key"]
        cert_kwargs = default_values["x509_args_cert"].copy()
        cert_kwargs["signing_private_key"] = ca_key
        cert_kwargs["signing_cert"] = ca_cert
        server_cert = x509.create_certificate(**cert_kwargs)

        # Save CA cert + key and server cert to disk as PEM files
        with tempfile.NamedTemporaryFile("w+", delete=False) as ca_key_file:
            ca_key_file.write(salt.utils.stringutils.to_str(ca_key))
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
            crl_kwargs = default_values.get("crl_args").copy()
            crl_kwargs["path"] = ca_crl_file.name
            crl_kwargs["signing_private_key"] = ca_key_file.name
            crl_kwargs["signing_cert"] = ca_cert_file.name
            # Add list of revoked certificates
            crl_kwargs["revoked"] = revoked
            x509.create_crl(**crl_kwargs)

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

    @skipIf(not HAS_M2CRYPTO, "Skipping, M2Crypto is unavailable")
    def test_read_certificate(self):
        """
        :return:
        """
        cet = dedent(
            """
                -----BEGIN CERTIFICATE-----
        MIICdDCCAd2gAwIBAgIUH6g+PC0bGKSY4LMq7PISP09M5B4wDQYJKoZIhvcNAQEL
        BQAwTDELMAkGA1UEBhMCVVMxEDAOBgNVBAgMB0FyaXpvbmExEzARBgNVBAcMClNj
        b3R0c2RhbGUxFjAUBgNVBAoMDVN1cGVyIFdpZGdpdHMwHhcNMjEwMzIzMDExNDE2
        WhcNMjIwMzIzMDExNDE2WjBMMQswCQYDVQQGEwJVUzEQMA4GA1UECAwHQXJpem9u
        YTETMBEGA1UEBwwKU2NvdHRzZGFsZTEWMBQGA1UECgwNU3VwZXIgV2lkZ2l0czCB
        nzANBgkqhkiG9w0BAQEFAAOBjQAwgYkCgYEAvtFFZP47UkzyAmVWtBnVHuXwe7iK
        yu19c3qx59KPVAMHkMKgCew4S2KBMDHySBVnspiEz1peP1ywozcP1tIeWHG6aY/7
        j2ewzl5bJ4HZPDBnEOYzGsC/NM8YY3qFlrteda/awvwoF99MkpVlrcLBMJzjt/c8
        HjuBb0zTlnm4r7ECAwEAAaNTMFEwHQYDVR0OBBYEFJwdb0PKsvu3dU0j3kx3uP4B
        NGpfMB8GA1UdIwQYMBaAFJwdb0PKsvu3dU0j3kx3uP4BNGpfMA8GA1UdEwEB/wQF
        MAMBAf8wDQYJKoZIhvcNAQELBQADgYEAZblVv70rSk6+7ti3mYxVo48VLf3hG5R/
        rMd434WYTeDOWlvl5GSklrBc4ToBW5GsJe/+JaFbUFo9YB+a0K0xjyNZ5CWWiaxg
        3lwqTx6vwK1ucS18B+nt2qqyq9hL0UvpSB7gH4KeCwCMDIfRMsrPi32jg1RyKftD
        B+O0S5LeuJw=
        -----END CERTIFICATE-----
        """
        )
        ret = x509.read_certificate(cet)
        assert "MD5 Finger Print" in ret


class X509FipsTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {x509: {"__opts__": {"fips_mode": True}}}

    @skipIf(not HAS_M2CRYPTO, "Skipping, M2Crypto is unavailable")
    def test_read_certificate(self):
        """
        :return:
        """
        cet = dedent(
            """
                -----BEGIN CERTIFICATE-----
        MIICdDCCAd2gAwIBAgIUH6g+PC0bGKSY4LMq7PISP09M5B4wDQYJKoZIhvcNAQEL
        BQAwTDELMAkGA1UEBhMCVVMxEDAOBgNVBAgMB0FyaXpvbmExEzARBgNVBAcMClNj
        b3R0c2RhbGUxFjAUBgNVBAoMDVN1cGVyIFdpZGdpdHMwHhcNMjEwMzIzMDExNDE2
        WhcNMjIwMzIzMDExNDE2WjBMMQswCQYDVQQGEwJVUzEQMA4GA1UECAwHQXJpem9u
        YTETMBEGA1UEBwwKU2NvdHRzZGFsZTEWMBQGA1UECgwNU3VwZXIgV2lkZ2l0czCB
        nzANBgkqhkiG9w0BAQEFAAOBjQAwgYkCgYEAvtFFZP47UkzyAmVWtBnVHuXwe7iK
        yu19c3qx59KPVAMHkMKgCew4S2KBMDHySBVnspiEz1peP1ywozcP1tIeWHG6aY/7
        j2ewzl5bJ4HZPDBnEOYzGsC/NM8YY3qFlrteda/awvwoF99MkpVlrcLBMJzjt/c8
        HjuBb0zTlnm4r7ECAwEAAaNTMFEwHQYDVR0OBBYEFJwdb0PKsvu3dU0j3kx3uP4B
        NGpfMB8GA1UdIwQYMBaAFJwdb0PKsvu3dU0j3kx3uP4BNGpfMA8GA1UdEwEB/wQF
        MAMBAf8wDQYJKoZIhvcNAQELBQADgYEAZblVv70rSk6+7ti3mYxVo48VLf3hG5R/
        rMd434WYTeDOWlvl5GSklrBc4ToBW5GsJe/+JaFbUFo9YB+a0K0xjyNZ5CWWiaxg
        3lwqTx6vwK1ucS18B+nt2qqyq9hL0UvpSB7gH4KeCwCMDIfRMsrPi32jg1RyKftD
        B+O0S5LeuJw=
        -----END CERTIFICATE-----
        """
        )
        ret = x509.read_certificate(cet)
        assert "MD5 Finger Print" not in ret
