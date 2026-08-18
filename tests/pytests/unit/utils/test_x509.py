import base64
import ipaddress
from datetime import datetime, timedelta, timezone

import pytest

import salt.exceptions
import salt.utils.x509 as x509
from tests.support.mock import ANY, Mock, patch

cryptography = pytest.importorskip(
    "cryptography", reason="Needs cryptography library", minversion="37.0"
)
cx509 = pytest.importorskip("cryptography.x509", reason="Needs cryptography library")
asn1 = pytest.importorskip(
    "cryptography.hazmat.asn1", reason="Needs cryptography library"
)
cprim = pytest.importorskip(
    "cryptography.hazmat.primitives", reason="Needs cryptography library"
)
rsa = pytest.importorskip(
    "cryptography.hazmat.primitives.asymmetric.rsa", reason="Needs cryptography library"
)


@pytest.fixture
def single_pem():
    return """\
-----BEGIN RSA PRIVATE KEY-----
MIIEogIBAAKCAQEAu4FN2FAbh06p0SalHsN0uyvEK/pmxoJqgnPll+NIyUtyEKms
GXuRzZ6hF++a74dkk6/YbmyGAHECuS1WPm1iqaO7KASFEB3daeLg9r3jlFP4cxZI
n3UnEZF+GDYHdox00JyW0CLp6VUouXxc1gogkVGmeyi52b4LsOlGXdO8/8Nbcjhu
V9GZvdvvp6CwTLZabPni6nL/WWl5EwRqYnVTcX323tsObRliGsP6FYy1lQQLiy0A
PNIU+sxdQFeIdsR5FZ2JyquyKGD4REGrNGp2VuxzPrOmzr46AKTHRdDUaCedzUDO
wwK/sE4+b2DKEvyhYI1O5K5rERAFG4voZGwVTQIDAQABAoIBAGdu1LpWtljVk+fE
IaHuwB3f7r8zyi4HEyoTNLusrSIddDas4jrMZ4m9z6+chSNM1LaDcii3xNPJg28T
C1g0jxB1OXDBzYUudE1M0jxKU5gnGg6iZD1SKtMOJzjD1SoYIPhS6P63w8DrMSPg
7nVD8OM431VhCeSLaXeVtzNa8g9DirSHQD8zHHb3H7jnPJ4SeFKYv8URl3lsN84A
frP64nO64OGYgmIPU5IgVpKmK0rjXll4zNRxx5UwO2BglJ2lR6EIZ6oBA8ooCrPd
qOKrfiVTHoV9sKVwUtBvP3mqC1WZ6CWmX9EdnrSG0jgUZezezonHfcg8eBtoOPpR
0shrbwECgYEA6Ey8OGK3N3LNYewMuvv9gl66+TSbQY8Dh5iASHppvYFh6rWpdqo6
tRJORHbPn01fb2p48Pne8XBqDZNkG5u0gfX+v0yq2W5U0ezd0plP/uirLTuUm5if
hP525ShnHW6DYGsc26brCwRDINx4jYDqEiCq+1DcgoTavWBsUq+59aUCgYEAzqKc
TB5R/O6iwjCuJeIXddiIxHNFCwoaXSdorkCw2A7VJWUeh8SOpYuE//rfxW7pJbIS
kDc7rbdr/oyE7EYA6nIonWHJdXQ6V23SHARFWDX+LEn10OWOpSQnigSlcd1zFXLO
UDBVronmstqFriTugZfDAJZo7x6zsPfU/2X3IIkCgYBPaYweqoB/0BsuEof3lBWB
7+hzMOyyaLWIMTYJkO98/TIADsIz8tXG+M8Q0J0BlG2/pOJbXtA8MXXP1kcuuPfo
RbQkqYzub61HZnYefJLATcHW4LtYxcAisurqQ/mcMh9vYq6m2FUZmwdnwHblyOA7
+jb5WxdG9yvf+YqOacxkkQKBgE6AlKSOeFOBTbA80kxuIr+QrhUEPdy9z9pIGIrq
5MSQjgWQ7xJhaFgYM0UUyGK3ijfZ+Rd1BGUw5ARm2jDxP3PSPv/boK/QokGI5WPj
c3zZtmCZEJx2OcUfgS38KeaiXRBu91abplGS7mRQhKzuNvZg86KLgf4mSdoXrYIB
+OsRAoGANP4NjqBAEzsIFszGvaXmslyzfdWY6XI5N1GgzbEW/K7UECiPxWxmWcCm
n7mpiv/r8zkskgfAua84Fe8qIr2f6UjNeIzJ7LwI0zSB2uuiS4oP3xqCEyb+J3F4
bQdPnxzSwrf6edD2AmIT9L8IwiCYiplC+JvqSlqDP2pxIQbilmw=
-----END RSA PRIVATE KEY-----
    """


@pytest.fixture
def multi_pem():
    return """\
-----BEGIN CERTIFICATE-----
MIIDKDCCAhCgAwIBAgIIEmd4S33OHDEwDQYJKoZIhvcNAQELBQAwKzELMAkGA1UE
BhMCVVMxDTALBgNVBAMMBFRlc3QxDTALBgNVBAoMBFNhbHQwHhcNMjIxMTE1MTQw
OTQ0WhcNMzIxMTEyMTQwOTQ0WjAuMQswCQYDVQQGEwJVUzEQMA4GA1UEAwwHVGVz
dENydDENMAsGA1UECgwEU2FsdDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoC
ggEBAOGTScvrjcEt6vsJcG9RUp6fKaDNDWZnJET0omanK9ZwaoGpJPp8UDYe/8AD
eI7N10wdyB4oDM9gRDjInBtdQO/PsrmKZF6LzqVFgLMxu2up+PHMi9z6B2P4esIA
zMu9PYxc9zH4HzLImHqscVD2HCabsjp9X134Af7hVY5NN/W/4qTP7uOM20wSG2TP
I6+BtA9VyPbEPMPRzXzrqc45rVYe6kb2bT84GE93Vcu/e5JZ/k2AKD8Hoa2cxLPs
TLq5igl+D+k+dfUtiABiKPvVQiYBsD1fyHDn2m7B6pCgvrGqHjsoAKufgFnXy6PJ
Rg7nvQfaxSiusM5s+VS+fjlvgwsCAwEAAaNNMEswCQYDVR0TBAIwADAdBgNVHQ4E
FgQUXPLx9FMpI57uQFqSo7QqLvWmi2cwHwYDVR0jBBgwFoAUXPLx9FMpI57uQFqS
o7QqLvWmi2cwDQYJKoZIhvcNAQELBQADggEBAFkYke/32PEmCDcs8YFDp5PDVwhv
8ZlfCtgRChaPcwoc+QpBeNhUEMhQ/v77Ojj6VNXzNDP7X1MCc7432Xo3VHCiCI8c
CMVNiyDWJNlEEll3eUIguNWRnkIfsCeHVs5/76M9tgwcrPOltQliI4UJ7Wy5pnXA
ywQFn43TqzNdU7HRIdX7QRUHeMOpe7Y4o7vjSOseQJcL2pQadho/BqK5rWuwZ8x/
Jsl40YjjXyLOnOCUYYpC13KC8iHOZKHVvA8eDtiuuLSgIk9DBD/ClU4cMCF2mvuQ
dtV9rM6byvPUJaIxKznODAUbZPGuFI/FWP9VheO17s7mDs/B12/UKXcTkvs=
-----END CERTIFICATE-----

-----BEGIN CERTIFICATE-----
MIIDODCCAiCgAwIBAgIIbfpgqP0VGPgwDQYJKoZIhvcNAQELBQAwKzELMAkGA1UE
BhMCVVMxDTALBgNVBAMMBFRlc3QxDTALBgNVBAoMBFNhbHQwHhcNMjIxMTE1MTQw
NDMzWhcNMzIxMTEyMTQwNDMzWjArMQswCQYDVQQGEwJVUzENMAsGA1UEAwwEVGVz
dDENMAsGA1UECgwEU2FsdDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEB
AOGTScvrjcEt6vsJcG9RUp6fKaDNDWZnJET0omanK9ZwaoGpJPp8UDYe/8ADeI7N
10wdyB4oDM9gRDjInBtdQO/PsrmKZF6LzqVFgLMxu2up+PHMi9z6B2P4esIAzMu9
PYxc9zH4HzLImHqscVD2HCabsjp9X134Af7hVY5NN/W/4qTP7uOM20wSG2TPI6+B
tA9VyPbEPMPRzXzrqc45rVYe6kb2bT84GE93Vcu/e5JZ/k2AKD8Hoa2cxLPsTLq5
igl+D+k+dfUtiABiKPvVQiYBsD1fyHDn2m7B6pCgvrGqHjsoAKufgFnXy6PJRg7n
vQfaxSiusM5s+VS+fjlvgwsCAwEAAaNgMF4wDwYDVR0TBAgwBgEB/wIBATALBgNV
HQ8EBAMCAQYwHQYDVR0OBBYEFFzy8fRTKSOe7kBakqO0Ki71potnMB8GA1UdIwQY
MBaAFFzy8fRTKSOe7kBakqO0Ki71potnMA0GCSqGSIb3DQEBCwUAA4IBAQBZS4MP
fXYPoGZ66seM+0eikScZHirbRe8vHxHkujnTBUjQITKm86WeQgeBCD2pobgBGZtt
5YFozM4cERqY7/1BdemUxFvPmMFFznt0TM5w+DfGWVK8un6SYwHnmBbnkWgX4Srm
GsL0HHWxVXkGnFGFk6Sbo3vnN7CpkpQTWFqeQQ5rHOw91pt7KnNZwc6I3ZjrCUHJ
+UmKKrga16a4Q+8FBpYdphQU609npo/0zuaE6FyiJYlW3tG+mlbbNgzY/+eUaxt2
9Bp9mtA+Hkox551Mfpq45Oi+ehwMt0xjZCjuFCM78oiUdHCGO+EmcT7ogiYALiOF
LN1w5sybsYwIw6QN
-----END CERTIFICATE-----
    """


def test_split_pems_single(single_pem):
    res = x509.split_pems(single_pem)
    assert len(res) == 1
    assert res[0].startswith(b"-----BEGIN RSA PRIVATE KEY-----\n")
    assert res[0].endswith(b"-----END RSA PRIVATE KEY-----\n")
    assert len(res[0].splitlines()) == 27


def test_split_pems_multi(multi_pem):
    res = x509.split_pems(multi_pem)
    assert len(res) == 2
    for x in res:
        assert x.startswith(b"-----BEGIN CERTIFICATE-----\n")
        assert x.endswith(b"-----END CERTIFICATE-----\n")
    assert len(res[0].splitlines()) == 19
    assert len(res[1].splitlines()) == 20


def test_split_pems_garbage_between(single_pem):
    garbage_pem = (
        single_pem
        + "\nI like turtles\nIntroduce a little anarchy. Upset the established order, and everything becomes chaos. I'm an agent of chaos.\n"
        + single_pem
    )
    res = x509.split_pems(garbage_pem)
    assert len(res) == 2
    for x in res:
        assert x.startswith(b"-----BEGIN RSA PRIVATE KEY-----\n")
        assert x.endswith(b"-----END RSA PRIVATE KEY-----\n")
        assert len(x.splitlines()) == 27


@pytest.fixture
def pubkey():
    return """\
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAumZ4+aD8Ez8ZTM2bg1K+
qN33oigksrzju9VsUS8cz1Hh1g43z9YAfOuLUw8ivGj3c3QNagJT0gonfEwhtvOk
7R89RsQ248qCPY3ItMK73nmWZC27YIarytJrMj/6yZ5QlPrequTNSxDnva/5qhUn
czf96zWG5vb9ow6fqbFQ3KsF0JpyLdCTDvXPH7Ghj0hIVOSxeItPLHjhf1Mpqeqr
n1WExZZvPDvdcMl8ufDwil86eXmKRgb5xfVnnSBdJUyglJr6IOHbtaGbkEM4RRJa
qrvPr5acj4aSWob8VBxqn5cnJ+vs331uQv5oUzQHyLvYaGPeUy0TT62QKhjkG6y1
4wIDAQAB
-----END PUBLIC KEY-----
"""


@pytest.mark.parametrize("get_encoding", (False, True))
def test_load_pubkey(pubkey, get_encoding):
    if get_encoding:
        pk, encoding = x509.load_pubkey(pubkey, get_encoding=True)
        assert encoding == "pem"
    else:
        pk = x509.load_pubkey(pubkey)
    assert isinstance(pk, rsa.RSAPublicKey)
    assert x509.to_pem(pk).decode().strip() == pubkey.strip()


