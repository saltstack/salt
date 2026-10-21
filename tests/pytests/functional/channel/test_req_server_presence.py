"""
Functional tests for presence recording in
:meth:`salt.channel.server.ReqServerChannel.handle_message` (issue #58592).

When ``presence_id_tracking`` is enabled the master records a ``last seen``
timestamp in the ``presence`` cache bank for every minion id that passes the
protocol version 3 checks (id binding, valid id, token signed by the accepted
minion key). Nothing may be recorded for unauthenticated or spoofed requests.

The tests build real encrypted payloads with a real minion key and session key
and push them through ``handle_message`` against a real on-disk cache.
"""

import asyncio
import ctypes
import multiprocessing
import pathlib
import time

import pytest

import salt.cache
import salt.channel.server
import salt.crypt
import salt.exceptions
import salt.master
import salt.utils.stringutils
from tests.support.mock import AsyncMock

pytestmark = [
    pytest.mark.windows_whitelisted,
]

PRESENCE_BANK = "presence"
TTL = 60


@pytest.fixture
def aes_secret():
    key = salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string())
    old = salt.master.SMaster.secrets.get("aes")
    salt.master.SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(ctypes.c_char, key),
        "serial": multiprocessing.Value(ctypes.c_longlong, lock=False),
        "reload": salt.crypt.Crypticle.generate_key_string,
    }
    try:
        yield key
    finally:
        if old is None:
            salt.master.SMaster.secrets.pop("aes", None)
        else:
            salt.master.SMaster.secrets["aes"] = old


@pytest.fixture
def server_opts(tmp_path):
    sock_dir = tmp_path / "sock"
    pki_dir = tmp_path / "pki"
    cache_dir = tmp_path / "cache"
    for path in (sock_dir, pki_dir / "minions", cache_dir):
        path.mkdir(parents=True)
    return {
        "sock_dir": str(sock_dir),
        "pki_dir": str(pki_dir),
        "cachedir": str(cache_dir),
        "cache": "localfs",
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
        "worker_pools_enabled": False,
        "minimum_auth_version": 3,
        "presence_id_tracking": True,
        "presence_id_ttl": TTL,
    }


@pytest.fixture
def make_server(server_opts, aes_secret):
    servers = []

    def _make(**overrides):
        server_opts.update(overrides)
        server = salt.channel.server.ReqServerChannel.factory(server_opts)
        server.crypticle = salt.channel.server._get_crypticle(
            server_opts, aes_secret.decode()
        )
        server.payload_handler = AsyncMock(return_value=({"ok": True}, {"fun": "send"}))
        servers.append(server)
        return server

    yield _make
    for server in servers:
        server.close()


@pytest.fixture
def server(make_server):
    return make_server()


@pytest.fixture
def cache(server_opts):
    return salt.cache.Cache(server_opts)


@pytest.fixture
def minion_key(server_opts):
    """
    Generate a key pair for ``minion1`` and accept its public key.
    """
    priv, pub = salt.crypt.gen_keys(2048)
    (pathlib.Path(server_opts["pki_dir"]) / "minions" / "minion1").write_text(pub)
    return salt.crypt.PrivateKey.from_str(priv)


def _payload(server, key, id_="minion1", *, claimed_id=None, version=3, tok=True):
    load = {
        "cmd": "test_cmd",
        "id": claimed_id or id_,
        "ts": int(time.time()),
        "nonce": "0" * 32,
    }
    if tok:
        load["tok"] = key.encrypt(b"salt")
    crypticle = salt.channel.server._get_crypticle(server.opts, server.session_key(id_))
    return {
        "enc": "aes",
        "version": version,
        "id": id_,
        "load": crypticle.dumps(load),
    }


async def test_verified_request_records_presence(server, cache, minion_key):
    ret = await server.handle_message(_payload(server, minion_key))
    assert ret != "bad load"
    server.payload_handler.assert_awaited_once()
    record = cache.fetch(PRESENCE_BANK, "minion1")
    assert abs(record["ts"] - time.time()) < 30


async def test_option_off_records_nothing(make_server, cache, minion_key):
    server = make_server(presence_id_tracking=False)
    ret = await server.handle_message(_payload(server, minion_key))
    assert ret != "bad load"
    assert not cache.fetch(PRESENCE_BANK, "minion1")


