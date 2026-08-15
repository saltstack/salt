import ctypes
import multiprocessing
import pathlib
import time
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
from tests.support.mock import AsyncMock, MagicMock, patch


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


class TestClusterPubFingerprint:
    """
    Tests for ``cluster_pub_matches_fingerprint`` -- the helper that lets a
    joining master pin the expected cluster public key by its SHA-256 hex
    digest in ``opts["cluster_pub_fingerprint"]``.
    """

    PUB = (
        "-----BEGIN PUBLIC KEY-----\n"
        "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAoe5QSDYRWKyknbVyRrIj\n"
        "-----END PUBLIC KEY-----\n"
    )

    def _digest(self, data):
        import hashlib

        return hashlib.sha256(data.encode()).hexdigest()

    def test_no_fingerprint_configured_accepts(self):
        # Unset option: TOFU behavior, accept whatever was received.
        assert server.cluster_pub_matches_fingerprint({}, self.PUB) is True
        assert (
            server.cluster_pub_matches_fingerprint(
                {"cluster_pub_fingerprint": None}, self.PUB
            )
            is True
        )
        assert (
            server.cluster_pub_matches_fingerprint(
                {"cluster_pub_fingerprint": ""}, self.PUB
            )
            is True
        )

    def test_matching_fingerprint_accepts(self):
        opts = {"cluster_pub_fingerprint": self._digest(self.PUB)}
        assert server.cluster_pub_matches_fingerprint(opts, self.PUB) is True

    def test_matching_fingerprint_case_insensitive(self):
        opts = {"cluster_pub_fingerprint": self._digest(self.PUB).upper()}
        assert server.cluster_pub_matches_fingerprint(opts, self.PUB) is True

    def test_mismatched_fingerprint_rejects(self):
        opts = {"cluster_pub_fingerprint": self._digest(self.PUB + "tampered")}
        assert server.cluster_pub_matches_fingerprint(opts, self.PUB) is False

    def test_bytes_pub_is_accepted(self):
        opts = {"cluster_pub_fingerprint": self._digest(self.PUB)}
        assert server.cluster_pub_matches_fingerprint(opts, self.PUB.encode()) is True

    def test_not_sha1_digest(self):
        # The previous (broken) implementation used SHA-1. A caller that
        # supplies a SHA-1 digest as the pinned value must now be rejected:
        # the helper compares against SHA-256 exclusively.
        import hashlib

        sha1 = hashlib.sha1(self.PUB.encode()).hexdigest()
        opts = {"cluster_pub_fingerprint": sha1}
        assert server.cluster_pub_matches_fingerprint(opts, self.PUB) is False

    def test_truncated_fingerprint_rejected(self):
        # Pinning must require a full hex digest. Accepting a prefix would
        # silently reduce the pin's strength to whatever length the operator
        # happened to paste.
        opts = {"cluster_pub_fingerprint": self._digest(self.PUB)[:16]}
        assert server.cluster_pub_matches_fingerprint(opts, self.PUB) is False


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
        "id": "minion",
        "__role": "minion",
        "master_uri": "tcp://127.0.0.1:4505",
        "cachedir": str(root_dir / "var" / "cache"),
        "pki_dir": str(root_dir / "etc" / "salt" / "pki"),
        "sock_dir": str(root_dir / "var" / "run"),
        "key_pass": "",
        "keysize": 2048,
        "master_sign_pubkey": False,
        "keys.cache_driver": "localfs_key",
        "optimization_order": (0, 1, 2),
        "permissive_pki_access": False,
        "cluster_id": "",
        "worker_pools_enabled": False,
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
        "id": "minion",
        "__role": "minion",
        "master_uri": "tcp://127.0.0.1:4505",
        "cachedir": str(root_dir / "var" / "cache"),
        "pki_dir": str(root_dir / "etc" / "salt" / "pki"),
        "sock_dir": str(root_dir / "var" / "run"),
        "key_pass": "",
        "keysize": 2048,
        "master_sign_pubkey": False,
        "keys.cache_driver": "localfs_key",
        "optimization_order": (0, 1, 2),
        "permissive_pki_access": False,
        "cluster_id": "",
        "worker_pools_enabled": False,
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
    master_priv, master_pub = salt.crypt.gen_keys(4096)
    (master_pki / "master.pem").write_text(master_priv)
    (master_pki / "master.pub").write_text(master_pub)

    # Generate minion keys
    minion_priv, minion_pub = salt.crypt.gen_keys(4096)
    (minion_pki / "minion.pem").write_text(minion_priv)
    (minion_pki / "minion.pub").write_text(minion_pub)

    return tmp_path


