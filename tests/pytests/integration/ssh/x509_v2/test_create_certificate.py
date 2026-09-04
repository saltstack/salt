"""
Tests for the x509_v2 module
"""

import base64
import copy
import logging
from pathlib import Path

import pytest

from salt.defaults.exitcodes import EX_AGGREGATE

try:
    import cryptography
    import cryptography.x509 as cx509
    from cryptography.hazmat.primitives.serialization import pkcs7, pkcs12

    import salt.utils.x509 as x509util

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

CRYPTOGRAPHY_VERSION = tuple(int(x) for x in cryptography.__version__.split("."))

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skipif(HAS_LIBS is False, reason="Needs cryptography library"),
]


@pytest.fixture
def cert_args(ca_minion_id, x509_data):
    return {
        "ca_server": ca_minion_id,
        "signing_policy": "testpolicy",
        "private_key": str(x509_data),
        "CA": "from_args",
    }


@pytest.fixture
def cert_args_exts():
    return {
        "basicConstraints": "critical, CA:TRUE, pathlen:1",
        "keyUsage": "critical, cRLSign, keyCertSign, digitalSignature",
        "extendedKeyUsage": "OCSPSigning",
        "subjectKeyIdentifier": "hash",
        "authorityKeyIdentifier": "keyid:always",
        "issuerAltName": "DNS:mysalt.ca",
        "authorityInfoAccess": "OCSP;URI:http://ocsp.salt.ca/",
        "subjectAltName": "DNS:me.salt.ca",
        "crlDistributionPoints": None,
        "certificatePolicies": "1.2.4.5",
        "policyConstraints": "requireExplicitPolicy:3",
        "inhibitAnyPolicy": 2,
        "nameConstraints": "permitted;IP:192.168.0.0/255.255.0.0,excluded;email:.com",
        "noCheck": True,
        "tlsfeature": "status_request",
    }


def test_sign_remote_certificate(x509_salt_ssh_cli, cert_args, ca_key, rsa_privkey):
    ret = x509_salt_ssh_cli.run("x509.create_certificate", **cert_args)
    assert ret.returncode == 0
    assert ret.data
    cert = _get_cert(ret.data)
    assert cert.subject.rfc4514_string() == "CN=from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


def test_sign_remote_certificate_match(
    x509_salt_ssh_cli, cert_args, ca_key, rsa_privkey
):
    cert_args["signing_policy"] = "testmatchpolicy"
    ret = x509_salt_ssh_cli.run("x509.create_certificate", **cert_args)
    assert ret.returncode == 0
    assert ret.data
    cert = _get_cert(ret.data)
    assert cert.subject.rfc4514_string() == "CN=from_matching_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


# Compound matching fails since
# a) before using the match runner: peer calls cannot target SSH minions
# b) after using the match runner: the SSH minion data is not cached as usual
# We cannot check though since the expression is only present on the CA minion.


def test_sign_remote_certificate_enc(x509_salt_ssh_cli, cert_args, ca_key, rsa_privkey):
    cert_args["private_key"] += "_enc"
    cert_args["private_key_passphrase"] = "hunter2"
    ret = x509_salt_ssh_cli.run("x509.create_certificate", **cert_args)
    assert ret.returncode == 0
    assert ret.data
    cert = _get_cert(ret.data)
    assert cert.subject.rfc4514_string() == "CN=from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


def test_sign_remote_certificate_ca_enc(
    x509_salt_ssh_cli, cert_args, ca_key, rsa_privkey
):
    cert_args["signing_policy"] = "testencpolicy"
    ret = x509_salt_ssh_cli.run("x509.create_certificate", **cert_args)
    assert ret.returncode == 0
    assert ret.data
    cert = _get_cert(ret.data)
    assert cert.subject.rfc4514_string() == "CN=from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


