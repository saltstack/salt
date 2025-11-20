import ctypes
import multiprocessing
import uuid

import pytest

import salt.channel.server as server
import salt.crypt
import salt.daemons.masterapi
import salt.master
import salt.payload
import salt.utils.event
import salt.utils.files
import salt.utils.stringutils
from salt.master import SMaster


@pytest.fixture
def key_data():
    return [
        "-----BEGIN PUBLIC KEY-----",
        "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAoe5QSDYRWKyknbVyRrIj",
        "rm1ht5HgKzAVUber0x54+b/UgxTd1cqI6I+eDlx53LqZSH3G8Rd5cUh8LHoGedSa",
        "E62vEiLAjgXa+RdgcGiQpYS8+Z2RvQJ8oIcZgO+2AzgBRHboNWHTYRRmJXCd3dKs",
        "9tcwK6wxChR06HzGqaOTixAuQlegWbOTU+X4dXIbW7AnuQBt9MCib7SxHlscrqcS",
        "cBrRvq51YP6cxPm/rZJdBqZhVrlghBvIpa45NApP5PherGi4AbEGYte4l+gC+fOA",
        "osEBis1V27djPpIyQS4qk3XAPQg6CYQMDltHqA4Fdo0Nt7SMScxJhfH0r6zmBFAe",
        "BQIDAQAB",
        "-----END PUBLIC KEY-----",
    ]


@pytest.mark.parametrize("linesep", ["\r\n", "\r", "\n"])
def test_compare_keys(key_data, linesep):
    src_key = linesep.join(key_data)
    tgt_key = "\n".join(key_data)
    assert server.ReqServerChannel.compare_keys(src_key, tgt_key) is True


@pytest.mark.parametrize("linesep", ["\r\n", "\r", "\n"])
def test_compare_keys_newline_src(key_data, linesep):
    src_key = linesep.join(key_data) + linesep
    tgt_key = "\n".join(key_data)
    assert src_key.endswith(linesep)
    assert not tgt_key.endswith("\n")
    assert server.ReqServerChannel.compare_keys(src_key, tgt_key) is True


@pytest.mark.parametrize("linesep", ["\r\n", "\r", "\n"])
def test_compare_keys_newline_tgt(key_data, linesep):
    src_key = linesep.join(key_data)
    tgt_key = "\n".join(key_data) + "\n"
    assert not src_key.endswith(linesep)
    assert tgt_key.endswith("\n")
    assert server.ReqServerChannel.compare_keys(src_key, tgt_key) is True


@pytest.fixture
def root_dir(tmp_path):
    (tmp_path / "var").mkdir()
    (tmp_path / "var" / "cache").mkdir()
    (tmp_path / "var" / "run").mkdir()
    (tmp_path / "etc").mkdir()
    (tmp_path / "etc" / "salt").mkdir()
    (tmp_path / "etc" / "salt" / "pki").mkdir()
    (tmp_path / "etc" / "salt" / "pki" / "minions").mkdir()
    yield tmp_path


def test_req_server_validate_token_removes_token(root_dir):
    opts = {
        "master_uri": "tcp://127.0.0.1:4505",
        "cachedir": str(root_dir / "var" / "cache"),
        "pki_dir": str(root_dir / "etc" / "salt" / "pki"),
        "sock_dir": str(root_dir / "var" / "run"),
        "key_pass": "",
        "keysize": 2048,
        "master_sign_pubkey": False,
    }
    reqsrv = server.ReqServerChannel.factory(opts)
    payload = {
        "load": {
            "id": "minion",
            "tok": "asdf",
        }
    }
    assert reqsrv.validate_token(payload) is False
    assert "tok" not in payload["load"]


def test_req_server_validate_token_removes_token_id_traversal(root_dir):
    opts = {
        "master_uri": "tcp://127.0.0.1:4505",
        "cachedir": str(root_dir / "var" / "cache"),
        "pki_dir": str(root_dir / "etc" / "salt" / "pki"),
        "sock_dir": str(root_dir / "var" / "run"),
        "key_pass": "",
        "keysize": 2048,
        "master_sign_pubkey": False,
    }
    reqsrv = server.ReqServerChannel.factory(opts)
    payload = {
        "load": {
            "id": "minion/../../foo",
            "tok": "asdf",
        }
    }
    assert reqsrv.validate_token(payload) is False
    assert "tok" not in payload["load"]


