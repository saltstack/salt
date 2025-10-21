import logging
from pathlib import Path

import pytest

from tests.support.helpers import system_python_version

try:
    from cryptography.hazmat.primitives import serialization

    import salt.utils.x509 as x509util

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False


log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skipif(HAS_LIBS is False, reason="Needs cryptography library"),
    pytest.mark.skipif(
        system_python_version() < (3, 10),
        reason="System Python too old for these tests",
    ),
]


@pytest.fixture(scope="module")
def other_backend(cert_exts, ssh_salt_ssh_cli, sshpki_salt_master, ca_pub):
    wrapper = f"""\
__virtualname__ = "other_backend"


def get_signing_policy(signing_policy, ca_server=None, donotfail=False):
    if donotfail is False:
        raise ValueError("Was not instructed to not fail :|")
    return {{
        "signing_public_key": "{ca_pub.strip()}",
        "cert_type": "user",
        "key_id": "saltstacktest",
        "serial_number": "03:68:6D:B3:0D:5E:F2:54",
        "not_before": "2023-06-28 08:03:14",
        "not_after": "2023-06-29 08:03:14",
        "critical_options": {{"force-command": "echo hi", "no-port-forwarding": True}},
        "extensions": {{"permit-X11-forwarding": True, "permit-agent-forwarding": True}},
        "valid_principals": ["salt", "stack"],
    }}

def create_certificate(
    ca_server=None,
    signing_policy=None,
    path=None,
    overwrite=False,
    raw=False,
    **kwargs,
):
    if not kwargs.get("donotfail"):
        raise ValueError("Was not instructed to not fail :|")
    return '''\
{cert_exts}'''
"""
    wrapper_dir = Path(sshpki_salt_master.config["file_roots"]["base"][0]) / "_wrapper"
    wrapper_tempfile = pytest.helpers.temp_file(
        "other_backend.py", wrapper, wrapper_dir
    )
    try:
        with wrapper_tempfile:
            ret = sshpki_salt_master.salt_run_cli().run("fileserver.update")
            assert ret.returncode == 0
            ret = sshpki_salt_master.salt_run_cli().run("saltutil.sync_wrapper")
            assert ret.returncode == 0
            assert "wrapper.other_backend" in ret.data
            yield
    finally:
        ret = ssh_salt_ssh_cli.run("saltutil.sync_wrapper")
        assert ret.returncode == 0


@pytest.fixture(scope="module", autouse=True)
def cm_wrapper(sshpki_salt_master):
    state_contents = """
    {{
        salt["ssh_pki.certificate_managed_wrapper"](
            pillar["args"]["name"],
            ca_server=pillar["args"]["ca_server"],
            signing_policy=pillar["args"]["signing_policy"],
            backend=pillar["args"].get("backend"),
            backend_args=pillar["args"].get("backend_args"),
            private_key_managed=pillar["args"].get("private_key_managed"),
            private_key=pillar["args"].get("private_key"),
            private_key_passphrase=pillar["args"].get("private_key_passphrase"),
            public_key=pillar["args"].get("public_key"),
            certificate_managed=pillar["args"].get("certificate_managed"),
            test=opts.get("test")
        ) | yaml(false)
    }}
    """
    with sshpki_salt_master.state_tree.base.temp_file("cert.sls", state_contents):
        yield


@pytest.fixture
def pk_tgt(tmp_path):
    return str(tmp_path / "managed_key")