class TestCreateExtension:
    @pytest.fixture
    def aki(self):
        with patch("cryptography.x509.AuthorityKeyIdentifier", autospec=True) as ext:
            yield ext

    @pytest.fixture
    def ca_crt(self):
        ca = Mock(spec=cx509.Certificate)
        return ca

    @pytest.mark.parametrize(
        "val,expected,critical,self_signed",
        [
            ("critical,CA:FALSE", (False, None), True, False),
            ("critical, CA:TRUE, pathlen:2", (True, 2), True, True),
            ("CA:TRUE", (True, None), False, True),
            ({"ca": False, "critical": True}, (False, None), True, False),
            ({"ca": True, "pathlen": 3}, (True, 3), False, True),
            (
                {"ca": True},
                (True, 0),
                False,
                False,
            ),  # default to one less than the issuer, which has 1
            ({"ca": True, "pathlen": 0}, (True, 0), False, False),
        ],
    )
    def test_create_basic_constraints(
        self, val, expected, critical, self_signed, ca_cert
    ):
        issuer_cert = x509.load_cert(ca_cert)
        exp = cx509.BasicConstraints(*expected)
        ext, crit = x509._create_extension(
            "basicConstraints",
            val,
            ca_crt=issuer_cert if not self_signed else None,
        )
        assert crit == critical
        assert ext == exp

    def test_create_basic_constraints_validates_pathlen(self, ca_cert):
        with pytest.raises(
            salt.exceptions.CommandExecutionError,
            match="less than or equal to requested pathlen",
        ):
            x509._create_extension(
                "basicConstraints",
                {"ca": True, "pathlen": 1, "critical": True},
                ca_crt=x509.load_cert(ca_cert),
            )

    @pytest.mark.parametrize(
        "val,expected,critical",
        [
            (
                "digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment, keyAgreement, keyCertSign, cRLSign, encipherOnly, decipherOnly",
                {
                    "digital_signature": True,
                    "content_commitment": True,
                    "key_encipherment": True,
                    "data_encipherment": True,
                    "key_agreement": True,
                    "key_cert_sign": True,
                    "crl_sign": True,
                    "encipher_only": True,
                    "decipher_only": True,
                },
                False,
            ),
            (
                "critical, keyCertSign, cRLSign",
                {
                    "digital_signature": False,
                    "content_commitment": False,
                    "key_encipherment": False,
                    "data_encipherment": False,
                    "key_agreement": False,
                    "key_cert_sign": True,
                    "crl_sign": True,
                    "encipher_only": False,
                    "decipher_only": False,
                },
                True,
            ),
            (
                ["critical", "digitalSignature"],
                {
                    "digital_signature": True,
                    "content_commitment": False,
                    "key_encipherment": False,
                    "data_encipherment": False,
                    "key_agreement": False,
                    "key_cert_sign": False,
                    "crl_sign": False,
                    "encipher_only": False,
                    "decipher_only": False,
                },
                True,
            ),
            (
                ["nonRepudiation"],
                {
                    "digital_signature": False,
                    "content_commitment": True,
                    "key_encipherment": False,
                    "data_encipherment": False,
                    "key_agreement": False,
                    "key_cert_sign": False,
                    "crl_sign": False,
                    "encipher_only": False,
                    "decipher_only": False,
                },
                False,
            ),
        ],
    )
    def test_create_key_usage(self, val, expected, critical):
        with patch("cryptography.x509.KeyUsage", autospec=True) as ext:
            _, crit = x509._create_extension("keyUsage", val)
            assert crit == critical
            ext.assert_called_once_with(**expected)

    @pytest.mark.parametrize(
        "val,expected,critical",
        [
            (
                "critical,serverAuth,clientAuth,codeSigning,emailProtection,timeStamping,OCSPSigning,msSmartcardLogin,pkInitKDC,ipsecIKE,msCodeInd,msCodeCom,msCTLSign,msEFS",
                list(x509.EXTENDED_KEY_USAGE_OID.values()),
                True,
            ),
            ("serverAuth", [x509.EXTENDED_KEY_USAGE_OID["serverAuth"]], False),
            (
                "timeStamping,1.2.3.4",
                [
                    x509.EXTENDED_KEY_USAGE_OID["timeStamping"],
                    cx509.ObjectIdentifier("1.2.3.4"),
                ],
                False,
            ),
            (
                ["critical", "OCSPSigning", "msCodeCom", "2.3.4.55"],
                [
                    x509.EXTENDED_KEY_USAGE_OID["OCSPSigning"],
                    x509.EXTENDED_KEY_USAGE_OID["msCodeCom"],
                    cx509.ObjectIdentifier("2.3.4.55"),
                ],
                True,
            ),
            (["clientAuth"], [x509.EXTENDED_KEY_USAGE_OID["clientAuth"]], False),
        ],
    )
    def test_create_extended_key_usage(self, val, expected, critical):
        with patch("cryptography.x509.ExtendedKeyUsage", autospec=True) as ext:
            _, crit = x509._create_extension("extendedKeyUsage", val)
            assert crit == critical
            ext.assert_called_once_with(expected)

    @pytest.mark.parametrize(
        "val,expected",
        [
            ("hash", None),
            (
                "BB:AF:7E:02:3D:FA:A6:F1:3C:84:8E:AD:EE:38:98:EC:D9:32:32:D4",
                b"\xbb\xaf~\x02=\xfa\xa6\xf1<\x84\x8e\xad\xee8\x98\xec\xd922\xd4",
            ),
            (
                "bbaf7e023dfaa6f13c848eadee3898ecd93232d4",
                b"\xbb\xaf~\x02=\xfa\xa6\xf1<\x84\x8e\xad\xee8\x98\xec\xd922\xd4",
            ),
        ],
    )
    def test_create_subject_key_identifier(self, val, expected):
        with patch("cryptography.x509.SubjectKeyIdentifier", autospec=True) as ext:
            _, crit = x509._create_extension(
                "subjectKeyIdentifier", val, subject_pubkey="testpub"
            )
            assert crit is False
            if val == "hash":
                ext.from_public_key.assert_called_once_with("testpub")
            else:
                ext.from_public_key.assert_not_called()
                ext.assert_called_once_with(expected)

    def test_create_authority_key_identifier_from_ski(self, aki, ca_crt):
        ca_crt.extensions.get_extension_for_class.return_value.value.digest = (
            b"\xde\xad\xbe\xef"
        )
        _, crit = x509._create_extension(
            "authorityKeyIdentifier", "keyid:always", ca_crt=ca_crt
        )
        assert crit is False
        aki.assert_called_once_with(
            key_identifier=b"\xde\xad\xbe\xef",
            authority_cert_issuer=None,
            authority_cert_serial_number=None,
        )

    def test_create_authority_key_identifier_from_pubkey(self, aki, ca_crt):
        def raise_notfound(*args, **kwargs):
            raise cx509.ExtensionNotFound("f", cx509.ObjectIdentifier("1.2.3.4"))

        ca_crt.extensions.get_extension_for_class.side_effect = raise_notfound
        aki.from_issuer_public_key.return_value.key_identifier = b"\xde\xad\xbe\xef"
        _, crit = x509._create_extension(
            "authorityKeyIdentifier", "keyid:always", ca_crt=ca_crt
        )
        assert crit is False
        aki.assert_called_once_with(
            key_identifier=b"\xde\xad\xbe\xef",
            authority_cert_issuer=None,
            authority_cert_serial_number=None,
        )

    def test_create_authority_key_identifier_from_ca_pub(self, aki):
        aki.from_issuer_public_key.return_value.key_identifier = b"\xde\xad\xbe\xef"
        _, crit = x509._create_extension(
            "authorityKeyIdentifier", "keyid:always", ca_pub="testpub"
        )
        assert crit is False
        aki.assert_called_once_with(
            key_identifier=b"\xde\xad\xbe\xef",
            authority_cert_issuer=None,
            authority_cert_serial_number=None,
        )

    @pytest.mark.parametrize(
        "ca_crt,ca_pub",
        [
            (Mock(), None),
            (None, Mock()),
            (Mock(), Mock()),
        ],
    )
    def test_create_authority_key_identifier_always(self, aki, ca_crt, ca_pub):
        aki.from_issuer_public_key.side_effect = RuntimeError
        if ca_crt is not None:
            ca_crt.extensions.get_extension_for_class.side_effect = RuntimeError
        elif ca_pub is not None:
            ca_pub.side_effect = RuntimeError
        with pytest.raises(salt.exceptions.CommandExecutionError):
            x509._create_extension(
                "authorityKeyIdentifier", "keyid:always", ca_crt=ca_crt, ca_pub=ca_pub
            )

    def test_create_authority_key_identifier_issuer(self, aki, ca_crt):
        ca_crt.issuer = "testissuer"
        ca_crt.serial_number = 1337
        with patch("cryptography.x509.DirectoryName") as dirname:
            _, crit = x509._create_extension(
                "authorityKeyIdentifier", "issuer", ca_crt=ca_crt
            )
            assert crit is False
            dirname.assert_called_once_with(ca_crt.issuer)
            aki.assert_called_once_with(
                key_identifier=None,
                authority_cert_issuer=ANY,
                authority_cert_serial_number=1337,
            )

    def test_create_authority_key_identifier_issuer_always(self, aki, ca_crt):
        with patch("cryptography.x509.DirectoryName") as dirname:
            dirname.side_effect = ValueError
            with pytest.raises(salt.exceptions.CommandExecutionError):
                x509._create_extension(
                    "authorityKeyIdentifier", "issuer:always", ca_crt=ca_crt
                )

    def test_create_authority_key_identifier_from_both(self, aki, ca_crt):
        ca_crt.issuer = "testissuer"
        ca_crt.serial_number = 1337
        ca_crt.extensions.get_extension_for_class.return_value.value.digest = (
            b"\xde\xad\xbe\xef"
        )
        with patch("cryptography.x509.DirectoryName"):
            _, crit = x509._create_extension(
                "authorityKeyIdentifier", "keyid:always,issuer:always", ca_crt=ca_crt
            )
            assert crit is False
            aki.assert_called_once_with(
                key_identifier=b"\xde\xad\xbe\xef",
                authority_cert_issuer=ANY,
                authority_cert_serial_number=1337,
            )

    def test_create_authority_key_identifier_from_both_issuer_fail(self, aki, ca_crt):
        ca_crt.issuer = "testissuer"
        ca_crt.serial_number = 1337
        ca_crt.extensions.get_extension_for_class.return_value.value.digest = (
            b"\xde\xad\xbe\xef"
        )
        with patch("cryptography.x509.DirectoryName") as dirname:
            dirname.side_effect = ValueError
            _, crit = x509._create_extension(
                "authorityKeyIdentifier", "keyid:always,issuer", ca_crt=ca_crt
            )
            assert crit is False
            aki.assert_called_once_with(
                key_identifier=b"\xde\xad\xbe\xef",
                authority_cert_issuer=None,
                authority_cert_serial_number=None,
            )

    @pytest.mark.parametrize(
        "val,ca_sub,expected,critical",
        [
            (
                ["email:ca@example.com", "dns:example.com"],
                None,
                [
                    cx509.RFC822Name("ca@example.com"),
                    cx509.DNSName("example.com"),
                ],
                False,
            ),
            (
                ["issuer:copy"],
                [
                    cx509.RFC822Name("me@example.com"),
                    cx509.DNSName("example.com"),
                ],
                [
                    cx509.RFC822Name("me@example.com"),
                    cx509.DNSName("example.com"),
                ],
                False,
            ),
            (
                ["critical", "issuer:copy", "dns:example.io"],
                [
                    cx509.RFC822Name("ca@example.com"),
                    cx509.DNSName("example.com"),
                ],
                [
                    cx509.RFC822Name("ca@example.com"),
                    cx509.DNSName("example.com"),
                    cx509.DNSName("example.io"),
                ],
                True,
            ),
            (
                "critical,issuer:copy,dns:example.io",
                [
                    cx509.RFC822Name("ca@example.com"),
                    cx509.DNSName("example.com"),
                ],
                [
                    cx509.RFC822Name("ca@example.com"),
                    cx509.DNSName("example.com"),
                    cx509.DNSName("example.io"),
                ],
                True,
            ),
            (
                "DNS:salt.ca",
                None,
                [
                    cx509.DNSName("salt.ca"),
                ],
                False,
            ),
        ],
    )
    @pytest.mark.parametrize(
        "tgt,extname",
        [
            ("IssuerAlternativeName", "issuerAltName"),
            ("CertificateIssuer", "certificateIssuer"),
        ],
    )
    def test_create_issuer_alt_name(
        self, val, ca_sub, expected, critical, ca_crt, tgt, extname
    ):
        ca_crt.extensions.get_extension_for_class.return_value._general_names._general_names = (
            ca_sub
        )
        with patch(f"cryptography.x509.{tgt}", autospec=True) as ext:
            res, crit = x509._create_extension(extname, val, ca_crt=ca_crt)
            assert crit == critical
            ext.assert_called_once_with(expected)

    @pytest.mark.parametrize(
        "val,expected",
        [
            (
                "OCSP;URI:http://ocsp.example.com/,caIssuers;URI:http://myca.example.com/ca.cer",
                [
                    cx509.AccessDescription(
                        access_method=x509.ACCESS_OID["OCSP"],
                        access_location=cx509.UniformResourceIdentifier(
                            "http://ocsp.example.com/"
                        ),
                    ),
                    cx509.AccessDescription(
                        access_method=x509.ACCESS_OID["caIssuers"],
                        access_location=cx509.UniformResourceIdentifier(
                            "http://myca.example.com/ca.cer"
                        ),
                    ),
                ],
            ),
            (
                {
                    "OCSP": "URI:http://ocsp.example.com/",
                },
                [
                    cx509.AccessDescription(
                        access_method=x509.ACCESS_OID["OCSP"],
                        access_location=cx509.UniformResourceIdentifier(
                            "http://ocsp.example.com/"
                        ),
                    ),
                ],
            ),
            (
                [
                    "critical",
                    {"OCSP": "URI:http://ocsp.example.com/"},
                    {"OCSP": "URI:http://ocsp2.example.com/"},
                ],
                [
                    cx509.AccessDescription(
                        access_method=x509.ACCESS_OID["OCSP"],
                        access_location=cx509.UniformResourceIdentifier(
                            "http://ocsp.example.com/"
                        ),
                    ),
                    cx509.AccessDescription(
                        access_method=x509.ACCESS_OID["OCSP"],
                        access_location=cx509.UniformResourceIdentifier(
                            "http://ocsp2.example.com/"
                        ),
                    ),
                ],
            ),
        ],
    )
    def test_create_authority_info_access(self, val, expected):
        with patch(
            "cryptography.x509.AuthorityInformationAccess", autospec=True
        ) as ext:
            res, crit = x509._create_extension("authorityInfoAccess", val)
            assert crit is False
            ext.assert_called_once_with(expected)

    @pytest.mark.parametrize(
        "val,expected,critical",
        [
            (
                ["email:user@example.com", "dns:example.com"],
                [
                    cx509.RFC822Name("user@example.com"),
                    cx509.DNSName("example.com"),
                ],
                False,
            ),
            (
                ["critical", "dns:*.example.io"],
                [cx509.DNSName("*.example.io")],
                True,
            ),
            (
                [{"ip": "1.2.3.4"}],
                [cx509.IPAddress(ipaddress.ip_address("1.2.3.4"))],
                False,
            ),
            (
                "critical,dns:example.io,email:hello@example.io",
                [
                    cx509.DNSName("example.io"),
                    cx509.RFC822Name("hello@example.io"),
                ],
                True,
            ),
            (
                "ip:2001:db8::1,uri:https://foo.bar.baz,uri:proto://*.foo.bar",
                [
                    cx509.IPAddress(ipaddress.ip_address("2001:db8::1")),
                    cx509.UniformResourceIdentifier("https://foo.bar.baz"),
                    cx509.UniformResourceIdentifier("proto://*.foo.bar"),
                ],
                False,
            ),
            (
                [
                    "email:user@überexample.com",
                    "dns:überexample.com",
                    "dns:*.überexample.com",
                    "uri:https://überexample.com",
                    "uri:proto://*.überexample.com",
                    "otherName:1.3.6.1.5.5.7.8.9;FORMAT:UTF8,UTF8String:föö@nönasciinäme.example.com",
                ],
                [
                    cx509.RFC822Name("user@xn--berexample-8db.com"),
                    cx509.DNSName("xn--berexample-8db.com"),
                    cx509.DNSName("*.xn--berexample-8db.com"),
                    cx509.UniformResourceIdentifier("https://xn--berexample-8db.com"),
                    cx509.UniformResourceIdentifier("proto://*.xn--berexample-8db.com"),
                    cx509.OtherName(
                        cx509.ObjectIdentifier("1.3.6.1.5.5.7.8.9"),
                        asn1.encode_der("föö@nönasciinäme.example.com"),
                    ),
                ],
                False,
            ),
        ],
    )
    def test_create_subject_alt_name(self, val, expected, critical):
        with patch("cryptography.x509.SubjectAlternativeName", autospec=True) as ext:
            res, crit = x509._create_extension("subjectAltName", val)
            assert crit == critical
            ext.assert_called_once_with(expected)

    @pytest.mark.parametrize(
        "val,expected,critical",
        [
            (
                "URI:http://example.com/myca.crl, URI:http://example.org/my.crl",
                [
                    cx509.DistributionPoint(
                        full_name=[
                            cx509.UniformResourceIdentifier(
                                "http://example.com/myca.crl"
                            )
                        ],
                        relative_name=None,
                        reasons=None,
                        crl_issuer=None,
                    ),
                    cx509.DistributionPoint(
                        full_name=[
                            cx509.UniformResourceIdentifier("http://example.org/my.crl")
                        ],
                        relative_name=None,
                        reasons=None,
                        crl_issuer=None,
                    ),
                ],
                False,
            ),
            (
                "critical,URI:http://example.com/myca.crl",
                [
                    cx509.DistributionPoint(
                        full_name=[
                            cx509.UniformResourceIdentifier(
                                "http://example.com/myca.crl"
                            )
                        ],
                        relative_name=None,
                        reasons=None,
                        crl_issuer=None,
                    )
                ],
                True,
            ),
            (
                [
                    {
                        "fullname": [
                            "URI:http://example.com/myca.crl",
                            "URI:http://example.org/my.crl",
                        ]
                    }
                ],
                [
                    cx509.DistributionPoint(
                        full_name=[
                            cx509.UniformResourceIdentifier(
                                "http://example.com/myca.crl"
                            ),
                            cx509.UniformResourceIdentifier(
                                "http://example.org/my.crl"
                            ),
                        ],
                        relative_name=None,
                        reasons=None,
                        crl_issuer=None,
                    )
                ],
                False,
            ),
            (
                [
                    {
                        "fullname": "URI:http://example.com/myca.crl",
                        "crlissuer": "DNS:example.org",
                        "reasons": ["keyCompromise"],
                    }
                ],
                [
                    cx509.DistributionPoint(
                        full_name=[
                            cx509.UniformResourceIdentifier(
                                "http://example.com/myca.crl"
                            )
                        ],
                        relative_name=None,
                        reasons=frozenset([cx509.ReasonFlags("keyCompromise")]),
                        crl_issuer=[cx509.DNSName("example.org")],
                    )
                ],
                False,
            ),
            pytest.param(
                [
                    "critical",
                    {
                        "relativename": "OU=foo+CN=Smith",
                        "crlissuer": ["DNS:example.org"],
                    },
                ],
                [
                    cx509.DistributionPoint(
                        full_name=None,
                        relative_name=cx509.RelativeDistinguishedName(
                            [
                                cx509.NameAttribute(
                                    cx509.ObjectIdentifier("2.5.4.11"), value="foo"
                                ),
                                cx509.NameAttribute(
                                    cx509.ObjectIdentifier("2.5.4.3"), value="Smith"
                                ),
                            ]
                        ),
                        reasons=None,
                        crl_issuer=[cx509.DNSName("example.org")],
                    )
                ],
                True,
            ),
        ],
    )
    @pytest.mark.parametrize(
        "tgt,extname",
        [
            ("CRLDistributionPoints", "crlDistributionPoints"),
            ("FreshestCRL", "freshestCRL"),
        ],
    )
    def test_create_crl_distribution_points_freshest_crl(
        self, val, expected, critical, tgt, extname
    ):
        with patch(f"cryptography.x509.{tgt}", autospec=True) as ext:
            res, crit = x509._create_extension(extname, val)
            if tgt == "FreshestCRL":
                assert crit is False
            else:
                assert crit == critical
            ext.assert_called_once_with(expected)

    @pytest.mark.parametrize(
        "val,expected,critical",
        [
            (
                {
                    "critical": True,
                    "fullname": [
                        "URI:http://example.com/myca.crl",
                        "URI:http://example.org/my.crl",
                    ],
                },
                {
                    "full_name": [
                        cx509.UniformResourceIdentifier("http://example.com/myca.crl"),
                        cx509.UniformResourceIdentifier("http://example.org/my.crl"),
                    ],
                    "relative_name": None,
                    "only_some_reasons": None,
                    "only_contains_user_certs": False,
                    "only_contains_ca_certs": False,
                    "only_contains_attribute_certs": False,
                    "indirect_crl": False,
                },
                True,
            ),
            (
                {
                    "fullname": "URI:http://example.com/myca.crl",
                    "onlysomereasons": ["keyCompromise"],
                    "onlyuser": True,
                    "onlyCA": False,
                    "onlyAA": False,
                    "indirectCRL": False,
                },
                {
                    "full_name": [
                        cx509.UniformResourceIdentifier("http://example.com/myca.crl")
                    ],
                    "relative_name": None,
                    "only_some_reasons": frozenset(
                        [cx509.ReasonFlags("keyCompromise")]
                    ),
                    "only_contains_user_certs": True,
                    "only_contains_ca_certs": False,
                    "only_contains_attribute_certs": False,
                    "indirect_crl": False,
                },
                False,
            ),
        ],
    )
    def test_create_issuing_distribution_point(self, val, expected, critical):
        with patch("cryptography.x509.IssuingDistributionPoint", autospec=True) as ext:
            res, crit = x509._create_extension("issuingDistributionPoint", val)
            assert crit == critical
            ext.assert_called_once_with(**expected)

    @pytest.mark.parametrize(
        "val,expected,critical",
        [
            (
                "critical, 1.2.4.5, 1.1.3.4",
                [
                    cx509.PolicyInformation(
                        policy_identifier=cx509.ObjectIdentifier("1.2.4.5"),
                        policy_qualifiers=None,
                    ),
                    cx509.PolicyInformation(
                        policy_identifier=cx509.ObjectIdentifier("1.1.3.4"),
                        policy_qualifiers=None,
                    ),
                ],
                True,
            ),
            (
                {
                    "critical": True,
                    "1.2.3.4.5": ["https://my.ca.com/pratice_statement"],
                },
                [
                    cx509.PolicyInformation(
                        policy_identifier=cx509.ObjectIdentifier("1.2.3.4.5"),
                        policy_qualifiers=["https://my.ca.com/pratice_statement"],
                    )
                ],
                True,
            ),
            (
                {
                    "1.2.3.4.5": [
                        "https://my.ca.com/pratice_statement",
                        {
                            "organization": "myorg",
                            "noticeNumbers": [1, 2, 3],
                            "text": "mytext",
                        },
                    ]
                },
                [
                    cx509.PolicyInformation(
                        policy_identifier=cx509.ObjectIdentifier("1.2.3.4.5"),
                        policy_qualifiers=[
                            "https://my.ca.com/pratice_statement",
                            cx509.UserNotice(
                                notice_reference=cx509.NoticeReference(
                                    organization="myorg", notice_numbers=[1, 2, 3]
                                ),
                                explicit_text="mytext",
                            ),
                        ],
                    )
                ],
                False,
            ),
        ],
    )
    def test_create_certificate_policies(self, val, expected, critical):
        with patch("cryptography.x509.CertificatePolicies", autospec=True) as ext:
            res, crit = x509._create_extension("certificatePolicies", val)
            assert crit == critical
            ext.assert_called_once_with(expected)

    @pytest.mark.parametrize(
        "val,expected,critical",
        [
            (
                "requireExplicitPolicy:3",
                {"require_explicit_policy": 3, "inhibit_policy_mapping": None},
                False,
            ),
            (
                "critical,requireExplicitPolicy:2,inhibitPolicyMapping:1",
                {"require_explicit_policy": 2, "inhibit_policy_mapping": 1},
                True,
            ),
            (
                {
                    "critical": True,
                    "requireExplicitPolicy": 4,
                    "inhibitPolicyMapping": 2,
                },
                {"require_explicit_policy": 4, "inhibit_policy_mapping": 2},
                True,
            ),
        ],
    )
    def test_create_policy_constraints(self, val, expected, critical):
        with patch("cryptography.x509.PolicyConstraints", autospec=True) as ext:
            res, crit = x509._create_extension("policyConstraints", val)
            assert crit == critical
            ext.assert_called_once_with(**expected)

    @pytest.mark.parametrize(
        "val,expected,critical",
        [
            (1, 1, False),
            ("critical, 1", 1, True),
            ({"critical": True, "value": 1}, 1, True),
        ],
    )
    def test_create_inhibit_any_policy(self, val, expected, critical):
        with patch("cryptography.x509.InhibitAnyPolicy", autospec=True) as ext:
            res, crit = x509._create_extension("inhibitAnyPolicy", val)
            assert crit == critical
            ext.assert_called_once_with(expected)

    @pytest.mark.parametrize(
        "val,excluded,permitted,critical",
        [
            (
                "critical,permitted;IP:192.168.0.0/255.255.0.0,permitted;email:.example.com,excluded;email:.com",
                [cx509.RFC822Name(".com")],
                [
                    cx509.IPAddress(ipaddress.ip_network("192.168.0.0/16")),
                    cx509.RFC822Name(".example.com"),
                ],
                True,
            ),
            (
                {
                    "critical": True,
                    "excluded": [
                        "dns:.no.example.com",
                        "dns:no.example.com",
                        "ip:192.168.1.0/24",
                        "ip:2001:500::/40",
                        "email:foo@example.io",
                        "email:foo.example.com",
                        "email:.foo.example.com",
                        "uri:no.foo.bar",
                        "uri:.no.foo.bar",
                    ],
                    "permitted": [
                        "dns:.example.com",
                        "dns:example.com",
                        "dns:überexample.com",
                        "dns:.überexample.com",
                        "ip:192.168.0.0/255.255.0.0",
                        "ip:2001:500::/32",
                        "email:foo@example.com",
                        "email:.example.com",
                        "email:example.io",
                        "email:foo@überexample.com",
                        "email:.überexample.com",
                        "email:überexample.io",
                        "uri:.foo.bar",
                        "uri:foo.bar.baz",
                        "uri:.föö.bar",
                        "uri:föö.bar.baz",
                    ],
                },
                [
                    cx509.DNSName(".no.example.com"),
                    cx509.DNSName("no.example.com"),
                    cx509.IPAddress(ipaddress.ip_network("192.168.1.0/24")),
                    cx509.IPAddress(ipaddress.ip_network("2001:500::/40")),
                    cx509.RFC822Name("foo@example.io"),
                    cx509.RFC822Name("foo.example.com"),
                    cx509.RFC822Name(".foo.example.com"),
                    cx509.UniformResourceIdentifier("no.foo.bar"),
                    cx509.UniformResourceIdentifier(".no.foo.bar"),
                ],
                [
                    cx509.DNSName(".example.com"),
                    cx509.DNSName("example.com"),
                    cx509.DNSName("xn--berexample-8db.com"),
                    cx509.DNSName(".xn--berexample-8db.com"),
                    cx509.IPAddress(ipaddress.ip_network("192.168.0.0/16")),
                    cx509.IPAddress(ipaddress.ip_network("2001:500::/32")),
                    cx509.RFC822Name("foo@example.com"),
                    cx509.RFC822Name(".example.com"),
                    cx509.RFC822Name("example.io"),
                    cx509.RFC822Name("foo@xn--berexample-8db.com"),
                    cx509.RFC822Name(".xn--berexample-8db.com"),
                    cx509.RFC822Name("xn--berexample-8db.io"),
                    cx509.UniformResourceIdentifier(".foo.bar"),
                    cx509.UniformResourceIdentifier("foo.bar.baz"),
                    cx509.UniformResourceIdentifier(".xn--f-1gaa.bar"),
                    cx509.UniformResourceIdentifier("xn--f-1gaa.bar.baz"),
                ],
                True,
            ),
        ],
    )
    def test_create_name_constraints(self, val, excluded, permitted, critical):
        with patch("cryptography.x509.NameConstraints", autospec=True) as ext:
            res, crit = x509._create_extension("nameConstraints", val)
            assert crit == critical
            ext.assert_called_once_with(
                permitted_subtrees=permitted, excluded_subtrees=excluded
            )

    def test_create_name_constraints_requires_at_least_one_definition(self):
        with patch("cryptography.x509.NameConstraints", autospec=True):
            with pytest.raises(salt.exceptions.SaltInvocationError):
                x509._create_extension("nameConstraints", {"permitted": []})

    @pytest.mark.parametrize(
        "val,critical", [([], False), ("critical", True), (["critical"], True)]
    )
    def test_create_no_check(self, val, critical):
        with patch("cryptography.x509.OCSPNoCheck", autospec=True):
            res, crit = x509._create_extension("noCheck", val)
            assert crit == critical

    @pytest.mark.parametrize(
        "val,expected,critical",
        [
            (
                "critical, status_request, status_request_v2",
                [
                    cx509.TLSFeatureType.status_request,
                    cx509.TLSFeatureType.status_request_v2,
                ],
                True,
            ),
            (
                ["critical", "status_request"],
                [cx509.TLSFeatureType.status_request],
                True,
            ),
        ],
    )
    def test_create_tlsfeature(self, val, expected, critical):
        with patch("cryptography.x509.TLSFeature", autospec=True) as ext:
            res, crit = x509._create_extension("tlsfeature", val)
            assert crit == critical
            ext.assert_called_once_with(expected)

    def test_create_crl_number(self):
        with patch("cryptography.x509.CRLNumber", autospec=True) as ext:
            res, crit = x509._create_extension("cRLNumber", 3)
            assert crit is False
            ext.assert_called_once_with(3)

    @pytest.mark.parametrize(
        "val,expected,critical",
        [
            (
                "critical, 3",
                3,
                True,
            ),
            (
                "3",
                3,
                False,
            ),
            (
                3,
                3,
                False,
            ),
        ],
    )
    def test_create_delta_crl_indicator(self, val, expected, critical):
        with patch("cryptography.x509.DeltaCRLIndicator", autospec=True) as ext:
            res, crit = x509._create_extension("deltaCRLIndicator", val)
            assert crit == critical
            ext.assert_called_once_with(expected)

    @pytest.mark.parametrize(
        "val,expected,critical",
        [
            (
                "critical, keyCompromise",
                cx509.ReasonFlags("keyCompromise"),
                True,
            ),
            (
                "aACompromise",
                cx509.ReasonFlags("aACompromise"),
                False,
            ),
            (
                {"critical": True, "superseded": True},
                cx509.ReasonFlags("superseded"),
                True,
            ),
            (
                ["critical", "privilegeWithdrawn"],
                cx509.ReasonFlags("privilegeWithdrawn"),
                True,
            ),
        ],
    )
    def test_create_crl_reason(self, val, expected, critical):
        with patch("cryptography.x509.CRLReason", autospec=True) as ext:
            res, crit = x509._create_extension("CRLReason", val)
            assert crit == critical
            ext.assert_called_once_with(expected)

    @pytest.mark.parametrize(
        "val,expected,critical",
        [
            (
                "critical, 2022-10-11 13:37:42",
                datetime.strptime("2022-10-11 13:37:42", "%Y-%m-%d %H:%M:%S"),
                True,
            ),
            (
                "2022-10-11 13:37:42",
                datetime.strptime("2022-10-11 13:37:42", "%Y-%m-%d %H:%M:%S"),
                False,
            ),
        ],
    )
    def test_create_invalidity_date(self, val, expected, critical):
        with patch("cryptography.x509.InvalidityDate", autospec=True) as ext:
            res, crit = x509._create_extension("invalidityDate", val)
            assert crit == critical
            ext.assert_called_once_with(expected)


