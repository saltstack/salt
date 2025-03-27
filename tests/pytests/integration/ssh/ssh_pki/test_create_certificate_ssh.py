import copy
import logging
from pathlib import Path

import pytest

from salt.defaults.exitcodes import EX_AGGREGATE

try:
    import cryptography
    from cryptography.hazmat.primitives import serialization

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
def cert_args(ca_minion_id, sshpki_data):
    return {
        "ca_server": ca_minion_id,
        "signing_policy": "testhostpolicy",
        "private_key": str(sshpki_data),
        "key_id": "from_args",
    }


@pytest.fixture
def cert_arg_exts():
    return {
        "permit-X11-forwarding": True,
        "permit-agent-forwarding": True,
        "permit-port-forwarding": True,
        "permit-pty": True,
        "permit-user-rc": False,
    }


@pytest.fixture
def cert_expected_exts():
    return {
        b"permit-X11-forwarding": b"",
        b"permit-agent-forwarding": b"",
        b"permit-port-forwarding": b"",
        b"permit-pty": b"",
    }


@pytest.fixture
def cert_arg_opts():
    return {
        "force-command": "echo hi",
        "no-port-forwarding": True,
        "verify-required": False,
    }


@pytest.fixture
def cert_expected_opts():
    return {
        b"force-command": b"echo hi",
        b"no-port-forwarding": b"",
    }


def test_sign_remote_certificate(ssh_salt_ssh_cli, cert_args, ca_key, rsa_privkey):
    ret = ssh_salt_ssh_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.returncode == 0
    assert ret.data
    cert = _get_cert(ret.data)
    assert cert.key_id == b"from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


def test_sign_remote_certificate_match(
    ssh_salt_ssh_cli, cert_args, ca_key, rsa_privkey
):
    cert_args["signing_policy"] = "testmatchpolicy"
    ret = ssh_salt_ssh_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.returncode == 0
    assert ret.data
    cert = _get_cert(ret.data)
    assert cert.key_id == b"from_matching_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


# Compound matching fails since the SSH minion data is not cached as usual.
# We cannot check though since the expression is only present on the CA minion.


def test_sign_remote_certificate_enc(ssh_salt_ssh_cli, cert_args, ca_key, rsa_privkey):
    cert_args["private_key"] += "_enc"
    cert_args["private_key_passphrase"] = "hunter1"
    ret = ssh_salt_ssh_cli.run("ssh_pki.create_certificate", **cert_args)
    if ret.returncode != 0 and "Need bcrypt module" in str(ret.data):
        pytest.skip("Test needs bcrypt module in the global Python PATH")
    assert ret.returncode == 0
    assert ret.data
    cert = _get_cert(ret.data)
    assert cert.key_id == b"from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


def test_sign_remote_certificate_ca_enc(
    ssh_salt_ssh_cli, cert_args, ca_key, rsa_privkey
):
    cert_args["signing_policy"] = "testencpolicy"
    ret = ssh_salt_ssh_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.returncode == 0
    assert ret.data
    cert = _get_cert(ret.data)
    assert cert.key_id == b"from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


def test_sign_remote_certificate_pubkey(
    ssh_salt_ssh_cli, cert_args, sshpki_data, ca_key, rsa_privkey
):
    cert_args.pop("private_key")
    cert_args["public_key"] = str(sshpki_data.parent / "key_pub")
    ret = ssh_salt_ssh_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.returncode == 0
    assert ret.data
    cert = _get_cert(ret.data)
    assert cert.key_id == b"from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


def test_sign_remote_certificate_nonexistent_policy(ssh_salt_ssh_cli, cert_args):
    cert_args["signing_policy"] = "missingpolicy"
    ret = ssh_salt_ssh_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.returncode == EX_AGGREGATE
    assert ret.data
    assert "signing_policy must be specified and defined" in ret.data


def test_sign_remote_certificate_disallowed_policy(ssh_salt_ssh_cli, cert_args):
    cert_args["signing_policy"] = "testmatchfailpolicy"
    ret = ssh_salt_ssh_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.returncode == EX_AGGREGATE
    assert ret.data
    assert "minion not permitted to use specified signing policy" in ret.data