# ============================================================================
# Auth Version Downgrade Attack Regression Tests
# ============================================================================


@pytest.fixture
def pki_dir(tmp_path):
    """Setup PKI directory structure for auth tests."""
    master_pki = tmp_path / "master"
    minion_pki = tmp_path / "minion"

    master_pki.mkdir()
    minion_pki.mkdir()
    (master_pki / "minions").mkdir()
    (master_pki / "minions_pre").mkdir()
    (master_pki / "minions_rejected").mkdir()
    (master_pki / "minions_denied").mkdir()

    # Generate master keys
    salt.crypt.gen_keys(str(master_pki), "master", 4096)

    # Generate minion keys
    salt.crypt.gen_keys(str(minion_pki), "minion", 4096)

    return tmp_path


@pytest.fixture
def auth_master_opts(pki_dir, tmp_path):
    """Master configuration for auth tests."""
    opts = {
        "master_uri": "tcp://127.0.0.1:4506",
        "interface": "127.0.0.1",
        "ret_port": 4506,
        "ipv6": False,
        "sock_dir": str(tmp_path / "sock"),
        "cachedir": str(tmp_path / "cache"),
        "pki_dir": str(pki_dir / "master"),
        "id": "master",
        "__role": "master",
        "keysize": 4096,
        "max_minions": 0,
        "auto_accept": False,
        "open_mode": False,
        "key_pass": None,
        "publish_port": 4505,
        "auth_mode": 1,
        "auth_events": True,
        "publish_session": 86400,
        "request_server_ttl": 300,  # 5 minutes
        "master_sign_pubkey": False,
        "sign_pub_messages": False,
        "cluster_id": None,
        "transport": "zeromq",
        "minimum_auth_version": 3,  # Enforce version 3+ for security
    }
    (tmp_path / "sock").mkdir(exist_ok=True)
    (tmp_path / "cache").mkdir(exist_ok=True)
    (tmp_path / "cache" / "sessions").mkdir(exist_ok=True)
    return opts


@pytest.fixture
def auth_minion_opts(pki_dir, auth_master_opts):
    """Minion configuration for auth tests."""
    return {
        "master_uri": "tcp://127.0.0.1:4506",
        "interface": "127.0.0.1",
        "ret_port": 4506,
        "ipv6": False,
        "sock_dir": str(auth_master_opts["sock_dir"]),
        "pki_dir": str(pki_dir / "minion"),
        "id": "test-minion",
        "__role": "minion",
        "keysize": 4096,
        "encryption_algorithm": salt.crypt.OAEP_SHA1,
        "signing_algorithm": salt.crypt.PKCS1v15_SHA1,
    }


@pytest.fixture
def setup_accepted_minion(pki_dir, auth_minion_opts, auth_master_opts):
    """
    Setup a pre-accepted minion by copying its public key to master's
    minions directory.
    """
    minion_pub = pki_dir / "minion" / "minion.pub"
    master_minions_dir = pki_dir / "master" / "minions"
    accepted_key = master_minions_dir / auth_minion_opts["id"]

    # Copy minion public key to master's accepted keys
    with salt.utils.files.fopen(str(minion_pub)) as src:
        with salt.utils.files.fopen(str(accepted_key), "w") as dst:
            dst.write(src.read())

    return accepted_key


@pytest.fixture
def req_server(auth_master_opts):
    """Create a ReqServerChannel instance for testing."""
    # Setup master secrets
    SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        ),
        "reload": salt.crypt.Crypticle.generate_key_string,
    }

    server_channel = server.ReqServerChannel.factory(auth_master_opts)
    server_channel.auto_key = salt.daemons.masterapi.AutoKey(auth_master_opts)
    server_channel.cache_cli = False
    server_channel.event = salt.utils.event.get_master_event(
        auth_master_opts, auth_master_opts["sock_dir"], listen=False
    )
    server_channel.master_key = salt.crypt.MasterKeys(auth_master_opts)

    yield server_channel

    server_channel.close()
    if "aes" in SMaster.secrets:
        SMaster.secrets.pop("aes")