def _parse_gn_ids(inpt):
    if isinstance(inpt, tuple):
        return ":".join(str(x) for x in inpt)
    if isinstance(inpt, bool):
        return "nc" if inpt else "reg"
    if isinstance(inpt, type):
        return inpt.__name__


@pytest.mark.parametrize(
    "inpt,name_constraints,cls,parsed",
    [
        (("DNS", "example.com"), False, cx509.DNSName, "example.com"),
        (("DNS", "example.com"), True, cx509.DNSName, "example.com"),
        (
            ("DNS", "example.com."),
            False,
            salt.exceptions.CommandExecutionError,
            "Trailing dots.*not allowed",
        ),
        (
            ("DNS", "example.com."),
            True,
            salt.exceptions.CommandExecutionError,
            "Trailing dots.*not allowed",
        ),
        (
            ("DNS", "*.example.com."),
            False,
            salt.exceptions.CommandExecutionError,
            "Trailing dots.*not allowed",
        ),
        (("DNS", "example｡com"), False, cx509.DNSName, "example.com"),
        (("DNS", "example｡com"), True, cx509.DNSName, "example.com"),
        (
            ("DNS", "example｡com｡"),
            False,
            salt.exceptions.CommandExecutionError,
            "Trailing dots.*not allowed",
        ),
        (
            ("DNS", "example｡com｡"),
            True,
            salt.exceptions.CommandExecutionError,
            "Trailing dots.*not allowed",
        ),
        (
            ("DNS", ".example.com"),
            False,
            salt.exceptions.CommandExecutionError,
            "Leading dots.*not allowed",
        ),
        (("DNS", ".example.com"), True, cx509.DNSName, ".example.com"),
        (
            ("DNS", "．example．com"),
            False,
            salt.exceptions.CommandExecutionError,
            "Leading dots.*not allowed",
        ),
        (("DNS", "。example。com"), True, cx509.DNSName, ".example.com"),
        (("DNS", "*.example.com"), False, cx509.DNSName, "*.example.com"),
        (
            ("DNS", "*.example.com"),
            True,
            salt.exceptions.CommandExecutionError,
            "Wildcards.*not allowed",
        ),
        # Also check trailing dots with wilcards, which are only allowed with `URI`
        (
            ("URI", "https://*.überexample.com."),
            False,
            cx509.UniformResourceIdentifier,
            "https://*.xn--berexample-8db.com.",
        ),
        # The following two are not valid per modern specs, but we're not validating higher-level semantics
        (("DNS", "foo.*.example.com"), False, cx509.DNSName, "foo.*.example.com"),
        (
            ("DNS", "foo*.example.com"),
            True,
            salt.exceptions.CommandExecutionError,
            "Wildcards.*not allowed",
        ),
        (("DNS", "foo*.example.com"), False, cx509.DNSName, "foo*.example.com"),
        (("DNS", "überexample.com"), False, cx509.DNSName, "xn--berexample-8db.com"),
        (("DNS", "überexample.com"), True, cx509.DNSName, "xn--berexample-8db.com"),
        (
            ("DNS", ".überexample.com"),
            False,
            salt.exceptions.CommandExecutionError,
            "Leading dots.*not allowed",
        ),
        (("DNS", ".überexample.com"), True, cx509.DNSName, ".xn--berexample-8db.com"),
        (
            ("DNS", "*.überexample.com"),
            False,
            cx509.DNSName,
            "*.xn--berexample-8db.com",
        ),
        (
            ("DNS", "*.überexample.com"),
            True,
            salt.exceptions.CommandExecutionError,
            "Wildcards.*not allowed",
        ),
        (
            ("DNS", "über*.example.com"),
            False,
            salt.exceptions.CommandExecutionError,
            "Label with wildcard must contain ASCII characters only",
        ),
        (
            ("DNS", "γνῶθι.σεαυτόν.gr"),
            False,
            cx509.DNSName,
            "xn--oxakdo9327a.xn--mxahzvhf4c.gr",
        ),
        (
            ("DNS", "γνῶθι.σεαυτόν.gr"),
            True,
            cx509.DNSName,
            "xn--oxakdo9327a.xn--mxahzvhf4c.gr",
        ),
        (
            ("DNS", "some.invalid_doma.in"),
            False,
            salt.exceptions.CommandExecutionError,
            "at position 8.*not allowed$",
        ),
        (
            ("DNS", "some.invalid_doma.in"),
            True,
            salt.exceptions.CommandExecutionError,
            "at position 8.*not allowed$",
        ),
        (
            ("DNS", "some..invalid-doma.in"),
            False,
            salt.exceptions.CommandExecutionError,
            "Empty Label",
        ),
        (
            ("DNS", "some..invalid-doma.in"),
            True,
            salt.exceptions.CommandExecutionError,
            "Empty Label",
        ),
        (
            ("DNS", "some.invalid-doma-.in"),
            False,
            salt.exceptions.CommandExecutionError,
            "Label must not start or end with a hyphen",
        ),
        (
            ("DNS", "some.invalid-doma-.in"),
            True,
            salt.exceptions.CommandExecutionError,
            "Label must not start or end with a hyphen",
        ),
        (
            ("DNS", ".*.wildcard-dot.test"),
            False,
            salt.exceptions.CommandExecutionError,
            "Leading dots.*not allowed",
        ),
        (
            ("DNS", "*..whats.this"),
            False,
            salt.exceptions.CommandExecutionError,
            "Empty Label",
        ),
        (
            ("DNS", 42),
            False,
            salt.exceptions.CommandExecutionError,
            "Expected string value, got int",
        ),
        (
            ("DNS", 42),
            True,
            salt.exceptions.CommandExecutionError,
            "Expected string value, got int",
        ),
        (
            ("DNS", ""),
            False,
            salt.exceptions.CommandExecutionError,
            "Empty domain",
        ),
        (
            ("DNS", ""),
            True,
            salt.exceptions.CommandExecutionError,
            "Empty domain",
        ),
        (
            ("DNS", "ἀνεῤῥίφθω.κύβος͵.gr"),
            False,
            salt.exceptions.CommandExecutionError,
            "not allowed at position 6 in 'κύβος͵'$",
        ),
        (
            ("DNS", "می\u200cخواهم\u200c.iran"),
            False,
            salt.exceptions.CommandExecutionError,
            # idna < 3.18 says "Joiner U+200C not allowed at position 9";
            # idna 3.18+ says "Unknown codepoint adjacent to joiner U+200C
            # at position 9". Accept either, so the test works across the
            # version range Salt 3006.x ships against.
            r"U\+200C.*at position 9 in '.*'",
        ),
        # Label length checks.
        # DNSName labels must be <64 chars.
        (
            ("DNS", 64 * "x" + ".bar.baz"),
            False,
            salt.exceptions.CommandExecutionError,
            "Label too long",
        ),
        (
            ("DNS", 63 * "x" + ".bar.baz"),
            False,
            cx509.DNSName,
            63 * "x" + ".bar.baz",
        ),
        # U-labels must be encoded to A-labels before the check.
        (
            ("DNS", 62 * "x" + "á" + ".bar.baz"),
            False,
            salt.exceptions.CommandExecutionError,
            "Label too long",
        ),
        # Wildcard chars should not count against the limit.
        (
            ("DNS", 63 * "x" + "*.bar.baz"),
            False,
            cx509.DNSName,
            63 * "x" + "*.bar.baz",
        ),
        (
            ("DNS", 64 * "x" + "*.bar.baz"),
            False,
            salt.exceptions.CommandExecutionError,
            "Label too long",
        ),
        # Domain length checks.
        # Domains must be <255 chars (including implicit absolute root marker, i.e. trailing dot).
        (
            (
                "DNS",
                "f.f." + 63 * "x" + "." + 63 * "x" + "." + 63 * "z" + "." + 58 * "x",
            ),
            False,
            salt.exceptions.CommandExecutionError,
            "Domain too long",
        ),
        (
            (
                "DNS",
                "f.f." + 63 * "x" + "." + 63 * "x" + "." + 63 * "z" + "." + 57 * "x",
            ),
            False,
            cx509.DNSName,
            "f.f." + 63 * "x" + "." + 63 * "x" + "." + 63 * "z" + "." + 57 * "x",
        ),
        # Ensure an explicit trailing dot does not count against limit. Only `URI` allows them
        (
            (
                "URI",
                "https://f.f."
                + 63 * "x"
                + "."
                + 63 * "x"
                + "."
                + 63 * "z"
                + "."
                + 57 * "x"
                + ".",
            ),
            False,
            cx509.UniformResourceIdentifier,
            "https://f.f."
            + 63 * "x"
            + "."
            + 63 * "x"
            + "."
            + 63 * "z"
            + "."
            + 57 * "x"
            + ".",
        ),
        # U-labels must be encoded to A-labels before the check.
        (
            (
                "DNS",
                "á.f." + 63 * "x" + "." + 63 * "x" + "." + 63 * "z" + "." + 57 * "x",
            ),
            False,
            salt.exceptions.CommandExecutionError,
            "Domain too long",
        ),
        # Wildcard chars should not count against the limit.
        (
            (
                "DNS",
                "*.f." + 63 * "x" + "." + 63 * "x" + "." + 63 * "z" + "." + 58 * "x",
            ),
            False,
            cx509.DNSName,
            "*.f." + 63 * "x" + "." + 63 * "x" + "." + 63 * "z" + "." + 58 * "x",
        ),
        (
            (
                "DNS",
                "*.á." + 63 * "x" + "." + 63 * "x" + "." + 63 * "z" + "." + 58 * "x",
            ),
            False,
            salt.exceptions.CommandExecutionError,
            "Domain too long",
        ),
        (("email", "me@example.com"), False, cx509.RFC822Name, "me@example.com"),
        (("email", "me@example.com"), True, cx509.RFC822Name, "me@example.com"),
        (
            ("email", "me@überexample.com"),
            False,
            cx509.RFC822Name,
            "me@xn--berexample-8db.com",
        ),
        (
            ("email", "me@überexample.com"),
            True,
            cx509.RFC822Name,
            "me@xn--berexample-8db.com",
        ),
        (
            ("email", "mé@example.com"),
            False,
            salt.exceptions.CommandExecutionError,
            "SmtpUTF8Mailbox",
        ),
        (
            ("email", "mé@example.com"),
            True,
            salt.exceptions.CommandExecutionError,
            "SmtpUTF8Mailbox",
        ),
        (
            ("email", ".example.com"),
            False,
            salt.exceptions.CommandExecutionError,
            "Not a valid.*in this context.*",
        ),
        (("email", ".example.com"), True, cx509.RFC822Name, ".example.com"),
        (
            ("email", "example.com"),
            False,
            salt.exceptions.CommandExecutionError,
            "Not a valid.*in this context.*",
        ),
        (
            ("email", "example.com"),
            True,
            cx509.RFC822Name,
            "example.com",
        ),
        (
            ("email", "invalid@*.mail.address"),
            False,
            salt.exceptions.CommandExecutionError,
            "Wildcards.*not allowed",
        ),
        (
            ("email", "invalid@*.mail.address"),
            True,
            salt.exceptions.CommandExecutionError,
            "Wildcards.*not allowed",
        ),
        (
            ("email", "invalid@.mail.address"),
            False,
            salt.exceptions.CommandExecutionError,
            "Leading dots are not allowed in this context",
        ),
        (
            ("email", "invalid@.mail.address"),
            True,
            salt.exceptions.CommandExecutionError,
            "Leading dots are not allowed in this context",
        ),
        (
            ("email", 42),
            False,
            salt.exceptions.CommandExecutionError,
            "Expected string value, got int",
        ),
        (
            ("email", 42),
            True,
            salt.exceptions.CommandExecutionError,
            "Expected string value, got int",
        ),
        (
            ("URI", "https://www.example.com"),
            False,
            cx509.UniformResourceIdentifier,
            "https://www.example.com",
        ),
        (
            ("URI", "https://www.example.com"),
            True,
            salt.exceptions.CommandExecutionError,
            "NameConstraints URI should be the same format as DNS",
        ),
        (
            ("URI", "*.example.com"),
            False,
            salt.exceptions.CommandExecutionError,
            "URI must contain a scheme",
        ),
        (
            ("URI", "*.example.com"),
            True,
            salt.exceptions.CommandExecutionError,
            "Wildcards.*not allowed",
        ),
        (
            ("URI", ".example.com"),
            False,
            salt.exceptions.CommandExecutionError,
            "Leading dots.*not allowed",
        ),
        (
            ("URI", ".example.com"),
            True,
            cx509.UniformResourceIdentifier,
            ".example.com",
        ),
        (
            ("URI", "https://1.2.3.4"),
            False,
            cx509.UniformResourceIdentifier,
            "https://1.2.3.4",
        ),
        (
            ("URI", "https://1.2.3.4"),
            True,
            salt.exceptions.CommandExecutionError,
            "NameConstraints URI should be the same format as DNS",
        ),
        (
            ("URI", "https://[2001:db8::1]"),
            False,
            cx509.UniformResourceIdentifier,
            "https://[2001:db8::1]",
        ),
        (
            ("URI", "https://[2001:db8::1]"),
            True,
            salt.exceptions.CommandExecutionError,
            "NameConstraints URI should be the same format as DNS",
        ),
        (
            ("URI", "https://www.überexample.com"),
            False,
            cx509.UniformResourceIdentifier,
            "https://www.xn--berexample-8db.com",
        ),
        (
            ("URI", "https://www.überexample.com"),
            True,
            salt.exceptions.CommandExecutionError,
            "NameConstraints URI should be the same format as DNS",
        ),
        (
            ("URI", "proto://*.example.com"),
            False,
            cx509.UniformResourceIdentifier,
            "proto://*.example.com",
        ),
        (
            ("URI", "proto://*.example.com"),
            True,
            salt.exceptions.CommandExecutionError,
            "NameConstraints URI should be the same format as DNS",
        ),
        (
            ("URI", "proto://.example.com"),
            False,
            salt.exceptions.CommandExecutionError,
            "Leading dots.*not allowed",
        ),
        (
            ("URI", "proto://.example.com"),
            True,
            salt.exceptions.CommandExecutionError,
            "NameConstraints URI should be the same format as DNS",
        ),
        (
            ("URI", "mailto:foo@example.com"),
            False,
            cx509.UniformResourceIdentifier,
            "mailto:foo@example.com",
        ),
        (
            ("URI", "mailto:foo@example.com"),
            True,
            salt.exceptions.CommandExecutionError,
            "NameConstraints URI should be the same format as DNS",
        ),
        (
            ("URI", "mailto:föö@überexample.com"),
            False,
            cx509.UniformResourceIdentifier,
            "mailto:f%C3%B6%C3%B6@%C3%BCberexample.com",  # not ideal, but we can't account for everything
        ),
        (
            ("URI", "https://user@example.com:1337"),
            False,
            cx509.UniformResourceIdentifier,
            "https://user@example.com:1337",
        ),
        (
            ("URI", "https://user@example.com:0x1337"),
            False,
            salt.exceptions.CommandExecutionError,
            "Port could not be cast to integer value",
        ),
        (
            ("URI", "https://user:pass@χάος.σκάλα.gr:1337"),
            False,
            cx509.UniformResourceIdentifier,
            "https://user:pass@xn--hxa2bjr.xn--hxakzf1b.gr:1337",
        ),
        (
            (
                "URI",
                "https://user:pass@example.com:1337/path/segment?query_param=foo#fragment",
            ),
            False,
            cx509.UniformResourceIdentifier,
            "https://user:pass@example.com:1337/path/segment?query_param=foo#fragment",
        ),
        (
            (
                "URI",
                "https://üsér:paß$WORD@example.com:1337/päth/ségment?quéry_päram=föö&othér=bär#frägment",
            ),
            False,
            cx509.UniformResourceIdentifier,
            "https://%C3%BCs%C3%A9r:pa%C3%9F$WORD@example.com:1337/p%C3%A4th/s%C3%A9gment?qu%C3%A9ry_p%C3%A4ram=f%C3%B6%C3%B6&oth%C3%A9r=b%C3%A4r#fr%C3%A4gment",
        ),
        (
            (
                "URI",
                "https://üsér:paß$WORD@überexample.com:1337/päth/ségment?quéry_päram=föö&othér=bär#frägment",
            ),
            False,
            cx509.UniformResourceIdentifier,
            "https://%C3%BCs%C3%A9r:pa%C3%9F$WORD@xn--berexample-8db.com:1337/p%C3%A4th/s%C3%A9gment?qu%C3%A9ry_p%C3%A4ram=f%C3%B6%C3%B6&oth%C3%A9r=b%C3%A4r#fr%C3%A4gment",
        ),
        (
            (
                "URI",
                "https://%C3%BCs%C3%A9r:pa%C3%9F$WORD@xn--berexample-8db.com:1337/p%C3%A4th/s%C3%A9gment?qu%C3%A9ry_p%C3%A4ram=f%C3%B6%C3%B6&oth%C3%A9r=b%C3%A4r#fr%C3%A4gment",
            ),
            False,
            cx509.UniformResourceIdentifier,
            "https://%C3%BCs%C3%A9r:pa%C3%9F$WORD@xn--berexample-8db.com:1337/p%C3%A4th/s%C3%A9gment?qu%C3%A9ry_p%C3%A4ram=f%C3%B6%C3%B6&oth%C3%A9r=b%C3%A4r#fr%C3%A4gment",
        ),
        (
            ("URI", "https://example.com/%foobar"),
            False,
            salt.exceptions.CommandExecutionError,
            "Invalid percent-encoding",
        ),
        (
            ("URI", "some/path/only"),
            False,
            salt.exceptions.CommandExecutionError,
            "URI must contain a scheme",
        ),
        (
            ("URI", "some/path/only"),
            True,
            salt.exceptions.CommandExecutionError,
            r"Codepoint U\+002F.*5 of 'some/path/only' not allowed",
        ),
        (
            ("URI", 42),
            False,
            salt.exceptions.CommandExecutionError,
            "Expected string value, got int",
        ),
        (
            ("URI", 42),
            True,
            salt.exceptions.CommandExecutionError,
            "Expected string value, got int",
        ),
        (
            ("RID", "1.2.3.4"),
            False,
            cx509.RegisteredID,
            cx509.ObjectIdentifier("1.2.3.4"),
        ),
        (
            ("IP", "13.37.13.37"),
            False,
            cx509.IPAddress,
            ipaddress.ip_address("13.37.13.37"),
        ),
        (
            ("IP", "13.37.13.37"),
            True,
            cx509.IPAddress,
            ipaddress.ip_network("13.37.13.37/32"),
        ),
        (
            ("IP", "13.37.13.0/24"),
            False,
            salt.exceptions.CommandExecutionError,
            "does not seem to be an IPv4/IPv6 address",
        ),
        (
            ("IP", "13.37.13.0/24"),
            True,
            cx509.IPAddress,
            ipaddress.ip_network("13.37.13.0/24"),
        ),
        (
            ("IP", "13.37.13.0/255.255.255.0"),
            True,
            cx509.IPAddress,
            ipaddress.ip_network("13.37.13.0/255.255.255.0"),
        ),
        (
            ("IP", "2001:0db8:85a3:0000:0000:8a2e:0370:7334"),
            False,
            cx509.IPAddress,
            ipaddress.ip_address("2001:0db8:85a3:0000:0000:8a2e:0370:7334"),
        ),
        (
            ("IP", "2001:0db8:85a3:0000:0000:8a2e:0370:7334"),
            True,
            cx509.IPAddress,
            ipaddress.ip_network("2001:0db8:85a3:0000:0000:8a2e:0370:7334/128"),
        ),
        (
            ("IP", "2001:db8:abcd:0012::0/64"),
            False,
            salt.exceptions.CommandExecutionError,
            "does not seem to be an IPv4/IPv6 address",
        ),
        (
            ("IP", "2001:db8:abcd:0012::0/64"),
            True,
            cx509.IPAddress,
            ipaddress.ip_network("2001:db8:abcd:0012::0/64"),
        ),
        (
            ("IP", "this is not an IP address"),
            False,
            salt.exceptions.CommandExecutionError,
            "does not seem to be an IPv4/IPv6 address",
        ),
        (
            ("IP", ("hi", "there")),
            False,
            salt.exceptions.CommandExecutionError,
            "does not seem to be an IPv4/IPv6 address",
        ),
        (
            ("IP", ("hi", "there")),
            True,
            salt.exceptions.CommandExecutionError,
            "does not seem to be an IPv4/IPv6 network range",
        ),
        pytest.param(
            (
                "dirName",
                "CN=mysite.com,O=My Company,L=San Francisco,ST=California,C=US",
            ),
            False,
            cx509.Name,
            [
                cx509.RelativeDistinguishedName(
                    [cx509.NameAttribute(cx509.ObjectIdentifier("2.5.4.6"), value="US")]
                ),
                cx509.RelativeDistinguishedName(
                    [
                        cx509.NameAttribute(
                            cx509.ObjectIdentifier("2.5.4.8"), value="California"
                        )
                    ]
                ),
                cx509.RelativeDistinguishedName(
                    [
                        cx509.NameAttribute(
                            cx509.ObjectIdentifier("2.5.4.7"), value="San Francisco"
                        )
                    ]
                ),
                cx509.RelativeDistinguishedName(
                    [
                        cx509.NameAttribute(
                            cx509.ObjectIdentifier("2.5.4.10"), value="My Company"
                        )
                    ]
                ),
                cx509.RelativeDistinguishedName(
                    [
                        cx509.NameAttribute(
                            cx509.ObjectIdentifier("2.5.4.3"), value="mysite.com"
                        )
                    ]
                ),
            ],
        ),
        (
            (
                "dirName",
                {
                    "C": "US",
                    "ST": "California",
                    "L": "San Francisco",
                    "O": "My Company",
                    "CN": "mysite.com",
                },
            ),
            False,
            cx509.Name,
            [
                cx509.RelativeDistinguishedName(
                    [cx509.NameAttribute(cx509.ObjectIdentifier("2.5.4.6"), value="US")]
                ),
                cx509.RelativeDistinguishedName(
                    [
                        cx509.NameAttribute(
                            cx509.ObjectIdentifier("2.5.4.8"), value="California"
                        )
                    ]
                ),
                cx509.RelativeDistinguishedName(
                    [
                        cx509.NameAttribute(
                            cx509.ObjectIdentifier("2.5.4.7"), value="San Francisco"
                        )
                    ]
                ),
                cx509.RelativeDistinguishedName(
                    [
                        cx509.NameAttribute(
                            cx509.ObjectIdentifier("2.5.4.10"), value="My Company"
                        )
                    ]
                ),
                cx509.RelativeDistinguishedName(
                    [
                        cx509.NameAttribute(
                            cx509.ObjectIdentifier("2.5.4.3"), value="mysite.com"
                        )
                    ]
                ),
            ],
        ),
        (
            ("dirName", "Et tu, Brute?"),
            False,
            salt.exceptions.CommandExecutionError,
            "Failed parsing rfc4514 dirName string",
        ),
        (
            ("otherName", "1.2.3.4;UTF8:some other identifier"),
            False,
            cx509.OtherName,
            (
                cx509.ObjectIdentifier("1.2.3.4"),
                asn1.encode_der("some other identifier"),
            ),
        ),
        (
            (
                "otherName",
                "1.3.6.1.5.5.7.8.9;FORMAT:UTF8,UTF8String:nonasciinäme.example.com",
            ),
            False,
            cx509.OtherName,
            (
                cx509.ObjectIdentifier("1.3.6.1.5.5.7.8.9"),
                asn1.encode_der("nonasciinäme.example.com"),
            ),
        ),
        (
            ("otherName", "1.2.3.4;BOOL:TRUE"),
            False,
            salt.exceptions.CommandExecutionError,
            ".*only UTF8STRING is supported.*",
        ),
        (
            ("otherName", {"oid": "1.2.3.4", "value": "some other identifier"}),
            False,
            cx509.OtherName,
            (
                cx509.ObjectIdentifier("1.2.3.4"),
                asn1.encode_der("some other identifier"),
            ),
        ),
        (
            ("otherName", {"oid": "1.2.3.4", "value": True}),
            False,
            cx509.OtherName,
            (cx509.ObjectIdentifier("1.2.3.4"), asn1.encode_der(True)),
        ),
        (
            ("otherName", {"oid": "1.2.3.4", "value": None}),
            False,
            cx509.OtherName,
            (cx509.ObjectIdentifier("1.2.3.4"), asn1.encode_der(asn1.Null())),
        ),
        (
            (
                "otherName",
                {
                    "oid": "1.2.3.4",
                    "der": "hex:" + asn1.encode_der("hex encoded utf8string").hex(),
                },
            ),
            False,
            cx509.OtherName,
            (
                cx509.ObjectIdentifier("1.2.3.4"),
                asn1.encode_der("hex encoded utf8string"),
            ),
        ),
        (
            (
                "otherName",
                {
                    "oid": "1.2.3.4",
                    "der": "b64:"
                    + base64.b64encode(
                        asn1.encode_der(
                            "base64 encoded utf8string, but arbitrary types are allowed"
                        )
                    ).decode(),
                },
            ),
            False,
            cx509.OtherName,
            (
                cx509.ObjectIdentifier("1.2.3.4"),
                asn1.encode_der(
                    "base64 encoded utf8string, but arbitrary types are allowed"
                ),
            ),
        ),
        (
            ("otherName", []),
            False,
            salt.exceptions.CommandExecutionError,
            ".*dict or string required.*",
        ),
        (
            ("otherName", {}),
            False,
            salt.exceptions.CommandExecutionError,
            ".*missing `oid` key.*",
        ),
        (
            ("otherName", {"oid": "1.2.3.4"}),
            False,
            salt.exceptions.CommandExecutionError,
            ".*missing `value` or `der` key.*",
        ),
        (
            ("otherName", {"oid": "1.2.3.4", "der": "foobar"}),
            False,
            salt.exceptions.CommandExecutionError,
            ".*needs `hex:` or `b64:` prefix.*",
        ),
        (
            ("invalidType", "L'état c'est moi!"),
            False,
            salt.exceptions.CommandExecutionError,
            "GeneralName type invalidtype is invalid",
        ),
    ],
    ids=_parse_gn_ids,
)
def test_parse_general_names(inpt, name_constraints, cls, parsed):
    if issubclass(cls, Exception):
        with pytest.raises(cls, match=parsed):
            x509.parse_general_names([inpt], name_constraints=name_constraints)
        return
    if inpt[0] == "otherName":
        expected = cls(*parsed)
    else:
        expected = cls(parsed)
    res = x509.parse_general_names([inpt], name_constraints=name_constraints)
    if inpt[0] == "dirName":
        assert res[0].value == expected
    else:
        assert res[0] == expected


