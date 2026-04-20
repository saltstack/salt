"""
Functional tests for :class:`salt.channel.server.ReqServerChannel`
internals that don't require a full master daemon -- session-key
caching / rotation, cluster-aware AES key selection, payload
validation, and key normalization.

These tests instantiate the ReqServerChannel directly against a
minimal on-disk opts layout; fixtures from ``conftest.py`` take care
of seeding ``salt.master.SMaster.secrets["aes"]``.
"""

import ctypes
import logging
import multiprocessing
import os
import pathlib
import time

import pytest

import salt.channel.server
import salt.crypt
import salt.master
import salt.utils.stringutils

log = logging.getLogger(__name__)


@pytest.fixture
def req_server_opts(tmp_path):
    """
    Minimal master opts dict sufficient to build a
    :class:`ReqServerChannel` without a running master.
    """
    sock_dir = tmp_path / "sock"
    pki_dir = tmp_path / "pki"
    cache_dir = tmp_path / "cache"
    sock_dir.mkdir()
    pki_dir.mkdir()
    cache_dir.mkdir()
    return {
        "sock_dir": str(sock_dir),
        "pki_dir": str(pki_dir),
        "cachedir": str(cache_dir),
        "key_pass": None,
        "keysize": 2048,
        "cluster_id": None,
        "master_sign_pubkey": False,
        "pub_server_niceness": None,
        "con_cache": False,
        "zmq_monitor": False,
        "request_server_ttl": 60,
        "publish_session": 600,
        "keys.cache_driver": "localfs_key",
        "id": "master",
        "optimization_order": [0, 1, 2],
        "__role": "master",
        "master_sign_key_name": "master_sign",
        "permissive_pki_access": True,
    }


@pytest.fixture
def req_server(req_server_opts):
    server = salt.channel.server.ReqServerChannel.factory(req_server_opts)
    try:
        yield server
    finally:
        server.close()


@pytest.fixture
def clustered_req_server(req_server_opts, tmp_path):
    """
    Like ``req_server`` but configured as a cluster member so the
    cluster-aware code paths activate. The cluster PKI dir is created
    inside the per-test ``tmp_path`` so the fixture is self-contained.
    """
    cluster_pki = tmp_path / "cluster_pki"
    cluster_pki.mkdir()
    (cluster_pki / "peers").mkdir()
    req_server_opts["cluster_id"] = "my_cluster"
    req_server_opts["cluster_pki_dir"] = str(cluster_pki)
    req_server_opts["cluster_key_pass"] = None
    req_server_opts["cluster_peers"] = []
    req_server_opts["cluster_secret"] = None
    server = salt.channel.server.ReqServerChannel.factory(req_server_opts)
    try:
        yield server
    finally:
        server.close()


@pytest.fixture
def cluster_aes_secret():
    """
    Install a ``cluster_aes`` entry in ``SMaster.secrets`` and remove
    it after the test so cluster-aware channels have something to read.
    """
    key = salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string())
    salt.master.SMaster.secrets["cluster_aes"] = {
        "secret": multiprocessing.Array(ctypes.c_char, key),
        "serial": multiprocessing.Value(ctypes.c_longlong, lock=False),
        "reload": salt.crypt.Crypticle.generate_key_string,
    }
    try:
        yield key
    finally:
        salt.master.SMaster.secrets.pop("cluster_aes", None)


def test_compare_keys_normalizes_line_endings():
    """
    :meth:`ReqServerChannel.compare_keys` must treat two keys as equal
    when they only differ by surrounding whitespace or CRLF vs LF line
    endings -- the minion half of the handshake does not guarantee
    either normalization.
    """
    unix = "-----BEGIN PUBLIC KEY-----\nAAAA\nBBBB\nCCCC\n-----END PUBLIC KEY-----"
    dos = unix.replace("\n", "\r\n") + "\r\n   "
    padded = "\n\n   " + unix + "\n\n"

    assert salt.channel.server.ReqServerChannel.compare_keys(unix, dos) is True
    assert salt.channel.server.ReqServerChannel.compare_keys(unix, padded) is True


def test_compare_keys_detects_real_difference():
    """
    Two different keys must NOT compare equal even after normalization;
    otherwise an attacker could bypass the minion-key check by
    resubmitting a different key with matching whitespace.
    """
    a = "-----BEGIN PUBLIC KEY-----\nAAAA\n-----END PUBLIC KEY-----"
    b = "-----BEGIN PUBLIC KEY-----\nBBBB\n-----END PUBLIC KEY-----"
    assert salt.channel.server.ReqServerChannel.compare_keys(a, b) is False


def test_aes_key_non_cluster_mode(req_server):
    """
    Without ``cluster_id`` set, ``aes_key`` returns the non-cluster
    ``SMaster.secrets['aes']`` value. The ``_prepare_aes`` fixture in
    ``conftest.py`` seeds that secret.
    """
    assert req_server.opts.get("cluster_id") in (None, "")
    expected = salt.master.SMaster.secrets["aes"]["secret"].value
    assert req_server.aes_key == expected


def test_aes_key_cluster_mode(clustered_req_server, cluster_aes_secret):
    """
    With ``cluster_id`` set, ``aes_key`` returns the cluster AES key
    -- NOT the per-master one. Mixing up the two would make a cluster
    master sign payloads with a key peers cannot verify.
    """
    assert clustered_req_server.aes_key == cluster_aes_secret
    # And explicitly different from the per-master aes secret.
    assert (
        clustered_req_server.aes_key
        != salt.master.SMaster.secrets["aes"]["secret"].value
    )


