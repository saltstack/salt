# -*- coding: utf-8 -*-
"""
Tests for the salt-run command
"""
# Import Python libs
from __future__ import absolute_import

import functools
import random
import string
import tempfile

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import NameOID
from salt.ext.six import text_type
from salt.ext.six.moves import range

# Import Salt Testing libs
from tests.support.case import ShellCase


def _random_name(prefix=""):
    ret = prefix
    for _ in range(8):
        ret += random.choice(string.ascii_lowercase)
    return ret


def with_random_name(func):
    """
    generate a randomized name for a container
    """

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        name = _random_name(prefix="salt_")
        return func(self, _random_name(prefix="salt-test-"), *args, **kwargs)

    return wrapper


class VenafiTest(ShellCase):
    """
    Test the venafi runner
    """

    @with_random_name
    def test_request(self, name):
        cn = "{0}.example.com".format(name)

        # Provide python27 compatibility
        if not isinstance(cn, text_type):
            cn = cn.decode()

        ret = self.run_run_plus(
            fun="venafi.request",
            minion_id=cn,
            dns_name=cn,
            key_password="secretPassword",
            zone="fake",
        )
        cert_output = ret["return"][0]
        assert cert_output is not None, "venafi_certificate not found in `output_value`"

        cert = x509.load_pem_x509_certificate(cert_output.encode(), default_backend())
        assert isinstance(cert, x509.Certificate)
        assert cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME) == [
            x509.NameAttribute(NameOID.COMMON_NAME, cn)
        ]

        pkey_output = ret["return"][1]
        assert pkey_output is not None, "venafi_private key not found in output_value"

        pkey = serialization.load_pem_private_key(
            pkey_output.encode(), password=b"secretPassword", backend=default_backend()
        )

        pkey_public_key_pem = pkey.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        cert_public_key_pem = cert.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        assert pkey_public_key_pem == cert_public_key_pem

    @with_random_name
    def test_sign(self, name):

        csr_pem = """-----BEGIN CERTIFICATE REQUEST-----
MIIFbDCCA1QCAQAwgbQxCzAJBgNVBAYTAlVTMQ0wCwYDVQQIDARVdGFoMRIwEAYD
VQQHDAlTYWx0IExha2UxFDASBgNVBAoMC1ZlbmFmaSBJbmMuMRQwEgYDVQQLDAtJ
bnRlZ3JhdGlvbjEnMCUGCSqGSIb3DQEJARYYZW1haWxAdmVuYWZpLmV4YW1wbGUu
Y29tMS0wKwYDVQQDDCR0ZXN0LWNzci0zMjMxMzEzMS52ZW5hZmkuZXhhbXBsZS5j
b20wggIiMA0GCSqGSIb3DQEBAQUAA4ICDwAwggIKAoICAQC4T0bdjq+mF+DABhF+
XWCwOXXUWbPNWa72VVhxoelbyTS0iIeZEe64AvNGykytFdOuT/F9pdkZa+Io07R1
ZMp6Ak8dp2Wjt4c5rayVZus6ZK+0ZwBRJO7if/cqhEpxy8Wz1RMfVLf2AE1u/xZS
QSYY0BTRWGmPqrFJrIGbnyQfvmGVPk3cA0RfdrwYJZXtZ2/4QNrbNCoSoSmqTHzt
NAtZhvT2dPU9U48Prx4b2460x+ck3xA1OdJNXV7n5u53QbxOIcjdGT0lJ62ml70G
5gvEHmdPcg+t5cw/Sm5cfDSUEDtNEXvD4oJXfP98ty6f1cYsZpcrgxRwk9RfGain
hvoweXhZP3NWnU5nRdn2nOfExv+xMeQOyB/rYv98zqzK6LvwKhwI5UB1l/n9KTpg
jgaNCP4x/KAsrPecbHK91oiqGSbPn4wtTYOmPkDxSzATN317u7fE20iqvVAUy/O+
7SCNNKEDPX2NP9LLz0IPK0roQxLiwd2CVyN6kEXuzs/3psptkNRMSlhyeAZdfrOE
CNOp46Pam9f9HGBqzXxxoIlfzLqHHL584kgFlBm7qmivVrgp6zdLPDa+UayXEl2N
O17SnGS8nkOTmfg3cez7lzX/LPLO9X/Y1xKYqx5hoGZhh754K8mzDWCVCYThWgou
yBOYY8uNXiX6ldqzQUHpbxxQgwIDAQABoHIwcAYJKoZIhvcNAQkOMWMwYTBfBgNV
HREEWDBWgilhbHQxLXRlc3QtY3NyLTMyMzEzMTMxLnZlbmFmaS5leGFtcGxlLmNv
bYIpYWx0Mi10ZXN0LWNzci0zMjMxMzEzMS52ZW5hZmkuZXhhbXBsZS5jb20wDQYJ
KoZIhvcNAQELBQADggIBAJd87BIdeh0WWoyQ4IX+ENpNqmm/sLmdfmUB/hj9NpBL
qbr2UTWaSr1jadoZ+mrDxtm1Z0YJDTTIrEWxkBOW5wQ039lYZNe2tfDXSJZwJn7u
2keaXtWQ2SdduK1wOPDO9Hra6WnH7aEq5D1AyoghvPsZwTqZkNynt/A1BZW5C/ha
J9/mwgWfL4qXBGBOhLwKN5GUo3erUkJIdH0TlMqI906D/c/YAuJ86SRdQtBYci6X
bJ7C+OnoiV6USn1HtQE6dfOMeS8voJuixpSIvHZ/Aim6kSAN1Za1f6FQAkyqbF+o
oKTJHDS1CPWikCeLdpPUcOCDIbsiISTsMZkEvIkzZ7dKBIlIugauxw3vaEpk47jN
Wq09r639RbSv/Qs8D6uY66m1IpL4zHm4lTAknrjM/BqihPxc8YiN76ssajvQ4SFT
DHPrDweEVe4KL1ENw8nv4wdkIFKwJTDarV5ZygbETzIhfa2JSBZFTdN+Wmd2Mh5h
OTu+vuHrJF2TO8g1G48EB/KWGt+yvVUpWAanRMwldnFX80NcUlM7GzNn6IXTeE+j
BttIbvAAVJPG8rVCP8u3DdOf+vgm5macj9oLoVP8RBYo/z0E3e+H50nXv3uS6JhN
xlAKgaU6i03jOm5+sww5L2YVMi1eeBN+kx7o94ogpRemC/EUidvl1PUJ6+e7an9V
-----END CERTIFICATE REQUEST-----
        """

        with tempfile.NamedTemporaryFile("w+") as f:
            f.write(csr_pem)
            f.flush()
            csr_path = f.name
            cn = "test-csr-32313131.venafi.example.com"

            # Provide python27 compatibility
            if not isinstance(cn, text_type):
                cn = cn.decode()

            ret = self.run_run_plus(
                fun="venafi.request", minion_id=cn, csr_path=csr_path, zone="fake"
            )
            cert_output = ret["return"][0]
            assert (
                cert_output is not None
            ), "venafi_certificate not found in `output_value`"

            cert = x509.load_pem_x509_certificate(
                cert_output.encode(), default_backend()
            )
            assert isinstance(cert, x509.Certificate)
            assert cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME) == [
                x509.NameAttribute(NameOID.COMMON_NAME, cn)
            ]