@pytest.mark.parametrize(
    "inpt,name_constraints,cls,parsed",
    [
        (("DNS", "example.com"), False, cx509.DNSName, "example.com"),
        (("DNS", "example.com"), True, cx509.DNSName, "example.com"),
        (("DNS", "*.example.com"), False, cx509.DNSName, "*.example.com"),
        (
            ("DNS", "*.example.com"),
            True,
            salt.exceptions.CommandExecutionError,
            "Wildcards are not allowed",
        ),
        (
            ("DNS", ".example.com"),
            False,
            salt.exceptions.CommandExecutionError,
            "Leading dots.*not allowed",
        ),
        (("DNS", ".example.com"), True, cx509.DNSName, ".example.com"),
        (
            ("DNS", "some*.wild.card"),
            False,
            cx509.DNSName,
            "some*.wild.card",
        ),
        (
            ("DNS", "some*.wild.card"),
            True,
            salt.exceptions.CommandExecutionError,
            "Wildcards are not allowed",
        ),
        (
            ("DNS", "some.*.wild.card"),
            False,
            cx509.DNSName,
            "some.*.wild.card",
        ),
        (
            ("DNS", ".*.wildcard-dot.test"),
            False,
            salt.exceptions.CommandExecutionError,
            "Leading dots.*not allowed",
        ),
        (
            ("DNS", "gott.würfelt.nicht"),
            False,
            salt.exceptions.CommandExecutionError,
            "Cannot encode non-ASCII strings",
        ),
        (
            ("DNS", "some.invalid_doma.in"),
            False,
            salt.exceptions.CommandExecutionError,
            "at position 8.*not allowed$",
        ),
        (
            ("DNS", "some.invalid_doma.in"),
            True,
            salt.exceptions.CommandExecutionError,
            "at position 8.*not allowed$",
        ),
        (
            ("DNS", "some-.invalid-doma.in"),
            False,
            salt.exceptions.CommandExecutionError,
            "Label must not start or end with a hyphen",
        ),
        (
            ("DNS", "some-.invalid-doma.in"),
            True,
            salt.exceptions.CommandExecutionError,
            "Label must not start or end with a hyphen",
        ),
        (
            ("DNS", "some..invalid-doma.in"),
            False,
            salt.exceptions.CommandExecutionError,
            "Empty Label",
        ),
        (
            ("DNS", 42),
            False,
            salt.exceptions.CommandExecutionError,
            "Expected string value, got int",
        ),
        (
            ("DNS", ""),
            False,
            salt.exceptions.CommandExecutionError,
            "Empty domain",
        ),
        (
            ("DNS", "*..whats.this"),
            False,
            salt.exceptions.CommandExecutionError,
            "Empty Label",
        ),
        # Label length checks.
        # Don't need to check wildcard variants, handling of them does not differ when missing idna.
        # Can't check U-label variants because we're simulating missing idna.
        # DNSName labels must be <64 chars.
        (
            ("DNS", 64 * "x" + ".bar.baz"),
            False,
            salt.exceptions.CommandExecutionError,
            "Label too long",
        ),
        (
            ("DNS", 63 * "x" + ".bar.baz"),
            False,
            cx509.DNSName,
            63 * "x" + ".bar.baz",
        ),
        # Domain length checks.
        # Domains must be <255 chars (including implicit absolute root marker, i.e. trailing dot).
        (
            (
                "DNS",
                "f.f." + 63 * "x" + "." + 63 * "x" + "." + 63 * "z" + "." + 58 * "x",
            ),
            False,
            salt.exceptions.CommandExecutionError,
            "Domain too long",
        ),
        (
            (
                "DNS",
                "f.f." + 63 * "x" + "." + 63 * "x" + "." + 63 * "z" + "." + 57 * "x",
            ),
            False,
            cx509.DNSName,
            "f.f." + 63 * "x" + "." + 63 * "x" + "." + 63 * "z" + "." + 57 * "x",
        ),
        # Ensure an explicit trailing dot does not count against limit. Only `URI` allows them
        (
            (
                "URI",
                "https://f.f."
                + 63 * "x"
                + "."
                + 63 * "x"
                + "."
                + 63 * "z"
                + "."
                + 57 * "x"
                + ".",
            ),
            False,
            cx509.UniformResourceIdentifier,
            "https://f.f."
            + 63 * "x"
            + "."
            + 63 * "x"
            + "."
            + 63 * "z"
            + "."
            + 57 * "x"
            + ".",
        ),
        (("email", "me@example.com"), False, cx509.RFC822Name, "me@example.com"),
        (("email", "me@example.com"), True, cx509.RFC822Name, "me@example.com"),
        (
            ("email", "me@überexample.com"),
            False,
            salt.exceptions.CommandExecutionError,
            "missing library: idna",
        ),
        (
            ("email", "me@überexample.com"),
            True,
            salt.exceptions.CommandExecutionError,
            "missing library: idna",
        ),
        (
            ("email", "mé@example.com"),
            False,
            salt.exceptions.CommandExecutionError,
            "SmtpUTF8Mailbox",
        ),
        (
            ("email", "mé@example.com"),
            True,
            salt.exceptions.CommandExecutionError,
            "SmtpUTF8Mailbox",
        ),
        (
            ("email", "invalid@*.mail.address"),
            False,
            salt.exceptions.CommandExecutionError,
            "Wildcards are not allowed in this context",
        ),
        (
            ("email", "invalid@.mail.address"),
            False,
            salt.exceptions.CommandExecutionError,
            "Leading dots are not allowed in this context",
        ),
        (
            ("email", "Invalid Email <invalid@mail.address>"),
            False,
            salt.exceptions.CommandExecutionError,
            "not allowed$",
        ),
        (
            ("email", 42),
            False,
            salt.exceptions.CommandExecutionError,
            "Expected string value, got int",
        ),
        (
            ("email", 42),
            True,
            salt.exceptions.CommandExecutionError,
            "Expected string value, got int",
        ),
        (
            ("URI", "https://www.example.com"),
            False,
            cx509.UniformResourceIdentifier,
            "https://www.example.com",
        ),
        (
            ("URI", "https://www.example.com"),
            True,
            salt.exceptions.CommandExecutionError,
            "NameConstraints URI should be the same format as DNS",
        ),
        (
            ("URI", "https://1.2.3.4"),
            False,
            cx509.UniformResourceIdentifier,
            "https://1.2.3.4",
        ),
        (
            ("URI", "https://[2001:db8::1]"),
            False,
            cx509.UniformResourceIdentifier,
            "https://[2001:db8::1]",
        ),
        (
            ("URI", "https://www.überexample.com"),
            False,
            salt.exceptions.CommandExecutionError,
            "missing library: idna",
        ),
        (
            ("URI", "https://www.example.com/päth/ségment"),
            False,
            cx509.UniformResourceIdentifier,
            "https://www.example.com/p%C3%A4th/s%C3%A9gment",
        ),
        (
            ("URI", "https://.invalid.host"),
            False,
            salt.exceptions.CommandExecutionError,
            "Leading dots.*not allowed",
        ),
        (
            ("URI", "https://*.example.com"),
            False,
            cx509.UniformResourceIdentifier,
            "https://*.example.com",
        ),
        (
            ("URI", 42),
            False,
            salt.exceptions.CommandExecutionError,
            "Expected string value, got int",
        ),
        (
            ("URI", 42),
            True,
            salt.exceptions.CommandExecutionError,
            "Expected string value, got int",
        ),
    ],
    ids=_parse_gn_ids,
)
def test_parse_general_names_without_idna(inpt, name_constraints, cls, parsed):
    with patch("salt.utils.x509.HAS_IDNA", False):
        if issubclass(cls, Exception):
            with pytest.raises(cls, match=parsed):
                x509.parse_general_names([inpt], name_constraints=name_constraints)
            return
        expected = cls(parsed)
        res = x509.parse_general_names([inpt], name_constraints=name_constraints)
        if inpt[0] == "dirName":
            assert res[0].value == expected
        else:
            assert res[0] == expected


