"""
Functional tests for authentication version downgrade attacks.

These tests demonstrate the vulnerability where a malicious minion can
downgrade its authentication protocol version to bypass security features.
"""

import ctypes
import multiprocessing
import pathlib

import pytest

import salt.channel.client
import salt.channel.server
import salt.config
import salt.crypt
import salt.daemons.masterapi
import salt.master
import salt.payload
import salt.utils.event
import salt.utils.files
import salt.utils.platform
import salt.utils.process
import salt.utils.stringutils
from salt.master import SMaster

pytestmark = [
    pytest.mark.skip_on_spawning_platform(
        reason="These tests are currently broken on spawning platforms. Need to be rewritten.",
    ),
    pytest.mark.timeout_unless_on_windows(120),
]


@pytest.fixture
def channel_minion_id():
    return "test-minion-downgrade"


@pytest.fixture
def auth_pki_dir(tmp_path):
    """Setup PKI directory structure for functional auth tests."""
    if salt.utils.platform.is_darwin():
        # To avoid 'OSError: AF_UNIX path too long'
        _root_dir = pathlib.Path("/tmp").resolve() / tmp_path.name
        root_dir = _root_dir
    else:
        root_dir = tmp_path

    master_pki = root_dir / "master_pki"
    minion_pki = root_dir / "minion_pki"

    master_pki.mkdir(parents=True)
    minion_pki.mkdir(parents=True)
    (master_pki / "minions").mkdir()
    (master_pki / "minions_pre").mkdir()
    (master_pki / "minions_rejected").mkdir()
    (master_pki / "minions_denied").mkdir()

    # Generate keys
    master_priv, master_pub = salt.crypt.gen_keys(4096)
    (master_pki / "master.pem").write_text(master_priv)
    (master_pki / "master.pub").write_text(master_pub)

    minion_priv, minion_pub = salt.crypt.gen_keys(4096)
    (minion_pki / "minion.pem").write_text(minion_priv)
    (minion_pki / "minion.pub").write_text(minion_pub)

    yield root_dir

    if salt.utils.platform.is_darwin():
        import shutil

        shutil.rmtree(str(root_dir), ignore_errors=True)


def _create_functional_master_opts(
    auth_pki_dir, channel_minion_id, minimum_auth_version=0
):
    """Helper to create master configuration with specified minimum_auth_version."""
    import salt.config
    import salt.syspaths

    # Start with default master opts to get all necessary loader paths
    opts = salt.config.DEFAULT_MASTER_OPTS.copy()

    # Override with test-specific configuration
    opts.update(
        {
            "master_uri": "tcp://127.0.0.1:44506",
            "interface": "127.0.0.1",
            "ret_port": 44506,
            "ipv6": False,
            "sock_dir": str(auth_pki_dir / "sock"),
            "cachedir": str(auth_pki_dir / "cache"),
            "pki_dir": str(auth_pki_dir / "master_pki"),
            "id": "master",
            "__role": "master",
            "transport": "zeromq",
            "keysize": 4096,
            "max_minions": 0,
            "auto_accept": True,
            "open_mode": False,
            "key_pass": None,
            "publish_port": 44505,
            "auth_mode": 1,
            "auth_events": True,
            "publish_session": 86400,
            "request_server_ttl": 300,  # 5 minutes
            "worker_threads": 1,
            "cluster_id": None,
            "master_sign_pubkey": False,
            "sign_pub_messages": False,
            "minimum_auth_version": minimum_auth_version,
            "keys.cache_driver": "localfs_key",
            "extension_modules": str(auth_pki_dir / "extmods"),
            "file_roots": {"base": [str(auth_pki_dir / "file_roots")]},
            "pillar_roots": {"base": [str(auth_pki_dir / "pillar_roots")]},
        }
    )
    (auth_pki_dir / "sock").mkdir(exist_ok=True)
    (auth_pki_dir / "cache").mkdir(exist_ok=True)
    (auth_pki_dir / "cache" / "sessions").mkdir(exist_ok=True)

    # Accept the minion key
    minion_pub = auth_pki_dir / "minion_pki" / "minion.pub"
    master_minions = auth_pki_dir / "master_pki" / "minions" / channel_minion_id
    if minion_pub.exists():
        with salt.utils.files.fopen(str(minion_pub)) as src:
            with salt.utils.files.fopen(str(master_minions), "w") as dst:
                dst.write(src.read())

    return opts


@pytest.fixture
def functional_master_opts(auth_pki_dir, channel_minion_id):
    """Master configuration for functional tests (default: minimum_auth_version=3)."""
    return _create_functional_master_opts(
        auth_pki_dir, channel_minion_id, minimum_auth_version=3
    )


@pytest.fixture
def functional_minion_opts(auth_pki_dir, functional_master_opts, channel_minion_id):
    """Minion configuration for functional tests."""
    return {
        "master_uri": "tcp://127.0.0.1:44506",
        "interface": "127.0.0.1",
        "ret_port": 44506,
        "ipv6": False,
        "sock_dir": str(functional_master_opts["sock_dir"]),
        "pki_dir": str(auth_pki_dir / "minion_pki"),
        "id": channel_minion_id,
        "__role": "minion",
        "transport": "zeromq",
        "keysize": 4096,
        "encryption_algorithm": salt.crypt.OAEP_SHA1,
        "signing_algorithm": salt.crypt.PKCS1v15_SHA1,
        "master_port": 44506,
        "master_ip": "127.0.0.1",
    }