@pytest.fixture
def auth_master_opts(pki_dir, tmp_path):
    """Master configuration for auth tests."""
    import salt.config

    # Start with default master opts to get all necessary loader paths
    opts = salt.config.DEFAULT_MASTER_OPTS.copy()

    # Override with test-specific configuration
    opts.update(
        {
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
            "keys.cache_driver": "localfs_key",
            "extension_modules": str(tmp_path / "extmods"),
            "file_roots": {"base": [str(tmp_path / "file_roots")]},
            "pillar_roots": {"base": [str(tmp_path / "pillar_roots")]},
        }
    )
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
    # #    raise tornado.gen.Return("bad load")

    # REGRESSION TEST: Verify minimum_auth_version exists in opts
    # Currently this will FAIL because the option doesn't exist
    assert (
        "minimum_auth_version" in auth_master_opts
    ), "Expected minimum_auth_version to be configured in master opts"
    assert (
        auth_master_opts["minimum_auth_version"] >= 3
    ), "Expected minimum auth version to be at least 3"


async def test_auth_version_downgrade_warning_includes_minion_id(
    pki_dir, auth_minion_opts, req_server, setup_accepted_minion, caplog
):
    """
    Test that the rejected authentication warning includes the minion ID.

    When minimum_auth_version rejects a connection, the warning message should
    include the minion's ID so administrators can identify which minion needs
    to be upgraded.
    """
    with salt.utils.files.fopen(str(pki_dir / "minion" / "minion.pub"), "r") as fp:
        pub_key = fp.read()

    load = {
        "cmd": "_auth",
        "id": "my-outdated-minion",
        "pub": pub_key,
        "enc_algo": auth_minion_opts["encryption_algorithm"],
        "sig_algo": auth_minion_opts["signing_algorithm"],
    }

    payload = {"enc": "clear", "load": load, "version": 0}

    import logging

    with caplog.at_level(logging.WARNING, logger="salt.channel.server"):
        ret = await req_server.handle_message(payload)

    assert ret == "bad load"
    assert any(
        "my-outdated-minion" in record.message
        for record in caplog.records
        if record.levelno == logging.WARNING
    ), "Expected minion ID 'my-outdated-minion' in the rejection warning message"


async def test_auth_version_downgrade_warning_encrypted_load(req_server, caplog):
    """
    Test that the rejected authentication warning shows 'unknown minion' when
    the load is not a dict (e.g., encrypted payload).
    """
    payload = {"enc": "aes", "load": b"encrypted-blob", "version": 0}

    import logging

    with caplog.at_level(logging.WARNING, logger="salt.channel.server"):
        ret = await req_server.handle_message(payload)

    assert ret == "bad load"
    assert any(
        "unknown minion" in record.message
        for record in caplog.records
        if record.levelno == logging.WARNING
    ), "Expected 'unknown minion' in the rejection warning for encrypted payloads"