@pytest.mark.parametrize(
    "inpt",
    [
        (("RID", "3.2.3.4")),
        (("RID", "1.2.3.4a")),
        (("IP", "13.37.1337.37")),
        (("IP", "13a.37.13.0/24")),
        (("IP", "13.37.13.0:255.255.255.0")),
        (("IP", "20010db8:85a3:0000:0000:8a2e:0370:7334")),
        (("IP", "2001:db8:abcd:0012::0.64")),
        (("dirName", "CC=US,ST=California,L=San Francisco,O=My Company,CN=mysite.com")),
    ],
)
def test_parse_general_names_rejects_invalid(inpt):
    with pytest.raises(salt.exceptions.CommandExecutionError):
        x509.parse_general_names([inpt])


@pytest.mark.parametrize(
    "inpt,expected",
    [
        pytest.param(
            "CN=example.com,O=Example Inc,C=US",
            [
                cx509.NameAttribute(x509.NAME_ATTRS_OID["C"], "US"),
                cx509.NameAttribute(x509.NAME_ATTRS_OID["O"], "Example Inc"),
                cx509.NameAttribute(x509.NAME_ATTRS_OID["CN"], "example.com"),
            ],
        ),
        pytest.param(
            ["C=US", "O=Example Inc", "CN=example.com"],
            [
                cx509.NameAttribute(x509.NAME_ATTRS_OID["C"], "US"),
                cx509.NameAttribute(x509.NAME_ATTRS_OID["O"], "Example Inc"),
                cx509.NameAttribute(x509.NAME_ATTRS_OID["CN"], "example.com"),
            ],
        ),
        pytest.param(
            ["C=US", "O=Example Inc", "OU=foo+CN=example.com"],
            [
                cx509.NameAttribute(x509.NAME_ATTRS_OID["C"], "US"),
                cx509.NameAttribute(x509.NAME_ATTRS_OID["O"], "Example Inc"),
                cx509.RelativeDistinguishedName(
                    {
                        cx509.NameAttribute(x509.NAME_ATTRS_OID["CN"], "example.com"),
                        cx509.NameAttribute(x509.NAME_ATTRS_OID["OU"], "foo"),
                    }
                ),
            ],
        ),
        (
            {"CN": "example.com", "O": "Example Inc", "C": "US", "irrelevant": "bar"},
            [
                cx509.NameAttribute(x509.NAME_ATTRS_OID["C"], "US"),
                cx509.NameAttribute(x509.NAME_ATTRS_OID["O"], "Example Inc"),
                cx509.NameAttribute(x509.NAME_ATTRS_OID["CN"], "example.com"),
            ],
        ),
    ],
)
def test_get_dn(inpt, expected):
    expected_parsed = [
        (
            cx509.RelativeDistinguishedName({x})
            if not isinstance(x, cx509.RelativeDistinguishedName)
            else x
        )
        for x in expected
    ]
    res = x509._get_dn(inpt)
    assert res.rdns == expected_parsed