async def test_invalid_token_records_nothing(make_server, cache, minion_key):
    """
    A request signed with a key that is not the accepted key for the id must
    neither be served nor recorded.
    """
    server = make_server()
    other_priv, _ = salt.crypt.gen_keys(2048)
    other_key = salt.crypt.PrivateKey.from_str(other_priv)
    ret = await server.handle_message(_payload(server, other_key))
    assert ret == "bad load"
    server.payload_handler.assert_not_awaited()
    assert not cache.fetch(PRESENCE_BANK, "minion1")


async def test_missing_token_records_nothing(server, cache, minion_key):
    ret = await server.handle_message(_payload(server, minion_key, tok=False))
    assert ret == "bad load"
    assert not cache.fetch(PRESENCE_BANK, "minion1")


async def test_forged_id_records_nothing(server, cache, minion_key, server_opts):
    """
    A minion encrypting with its own session but claiming another minion's id
    in the load must not mark either id as present.
    """
    other = pathlib.Path(server_opts["pki_dir"]) / "minions" / "minion2"
    other.write_text("fake-public-key")
    ret = await server.handle_message(
        _payload(server, minion_key, id_="minion1", claimed_id="minion2")
    )
    assert ret == "bad load"
    assert not cache.fetch(PRESENCE_BANK, "minion1")
    assert not cache.fetch(PRESENCE_BANK, "minion2")


async def test_old_protocol_version_records_nothing(
    make_server, cache, minion_key, server_opts
):
    """
    Below protocol version 3 the id is not bound to the session, so it must
    never be trusted for presence (even if an operator lowered
    ``minimum_auth_version``).
    """
    server = make_server(minimum_auth_version=0)
    payload = _payload(server, minion_key, version=2)
    # version 2 and below use the shared master AES key
    payload["load"] = server.crypticle.dumps(
        {"cmd": "test_cmd", "id": "minion1", "nonce": "0" * 32}
    )
    ret = await server.handle_message(payload)
    assert ret != "bad load"
    server.payload_handler.assert_awaited_once()
    assert not cache.fetch(PRESENCE_BANK, "minion1")


async def test_writes_are_throttled(server, cache, minion_key, monkeypatch):
    """
    Many requests inside the throttle window result in a single cache write.
    """
    stores = []
    real_store = salt.cache.Cache.store

    def counting_store(self, bank, key, data, *args, **kwargs):
        if bank == PRESENCE_BANK:
            stores.append(key)
        return real_store(self, bank, key, data, *args, **kwargs)

    monkeypatch.setattr(salt.cache.Cache, "store", counting_store)
    for _ in range(5):
        await server.handle_message(_payload(server, minion_key))
    assert stores == ["minion1"]
    assert cache.fetch(PRESENCE_BANK, "minion1")


async def test_cache_failure_does_not_fail_request(
    server, cache, minion_key, monkeypatch
):
    """
    Recording presence is best effort: a failing cache backend must not turn
    a valid minion request into an error.
    """

    def failing_store(self, bank, key, data, *args, **kwargs):
        raise salt.exceptions.SaltCacheError("boom")

    monkeypatch.setattr(salt.cache.Cache, "store", failing_store)
    ret = await server.handle_message(_payload(server, minion_key))
    assert ret not in ("bad load", "Some exception handling minion payload")
    server.payload_handler.assert_awaited_once()


async def test_recording_does_not_block_the_event_loop(
    server, cache, minion_key, monkeypatch
):
    """
    The cache write runs in an executor so a slow backend cannot stall the
    worker's event loop.
    """
    ticks = []

    def slow_store(self, bank, key, data, *args, **kwargs):
        time.sleep(0.5)

    async def ticker():
        while True:
            ticks.append(time.monotonic())
            await asyncio.sleep(0.05)

    monkeypatch.setattr(salt.cache.Cache, "store", slow_store)
    task = asyncio.ensure_future(ticker())
    try:
        await server.handle_message(_payload(server, minion_key))
    finally:
        task.cancel()
    assert len(ticks) >= 5