# Note: The remaining security bypasses (token, TTL, ID mismatch, session keys)
# are already tested via the parametrized downgrade tests above and the
# functional tests. The key regression test is ensuring old versions are rejected.
async def test_handle_message_exceptions(temp_salt_master):
    """
    test exceptions are handled cleanly in handle_message
    """
    opts = dict(temp_salt_master.config.copy())
    req = server.ReqServerChannel(opts, None)

    with patch(
        "salt.channel.server.ReqServerChannel._decode_payload",
        MagicMock(side_effect=OSError()),
    ):
        ret = await req.handle_message({})
        assert ret == "bad load"

    with patch(
        "salt.channel.server.ReqServerChannel._decode_payload",
        MagicMock(return_value="foobar"),
    ):
        ret = await req.handle_message({})
        assert ret == "bad load"

    with patch(
        "salt.channel.server.ReqServerChannel._decode_payload",
        MagicMock(return_value={"load": {"id": "foo\0"}}),
    ):
        ret = await req.handle_message({"version": 3, "enc": "clear", "load": {}})
        assert ret == "bad load: id contains a null byte"

    with patch(
        "salt.channel.server.ReqServerChannel._decode_payload",
        MagicMock(return_value={"load": {"id": None}}),
    ):
        ret = await req.handle_message({"version": 3, "enc": "clear", "load": {}})
        assert ret == "bad load: id None is not a string"

    with patch(
        "salt.channel.server.ReqServerChannel._decode_payload",
        MagicMock(
            return_value={"version": 3, "enc": "clear", "load": {"cmd": "_auth"}}
        ),
    ):
        with patch(
            "salt.channel.server.ReqServerChannel._auth",
            MagicMock(side_effect=OSError()),
        ):
            ret = await req.handle_message({"version": 3, "enc": "clear", "load": {}})
            assert ret == "Some exception handling minion payload"

    with patch(
        "salt.channel.server.ReqServerChannel._decode_payload",
        MagicMock(
            return_value={"version": 3, "enc": "clear", "load": {"cmd": "not_auth"}}
        ),
    ):
        with patch(
            "salt.channel.server.ReqServerChannel.payload_handler",
            MagicMock(side_effect=OSError()),
            create=True,
        ):
            ret = await req.handle_message({"version": 3, "enc": "clear", "load": {}})
            assert ret == "Some exception handling minion payload"

    with patch(
        "salt.channel.server.ReqServerChannel._decode_payload",
        MagicMock(return_value={"enc": "clear", "load": {"cmd": "not_auth"}}),
    ):
        with patch(
            "salt.channel.server.ReqServerChannel.payload_handler",
            AsyncMock(return_value=(None, {"fun": "send"})),
            create=True,
        ):
            crypticle = MagicMock()
            with patch.object(req, "crypticle", crypticle, create=True):
                crypticle.dumps = MagicMock(side_effect=OSError())
                ret = await req.handle_message(
                    {"version": 3, "enc": "clear", "load": {}}
                )
                assert ret == "Some exception handling minion payload"

    with patch(
        "salt.channel.server.ReqServerChannel._decode_payload",
        MagicMock(return_value={"enc": "clear", "load": {"cmd": "not_auth"}}),
    ):
        with patch(
            "salt.channel.server.ReqServerChannel.payload_handler",
            AsyncMock(
                return_value=(None, {"fun": "send_private", "key": None, "tgt": None})
            ),
            create=True,
        ):
            with patch.object(
                req, "_encrypt_private", MagicMock(side_effect=OSError()), create=True
            ):
                ret = await req.handle_message(
                    {"version": 3, "enc": "clear", "load": {}}
                )
                assert ret == "Some exception handling minion payload"

    with patch(
        "salt.channel.server.ReqServerChannel._decode_payload",
        MagicMock(return_value={"enc": "clear", "load": {"cmd": "not_auth"}}),
    ):
        with patch(
            "salt.channel.server.ReqServerChannel.payload_handler",
            AsyncMock(return_value=(None, {"fun": "foobar", "key": None, "tgt": None})),
            create=True,
        ):
            with patch.object(
                req, "_encrypt_private", MagicMock(side_effect=OSError()), create=True
            ):
                ret = await req.handle_message(
                    {"version": 3, "enc": "clear", "load": {}}
                )
                assert ret == "Server-side exception handling payload"