def test_sign_remote_certificate_pubkey(
    x509_salt_ssh_cli, cert_args, x509_data, ca_key, rsa_privkey
):
    cert_args.pop("private_key")
    cert_args["public_key"] = str(x509_data.parent / "key_pub")
    ret = x509_salt_ssh_cli.run("x509.create_certificate", **cert_args)
    assert ret.returncode == 0
    assert ret.data
    cert = _get_cert(ret.data)
    assert cert.subject.rfc4514_string() == "CN=from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


def test_sign_remote_certificate_csr(
    x509_salt_ssh_cli, cert_args, x509_data, ca_key, rsa_privkey
):
    cert_args.pop("private_key")
    cert_args["csr"] = str(x509_data.parent / "csr")
    ret = x509_salt_ssh_cli.run("x509.create_certificate", **cert_args)
    assert ret.returncode == 0
    assert ret.data
    cert = _get_cert(ret.data)
    assert cert.subject.rfc4514_string() == "CN=from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


def test_sign_remote_certificate_nonexistent_policy(x509_salt_ssh_cli, cert_args):
    cert_args["signing_policy"] = "missingpolicy"
    ret = x509_salt_ssh_cli.run("x509.create_certificate", **cert_args)
    assert ret.returncode == EX_AGGREGATE
    assert ret.data
    assert "signing_policy must be specified and defined" in ret.data


def test_sign_remote_certificate_disallowed_policy(x509_salt_ssh_cli, cert_args):
    cert_args["signing_policy"] = "testmatchfailpolicy"
    ret = x509_salt_ssh_cli.run("x509.create_certificate", **cert_args)
    assert ret.returncode == EX_AGGREGATE
    assert ret.data
    assert "minion not permitted to use specified signing policy" in ret.data


@pytest.mark.skipif(
    CRYPTOGRAPHY_VERSION[0] < 37,
    reason="Parsing of RFC4514 strings requires cryptography >= 37",
)
def test_sign_remote_certificate_no_subject_override(
    x509_salt_ssh_cli, cert_args, ca_key, rsa_privkey, _check_cryptography
):
    """
    Ensure that kwargs from remote requests are overridden
    by signing policies as is done for regular ones
    """
    if _check_cryptography < (37,):
        pytest.skip(
            "Parsing of RFC4514 strings requires cryptography >= 37 on the host Python"
        )
    cert_args["subject"] = {"O": "from_call"}
    cert_args["signing_policy"] = "testsubjectstrpolicy"
    ret = x509_salt_ssh_cli.run("x509.create_certificate", **cert_args)
    assert ret.returncode == 0
    assert ret.data
    cert = _get_cert(ret.data)
    assert cert.subject.rfc4514_string() == "CN=from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


@pytest.mark.skipif(
    CRYPTOGRAPHY_VERSION[0] < 37,
    reason="Parsing of RFC4514 strings requires cryptography >= 37",
)
def test_sign_remote_certificate_no_name_attribute_override(
    x509_salt_ssh_cli, cert_args, ca_key, rsa_privkey, _check_cryptography
):
    """
    Ensure that kwargs from remote requests are overridden
    by signing policies as is done for regular ones
    """
    if _check_cryptography < (37,):
        pytest.skip(
            "Parsing of RFC4514 strings requires cryptography >= 37 on the host Python"
        )
    cert_args["subject"] = "CN=from_call"
    cert_args["signing_policy"] = "testnosubjectpolicy"
    ret = x509_salt_ssh_cli.run("x509.create_certificate", **cert_args)
    assert ret.returncode == 0
    assert ret.data
    cert = _get_cert(ret.data)
    assert cert.subject.rfc4514_string() == "CN=from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


def test_get_signing_policy_remote(x509_salt_ssh_cli, cert_args, ca_minion_config):
    testpolicy = copy.deepcopy(
        ca_minion_config["x509_signing_policies"]["testencpolicy"]
    )
    testpolicy.pop("signing_private_key", None)
    testpolicy.pop("signing_private_key_passphrase", None)
    ret = x509_salt_ssh_cli.run(
        "x509.get_signing_policy", "testencpolicy", ca_server=cert_args["ca_server"]
    )
    assert ret.returncode == 0
    assert ret.data
    assert ret.data == testpolicy