@pytest.mark.parametrize(
    "inpt,expected",
    [
        (
            cx509.Extension(
                cx509.BasicConstraints.oid,
                value=cx509.BasicConstraints(ca=True, path_length=2),
                critical=True,
            ),
            {"ca": True, "critical": True, "pathlen": 2},
        ),
        (
            cx509.Extension(
                cx509.KeyUsage.oid,
                value=cx509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            ),
            {
                "cRLSign": False,
                "critical": True,
                "dataEncipherment": False,
                "decipherOnly": False,
                "digitalSignature": True,
                "encipherOnly": False,
                "keyAgreement": False,
                "keyCertSign": False,
                "keyEncipherment": False,
                "nonRepudiation": False,
            },
        ),
        (
            cx509.Extension(
                cx509.ExtendedKeyUsage.oid,
                value=cx509.ExtendedKeyUsage(
                    [
                        x509.EXTENDED_KEY_USAGE_OID["OCSPSigning"],
                        x509.EXTENDED_KEY_USAGE_OID["msCodeCom"],
                        cx509.ObjectIdentifier("2.3.4.55"),
                    ]
                ),
                critical=True,
            ),
            {
                "critical": True,
                "value": ["OCSPSigning", "1.3.6.1.4.1.311.2.1.22", "2.3.4.55"],
            },
        ),
        (
            cx509.Extension(
                cx509.SubjectKeyIdentifier.oid,
                value=cx509.SubjectKeyIdentifier(
                    b"\xbb\xaf~\x02=\xfa\xa6\xf1<\x84\x8e\xad\xee8\x98\xec\xd922\xd4"
                ),
                critical=False,
            ),
            {
                "critical": False,
                "value": "BB:AF:7E:02:3D:FA:A6:F1:3C:84:8E:AD:EE:38:98:EC:D9:32:32:D4",
            },
        ),
        (
            cx509.Extension(
                cx509.AuthorityKeyIdentifier.oid,
                value=cx509.AuthorityKeyIdentifier(
                    key_identifier=b"\xde\xad\xbe\xef",
                    authority_cert_issuer=[
                        cx509.DirectoryName(
                            cx509.Name(
                                [
                                    cx509.RelativeDistinguishedName(
                                        [
                                            cx509.NameAttribute(
                                                cx509.ObjectIdentifier("2.5.4.3"),
                                                value="foo",
                                            )
                                        ]
                                    )
                                ]
                            )
                        )
                    ],
                    authority_cert_serial_number=1337,
                ),
                critical=False,
            ),
            {
                "critical": False,
                "issuer": ["dirName:CN=foo"],
                "issuer_sn": "05:39",
                "keyid": "DE:AD:BE:EF",
            },
        ),
        (
            cx509.Extension(
                cx509.IssuerAlternativeName.oid,
                value=cx509.IssuerAlternativeName(
                    [
                        cx509.RFC822Name("ca@example.com"),
                        cx509.DNSName("example.com"),
                        cx509.DNSName("example.io"),
                    ]
                ),
                critical=False,
            ),
            {
                "critical": False,
                "value": ["email:ca@example.com", "DNS:example.com", "DNS:example.io"],
            },
        ),
        (
            cx509.Extension(
                cx509.CertificateIssuer.oid,
                value=cx509.CertificateIssuer(
                    [
                        cx509.RFC822Name("ca@example.com"),
                        cx509.DNSName("example.com"),
                        cx509.DNSName("example.io"),
                    ]
                ),
                critical=False,
            ),
            {
                "critical": False,
                "value": ["email:ca@example.com", "DNS:example.com", "DNS:example.io"],
            },
        ),
        (
            cx509.Extension(
                cx509.AuthorityInformationAccess.oid,
                value=cx509.AuthorityInformationAccess(
                    [
                        cx509.AccessDescription(
                            access_method=x509.ACCESS_OID["OCSP"],
                            access_location=cx509.UniformResourceIdentifier(
                                "http://ocsp.example.com/"
                            ),
                        ),
                        cx509.AccessDescription(
                            access_method=x509.ACCESS_OID["OCSP"],
                            access_location=cx509.UniformResourceIdentifier(
                                "http://ocsp2.example.com/"
                            ),
                        ),
                    ]
                ),
                critical=False,
            ),
            {
                "critical": False,
                "value": [
                    {"OCSP": "http://ocsp.example.com/"},
                    {"OCSP": "http://ocsp2.example.com/"},
                ],
            },
        ),
        (
            cx509.Extension(
                cx509.SubjectAlternativeName.oid,
                value=cx509.SubjectAlternativeName(
                    [
                        cx509.DNSName("example.io"),
                        cx509.RFC822Name("hello@example.io"),
                        cx509.OtherName(
                            cx509.ObjectIdentifier("1.2.3.4"), asn1.encode_der("foobar")
                        ),
                        cx509.OtherName(
                            cx509.ObjectIdentifier("1.2.3.4.5"), asn1.encode_der(True)
                        ),
                    ]
                ),
                critical=False,
            ),
            {
                "critical": False,
                "value": [
                    "DNS:example.io",
                    "email:hello@example.io",
                    "otherName:1.2.3.4;UTF8:foobar",
                    "otherName:1.2.3.4.5;<hex:0101ff>",
                ],
            },
        ),
        (
            cx509.Extension(
                cx509.CRLDistributionPoints.oid,
                value=cx509.CRLDistributionPoints(
                    [
                        cx509.DistributionPoint(
                            full_name=[
                                cx509.UniformResourceIdentifier(
                                    "http://example.com/myca.crl"
                                )
                            ],
                            relative_name=None,
                            reasons=frozenset([cx509.ReasonFlags("keyCompromise")]),
                            crl_issuer=[cx509.DNSName("example.org")],
                        ),
                        cx509.DistributionPoint(
                            full_name=None,
                            relative_name=cx509.RelativeDistinguishedName(
                                [
                                    cx509.NameAttribute(
                                        cx509.ObjectIdentifier("2.5.4.11"), value="foo"
                                    ),
                                    cx509.NameAttribute(
                                        cx509.ObjectIdentifier("2.5.4.3"), value="Smith"
                                    ),
                                ]
                            ),
                            reasons=None,
                            crl_issuer=[cx509.DNSName("example.org")],
                        ),
                    ]
                ),
                critical=False,
            ),
            {
                "critical": False,
                "value": [
                    {
                        "crlissuer": ["DNS:example.org"],
                        "fullname": ["URI:http://example.com/myca.crl"],
                        "reasons": ["keyCompromise"],
                        "relativename": None,
                    },
                    {
                        "crlissuer": ["DNS:example.org"],
                        "fullname": [],
                        "reasons": [],
                        "relativename": "OU=foo+CN=Smith",
                    },
                ],
            },
        ),
        (
            cx509.Extension(
                cx509.FreshestCRL.oid,
                value=cx509.FreshestCRL(
                    [
                        cx509.DistributionPoint(
                            full_name=[
                                cx509.UniformResourceIdentifier(
                                    "http://example.com/myca.crl"
                                )
                            ],
                            relative_name=None,
                            reasons=frozenset([cx509.ReasonFlags("keyCompromise")]),
                            crl_issuer=[cx509.DNSName("example.org")],
                        ),
                        cx509.DistributionPoint(
                            full_name=None,
                            relative_name=cx509.RelativeDistinguishedName(
                                [
                                    cx509.NameAttribute(
                                        cx509.ObjectIdentifier("2.5.4.11"), value="foo"
                                    ),
                                    cx509.NameAttribute(
                                        cx509.ObjectIdentifier("2.5.4.3"), value="Smith"
                                    ),
                                ]
                            ),
                            reasons=None,
                            crl_issuer=[cx509.DNSName("example.org")],
                        ),
                    ]
                ),
                critical=False,
            ),
            {
                "critical": False,
                "value": [
                    {
                        "crlissuer": ["DNS:example.org"],
                        "fullname": ["URI:http://example.com/myca.crl"],
                        "reasons": ["keyCompromise"],
                        "relativename": None,
                    },
                    {
                        "crlissuer": ["DNS:example.org"],
                        "fullname": [],
                        "reasons": [],
                        "relativename": "OU=foo+CN=Smith",
                    },
                ],
            },
        ),
        (
            cx509.Extension(
                cx509.IssuingDistributionPoint.oid,
                value=cx509.IssuingDistributionPoint(
                    full_name=[
                        cx509.UniformResourceIdentifier("http://example.com/myca.crl")
                    ],
                    relative_name=None,
                    only_some_reasons=frozenset([cx509.ReasonFlags("keyCompromise")]),
                    only_contains_user_certs=True,
                    only_contains_ca_certs=False,
                    only_contains_attribute_certs=False,
                    indirect_crl=False,
                ),
                critical=False,
            ),
            {
                "critical": False,
                "fullname": ["URI:http://example.com/myca.crl"],
                "indirectCRL": False,
                "onlyAA": False,
                "onlyCA": False,
                "onlyuser": True,
                "onlysomereasons": ["keyCompromise"],
                "relativename": None,
            },
        ),
        (
            cx509.Extension(
                cx509.CertificatePolicies.oid,
                value=cx509.CertificatePolicies(
                    [
                        cx509.PolicyInformation(
                            policy_identifier=cx509.ObjectIdentifier("1.2.3.4.5"),
                            policy_qualifiers=[
                                "https://my.ca.com/pratice_statement",
                                cx509.UserNotice(
                                    notice_reference=cx509.NoticeReference(
                                        organization="myorg", notice_numbers=[1, 2, 3]
                                    ),
                                    explicit_text="mytext",
                                ),
                            ],
                        )
                    ]
                ),
                critical=False,
            ),
            {
                "critical": False,
                "value": [
                    {
                        "1.2.3.4.5": [
                            {
                                "practice_statement": "https://my.ca.com/pratice_statement"
                            },
                            {
                                "explicit_text": "mytext",
                                "notice_numbers": [1, 2, 3],
                                "organization": "myorg",
                            },
                        ]
                    }
                ],
            },
        ),
        (
            cx509.Extension(
                cx509.PolicyConstraints.oid,
                value=cx509.PolicyConstraints(
                    require_explicit_policy=4, inhibit_policy_mapping=2
                ),
                critical=False,
            ),
            {"critical": False, "inhibitPolicyMapping": 2, "requireExplicitPolicy": 4},
        ),
        (
            cx509.Extension(
                cx509.InhibitAnyPolicy.oid,
                value=cx509.InhibitAnyPolicy(1),
                critical=False,
            ),
            {"critical": False, "value": 1},
        ),
        (
            cx509.Extension(
                cx509.NameConstraints.oid,
                value=cx509.NameConstraints(
                    [
                        cx509.IPAddress(ipaddress.ip_network("192.168.0.0/16")),
                        cx509.RFC822Name(".example.com"),
                    ],
                    [cx509.RFC822Name(".com")],
                ),
                critical=False,
            ),
            {
                "critical": False,
                "excluded": ["email:.com"],
                "permitted": ["IP:192.168.0.0/16", "email:.example.com"],
            },
        ),
        (
            cx509.Extension(
                cx509.OCSPNoCheck.oid, value=cx509.OCSPNoCheck(), critical=False
            ),
            {"critical": False, "value": True},
        ),
        (
            cx509.Extension(
                cx509.TLSFeature.oid,
                value=cx509.TLSFeature([cx509.TLSFeatureType.status_request]),
                critical=False,
            ),
            {"critical": False, "value": ["status_request"]},
        ),
        (
            cx509.Extension(
                cx509.CRLNumber.oid, value=cx509.CRLNumber(3), critical=False
            ),
            {"critical": False, "value": 3},
        ),
        (
            cx509.Extension(
                cx509.DeltaCRLIndicator.oid,
                value=cx509.DeltaCRLIndicator(3),
                critical=False,
            ),
            {"critical": False, "value": 3},
        ),
        (
            cx509.Extension(
                cx509.CRLReason.oid,
                value=cx509.CRLReason(cx509.ReasonFlags("superseded")),
                critical=False,
            ),
            {"critical": False, "value": "superseded"},
        ),
        (
            cx509.Extension(
                cx509.InvalidityDate.oid,
                value=cx509.InvalidityDate(
                    datetime.strptime("2022-10-11 13:37:42", "%Y-%m-%d %H:%M:%S")
                ),
                critical=False,
            ),
            {"critical": False, "value": "2022-10-11 13:37:42"},
        ),
    ],
)
def test_render_extension(inpt, expected):
    ret = x509.render_extension(inpt)
    assert ret == expected