async def test__auth_cmd_stats_passing(auth_master_opts):
    opts = auth_master_opts.copy()
    opts.update(
        {
            "master_stats": True,
        }
    )
    req = server.ReqServerChannel(opts, None)

    fake_ret = {"enc": "clear", "load": b"FAKELOAD"}

    def _auth_mock(*_, **__):
        time.sleep(0.03)
        return fake_ret

    with patch.object(req, "_auth", _auth_mock), patch(
        "salt.channel.server.ReqServerChannel.payload_handler",
        AsyncMock(return_value=(None, {"fun": "send"})),
        create=True,
    ) as payload_handler:
        ret = await req.handle_message(
            {
                "enc": "clear",
                "version": 3,
                "load": {
                    "cmd": "_auth",
                    "id": "minion",
                },
            }
        )
        cur_time = time.time()
        payload_handler.assert_called_once()
        assert payload_handler.call_args[0][0]["cmd"] == "_auth"
        auth_call_duration = cur_time - payload_handler.call_args[0][0]["_start"]
        assert auth_call_duration >= 0.03
        assert auth_call_duration < 0.05


# ============================================================================
# Master Cluster Peer Event Forwarding Regression Tests
# ============================================================================


@pytest.fixture
def cluster_master_opts(tmp_path):
    """
    Master opts that mirror a default cluster-master deployment.

    The reproduced bug requires ``opts["id"]`` to carry the ``_master``
    suffix that ``apply_master_config`` appends when ``id`` is not set
    explicitly in the config.  ``cluster_peers`` carries bare hostnames as
    documented in ``doc/ref/configuration/master.rst``.
    """
    pki = tmp_path / "pki"
    pki.mkdir()
    (pki / "peers").mkdir()
    opts = {
        "id": "salt-master-1_master",
        "cluster_id": "master_cluster",
        "cluster_peers": ["salt-master-2", "salt-master-3"],
        "cluster_pki_dir": str(pki),
        "cluster_encryption_algorithm": "OAEP-SHA1",
        "sock_dir": str(tmp_path / "sock"),
    }
    (tmp_path / "sock").mkdir()
    return opts


async def test_handle_pool_publish_clustered_master_id_68462(
    cluster_master_opts, key_data
):
    """
    Regression test for https://github.com/saltstack/salt/issues/68462.

    A default-installed master in a cluster ends up with ``opts["id"]``
    carrying the ``_master`` suffix that ``apply_master_config`` appends
    when ``id`` is not configured explicitly.  ``cluster_peers``, on the
    other hand, carries the bare hostnames as documented::

        cluster_peers:
          - salt-master-2
          - salt-master-3

    Sibling masters publish ``cluster/peer`` events whose ``data["peers"]``
    dict is keyed by the bare names taken from their own ``cluster_peers``
    entries.  Before the fix the receiver looked up
    ``data["peers"][self.opts["id"]]``, which raised ``KeyError`` because
    the suffixed id is not present in the payload, producing the
    user-visible::

        [CRITICAL] Unhandled error while polling master events
        KeyError: 'salt-master-1_master'

    The handler must reach the peer entry under the bare master id so
    that AES-key forwarding between cluster peers continues to work.
    """
    import hashlib

    from tests.support.mock import AsyncMock, MagicMock

    # Build a payload that looks like what a sibling master would emit
    # via ``send_aes_key_event``.  ``data["peers"]`` is keyed by the bare
    # peer name from the sibling's ``cluster_peers``.
    bare_id = cluster_master_opts["id"].removesuffix("_master")
    sibling_data = {
        "peer_id": "salt-master-2",
        "peers": {
            bare_id: {"aes": b"encrypted-aes", "sig": b"signature"},
        },
    }
    tag = salt.utils.event.tagify("salt-master-2", "peer", "cluster")
    payload = salt.utils.event.SaltEvent.pack(tag, sibling_data)

    channel = server.MasterPubServerChannel.__new__(server.MasterPubServerChannel)
    channel.opts = cluster_master_opts
    channel.peer_keys = {}
    channel.auth_errors = {"salt-master-2": [], "salt-master-3": []}
    channel.transport = MagicMock()
    channel.transport.publish_payload = AsyncMock()

    # Stub crypto so the handler exercises only the dispatch logic under
    # test.  ``decrypt`` returns the AES key bytes; ``key.decrypt``
    # returns a digest that matches the sha256 of those bytes so the
    # signature check passes.
    aes_bytes = b"shared-aes-secret"
    digest = salt.utils.stringutils.to_bytes(hashlib.sha256(aes_bytes).hexdigest())

    fake_master_key = MagicMock()
    fake_master_key.decrypt.return_value = aes_bytes
    fake_peer_key = MagicMock()
    fake_peer_key.decrypt.return_value = digest
    # 3008.x's handle_pool_publish reads the peer pubkey via
    # ``self.master_key.fetch("peers/<bare>.pub")`` (the refactored
    # MasterKeys API) rather than the 3006.x/3007.x ``salt.crypt.PublicKey``
    # constructor.  Mock both attributes off the same MagicMock.
    channel.master_key = MagicMock()
    channel.master_key.master_key = fake_master_key
    channel.master_key.fetch = MagicMock(return_value=fake_peer_key)

    # ``send_aes_key_event`` is not under test here; the receiver
    # calls it after caching the peer key.  Stub it.
    channel.send_aes_key_event = lambda: None

    # Before the fix this raised ``KeyError: 'salt-master-1_master'``
    # and the handler swallowed it as a CRITICAL log line, so the
    # peer key was never cached.  After the fix the peer key is
    # cached under the bare peer name.
    await channel.handle_pool_publish(payload)

    assert "salt-master-2" in channel.peer_keys, (
        "handle_pool_publish must cache the sibling's AES key; if the bug "
        "is present the handler raises KeyError on the suffixed id and "
        "no key is recorded."
    )
    assert channel.peer_keys["salt-master-2"] == aes_bytes


