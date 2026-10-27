"""
Regression tests for mutual-TLS masters: the worker-pool router must not
wrap its local IPC hop in TLS, and the publish-server channel must survive a
pickle round trip (``spawn``/``forkserver`` start methods).
"""

import asyncio
import pickle
import ssl

import pytest

import salt.channel.server as server
import salt.crypt
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.core_test,
]


SSL_OPTS = {
    "certfile": "/etc/pki/tls/certs/salt-master.crt",
    "keyfile": "/etc/pki/tls/private/salt-master.key",
    "ca_certs": "/etc/pki/tls/certs/corp-root.crt",
    "cert_reqs": ssl.CERT_REQUIRED,
}


def _post_fork(channel, io_loop):
    """
    Run ``post_fork`` for the routing process with the master-side
    infrastructure (secrets, event bus, master keys, auth helpers) stubbed.
    """
    secrets = {
        "aes": {"secret": MagicMock(value=salt.crypt.Crypticle.generate_key_string())}
    }
    with patch("salt.master.SMaster.secrets", secrets), patch(
        "salt.utils.event.get_master_event"
    ), patch("salt.crypt.MasterKeys"), patch.object(
        channel, "_ensure_auth_support", MagicMock()
    ):
        channel.post_fork(MagicMock(), io_loop)


@pytest.fixture
def tls_master_opts(master_opts):
    master_opts["transport"] = "tcp"
    master_opts["ssl"] = dict(SSL_OPTS)
    master_opts["worker_pools_enabled"] = True
    master_opts["ipc_mode"] = "ipc"
    return master_opts


@pytest.fixture
def pool_channel(tls_master_opts):
    transport = MagicMock()
    channel = server.PoolRoutingChannel(
        tls_master_opts, transport, {"default": {"commands": ["*"], "worker_count": 2}}
    )
    return channel


def test_pool_routing_pre_fork_does_not_inherit_ssl(pool_channel, tls_master_opts):
    """
    The pool RequestServer listens on a unix socket (or loopback TCP) that the
    router's RequestClient connects to in plaintext.  Inheriting the external
    ``ssl`` dict made every request fail with WRONG_VERSION_NUMBER.
    """
    seen = []

    def fake_create_server_transport(opts):
        seen.append(opts)
        return MagicMock()

    with patch(
        "salt.utils.channel.create_server_transport", fake_create_server_transport
    ), patch.object(server, "ReqServerChannel") as req_server_channel, patch(
        "salt.master.SMaster.secrets", {}
    ):
        pool_channel.pre_fork(MagicMock())

    assert len(seen) == 1
    assert seen[0]["ssl"] is None
    assert seen[0]["pool_name"] == "default"
    assert seen[0]["worker_pools_enabled"] is False
    # The external transport still carries the operator's TLS settings.
    assert tls_master_opts["ssl"] == SSL_OPTS
    req_server_channel.assert_called_once()
    assert req_server_channel.call_args.args[0]["ssl"] is None


def test_pool_routing_post_fork_clients_do_not_inherit_ssl(
    pool_channel, tls_master_opts
):
    seen = []

    def fake_create_request_client(opts, io_loop):
        seen.append(opts)
        return MagicMock()

    loop = asyncio.new_event_loop()
    try:
        with patch(
            "salt.utils.channel.create_request_client", fake_create_request_client
        ):
            _post_fork(pool_channel, loop)
    finally:
        loop.close()

    assert seen, "no pool RequestClient was created"
    for opts in seen:
        assert opts["ssl"] is None
        assert opts["master_uri"].startswith("ipc://")
    assert tls_master_opts["ssl"] == SSL_OPTS


def test_pool_routing_pre_fork_tcp_ipc_binds_loopback_only(tls_master_opts):
    """
    With TLS stripped, the pool RequestServer on ``ipc_mode: tcp`` must bind
    loopback, never ``interface`` -- otherwise it would be a plaintext,
    unauthenticated path into the MWorkers.
    """
    tls_master_opts["ipc_mode"] = "tcp"
    tls_master_opts["interface"] = "0.0.0.0"
    tls_master_opts["ipv6"] = True
    channel = server.PoolRoutingChannel(
        tls_master_opts,
        MagicMock(),
        {"default": {"commands": ["*"], "worker_count": 1}},
    )
    seen = []

    def fake_create_server_transport(opts):
        seen.append(opts)
        return MagicMock()

    with patch(
        "salt.utils.channel.create_server_transport", fake_create_server_transport
    ), patch.object(server, "ReqServerChannel"), patch(
        "salt.master.SMaster.secrets", {}
    ):
        channel.pre_fork(MagicMock())

    assert seen[0]["ssl"] is None
    assert seen[0]["interface"] == "127.0.0.1"
    assert seen[0]["ipv6"] is False
    assert tls_master_opts["interface"] == "0.0.0.0"


def test_pool_routing_post_fork_tcp_ipc_clients_do_not_inherit_ssl(
    tls_master_opts,
):
    tls_master_opts["ipc_mode"] = "tcp"
    channel = server.PoolRoutingChannel(
        tls_master_opts,
        MagicMock(),
        {"default": {"commands": ["*"], "worker_count": 1}},
    )
    seen = []

    def fake_create_request_client(opts, io_loop):
        seen.append(opts)
        return MagicMock()

    loop = asyncio.new_event_loop()
    try:
        with patch(
            "salt.utils.channel.create_request_client", fake_create_request_client
        ):
            _post_fork(channel, loop)
    finally:
        loop.close()

    assert seen
    assert all(opts["ssl"] is None for opts in seen)
    assert all(opts["master_uri"].startswith("tcp://127.0.0.1:") for opts in seen)


class _PicklableTransport:
    """Stand-in transport that survives pickling."""

    def close(self):
        pass


def test_pub_server_channel_pickle_roundtrip_restores_presence_state(master_opts):
    """
    ``PubServerChannel`` is handed to the publish daemon process.  Under the
    ``spawn`` start method it is pickled, and ``__setstate__`` used to drop
    ``aes_funcs`` (needed by ``presence_callback``) and to store
    ``presence_events`` under the wrong attribute name.
    """
    with patch("salt.master.AESFuncs") as aes_funcs, patch(
        "salt.utils.event.get_event"
    ), patch("salt.crypt.MasterKeys"), patch("salt.utils.minions.CkMinions"):
        channel = server.PubServerChannel(
            master_opts, _PicklableTransport(), presence_events=True
        )
        restored = pickle.loads(pickle.dumps(channel))

    assert restored.presence_events is True
    assert not hasattr(restored, "state")
    assert restored.aes_funcs is aes_funcs.return_value
    # Constructed once in __init__ and once more in __setstate__.
    assert aes_funcs.call_count == 2
    assert restored.present == {}