def test_get_signing_policy_remote_deprecated_name(
    x509_salt_ssh_cli, cert_args, ca_minion_config
):
    ret = x509_salt_ssh_cli.run(
        "x509.get_signing_policy",
        "testdeprecatednamepolicy",
        ca_server=cert_args["ca_server"],
    )
    assert ret.returncode == 0
    assert ret.data
    assert "commonName" not in ret.data
    assert "CN" in ret.data
    assert ret.data["CN"] == "deprecated"


def test_get_signing_policy_remote_deprecated_ext(
    x509_salt_ssh_cli, cert_args, ca_minion_config
):
    ret = x509_salt_ssh_cli.run(
        "x509.get_signing_policy",
        "testdeprecatedextpolicy",
        ca_server=cert_args["ca_server"],
    )
    assert ret.returncode == 0
    assert ret.data
    assert "X509v3 Basic Constraints" not in ret.data
    assert "basicConstraints" in ret.data
    assert ret.data["basicConstraints"] == "critical CA:FALSE"


def test_sign_remote_certificate_ext_override(
    x509_salt_ssh_cli, cert_args, cert_args_exts
):
    cert_args.update(cert_args_exts)
    cert_args["signing_policy"] = "testextpolicy"
    ret = x509_salt_ssh_cli.run("x509.create_certificate", **cert_args)
    assert ret.returncode == 0
    assert ret.data
    cert = _get_cert(ret.data)
    assert (
        cert.extensions.get_extension_for_class(cx509.BasicConstraints).value.ca
        is False
    )
    assert (
        cert.extensions.get_extension_for_class(cx509.KeyUsage).value.digital_signature
        is False
    )
    with pytest.raises(cx509.ExtensionNotFound):
        cert.extensions.get_extension_for_class(cx509.ExtendedKeyUsage)
    assert (
        cert.extensions.get_extension_for_class(
            cx509.IssuerAlternativeName
        ).value.get_values_for_type(cx509.DNSName)[0]
        == "salt.ca"
    )
    assert (
        cert.extensions.get_extension_for_class(
            cx509.SubjectAlternativeName
        ).value.get_values_for_type(cx509.DNSName)[0]
        == "sub.salt.ca"
    )


def _belongs_to(cert_or_pubkey, privkey):
    if isinstance(cert_or_pubkey, cx509.Certificate):
        cert_or_pubkey = cert_or_pubkey.public_key()
    return x509util.is_pair(cert_or_pubkey, x509util.load_privkey(privkey))


def _signed_by(cert, privkey):
    return x509util.verify_signature(cert, x509util.load_privkey(privkey).public_key())


def _get_cert(cert, encoding="pem", passphrase=None):
    try:
        p = Path(cert)
        if p.exists():
            cert = p.read_bytes()
    except Exception:  # pylint: disable=broad-except
        pass

    if encoding == "pem":
        if not isinstance(cert, bytes):
            cert = cert.encode()
        return cx509.load_pem_x509_certificate(cert)
    if encoding == "der":
        if not isinstance(cert, bytes):
            cert = base64.b64decode(cert)
        return cx509.load_der_x509_certificate(cert)
    if encoding == "pkcs7_pem":
        if not isinstance(cert, bytes):
            cert = cert.encode()
        return pkcs7.load_pem_pkcs7_certificates(cert)
    if encoding == "pkcs7_der":
        if not isinstance(cert, bytes):
            cert = base64.b64decode(cert)
        return pkcs7.load_der_pkcs7_certificates(cert)
    if encoding == "pkcs12":
        if not isinstance(cert, bytes):
            cert = base64.b64decode(cert)
        if passphrase is not None and not isinstance(passphrase, bytes):
            passphrase = passphrase.encode()
        return pkcs12.load_pkcs12(cert, passphrase)