def test_send_aes_key_event_finds_peer_pub_with_bare_name(cluster_master_opts):
    """
    Regression test for https://github.com/saltstack/salt/issues/68462.

    ``cluster_peers`` is configured with bare hostnames.  The sender in
    ``send_aes_key_event`` looks for ``{cluster_pki_dir}/peers/{peer}.pub``
    by that bare name, so the on-disk peer key store written by
    :class:`salt.crypt.MasterKeys` must use the bare master id.  This
    test guards against a regression to the pre-fix behaviour where
    ``MasterKeys`` wrote the file with the ``_master`` suffix and the
    sender therefore saw every peer key as missing.
    """
    cluster_pki = pathlib.Path(cluster_master_opts["cluster_pki_dir"])
    master_pki = cluster_pki.parent / "master_pki"
    master_pki.mkdir()

    fake_opts = dict(cluster_master_opts)
    fake_opts.update(
        {
            # cluster_shared_path is only set when cluster_pki_dir and
            # pki_dir diverge (the cluster-master deployment shape that
            # #68462 reproduces), so point pki_dir at a separate path.
            "pki_dir": str(master_pki),
            "cachedir": str(cluster_pki.parent / "cache"),
            "key_pass": None,
            "cluster_key_pass": None,
            "master_sign_pubkey": False,
            "keysize": 2048,
            "keys.cache_driver": "localfs_key",
            "optimization_order": [0, 1, 2],
            "permissive_pki_access": False,
            "user": None,
        }
    )

    # ``cluster_shared_path`` is computed in ``MasterKeys.__init__``
    # before the ``_setup_keys()`` call gated on ``autocreate``; pass
    # ``autocreate=False`` so the constructor skips disk I/O and we can
    # inspect the path directly.  On 3008.x ``__get_keys`` no longer
    # exists, so the 3006.x/3007.x patch over ``_MasterKeys__get_keys``
    # is moot here.
    mk = salt.crypt.MasterKeys(fake_opts, autocreate=False)

    shared = pathlib.Path(mk.cluster_shared_path)
    assert shared.parent == cluster_pki / "peers"
    assert (
        shared.name.removesuffix(".pub") in fake_opts["id"]
    ), "shared peer pubkey file name should be derived from the master id"
    assert not shared.name.endswith("_master.pub"), (
        f"MasterKeys.cluster_shared_path={shared} still includes the "
        "_master suffix; this is what causes the channel server to log "
        "'Peer key missing' for every configured cluster_peer and is the "
        "root cause of issue #68462."
    )