async def test_update_aes_picks_up_rotation(req_server, io_loop):
    """
    When the shared ``SMaster.secrets['aes']`` value is rotated out
    from under the channel, :meth:`_update_aes` must detect the change
    and re-build its ``crypticle`` so subsequent encrypted responses
    use the new key.
    """

    async def handler(payload):
        return payload, {"fun": "send"}

    req_server.post_fork(handler, io_loop)
    original_crypticle = req_server.crypticle

    assert req_server._update_aes() is False

    new_key = salt.utils.stringutils.to_bytes(
        salt.crypt.Crypticle.generate_key_string()
    )
    salt.master.SMaster.secrets["aes"]["secret"].value = new_key

    assert req_server._update_aes() is True
    assert req_server.crypticle is not original_crypticle
    assert req_server.crypticle.key_string == new_key
    assert req_server._update_aes() is False


async def test_update_aes_uses_cluster_key_when_clustered(
    clustered_req_server, io_loop, cluster_aes_secret
):
    """
    When ``cluster_id`` is set the rotation detection must watch
    ``cluster_aes`` rather than the per-master ``aes`` -- otherwise
    cluster AES rotations would never be picked up.
    """

    async def handler(payload):
        return payload, {"fun": "send"}

    clustered_req_server.post_fork(handler, io_loop)
    assert clustered_req_server.crypticle.key_string == cluster_aes_secret

    new_key = salt.utils.stringutils.to_bytes(
        salt.crypt.Crypticle.generate_key_string()
    )
    salt.master.SMaster.secrets["cluster_aes"]["secret"].value = new_key

    # Rotating the non-cluster aes key must NOT trigger a refresh.
    salt.master.SMaster.secrets["aes"]["secret"].value = (
        salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string())
    )

    assert clustered_req_server._update_aes() is True
    assert clustered_req_server.crypticle.key_string == new_key


def test_session_key_creates_file_and_caches(req_server):
    """
    The first call to :meth:`session_key` for a minion generates a
    per-minion session key on disk under ``{cachedir}/sessions/`` and
    caches it in memory; the second call returns the same value
    without touching disk again.
    """
    path = pathlib.Path(req_server.opts["cachedir"]) / "sessions" / "minionA"
    assert not path.exists()

    key_one = req_server.session_key("minionA")
    assert path.exists()
    # In-memory cache is populated.
    assert "minionA" in req_server.sessions
    cached_mtime = req_server.sessions["minionA"][0]

    key_two = req_server.session_key("minionA")
    assert key_one == key_two
    # Same cache entry -- no rotation and no file rewrite.
    assert req_server.sessions["minionA"][0] == cached_mtime


def test_session_key_rotates_after_expiry(req_server):
    """
    When the per-minion session file on disk is older than
    ``publish_session``, :meth:`session_key` must rotate the key
    rather than keep serving the expired one.
    """
    req_server.opts["publish_session"] = 1

    original = req_server.session_key("minionB")
    path = pathlib.Path(req_server.opts["cachedir"]) / "sessions" / "minionB"

    # Drop the in-memory cache entry so the file-mtime check runs, and
    # back-date the file on disk to force rotation.
    req_server.sessions.pop("minionB", None)
    stale_time = time.time() - 3600
    os.utime(path, (stale_time, stale_time))

    rotated = req_server.session_key("minionB")
    assert rotated != original
    # And the in-memory cache is now refreshed with the new value.
    assert req_server.sessions["minionB"][1] == rotated


def test_session_keys_are_unique_per_minion(req_server):
    """
    Session keys must be per-minion; a minion must not be able to
    decrypt frames destined for another minion with its own session
    key.
    """
    a = req_server.session_key("minionA")
    b = req_server.session_key("minionB")
    c = req_server.session_key("minionC")
    assert len({a, b, c}) == 3


async def test_handle_message_rejects_non_dict(req_server, io_loop):
    """
    A non-dict payload must be rejected with the standard ``bad
    load`` reply, not an unhandled exception.
    """

    async def handler(payload):
        return payload, {"fun": "send"}

    req_server.post_fork(handler, io_loop)
    for bad in (b"raw bytes", ["not", "a", "dict"], "string", 12345):
        assert await req_server.handle_message(bad) == "bad load"


async def test_handle_message_rejects_missing_fields(req_server, io_loop):
    """
    Dict payloads lacking ``enc`` or ``load`` must be rejected
    before any decryption is attempted.
    """

    async def handler(payload):
        return payload, {"fun": "send"}

    req_server.post_fork(handler, io_loop)
    assert await req_server.handle_message({"load": {}}) == "bad load"
    assert await req_server.handle_message({"enc": "aes"}) == "bad load"
    assert await req_server.handle_message({}) == "bad load"


async def test_handle_message_rejects_old_protocol_version(req_server, io_loop, caplog):
    """
    If ``minimum_auth_version`` is configured, any payload advertising
    a lower version must be rejected with ``bad load`` and an audit
    log line identifying the offending minion.
    """

    async def handler(payload):
        return payload, {"fun": "send"}

    req_server.post_fork(handler, io_loop)
    req_server.opts["minimum_auth_version"] = 3

    payload = {
        "enc": "aes",
        "version": 2,
        "load": {"id": "too-old-minion"},
    }
    with caplog.at_level(logging.WARNING):
        ret = await req_server.handle_message(payload)
    assert ret == "bad load"
    assert "too-old-minion" in caplog.text
    assert "minimum required: 3" in caplog.text
