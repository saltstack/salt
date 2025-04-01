from textwrap import dedent

import pytest

import salt.utils.x509 as x509

cx509 = pytest.importorskip("cryptography.x509")


@pytest.fixture
def b64cert_with_prefix():
    return (
        "b64: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"
    )


@pytest.fixture
def b64cert(b64cert_with_prefix):
    return b64cert_with_prefix[4:]


@pytest.fixture
def pemcert():
    return dedent(
        """-----BEGIN CERTIFICATE-----
        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
        -----END CERTIFICATE-----"""
    )


def test_load_file_or_bytes_base64_der_with_b64_prefix(b64cert_with_prefix):
    der = x509.load_file_or_bytes(b64cert_with_prefix)
    cert = cx509.load_der_x509_certificate(der)
    assert (
        cert.subject.rfc4514_string() == "CN=nifi.cdx.eitr.dev,L=Sykesville,ST=MD,C=US"
    )


def test_load_file_or_bytes_base64_der(b64cert):
    der = x509.load_file_or_bytes(b64cert)
    cert = cx509.load_der_x509_certificate(der)
    assert (
        cert.subject.rfc4514_string() == "CN=nifi.cdx.eitr.dev,L=Sykesville,ST=MD,C=US"
    )


def test_load_file_or_bytes_pem(pemcert):
    pem = x509.load_file_or_bytes(pemcert)
    cert = cx509.load_pem_x509_certificate(pem)
    assert (
        cert.subject.rfc4514_string() == "CN=nifi.cdx.eitr.dev,L=Sykesville,ST=MD,C=US"
    )