@pytest.fixture
def ca_cert():
    return """\
-----BEGIN CERTIFICATE-----
MIIDODCCAiCgAwIBAgIIbfpgqP0VGPgwDQYJKoZIhvcNAQELBQAwKzELMAkGA1UE
BhMCVVMxDTALBgNVBAMMBFRlc3QxDTALBgNVBAoMBFNhbHQwHhcNMjIxMTE1MTQw
NDMzWhcNMzIxMTEyMTQwNDMzWjArMQswCQYDVQQGEwJVUzENMAsGA1UEAwwEVGVz
dDENMAsGA1UECgwEU2FsdDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEB
AOGTScvrjcEt6vsJcG9RUp6fKaDNDWZnJET0omanK9ZwaoGpJPp8UDYe/8ADeI7N
10wdyB4oDM9gRDjInBtdQO/PsrmKZF6LzqVFgLMxu2up+PHMi9z6B2P4esIAzMu9
PYxc9zH4HzLImHqscVD2HCabsjp9X134Af7hVY5NN/W/4qTP7uOM20wSG2TPI6+B
tA9VyPbEPMPRzXzrqc45rVYe6kb2bT84GE93Vcu/e5JZ/k2AKD8Hoa2cxLPsTLq5
igl+D+k+dfUtiABiKPvVQiYBsD1fyHDn2m7B6pCgvrGqHjsoAKufgFnXy6PJRg7n
vQfaxSiusM5s+VS+fjlvgwsCAwEAAaNgMF4wDwYDVR0TBAgwBgEB/wIBATALBgNV
HQ8EBAMCAQYwHQYDVR0OBBYEFFzy8fRTKSOe7kBakqO0Ki71potnMB8GA1UdIwQY
MBaAFFzy8fRTKSOe7kBakqO0Ki71potnMA0GCSqGSIb3DQEBCwUAA4IBAQBZS4MP
fXYPoGZ66seM+0eikScZHirbRe8vHxHkujnTBUjQITKm86WeQgeBCD2pobgBGZtt
5YFozM4cERqY7/1BdemUxFvPmMFFznt0TM5w+DfGWVK8un6SYwHnmBbnkWgX4Srm
GsL0HHWxVXkGnFGFk6Sbo3vnN7CpkpQTWFqeQQ5rHOw91pt7KnNZwc6I3ZjrCUHJ
+UmKKrga16a4Q+8FBpYdphQU609npo/0zuaE6FyiJYlW3tG+mlbbNgzY/+eUaxt2
9Bp9mtA+Hkox551Mfpq45Oi+ehwMt0xjZCjuFCM78oiUdHCGO+EmcT7ogiYALiOF
LN1w5sybsYwIw6QN
-----END CERTIFICATE-----
"""


