import base64
from pathlib import Path

import pytest

try:
    import cryptography
    import cryptography.x509 as cx509
    from cryptography.hazmat.primitives.serialization import (
        load_der_private_key,
        load_pem_private_key,
        pkcs7,
        pkcs12,
    )

    import salt.utils.x509 as x509util

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False


CRYPTOGRAPHY_VERSION = tuple(int(x) for x in cryptography.__version__.split("."))


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skipif(HAS_LIBS is False, reason="Needs cryptography library"),
]


@pytest.fixture
def cert_args(ca_minion_id, tmp_path, x509_data):
    return {
        "name": str(tmp_path / "cert_managed"),
        "ca_server": ca_minion_id,
        "signing_policy": "testpolicy",
        "private_key": str(x509_data),
        "certificate_managed": {
            "CA": "from_args",
        },
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


@pytest.fixture(scope="module", autouse=True)
def cm_wrapper(x509_salt_master):
    state_contents = """
    {{
        salt["x509.certificate_managed_wrapper"](
            pillar["args"]["name"],
            ca_server=pillar["args"]["ca_server"],
            signing_policy=pillar["args"]["signing_policy"],
            private_key_managed=pillar["args"].get("private_key_managed"),
            private_key=pillar["args"].get("private_key"),
            private_key_passphrase=pillar["args"].get("private_key_passphrase"),
            csr=pillar["args"].get("csr"),
            public_key=pillar["args"].get("public_key"),
            certificate_managed=pillar["args"].get("certificate_managed"),
        ) | yaml(false)
    }}
    """
    with x509_salt_master.state_tree.base.temp_file("cert.sls", state_contents):
        yield


@pytest.fixture
def pk_tgt(tmp_path):
    return str(tmp_path / "managed_key")


@pytest.fixture(params=[{}])
def existing_cert(x509_salt_ssh_cli, cert_args, ca_key, rsa_privkey, request, pk_tgt):
    cert_managed_params = request.param.pop("certificate_managed", {})
    pk_managed = {}
    exp_key = rsa_privkey
    if "private_key_managed" in request.param:
        pk_managed = {"private_key_managed": request.param.pop("private_key_managed")}
        pk_managed["private_key_managed"]["name"] = pk_tgt
        exp_key = pk_tgt
    cert_args.update(request.param)
    cert_args.update(pk_managed)
    cert_args["certificate_managed"].update(cert_managed_params)
    ret = x509_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    cert = _get_cert(cert_args["name"])
    assert cert.subject.rfc4514_string() == "CN=from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, exp_key)
    yield cert_args["name"]


@pytest.fixture(params=["1234"])
def existing_file(tmp_path, request):
    text = request.param
    if callable(text):
        text = request.getfixturevalue(text.__name__)
    test_file = tmp_path / "existingfile"
    test_file.write_text(text)
    yield test_file


@pytest.fixture(params=["x509_data"])
def existing_symlink(request):
    existing = request.getfixturevalue(request.param)
    test_file = Path(existing).with_name("symlink")
    test_file.symlink_to(existing)
    try:
        yield test_file
    finally:
        test_file.unlink(missing_ok=True)


def test_certificate_managed_remote(x509_salt_ssh_cli, cert_args, ca_key, rsa_privkey):
    ret = x509_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    cert = _get_cert(cert_args["name"])
    assert cert.subject.rfc4514_string() == "CN=from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


def test_certificate_managed_remote_with_privkey_managed(
    x509_salt_ssh_cli, cert_args, tmp_path, ca_key
):
    pk_args = {"name": str(tmp_path / "newkey")}
    cert_args["private_key_managed"] = pk_args
    ret = x509_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    cert = _get_cert(cert_args["name"])
    privkey = _get_privkey(pk_args["name"])
    assert cert.subject.rfc4514_string() == "CN=from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, privkey)
    assert ret.data
    assert len(ret.data) == 4
    for state in ret.data:
        # file.managed creates the files before moving data into them
        assert ret.data[state]["changes"]


@pytest.mark.parametrize("overwrite", (False, True))
def test_certificate_managed_privkey_managed_existing_not_a_privkey(
    x509_salt_ssh_cli, cert_args, ca_key, existing_file, overwrite
):
    """
    If an existing managed private key cannot be read, it should be
    possible to overwrite it by specifying `overwrite: true`.
    """
    _test_certificate_managed_existing_privkey_path(
        x509_salt_ssh_cli, cert_args, ca_key, existing_file, overwrite
    )


@pytest.mark.parametrize("overwrite", (False, True))
def test_certificate_managed_privkey_managed_existing_symlink(
    x509_salt_ssh_cli, cert_args, ca_key, existing_symlink, overwrite
):
    """
    If an existing managed private key is a symlink, it will be
    written over instead of followed. Ensure the user is warned
    about that and needs to opt-in.
    """
    # This test is essentially the same as for existing files, but
    # parametrized fixtures cannot be requested with request.getfixturevalue
    _test_certificate_managed_existing_privkey_path(
        x509_salt_ssh_cli, cert_args, ca_key, existing_symlink, overwrite
    )


def _test_certificate_managed_existing_privkey_path(
    x509_salt_ssh_cli, cert_args, ca_key, existing, overwrite
):
    cert_args["private_key_managed"] = {
        "name": str(existing),
        "overwrite": overwrite,
    }
    ret = x509_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert (ret.returncode == 0) is overwrite
    if not overwrite:
        state = next(x for x in ret.data if x.endswith("private_key_managed_ssh"))
        assert "pass overwrite: true" in ret.data[state]["comment"]
        return
    cert = _get_cert(cert_args["name"])
    privkey = _get_privkey(cert_args["private_key_managed"]["name"])
    assert cert.subject.rfc4514_string() == "CN=from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, privkey)
    assert ret.data
    assert len(ret.data) == 4
    for state in ret.data:
        if state.startswith("x509") or "_crt" in state:
            assert ret.data[state]["changes"]
            if "symlink" in existing.name and state.endswith("private_key_managed_ssh"):
                assert "removed_link" in ret.data[state]["changes"]
        else:
            # key file sub state run
            assert bool(ret.data[state]["changes"]) is ("symlink" in existing.name)


def test_certificate_managed_existing_not_a_cert(
    x509_salt_ssh_cli, cert_args, existing_file, rsa_privkey, ca_key
):
    """
    If `name` is not a valid certificate, a new one should be issued at the path
    """
    cert_args["name"] = str(existing_file)
    ret = x509_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    cert_state = next(x for x in ret.data if x.endswith("certificate_managed_ssh"))
    assert "created" in ret.data[cert_state]["changes"]
    assert ret.data[cert_state]["changes"]["created"] == str(existing_file)
    cert = _get_cert(cert_args["name"])
    assert cert.subject.rfc4514_string() == "CN=from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_no_changes(
    x509_salt_ssh_cli, cert_args, ca_key, rsa_privkey
):
    ret = x509_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    assert ret.data[next(iter(ret.data))]["changes"] == {}


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize("existing_cert", ({"private_key_managed": {}},), indirect=True)
def test_certificate_managed_remote_no_changes_with_privkey_managed(
    x509_salt_ssh_cli, cert_args, ca_key, pk_tgt
):
    privkey = _get_privkey(pk_tgt)
    ret = x509_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    cert = _get_cert(cert_args["name"])
    assert cert.subject.rfc4514_string() == "CN=from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, privkey)
    assert ret.data
    assert len(ret.data) == 4
    for state in ret.data:
        assert ret.data[state]["changes"] == {}


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_policy_change(
    x509_salt_ssh_cli, cert_args, ca_key, rsa_privkey
):
    cert_args["signing_policy"] = "testchangepolicy"
    ret = x509_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    assert "subject_name" in ret.data[next(iter(ret.data))]["changes"]
    cert = _get_cert(cert_args["name"])
    assert cert.subject.rfc4514_string() == "CN=from_changed_signing_policy"


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize("existing_cert", ({"private_key_managed": {}},), indirect=True)
def test_certificate_managed_remote_policy_change_with_privkey_managed(
    x509_salt_ssh_cli, cert_args, ca_key, pk_tgt
):
    privkey = _get_privkey(pk_tgt)
    cert_args["signing_policy"] = "testchangepolicy"
    ret = x509_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    cert = _get_cert(cert_args["name"])
    assert cert.subject.rfc4514_string() == "CN=from_changed_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, privkey)
    assert ret.data
    assert len(ret.data) == 4
    for state in ret.data:
        if state.startswith("x509"):
            if state.endswith("private_key_managed_ssh"):
                assert not ret.data[state]["changes"]
            else:
                assert "subject_name" in ret.data[state]["changes"]
        else:
            # file sub state runs
            assert not ret.data[state]["changes"]


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize(
    "existing_cert", ({"private_key_managed": {"new": True}},), indirect=True
)
def test_certificate_managed_remote_policy_change_with_privkey_managed_new(
    x509_salt_ssh_cli, cert_args, ca_key, pk_tgt
):
    privkey = _get_privkey(pk_tgt)
    cert_args["signing_policy"] = "testchangepolicy"
    ret = x509_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    cert = _get_cert(cert_args["name"])
    assert cert.subject.rfc4514_string() == "CN=from_changed_signing_policy"
    assert _signed_by(cert, ca_key)
    assert not _belongs_to(cert, privkey)
    new_privkey = _get_privkey(pk_tgt)
    assert _belongs_to(cert, new_privkey)
    assert ret.data
    assert len(ret.data) == 4
    for state in ret.data:
        if state.startswith("x509"):
            if state.endswith("private_key_managed_ssh"):
                assert ret.data[state]["changes"]
            else:
                assert "subject_name" in ret.data[state]["changes"]
        else:
            # file sub state runs
            assert not ret.data[state]["changes"]


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_ca_cert_change(
    x509_salt_ssh_cli, cert_args, ca_key, rsa_privkey
):
    cert_args["signing_policy"] = "testchangecapolicy"
    ret = x509_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    assert ret.data
    changes = ret.data[next(iter(ret.data))]["changes"]
    assert changes
    assert "signing_private_key" in changes
    assert "issuer_name" in changes
    assert "extensions" in changes
    assert "authorityKeyIdentifier" in changes["extensions"]["changed"]


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_no_changes_signing_policy_override(
    x509_salt_ssh_cli, cert_args, ca_key, rsa_privkey
):
    cert_args["certificate_managed"][
        "basicConstraints"
    ] = "critical, CA:TRUE, pathlen:3"
    ret = x509_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    assert ret.data[next(iter(ret.data))]["changes"] == {}


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_renew(x509_salt_ssh_cli, cert_args):
    cert_cur = _get_cert(cert_args["name"])
    cert_args["certificate_managed"]["days_remaining"] = 999
    ret = x509_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    cert_new = _get_cert(cert_args["name"])
    assert cert_new.serial_number != cert_cur.serial_number


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


def _get_privkey(pk, encoding="pem", passphrase=None):
    try:
        p = Path(pk)
        if p.exists():
            pk = p.read_bytes()
    except Exception:  # pylint: disable=broad-except
        pass
    if passphrase is not None:
        passphrase = passphrase.encode()

    if encoding == "pem":
        if not isinstance(pk, bytes):
            pk = pk.encode()
        return load_pem_private_key(pk, passphrase)
    if encoding == "der":
        if not isinstance(pk, bytes):
            pk = base64.b64decode(pk)
        return load_der_private_key(pk, passphrase)
    if encoding == "pkcs12":
        if not isinstance(pk, bytes):
            pk = base64.b64decode(pk)
        return pkcs12.load_pkcs12(pk, passphrase).key
    raise ValueError("Need correct encoding")