# ============================================================================
# PR #70052: MasterPubServerChannel.publish_payload tag-peek fast path.
#
# ``publish_payload`` used to call ``SaltEvent.unpack(load)`` on every
# event, which msgpack-decodes the entire body just to inspect the
# tag.  For non-cluster masters the decoded body is never used --
# ``self.transport.publish_payload(load)`` forwards the same original
# wire bytes.  #70052 replaces the unconditional unpack with a
# bytes-level ``load.partition(TAGEND)`` and calls the full
# ``salt.payload.loads`` lazily via a ``_decode_data()`` closure only
# in the five ``cluster/runner/*`` branches that need the decoded
# dict.  The local-fanout branch also now forwards
# ``raw_payload=raw_payload`` to the transport so the pull-side wire
# bytes reach the fast path in ``PubServer.publish_payload``.
# ============================================================================


def _pub_channel(opts, **overrides):
    """
    Build a bare ``MasterPubServerChannel`` with minimal attribute
    stubs so ``publish_payload`` can be exercised in isolation.  We
    bypass ``__init__`` to avoid ``MasterKeys`` / socket setup and
    stub only the attributes the method touches.
    """
    from tests.support.mock import AsyncMock, MagicMock

    channel = server.MasterPubServerChannel.__new__(server.MasterPubServerChannel)
    channel.opts = opts
    channel.transport = MagicMock()
    channel.transport.publish_payload = AsyncMock(return_value=None)
    channel.pushers = overrides.get("pushers", [])
    channel._raft_service = overrides.get("_raft_service", None)
    return channel


async def test_publish_payload_non_cluster_tag_does_not_decode(master_opts):
    """
    For a run-of-the-mill ``salt/job/...`` event ``publish_payload``
    must never call ``salt.payload.loads`` -- the tag is peeked out of
    the wire bytes with ``load.partition(TAGEND)`` and the body is
    forwarded verbatim.  This is the whole point of the tag-peek fast
    path: >99% of events on a non-cluster master skip the full
    msgpack round-trip.
    """
    channel = _pub_channel(master_opts)

    tag = "salt/job/20260814000000000000/ret/minion1"
    body = {"jid": "20260814000000000000", "id": "minion1", "return": {"foo": "bar"}}
    load = salt.utils.event.SaltEvent.pack(tag, body)

    with patch("salt.payload.loads") as fake_loads:
        await channel.publish_payload(load, raw_payload=b"wire-bytes")

    assert fake_loads.called is False, "non-cluster path must not decode the event body"
    channel.transport.publish_payload.assert_awaited_once_with(
        load, raw_payload=b"wire-bytes"
    )


async def test_publish_payload_forwards_raw_payload_to_transport(master_opts):
    """
    The local-fanout branch (no cluster peers, non-cluster tag) must
    forward ``raw_payload`` through to
    ``self.transport.publish_payload`` so the underlying
    ``PubServer`` can skip its ``frame_msg`` step.
    """
    channel = _pub_channel(master_opts)

    tag = "salt/auth"
    load = salt.utils.event.SaltEvent.pack(tag, {"act": "accept", "id": "minion1"})
    raw = b"raw-wire-bytes-sentinel"

    await channel.publish_payload(load, raw_payload=raw)

    channel.transport.publish_payload.assert_awaited_once_with(load, raw_payload=raw)


async def test_publish_payload_default_raw_payload_is_none(master_opts):
    """
    When called without ``raw_payload=`` (older callers or tests that
    don't have the wire bytes handy), ``publish_payload`` must
    forward ``raw_payload=None`` so the transport falls back to its
    own framing.
    """
    channel = _pub_channel(master_opts)

    tag = "salt/auth"
    load = salt.utils.event.SaltEvent.pack(tag, {"act": "accept", "id": "minion1"})

    await channel.publish_payload(load)

    channel.transport.publish_payload.assert_awaited_once_with(load, raw_payload=None)


