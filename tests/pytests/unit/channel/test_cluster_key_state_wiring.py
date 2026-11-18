"""
Server-side wiring tests for the unified cluster-key propagation
state machine.

These tests focus on the ``MasterPubServerChannel.handle_pool_publish``
install sites for ``cluster_aes`` and ``cluster.pem`` under
``cluster/peer/join-reply``:

* The state machine is consulted on every install path.
* BOOTSTRAP accepts the first arrival and commits.
* COMMITTED equal is a no-op (no cache.store, no master_key.key
  rebind for cluster.pem).
* COMMITTED mismatch WARNs + skips (critically: no cluster.pem
  rewrite, no master_key.key flip -- NEW-11 closure).
* The founder-wait window DEFERs non-founder arrivals during
  BOOTSTRAP.
* ``drop_all_pending`` fires on BOOTSTRAP -> COMMITTED for
  ``cluster_aes``.

The tests build a stripped-down channel via ``__new__`` and drive
``handle_pool_publish`` directly with a crafted inner payload, same
pattern as the existing ``test_join_reply_refreshes_master_keys_cache_70090``.
"""

import pytest

import salt.channel._cluster_key_state as _cks
import salt.channel.server as server
import salt.crypt
import salt.master
import salt.payload
import salt.utils.event
from tests.support.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_channel(tmp_path, opts_extra=None):
    """Build a minimal ``MasterPubServerChannel`` for the join-reply tests."""
    cluster_pki = tmp_path / "cluster_pki"
    cluster_pki.mkdir()
    opts = {
        "id": "joiner_master",
        "cluster_id": "cluster-A",
        "cluster_peers": ["founder"],
        "cluster_pki_dir": str(cluster_pki),
        "cluster_encryption_algorithm": "OAEP-SHA1",
        "sock_dir": str(tmp_path / "sock"),
        _cks.OPT_FOUNDER_WAIT: 2.0,
    }
    if opts_extra:
        opts.update(opts_extra)
    (tmp_path / "sock").mkdir()
    channel = server.MasterPubServerChannel.__new__(server.MasterPubServerChannel)
    channel.opts = opts
    channel._discover_token = b"test-token-0000000000000000000000"
    channel._discover_event = None
    channel._raft_dispatcher = None
    channel._raft_service = None
    channel._cluster_key_sm = None
    channel._mark_joined_cluster = MagicMock()
    channel._start_raft_as_learner = MagicMock()
    fake_master_key = MagicMock()
    fake_master_key.master_rsa_path = str(tmp_path / "master.pem")
    fake_master_key.cluster_key = "PLACEHOLDER-CLUSTER-KEY"
    fake_master_key.key = "PLACEHOLDER-CLUSTER-KEY"
    fake_master_key.cache = MagicMock()
    channel.master_key = fake_master_key
    return channel, cluster_pki


def _pack_join_reply(inner_payload, tag_suffix="founder"):
    data = {"payload": salt.payload.dumps(inner_payload), "sig": b"sig"}
    tag = f"cluster/peer/join-reply/{tag_suffix}"
    return salt.utils.event.SaltEvent.pack(tag, data)


# ---------------------------------------------------------------------------
# cluster.pem: COMMITTED + divergent arrival must NOT rewrite disk
# or flip master_key.key -- this is the NEW-11 closure.
# ---------------------------------------------------------------------------