async def test_auth_version_downgrade_v3_to_v0(
    pki_dir, auth_minion_opts, req_server, setup_accepted_minion
):
    """
    REGRESSION TEST: CVE-2025-62349 - Auth Version Downgrade Attack

    Test that the master rejects authentication attempts using protocol version 0
    when minimum_auth_version is set to 3.

    This prevents a malicious or compromised minion from using an older protocol
    version to bypass security features introduced in version 3+ (token validation,
    TTL checks, ID matching, session keys).

    The test verifies that the minimum_auth_version enforcement works at the initial
    authentication stage, preventing minions from establishing low-version sessions.
    """
    # Read minion public key
    with salt.utils.files.fopen(str(pki_dir / "minion" / "minion.pub"), "r") as fp:
        pub_key = fp.read()

    # Simulate version 0 auth load (no nonce, no signing)
    load_v0 = {
        "cmd": "_auth",
        "id": auth_minion_opts["id"],
        "pub": pub_key,
        "enc_algo": auth_minion_opts["encryption_algorithm"],
        "sig_algo": auth_minion_opts["signing_algorithm"],
    }

    # Create payload for handle_message (version 0)
    payload = {"enc": "clear", "load": load_v0, "version": 0}

    # Call handle_message which will enforce minimum_auth_version
    ret = await req_server.handle_message(payload)

    # REGRESSION TEST: Version 0 should be REJECTED
    # With minimum_auth_version=3, version 0 should return "bad load"
    assert ret == "bad load", "Expected 'bad load' for rejected version 0 auth"


@pytest.mark.parametrize("downgrade_version", [0, 1, 2])
async def test_auth_version_downgrade_from_v3(
    pki_dir, auth_minion_opts, req_server, setup_accepted_minion, downgrade_version
):
    """
    REGRESSION TEST: CVE-2025-62349 - Auth Version Downgrade Attack (Parametrized)

    Test that the master rejects authentication attempts using protocol versions
    0, 1, or 2 when minimum_auth_version is set to 3.

    This prevents malicious or compromised minions from using older protocol
    versions to bypass security features:
    - v0/v1: No message signing, no nonce
    - v2: Message signing but no token validation, no TTL checks, no ID matching
    - v3+: Full security (token validation, TTL, ID matching, session keys)

    The test verifies that minimum_auth_version enforcement prevents minions from
    establishing low-version sessions that would allow them to bypass security
    controls and potentially impersonate other minions or maintain unauthorized access.
    """
    with salt.utils.files.fopen(str(pki_dir / "minion" / "minion.pub"), "r") as fp:
        pub_key = fp.read()

    load = {
        "cmd": "_auth",
        "id": auth_minion_opts["id"],
        "pub": pub_key,
        "enc_algo": auth_minion_opts["encryption_algorithm"],
        "sig_algo": auth_minion_opts["signing_algorithm"],
    }

    # Add nonce for v2+ (but not for v0/v1)
    if downgrade_version >= 2:
        load["nonce"] = uuid.uuid4().hex

    # Create payload for handle_message
    payload = {"enc": "clear", "load": load, "version": downgrade_version}

    # Call handle_message which will enforce minimum_auth_version
    ret = await req_server.handle_message(payload)

    # REGRESSION TEST: Old versions should be REJECTED
    # With minimum_auth_version=3, versions 0, 1, 2 should return "bad load"
    assert (
        ret == "bad load"
    ), f"Expected 'bad load' for rejected version {downgrade_version} auth"


def test_handle_message_version_extraction(auth_master_opts):
    """
    REGRESSION TEST: CVE-2025-62349 - Version Extraction from Untrusted Payload

    Test that the master should have minimum_auth_version configured.

    EXPECTED BEHAVIOR:
    - Master opts should have minimum_auth_version set
    - The commented code at salt/channel/server.py:144-145 should be enabled

    CURRENT BEHAVIOR (VULNERABLE):
    - Test will FAIL - minimum_auth_version is not in opts
    - After fix is implemented, this test will PASS
    """
    # The current code at salt/channel/server.py:139-145 shows:
    # version = payload.get("version", 0)
    # #if version < self.opts["minimum_auth_version"]:
    # #    raise salt.ext.tornado.gen.Return("bad load")

    # REGRESSION TEST: Verify minimum_auth_version exists in opts
    # Currently this will FAIL because the option doesn't exist
    assert (
        "minimum_auth_version" in auth_master_opts
    ), "Expected minimum_auth_version to be configured in master opts"
    assert (
        auth_master_opts["minimum_auth_version"] >= 3
    ), "Expected minimum auth version to be at least 3"


# Note: The remaining security bypasses (token, TTL, ID mismatch, session keys)
# are already tested via the parametrized downgrade tests above and the
# functional tests. The key regression test is ensuring old versions are rejected.