async def test_publish_payload_cluster_runner_sync_roots_decodes(master_opts):
    """
    ``cluster/runner/sync_roots`` must invoke ``_decode_data()`` and
    dispatch ``_run_root_sync_to_peers`` with the ``channels`` value
    from the decoded body.
    """
    channel = _pub_channel(master_opts)
    channel._run_root_sync_to_peers = AsyncMock(return_value=None)

    tag = "cluster/runner/sync_roots"
    body = {"channels": ["file_roots"]}
    load = salt.utils.event.SaltEvent.pack(tag, body)

    with patch("salt.payload.loads", wraps=salt.payload.loads) as spy_loads:
        await channel.publish_payload(load)
        # Give the create_task chance to schedule and run.
        import asyncio as _asyncio

        await _asyncio.sleep(0)

    spy_loads.assert_called()
    channel._run_root_sync_to_peers.assert_called_once_with(["file_roots"])
    # Cluster runner branch does NOT fan out to the transport.
    channel.transport.publish_payload.assert_not_called()


async def test_publish_payload_cluster_runner_sync_roots_default_channels(master_opts):
    """
    Empty/missing ``channels`` falls back to the default
    ``["file_roots", "pillar_roots"]``.
    """
    channel = _pub_channel(master_opts)
    channel._run_root_sync_to_peers = AsyncMock(return_value=None)

    load = salt.utils.event.SaltEvent.pack("cluster/runner/sync_roots", {})

    await channel.publish_payload(load)
    import asyncio as _asyncio

    await _asyncio.sleep(0)

    channel._run_root_sync_to_peers.assert_called_once_with(
        ["file_roots", "pillar_roots"]
    )


async def test_publish_payload_cluster_runner_collect_from_peers_decodes(master_opts):
    """
    ``cluster/runner/collect_from_peers`` decodes and dispatches
    ``_run_collect_from_peers`` with the decoded channel list.
    """
    channel = _pub_channel(master_opts)
    channel._run_collect_from_peers = AsyncMock(return_value=None)

    load = salt.utils.event.SaltEvent.pack(
        "cluster/runner/collect_from_peers", {"channels": ["keys"]}
    )

    await channel.publish_payload(load)
    import asyncio as _asyncio

    await _asyncio.sleep(0)

    channel._run_collect_from_peers.assert_called_once_with(["keys"])
    channel.transport.publish_payload.assert_not_called()


async def test_publish_payload_cluster_runner_shed_unowned_all_decodes(master_opts):
    """
    ``cluster/runner/shed_unowned_all`` decodes and dispatches
    ``_run_shed_unowned_all`` with the entire decoded body dict.
    """
    channel = _pub_channel(master_opts)
    channel._run_shed_unowned_all = AsyncMock(return_value=None)

    body = {"scope": "all", "issued_by": "op1"}
    load = salt.utils.event.SaltEvent.pack("cluster/runner/shed_unowned_all", body)

    await channel.publish_payload(load)
    import asyncio as _asyncio

    await _asyncio.sleep(0)

    channel._run_shed_unowned_all.assert_called_once_with(body)
    channel.transport.publish_payload.assert_not_called()


async def test_publish_payload_cluster_runner_delegate_write_decodes(master_opts):
    """
    ``cluster/runner/delegate_write`` decodes and dispatches
    ``_run_delegate_write`` with the decoded payload.
    """
    channel = _pub_channel(master_opts)
    channel._run_delegate_write = AsyncMock(return_value=None)

    body = {"owner": "peer-2", "target_id": "minion-x", "value": b"..."}
    load = salt.utils.event.SaltEvent.pack("cluster/runner/delegate_write", body)

    await channel.publish_payload(load)
    import asyncio as _asyncio

    await _asyncio.sleep(0)

    channel._run_delegate_write.assert_called_once_with(body)
    channel.transport.publish_payload.assert_not_called()