async def test_cluster_pem_committed_mismatch_skips_install(tmp_path, caplog):
    import logging as _logging

    channel, cluster_pki = _build_channel(tmp_path)
    # Pre-seed as COMMITTED with "cluster-authoritative" PEM.
    committed_pem = b"-----BEGIN RSA PRIVATE KEY-----\nAUTHORITATIVE\n-----END RSA PRIVATE KEY-----\n"
    (cluster_pki / "cluster.pem").write_bytes(committed_pem)
    (cluster_pki / "cluster.pub").write_text("AUTHORITATIVE-PUB")
    # Write the sentinel so load_from_disk transitions to COMMITTED.
    _cks.write_sentinel_fingerprint(
        _cks.cluster_key_sentinel_path(cluster_pki, "cluster_pem"),
        _cks.fingerprint_bytes(committed_pem),
    )

    divergent_pem = (
        b"-----BEGIN RSA PRIVATE KEY-----\nDIVERGENT\n-----END RSA PRIVATE KEY-----\n"
    )
    session_key = salt.crypt.Crypticle.generate_key_string()
    salted_session_bytes = channel._discover_token + session_key.encode()
    fake_private_key = MagicMock()
    fake_private_key.decrypt.return_value = salted_session_bytes
    fake_crypticle = MagicMock()
    fake_crypticle.decrypt.return_value = divergent_pem

    caplog.set_level(_logging.WARNING, logger="salt.channel._cluster_key_state")

    with patch("salt.crypt.PrivateKey.from_file", return_value=fake_private_key), patch(
        "salt.crypt.Crypticle", return_value=fake_crypticle
    ), patch("salt.crypt.PrivateKey.from_str", return_value=object()):
        inner_payload = {
            "peer_id": "attacker",
            "cluster_key_session": b"enc",
            "cluster_pem": b"enc-pem",
            "cluster_pub": "ATTACKER-PUB",
            "peers": {},
        }
        await channel.handle_pool_publish(_pack_join_reply(inner_payload, "attacker"))

    # Disk unchanged -- committed PEM survives.
    assert (cluster_pki / "cluster.pem").read_bytes() == committed_pem
    assert (cluster_pki / "cluster.pub").read_text() == "AUTHORITATIVE-PUB"
    # master_key.key / master_key.cluster_key unchanged.
    assert channel.master_key.cluster_key == "PLACEHOLDER-CLUSTER-KEY"
    assert channel.master_key.key == "PLACEHOLDER-CLUSTER-KEY"
    # WARN emitted.
    assert any(
        "refusing install" in rec.getMessage() for rec in caplog.records
    ), f"expected refusing-install WARN; got {[r.getMessage() for r in caplog.records]}"


# ---------------------------------------------------------------------------
# cluster.pem: COMMITTED + identical arrival is a silent no-op
# ---------------------------------------------------------------------------


async def test_cluster_pem_committed_equal_is_noop(tmp_path):
    channel, cluster_pki = _build_channel(tmp_path)
    committed_pem = (
        b"-----BEGIN RSA PRIVATE KEY-----\nSAME\n-----END RSA PRIVATE KEY-----\n"
    )
    (cluster_pki / "cluster.pem").write_bytes(committed_pem)
    (cluster_pki / "cluster.pub").write_text("SAME-PUB")
    _cks.write_sentinel_fingerprint(
        _cks.cluster_key_sentinel_path(cluster_pki, "cluster_pem"),
        _cks.fingerprint_bytes(committed_pem),
    )

    session_key = salt.crypt.Crypticle.generate_key_string()
    salted_session_bytes = channel._discover_token + session_key.encode()
    fake_private_key = MagicMock()
    fake_private_key.decrypt.return_value = salted_session_bytes
    fake_crypticle = MagicMock()
    # Arriving bytes identical to committed -> noop.
    fake_crypticle.decrypt.return_value = committed_pem

    with patch("salt.crypt.PrivateKey.from_file", return_value=fake_private_key), patch(
        "salt.crypt.Crypticle", return_value=fake_crypticle
    ), patch("salt.crypt.PrivateKey.from_str", return_value=object()):
        inner_payload = {
            "peer_id": "founder",
            "cluster_key_session": b"enc",
            "cluster_pem": b"enc-pem",
            "cluster_pub": "SAME-PUB",
            "peers": {},
        }
        await channel.handle_pool_publish(_pack_join_reply(inner_payload))

    # No cache.store calls -- state machine short-circuited the install.
    stored_keys = {
        call.args[1]
        for call in channel.master_key.cache.store.call_args_list
        if len(call.args) >= 2
    }
    assert (
        stored_keys == set()
    ), f"COMMITTED+equal path must not call cache.store; got {stored_keys}"
    # master_key.cluster_key unchanged.
    assert channel.master_key.cluster_key == "PLACEHOLDER-CLUSTER-KEY"


# ---------------------------------------------------------------------------
# cluster.pem: BOOTSTRAP + founder arrival commits and persists sentinel
# ---------------------------------------------------------------------------