@pytest.mark.parametrize(
    "minimum_auth_version,attack_version,should_pass",
    [
        pytest.param(
            0,
            0,
            False,
            marks=pytest.mark.xfail(
                reason="Vulnerable: minimum_auth_version=0 allows all versions",
                strict=True,
            ),
        ),
        pytest.param(
            0,
            1,
            False,
            marks=pytest.mark.xfail(
                reason="Vulnerable: minimum_auth_version=0 allows all versions",
                strict=True,
            ),
        ),
        pytest.param(
            0,
            2,
            False,
            marks=pytest.mark.xfail(
                reason="Vulnerable: minimum_auth_version=0 allows all versions",
                strict=True,
            ),
        ),
        pytest.param(1, 0, True, id="v1-rejects-v0"),
        pytest.param(
            1,
            1,
            False,
            marks=pytest.mark.xfail(
                reason="Vulnerable: minimum_auth_version=1 allows v1", strict=True
            ),
        ),
        pytest.param(
            1,
            2,
            False,
            marks=pytest.mark.xfail(
                reason="Vulnerable: minimum_auth_version=1 allows v2", strict=True
            ),
        ),
        pytest.param(2, 0, True, id="v2-rejects-v0"),
        pytest.param(2, 1, True, id="v2-rejects-v1"),
        pytest.param(
            2,
            2,
            False,
            marks=pytest.mark.xfail(
                reason="Vulnerable: minimum_auth_version=2 allows v2", strict=True
            ),
        ),
        pytest.param(3, 0, True, id="v3-rejects-v0"),
        pytest.param(3, 1, True, id="v3-rejects-v1"),
        pytest.param(3, 2, True, id="v3-rejects-v2-SECURE"),
    ],
)
async def test_replay_attack_via_version_downgrade(
    auth_pki_dir,
    functional_minion_opts,
    channel_minion_id,
    minimum_auth_version,
    attack_version,
    should_pass,
):
    """
    REGRESSION TEST: CVE-2025-62349 - Authentication Protocol Version Downgrade Attack

    This parameterized test verifies that version downgrade attacks are prevented
    based on the minimum_auth_version configuration.

    Attack Scenario:
    A malicious or compromised minion attempts to authenticate using an older protocol
    version to bypass security features introduced in newer versions (token validation,
    TTL checks, ID matching, session keys). This allows the attacker to impersonate
    other minions or maintain persistent unauthorized access.

    Test Matrix:
    - minimum_auth_version=0: VULNERABLE - accepts all versions (xfail)
    - minimum_auth_version=1: Partially secure - rejects v0 only
    - minimum_auth_version=2: Partially secure - rejects v0, v1
    - minimum_auth_version=3: SECURE - rejects v0, v1, v2 (default and recommended)

    This test uses xfail for vulnerable configurations to document the security risk.
    """
    # Create master opts with the specified minimum_auth_version
    master_opts = _create_functional_master_opts(
        auth_pki_dir, channel_minion_id, minimum_auth_version
    )

    # Setup master secrets
    SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        ),
        "serial": multiprocessing.Value(ctypes.c_longlong, lock=False),
    }

    # Create server channel
    server_channel = salt.channel.server.ReqServerChannel.factory(master_opts)
    server_channel.auto_key = salt.daemons.masterapi.AutoKey(master_opts)
    server_channel.cache_cli = False
    server_channel.event = salt.utils.event.get_master_event(
        master_opts, master_opts["sock_dir"], listen=False
    )
    server_channel.master_key = salt.crypt.MasterKeys(master_opts)

    try:
        # Verify the configuration
        assert (
            master_opts.get("minimum_auth_version") == minimum_auth_version
        ), f"Master should have minimum_auth_version={minimum_auth_version}"

        # Read minion public key
        with salt.utils.files.fopen(
            str(auth_pki_dir / "minion_pki" / "minion.pub"), "r"
        ) as fp:
            pub_key = fp.read()

        # Create auth load for the attack version
        load = {
            "cmd": "_auth",
            "id": channel_minion_id,
            "pub": pub_key,
            "enc_algo": salt.crypt.OAEP_SHA1,
            "sig_algo": salt.crypt.PKCS1v15_SHA1,
        }

        # Add nonce for version 2+
        if attack_version >= 2:
            load["nonce"] = "test-nonce"

        # Create payload for handle_message
        payload = {"enc": "clear", "load": load, "version": attack_version}

        # Call handle_message which will enforce minimum_auth_version
        ret = await server_channel.handle_message(payload)

        # Check if attack was blocked
        if should_pass:
            # Attack should be blocked (old version rejected)
            # With proper minimum_auth_version, handle_message returns "bad load"
            assert ret == "bad load", (
                f"Expected 'bad load' for rejected version {attack_version} "
                f"with minimum {minimum_auth_version}"
            )
        else:
            # Vulnerable: attack succeeds (old version accepted)
            # Assert that auth SHOULD be rejected (but it won't be - causing xfail)
            # This assertion will FAIL for vulnerable configs, documenting the security issue
            assert ret == "bad load", (
                f"SECURITY ISSUE: Version {attack_version} was accepted "
                f"with minimum_auth_version={minimum_auth_version}"
            )

    finally:
        server_channel.close()
        if "aes" in SMaster.secrets:
            SMaster.secrets.pop("aes")


# Note: Additional functional tests for ID mismatch and token bypass
# have been covered in the unit tests. This single functional test
# demonstrates the replay attack scenario which is the most critical
# end-to-end attack vector.