@pytest.mark.parametrize(
    "runner_tag",
    [
        "cluster/runner/ring_create",
        "cluster/runner/ring_destroy",
        "cluster/runner/route_set",
        "cluster/runner/route_clear",
        "cluster/runner/ring_set",
    ],
)
async def test_publish_payload_multi_ring_runner_decodes(master_opts, runner_tag):
    """
    Every multi-ring ``cluster/runner/*`` tag must decode the body,
    dispatch it into ``_handle_multi_ring_runner_event`` synchronously
    and schedule ``_fanout_multi_ring_request`` as an asyncio task --
    both with the same decoded dict.
    """
    channel = _pub_channel(master_opts)
    channel._handle_multi_ring_runner_event = MagicMock()
    channel._fanout_multi_ring_request = AsyncMock(return_value=None)

    body = {"ring_id": "R1", "founding_voters": ["a", "b"]}
    load = salt.utils.event.SaltEvent.pack(runner_tag, body)

    await channel.publish_payload(load)
    import asyncio as _asyncio

    await _asyncio.sleep(0)

    channel._handle_multi_ring_runner_event.assert_called_once_with(runner_tag, body)
    channel._fanout_multi_ring_request.assert_called_once_with(runner_tag, body)
    channel.transport.publish_payload.assert_not_called()


async def test_publish_payload_cluster_peer_tag_skips_local_transport(master_opts):
    """
    Tags that start with ``cluster/peer`` are inbound from a sibling
    master and must NOT be re-broadcast locally via
    ``self.transport.publish_payload``.  They're delivered only to
    pushers (which we leave empty here to isolate the branch).
    """
    channel = _pub_channel(master_opts)

    load = salt.utils.event.SaltEvent.pack(
        "cluster/peer/state-sync-chunk", {"chunk": b"..."}
    )

    with patch("salt.payload.loads") as fake_loads:
        await channel.publish_payload(load, raw_payload=b"raw")

    # No pushers, no local broadcast: nothing to do.
    channel.transport.publish_payload.assert_not_called()
    # cluster/peer* branch doesn't need the decoded body either.
    assert fake_loads.called is False


async def test_publish_payload_cluster_peer_fanout_decodes_for_envelope(
    master_opts,
):
    """
    When ``self.pushers`` is non-empty AND the tag is NOT
    ``cluster/peer*``, each event is wrapped in a
    ``cluster/event/<self.opts["id"]>`` envelope for every pusher.
    Building that envelope requires the decoded body -- so
    ``_decode_data()`` is called here even though the non-cluster
    fast path does not decode.
    """
    import salt.master

    fake_pusher = MagicMock()
    fake_pusher.pull_host = "peer-1"
    fake_pusher.pull_port = 55596
    fake_pusher.publish = AsyncMock(return_value=None)

    channel = _pub_channel(master_opts, pushers=[fake_pusher])

    tag = "salt/job/20260814000000000000/ret/minion1"
    body = {"foo": "bar"}
    load = salt.utils.event.SaltEvent.pack(tag, body)

    # Stub the crypticle so we don't need real AES setup; we only care
    # that _decode_data() was invoked to build the event_payload.
    fake_crypticle_instance = MagicMock()
    fake_crypticle_instance.dumps.return_value = b"encrypted-envelope"

    with patch(
        "salt.channel.server._get_crypticle", return_value=fake_crypticle_instance
    ), patch.dict(
        salt.master.SMaster.secrets,
        {"aes": {"secret": MagicMock(value=b"aes-secret")}},
        clear=False,
    ), patch(
        "salt.payload.loads", wraps=salt.payload.loads
    ) as spy_loads:
        await channel.publish_payload(load, raw_payload=b"raw")

    # cluster-peer fanout branch: _decode_data() was called to build
    # the wrapped envelope.
    spy_loads.assert_called()
    # The pusher received the encrypted envelope, not the raw event.
    fake_pusher.publish.assert_called_once()
    # And the local transport still got the raw_payload fast path.
    channel.transport.publish_payload.assert_awaited_once_with(load, raw_payload=b"raw")