async def test_cluster_pem_bootstrap_founder_arrival_commits(tmp_path):
    channel, cluster_pki = _build_channel(tmp_path)
    (cluster_pki / "cluster.pem").write_bytes(b"PLACEHOLDER")
    (cluster_pki / "cluster.pub").write_text("PLACEHOLDER-PUB")

    delivered_pem = (
        b"-----BEGIN RSA PRIVATE KEY-----\nFOUNDER\n-----END RSA PRIVATE KEY-----\n"
    )
    delivered_pub = "FOUNDER-PUB"

    session_key = salt.crypt.Crypticle.generate_key_string()
    salted_session_bytes = channel._discover_token + session_key.encode()
    fake_private_key = MagicMock()
    fake_private_key.decrypt.return_value = salted_session_bytes
    fake_crypticle = MagicMock()
    fake_crypticle.decrypt.return_value = delivered_pem
    reloaded = object()

    with patch("salt.crypt.PrivateKey.from_file", return_value=fake_private_key), patch(
        "salt.crypt.Crypticle", return_value=fake_crypticle
    ), patch("salt.crypt.PrivateKey.from_str", return_value=reloaded):
        inner_payload = {
            "peer_id": "founder",
            "cluster_key_session": b"enc",
            "cluster_pem": b"enc-pem",
            "cluster_pub": delivered_pub,
            "peers": {},
        }
        await channel.handle_pool_publish(_pack_join_reply(inner_payload))

    # Disk updated.
    assert (cluster_pki / "cluster.pem").read_bytes() == delivered_pem
    assert (cluster_pki / "cluster.pub").read_text() == delivered_pub
    # master_key.key rebound.
    assert channel.master_key.cluster_key is reloaded
    assert channel.master_key.key is reloaded
    # Sentinel exists with matching fingerprint.
    sentinel = _cks.cluster_key_sentinel_path(cluster_pki, "cluster_pem")
    assert sentinel.exists()
    assert _cks.read_sentinel_fingerprint(sentinel) == _cks.fingerprint_bytes(
        delivered_pem
    )
    # In-memory state machine is now COMMITTED.
    sm = channel._cluster_key_state_machine()
    assert sm.is_committed("cluster_pem")


# ---------------------------------------------------------------------------
# cluster.pem: BOOTSTRAP + non-founder arrival within window DEFERs
# ---------------------------------------------------------------------------


async def test_cluster_pem_bootstrap_non_founder_deferred(tmp_path):
    channel, cluster_pki = _build_channel(
        tmp_path, opts_extra={_cks.OPT_FOUNDER_WAIT: 5.0}
    )
    (cluster_pki / "cluster.pem").write_bytes(b"PLACEHOLDER")
    (cluster_pki / "cluster.pub").write_text("PLACEHOLDER-PUB")

    non_founder_pem = (
        b"-----BEGIN RSA PRIVATE KEY-----\nNONFOUNDER\n-----END RSA PRIVATE KEY-----\n"
    )
    session_key = salt.crypt.Crypticle.generate_key_string()
    salted_session_bytes = channel._discover_token + session_key.encode()
    fake_private_key = MagicMock()
    fake_private_key.decrypt.return_value = salted_session_bytes
    fake_crypticle = MagicMock()
    fake_crypticle.decrypt.return_value = non_founder_pem

    with patch("salt.crypt.PrivateKey.from_file", return_value=fake_private_key), patch(
        "salt.crypt.Crypticle", return_value=fake_crypticle
    ), patch("salt.crypt.PrivateKey.from_str", return_value=object()):
        inner_payload = {
            "peer_id": "non_founder_peer",
            "cluster_key_session": b"enc",
            "cluster_pem": b"enc-pem",
            "cluster_pub": "NONFOUNDER-PUB",
            "peers": {},
        }
        await channel.handle_pool_publish(
            _pack_join_reply(inner_payload, "non_founder_peer")
        )

    # Disk unchanged -- deferred.
    assert (cluster_pki / "cluster.pem").read_bytes() == b"PLACEHOLDER"
    # Sentinel NOT written.
    sentinel = _cks.cluster_key_sentinel_path(cluster_pki, "cluster_pem")
    assert not sentinel.exists()
    # State still BOOTSTRAP.
    sm = channel._cluster_key_state_machine()
    assert sm.state_of("cluster_pem") == _cks.STATE_BOOTSTRAP


# ---------------------------------------------------------------------------
# cluster_aes: BOOTSTRAP + founder arrival commits + fires drop_all_pending
# on bytes-change (prev != new).
# ---------------------------------------------------------------------------