def test_get_signing_policy_remote(
    ssh_salt_ssh_cli, cert_args, ca_minion_config, ca_pub
):
    testpolicy = copy.deepcopy(
        ca_minion_config["ssh_signing_policies"]["testencpolicy"]
    )
    testpolicy.pop("signing_private_key", None)
    testpolicy.pop("signing_private_key_passphrase", None)
    testpolicy["signing_public_key"] = ca_pub
    ret = ssh_salt_ssh_cli.run(
        "ssh_pki.get_signing_policy", "testencpolicy", ca_server=cert_args["ca_server"]
    )
    assert ret.returncode == 0
    assert ret.data
    assert ret.data == testpolicy


def test_sign_remote_certificate_ext_opt_override(ssh_salt_ssh_cli, cert_args):
    cert_args["signing_policy"] = "testuserpolicy"
    cert_args["extensions"] = {"permit-user-rc": True, "no-touch-required": True}
    cert_args["critical_options"] = {
        "force-command": "rm -rf /",
        "source-address": "1.3.3.7",
        "verify-required": True,
    }
    ret = ssh_salt_ssh_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.returncode == 0
    assert ret.data
    cert = _get_cert(ret.data)
    assert b"permit-user-rc" not in cert.extensions
    assert b"no-touch-required" in cert.extensions
    assert cert.critical_options[b"force-command"] == b"echo hi"
    assert cert.critical_options[b"verify-required"] == b""
    assert b"source-address" not in cert.critical_options


@pytest.mark.parametrize(
    "principals,expected", [(["a", "b"], {b"a", b"b"}), (["a", "d"], {b"a"})]
)
def test_sign_remote_certificate_principals_override(
    ssh_salt_ssh_cli, cert_args, principals, expected
):
    """
    Ensure valid_principals can only be a subset of the ones dictated
    by the signing policy.
    """
    cert_args["signing_policy"] = "testprincipalspolicy"
    cert_args["valid_principals"] = principals
    ret = ssh_salt_ssh_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.returncode == 0
    assert ret.data
    cert = _get_cert(ret.data)
    assert set(cert.valid_principals) == expected


def test_sign_remote_certificate_all_principals_from_local_override(
    ssh_salt_ssh_cli, cert_args
):
    """
    Ensure requesting all principals to be valid when the policy
    dictates a set results in the set from the signing policy to be valid.
    """
    cert_args["signing_policy"] = "testprincipalspolicy"
    cert_args["all_principals"] = True
    ret = ssh_salt_ssh_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.returncode == 0
    assert ret.data
    cert = _get_cert(ret.data)
    assert set(cert.valid_principals) == {b"a", b"b", b"c"}


def test_sign_remote_certificate_all_principals_on_remote_override(
    ssh_salt_ssh_cli, cert_args
):
    """
    Ensure requesting a set of principals to be valid when the policy
    allows all results in only the set to be valid.
    """
    cert_args["signing_policy"] = "testallprincipalspolicy"
    cert_args["valid_principals"] = ["a"]
    ret = ssh_salt_ssh_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.returncode == 0
    assert ret.data
    cert = _get_cert(ret.data)
    assert set(cert.valid_principals) == {b"a"}


def _belongs_to(cert_or_pubkey, privkey):
    if isinstance(cert_or_pubkey, serialization.SSHCertificate):
        cert_or_pubkey = cert_or_pubkey.public_key()
    return x509util.is_pair(cert_or_pubkey, _get_privkey(privkey))


def _signed_by(cert, privkey):
    cert.verify_cert_signature()
    return x509util.is_pair(cert.signature_key(), _get_privkey(privkey))


def _get_cert(cert):
    try:
        p = Path(cert)
        if p.exists():
            cert = p.read_bytes()
    except Exception:  # pylint: disable=broad-except
        pass
    if isinstance(cert, str):
        cert = cert.encode()
    ret = serialization.load_ssh_public_identity(cert)
    if not isinstance(ret, serialization.SSHCertificate):
        raise ValueError(f"Expected SSHCertificate, got {ret.__class__.__name__}")
    return ret


def _get_privkey(pk, passphrase=None):
    try:
        p = Path(pk)
        if p.exists():
            pk = p.read_bytes()
        else:
            pk = pk.encode()
    except Exception:  # pylint: disable=broad-except
        pass
    if isinstance(pk, str):
        pk = pk.encode()
    if passphrase is not None:
        passphrase = passphrase.encode()

    return serialization.load_ssh_private_key(pk, password=passphrase)