@pytest.fixture
def cert_args(ca_minion_id, sshpki_data, tmp_path):
    return {
        "name": f"{tmp_path}/cert",
        "ca_server": ca_minion_id,
        "signing_policy": "testpolicy",
        "private_key": str(sshpki_data),
        "certificate_managed": {
            "key_id": "from_args",
        },
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


@pytest.fixture(params=[{}])
def existing_cert(ssh_salt_ssh_cli, cert_args, ca_key, rsa_privkey, request, pk_tgt):
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
    ret = ssh_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    cert = _get_cert(cert_args["name"])
    assert cert.key_id == b"from_signing_policy"
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


@pytest.fixture(params=["sshpki_data"])
def existing_symlink(request):
    existing = request.getfixturevalue(request.param)
    test_file = Path(existing).with_name("symlink")
    test_file.symlink_to(existing)
    try:
        yield test_file
    finally:
        test_file.unlink(missing_ok=True)


@pytest.mark.usefixtures("_check_bcrypt")
def test_certificate_managed_remote(ssh_salt_ssh_cli, cert_args, ca_key, rsa_privkey):
    ret = ssh_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    cert = _get_cert(cert_args["name"])
    assert cert.key_id == b"from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


@pytest.mark.usefixtures("_check_bcrypt")
def test_certificate_managed_remote_with_privkey_managed(
    ssh_salt_ssh_cli, cert_args, tmp_path, ca_key
):
    pk_args = {"name": str(tmp_path / "newkey")}
    cert_args["private_key_managed"] = pk_args
    ret = ssh_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    cert = _get_cert(cert_args["name"])
    privkey = _get_privkey(pk_args["name"])
    assert cert.key_id == b"from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, privkey)
    assert ret.data
    assert len(ret.data) == 4
    for state in ret.data:
        # file.managed creates the files before moving data into them
        assert ret.data[state]["changes"]


@pytest.mark.usefixtures("_check_bcrypt")
@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_no_changes(ssh_salt_ssh_cli, cert_args):
    ret = ssh_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    assert ret.data[next(iter(ret.data))]["changes"] == {}


@pytest.mark.usefixtures("_check_bcrypt")
@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize("existing_cert", ({"private_key_managed": {}},), indirect=True)
def test_certificate_managed_remote_no_changes_with_privkey_managed(
    ssh_salt_ssh_cli, cert_args, ca_key, pk_tgt
):
    privkey = _get_privkey(pk_tgt)
    ret = ssh_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    cert = _get_cert(cert_args["name"])
    assert cert.key_id == b"from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, privkey)
    assert ret.data
    assert len(ret.data) == 4
    for state in ret.data:
        assert ret.data[state]["changes"] == {}


@pytest.mark.usefixtures("_check_bcrypt")
@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_policy_change(ssh_salt_ssh_cli, cert_args):
    cert_args["signing_policy"] = "testchangepolicy"
    ret = ssh_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    assert "key_id" in ret.data[next(iter(ret.data))]["changes"]
    cert = _get_cert(cert_args["name"])
    assert cert.key_id == b"from_changed_signing_policy"


@pytest.mark.usefixtures("_check_bcrypt")
@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize("existing_cert", ({"private_key_managed": {}},), indirect=True)
def test_certificate_managed_remote_policy_change_with_privkey_managed(
    ssh_salt_ssh_cli, cert_args, ca_key, pk_tgt
):
    privkey = _get_privkey(pk_tgt)
    cert_args["signing_policy"] = "testchangepolicy"
    ret = ssh_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    cert = _get_cert(cert_args["name"])
    assert cert.key_id == b"from_changed_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, privkey)
    assert ret.data
    assert len(ret.data) == 4
    for state in ret.data:
        if state.startswith("ssh_pki"):
            if state.endswith("private_key_managed_ssh"):
                assert not ret.data[state]["changes"]
            else:
                assert "key_id" in ret.data[state]["changes"]
        else:
            # file sub state runs
            assert not ret.data[state]["changes"]


@pytest.mark.usefixtures("_check_bcrypt")
@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize(
    "existing_cert", ({"private_key_managed": {"new": True}},), indirect=True
)
def test_certificate_managed_remote_policy_change_with_privkey_managed_new(
    ssh_salt_ssh_cli, cert_args, ca_key, pk_tgt
):
    privkey = _get_privkey(pk_tgt)
    cert_args["signing_policy"] = "testchangepolicy"
    ret = ssh_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    cert = _get_cert(cert_args["name"])
    assert cert.key_id == b"from_changed_signing_policy"
    assert _signed_by(cert, ca_key)
    assert not _belongs_to(cert, privkey)
    new_privkey = _get_privkey(pk_tgt)
    assert _belongs_to(cert, new_privkey)
    assert ret.data
    assert len(ret.data) == 4
    for state in ret.data:
        if state.startswith("ssh_pki"):
            if state.endswith("private_key_managed_ssh"):
                assert ret.data[state]["changes"]
            else:
                assert "key_id" in ret.data[state]["changes"]
        else:
            # file sub state runs
            assert not ret.data[state]["changes"]


@pytest.mark.usefixtures("_check_bcrypt")
@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_signing_key_change(ssh_salt_ssh_cli, cert_args):
    cert_args["signing_policy"] = "testchangecapolicy"
    ret = ssh_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    assert ret.data
    changes = ret.data[next(iter(ret.data))]["changes"]
    assert changes
    assert "signing_private_key" in changes


@pytest.mark.usefixtures("_check_bcrypt")
@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_no_changes_signing_policy_override(
    ssh_salt_ssh_cli, cert_args
):
    cert_args["extensions"] = {"permit-user-rc": True}
    cert_args["critical_options"] = {"force-command": "rm -rf /"}
    cert_args["cert_type"] = "host"
    ret = ssh_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    assert ret.data[next(iter(ret.data))]["changes"] == {}


@pytest.mark.usefixtures("_check_bcrypt")
@pytest.mark.parametrize("overwrite", (False, True))
def test_certificate_managed_privkey_managed_existing_not_a_privkey(
    ssh_salt_ssh_cli, cert_args, ca_key, existing_file, overwrite
):
    """
    If an existing managed private key cannot be read, it should be
    possible to overwrite it by specifying `overwrite: true`.
    """
    _test_certificate_managed_existing_path(
        ssh_salt_ssh_cli, cert_args, ca_key, existing_file, overwrite
    )


@pytest.mark.usefixtures("_check_bcrypt")
@pytest.mark.parametrize("overwrite", (False, True))
def test_certificate_managed_privkey_managed_existing_symlink(
    ssh_salt_ssh_cli, cert_args, ca_key, existing_symlink, overwrite
):
    """
    If an existing managed private key is a symlink, it will be
    written over instead of followed. Ensure the user is warned
    about that and needs to opt-in.
    """
    # This test is essentially the same as for existing files, but
    # parametrized fixtures cannot be requested with request.getfixturevalue
    _test_certificate_managed_existing_path(
        ssh_salt_ssh_cli, cert_args, ca_key, existing_symlink, overwrite
    )


def _test_certificate_managed_existing_path(
    ssh_salt_ssh_cli, cert_args, ca_key, existing, overwrite
):
    cert_args["private_key_managed"] = {
        "name": str(existing),
        "overwrite": overwrite,
    }
    ret = ssh_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert (ret.returncode == 0) is overwrite
    if not overwrite:
        state = next(x for x in ret.data if x.endswith("private_key_managed_ssh"))
        assert "pass overwrite: true" in ret.data[state]["comment"]
        return
    cert = _get_cert(cert_args["name"])
    privkey = _get_privkey(cert_args["private_key_managed"]["name"])
    assert cert.key_id == b"from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, privkey)
    assert ret.data
    assert len(ret.data) == 4
    for state in ret.data:
        if state.startswith("ssh_pki") or "_crt" in state:
            assert ret.data[state]["changes"]
            if "symlink" in existing.name and state.endswith("private_key_managed_ssh"):
                assert "removed_link" in ret.data[state]["changes"]
        else:
            # key file sub state run
            assert bool(ret.data[state]["changes"]) is ("symlink" in existing.name)


@pytest.mark.usefixtures("_check_bcrypt")
def test_certificate_managed_existing_not_a_cert(
    ssh_salt_ssh_cli, cert_args, existing_file, rsa_privkey, ca_key
):
    """
    If `name` is not a valid certificate, a new one should be issued at the path
    """
    cert_args["name"] = str(existing_file)
    ret = ssh_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    cert_state = next(x for x in ret.data if x.endswith("certificate_managed_ssh"))
    assert "created" in ret.data[cert_state]["changes"]
    assert ret.data[cert_state]["changes"]["created"] == str(existing_file)
    cert = _get_cert(cert_args["name"])
    assert cert.key_id == b"from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


@pytest.mark.usefixtures("_check_bcrypt")
@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_renew(ssh_salt_ssh_cli, cert_args):
    cert_cur = _get_cert(cert_args["name"])
    cert_args["certificate_managed"]["ttl_remaining"] = "999d"
    ret = ssh_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    cert_new = _get_cert(cert_args["name"])
    assert cert_new.serial != cert_cur.serial


@pytest.mark.usefixtures("other_backend")
def test_certificate_managed_different_backend(ssh_salt_ssh_cli, cert_args, cert_exts):
    cert_args["backend"] = "other_backend"
    cert_args["backend_args"] = {"donotfail": True}
    ret = ssh_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    changes = ret.data[next(iter(ret.data))]["changes"]
    assert changes
    assert changes.get("created") == cert_args["name"]
    cert = _get_cert(cert_args["name"])
    assert cert.public_bytes().decode().strip() == cert_exts


@pytest.mark.usefixtures("_check_bcrypt")
@pytest.mark.usefixtures("other_backend")
@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_existing_different_backend(
    ssh_salt_ssh_cli, cert_args, cert_exts
):
    cert_args.pop("ca_server", None)
    cert_args["backend"] = "other_backend"
    cert_args["backend_args"] = {"donotfail": True}
    ret = ssh_salt_ssh_cli.run("state.apply", "cert", pillar={"args": cert_args})
    assert ret.returncode == 0
    changes = ret.data[next(iter(ret.data))]["changes"]
    assert changes
    assert not changes["extensions"]["added"]
    assert not changes["extensions"]["changed"]
    assert set(changes["extensions"]["removed"]) == {
        "permit-port-forwarding",
        "permit-pty",
    }
    assert set(changes["principals"]["added"]) == {"salt", "stack"}
    assert set(changes["principals"]["removed"]) == {"from_signing_policy"}
    assert changes["key_id"] == {"old": "from_signing_policy", "new": "saltstacktest"}
    assert "critical_options" not in changes
    cert = _get_cert(cert_args["name"])
    assert cert.public_bytes().decode().strip() == cert_exts


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
    if hasattr(pk, "private_bytes"):
        return pk
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