async def test_cluster_aes_bootstrap_founder_commits_and_drops_pending(tmp_path):
    channel, cluster_pki = _build_channel(tmp_path)
    # SMaster.secrets["cluster_aes"] must exist with a different
    # value so drop_all_pending fires on the transition.
    existing = bytearray(b"PRE-BOOTSTRAP-AES" + b"\0" * 32)
    fake_secret = MagicMock()
    fake_secret.value = bytes(existing)
    fake_lock = MagicMock()
    fake_lock.__enter__ = MagicMock(return_value=None)
    fake_lock.__exit__ = MagicMock(return_value=None)
    fake_secret.get_lock = MagicMock(return_value=fake_lock)
    salt.master.SMaster.secrets["cluster_aes"] = {"secret": fake_secret}

    delivered_aes = b"FOUNDER-AES-KEY-BYTES-32-LONG-OK"
    salted_bytes = channel._discover_token + delivered_aes
    fake_private_key = MagicMock()
    fake_private_key.decrypt.return_value = salted_bytes

    with patch("salt.crypt.PrivateKey.from_file", return_value=fake_private_key), patch(
        "salt.cache._cluster_replicator.drop_all_pending"
    ) as drop_mock:
        inner_payload = {
            "peer_id": "founder",
            "cluster_aes": b"encrypted-aes",
            # No cluster_pem / cluster_key_session -- skip PEM branch.
            "peers": {},
        }
        await channel.handle_pool_publish(_pack_join_reply(inner_payload))

    # .aes written with delivered bytes.
    assert (cluster_pki / ".aes").read_bytes() == delivered_aes
    # SMaster.secrets value flipped.
    assert salt.master.SMaster.secrets["cluster_aes"]["secret"].value == delivered_aes
    # drop_all_pending fired on the transition.
    assert drop_mock.called, "drop_all_pending must fire on BOOTSTRAP->COMMITTED"
    # Sentinel on disk.
    sentinel = _cks.cluster_key_sentinel_path(cluster_pki, "cluster_aes")
    assert sentinel.exists()
    assert _cks.read_sentinel_fingerprint(sentinel) == _cks.fingerprint_bytes(
        delivered_aes
    )


# ---------------------------------------------------------------------------
# cluster_aes: COMMITTED + equal arrival is a no-op (no drop_all_pending)
# ---------------------------------------------------------------------------


async def test_cluster_aes_committed_equal_is_noop(tmp_path):
    channel, cluster_pki = _build_channel(tmp_path)
    committed_aes = b"COMMITTED-AES-BYTES-32-BYTES-OKK"
    (cluster_pki / ".aes").write_bytes(committed_aes)
    _cks.write_sentinel_fingerprint(
        _cks.cluster_key_sentinel_path(cluster_pki, "cluster_aes"),
        _cks.fingerprint_bytes(committed_aes),
    )

    fake_secret = MagicMock()
    fake_secret.value = committed_aes
    fake_lock = MagicMock()
    fake_lock.__enter__ = MagicMock(return_value=None)
    fake_lock.__exit__ = MagicMock(return_value=None)
    fake_secret.get_lock = MagicMock(return_value=fake_lock)
    salt.master.SMaster.secrets["cluster_aes"] = {"secret": fake_secret}

    salted_bytes = channel._discover_token + committed_aes  # equal
    fake_private_key = MagicMock()
    fake_private_key.decrypt.return_value = salted_bytes

    with patch("salt.crypt.PrivateKey.from_file", return_value=fake_private_key), patch(
        "salt.cache._cluster_replicator.drop_all_pending"
    ) as drop_mock:
        inner_payload = {
            "peer_id": "founder",
            "cluster_aes": b"enc",
            "peers": {},
        }
        await channel.handle_pool_publish(_pack_join_reply(inner_payload))

    # SMaster.secrets value unchanged (lock NOT entered; secret setter
    # NOT called).
    assert salt.master.SMaster.secrets["cluster_aes"]["secret"].value == committed_aes
    # No drop_all_pending on equal arrival.
    assert not drop_mock.called


@pytest.fixture(autouse=True)
def _restore_smaster_secrets():
    """Restore a baseline SMaster.secrets after each test."""
    saved = dict(salt.master.SMaster.secrets)
    yield
    salt.master.SMaster.secrets.clear()
    salt.master.SMaster.secrets.update(saved)