@pytest.fixture
def ca_key():
    return """\
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA4ZNJy+uNwS3q+wlwb1FSnp8poM0NZmckRPSiZqcr1nBqgakk
+nxQNh7/wAN4js3XTB3IHigMz2BEOMicG11A78+yuYpkXovOpUWAszG7a6n48cyL
3PoHY/h6wgDMy709jFz3MfgfMsiYeqxxUPYcJpuyOn1fXfgB/uFVjk039b/ipM/u
44zbTBIbZM8jr4G0D1XI9sQ8w9HNfOupzjmtVh7qRvZtPzgYT3dVy797kln+TYAo
PwehrZzEs+xMurmKCX4P6T519S2IAGIo+9VCJgGwPV/IcOfabsHqkKC+saoeOygA
q5+AWdfLo8lGDue9B9rFKK6wzmz5VL5+OW+DCwIDAQABAoIBAFfImc9hu6iR1gAb
jEXFwAE6r1iEc9KGEPdEvG52X/jzhn8u89UGy7BEIAL5VtE8Caz1agtSSqnpLKNs
blO31q18hnDuCmFAxwpKIeuaTvV3EAoJL+Su6HFfIWaeKRSgcHNPOmOXy4xXw/75
XJ/FJu9fZ9ybLaHEAgLObh0Sr9RSPQbZ72ZawPP8+5WCbR+2w90RApHXQL0piSbW
lIx1NE6o5wQb3vik8z/k5FqLCY2a8++WNyfvS+WWFY5WXGI7ZiDDQk46gnslquH2
Lon5CEn3JlTGQFhxaaa2ivssscf2lA2Rvm2E8o1rdZJS2OpSE0ai4TXY9XnyjZj1
5usWIwECgYEA+3Mwu03A7PyLEBksS/u3MSo/176S9lF/uXcecQNdhAIalUZ8AgV3
7HP2yI9ZC0ekA809ZzFjGFostXm9VfUOEZ549jLOMzvBtCdaI0aBUE8icu52fX4r
fT2NY6hYgz5/fxD8sq1XH/fqNNexABwtViH6YAly/9A1/8M3BOWt72UCgYEA5ag8
sIfiBUoWd1sS6qHDuugWlpx4ZWYC/59XEJyCN2wioP8qFji/aNZxF1wLfyQe/zaa
YBFusjsBnSfBU1p4UKCRHWQ9/CnC0DzqTkyKC4Fv8GuxgywNm5W9gPKk7idHP7mw
e+7Uvf1pOQccqEPh7yltpW+Xw27gfsC2DMAIGa8CgYByv/q5P56PiCCeVB6W/mR3
l2RTPLEsn7y+EtJdmL+QgrVG8kedVImJ6tHwbRqhvyvmYD9pXGxwrJZCqy/wjkjB
WaSyFjVrxBV99Yd5Ga/hyntaH+ELHA0UtoZTuHvMSTU9866ei+R6vlSvkM9B0ZoO
+KqeMTG99HLwKVJudbKO0QKBgQCd33U49XBOqoufKSBr4yAmUH2Ws6GgMuxExUiY
xr5NUyzK+B36gLA0ZZYAtOnCURZt4x9kgxdRtnZ5jma74ilrY7XeOpbRzfN6KyX3
BW6wUh6da6rvvUztc5Z+Gk9+18mG6SOFTr04jgfTiCwPD/s06YnSfFAbrRDukZOU
WD45SQKBgBvjSwl3AbPoJnRjZjGuCUMKQKrLm30xCeorxasu+di/4YV5Yd8VUjaO
mYyqXW6bQndKLuXT+AXtCd/Xt2sI96z8mc0G5fImDUxQjMUuS3RyQK357cEOu8Zy
HdI7Pfaf/l0HozAw/Al+LXbpmSBdfmz0U/EGAKRqXMW5+vQ7XHXD
-----END RSA PRIVATE KEY-----"""


def test_build_crl_accounts_for_local_time_zone(ca_key, ca_cert):
    curr_time = datetime.now(tz=timezone(timedelta(hours=1)))
    curr_time_naive = curr_time.replace(tzinfo=None)

    def dtn(tz=None):
        if tz is None:
            return curr_time_naive
        return curr_time

    curr_time_utc = curr_time.astimezone(timezone.utc).replace(microsecond=0)
    curr_time_utc_naive = curr_time_utc.replace(tzinfo=None)
    privkey = cprim.serialization.load_pem_private_key(ca_key.encode(), password=None)
    cert = cx509.load_pem_x509_certificate(ca_cert.encode())
    with patch("salt.utils.x509.datetime") as fakedate:
        fakedate.today.return_value = curr_time_naive
        fakedate.now.side_effect = dtn
        fakedate.utcnow.return_value = curr_time_utc_naive
        builder, _ = x509.build_crl(privkey, [], signing_cert=cert)
        crl = builder.sign(privkey, algorithm=cprim.hashes.SHA256())
    try:
        assert crl.last_update_utc == curr_time_utc
    except AttributeError:
        assert crl.last_update == curr_time_utc_naive


@pytest.mark.parametrize("timestr", ("not_before", "not_after"))
def test_build_crt_malformed_date_raises_salt_invocation_error(ca_key, timestr):
    """
    A malformed not_before/not_after must surface as a SaltInvocationError
    (caught by the state) instead of a raw ValueError from strptime.
    """
    with pytest.raises(
        salt.exceptions.SaltInvocationError, match=f"Invalid date.*{timestr}.*"
    ):
        x509.build_crt(ca_key, **{timestr: "booh"})


@pytest.mark.parametrize("timestr", ("not_after", "revocation_date"))
def test_build_crl_malformed_date_raises_salt_invocation_error(
    ca_cert, ca_key, timestr
):
    """
    Malformed date definitions must surface as a SaltInvocationError
    (caught by the state) instead of a raw ValueError from strptime.
    """
    with pytest.raises(
        salt.exceptions.SaltInvocationError, match=f"Invalid date.*{timestr}.*"
    ):
        x509.build_crl(ca_key, [{"serial_number": 1, timestr: "booh"}], ca_cert)
