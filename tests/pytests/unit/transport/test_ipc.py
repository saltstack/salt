import hashlib

import pytest
import tornado.iostream
from pytestshellutils.utils import ports

import salt.config
import salt.transport
import salt.transport.ipc
import salt.utils.asynchronous
import salt.utils.platform

pytestmark = [
    pytest.mark.core_test,
]


@pytest.fixture
def sock_dir(tmp_path):
    sock_dir_path = tmp_path / "test-socks"
    sock_dir_path.mkdir(parents=True, exist_ok=True)
    yield sock_dir_path


@pytest.fixture
def minion_config(sock_dir, minion_opts):
    minion_opts["sock_dir"] = sock_dir
    yield minion_opts


def test_ipc_connect_in_async_methods():
    "The connect method is in IPCMessageSubscriber's async_methods property"
    assert "connect" in salt.transport.ipc.IPCMessageSubscriber.async_methods


async def test_ipc_connect_sync_wrapped(io_loop, tmp_path):
    """
    Ensure IPCMessageSubscriber.connect gets wrapped by
    salt.utils.asynchronous.SyncWrapper.
    """
    if salt.utils.platform.is_windows():
        socket_path = ports.get_unused_localhost_port()
    else:
        socket_path = str(tmp_path / "noexist.ipc")
    subscriber = salt.utils.asynchronous.SyncWrapper(
        salt.transport.ipc.IPCMessageSubscriber,
        args=(socket_path,),
        kwargs={"io_loop": io_loop},
        loop_kwarg="io_loop",
    )
    with pytest.raises(tornado.iostream.StreamClosedError):
        # Don't `await subscriber.connect()`, that's the purpose of the SyncWrapper
        subscriber.connect()


@pytest.fixture
def master_config(sock_dir, master_opts):
    master_opts["sock_dir"] = sock_dir
    yield master_opts


@pytest.mark.skip_on_windows(reason="Unix socket not available on win32")
def test_master_ipc_server_unix(master_config, sock_dir):
    assert master_config.get("ipc_mode") != "tcp"
    server = salt.transport.ipc_publish_server("master", master_config)
    assert server.pub_path == str(sock_dir / "master_event_pub.ipc")
    assert server.pull_path == str(sock_dir / "master_event_pull.ipc")


@pytest.mark.skip_on_windows(reason="Unix socket not available on win32")
def test_minion_ipc_server_unix(minion_config, sock_dir):
    minion_config["id"] = "foo"
    id_hash = hashlib.sha256(
        salt.utils.stringutils.to_bytes(minion_config["id"])
    ).hexdigest()[:10]
    assert minion_config.get("ipc_mode") != "tcp"
    server = salt.transport.ipc_publish_server("minion", minion_config)
    assert server.pub_path == str(sock_dir / f"minion_event_{id_hash}_pub.ipc")
    assert server.pull_path == str(sock_dir / f"minion_event_{id_hash}_pull.ipc")


def test_master_ipc_server_tcp(master_config, sock_dir):
    master_config["ipc_mode"] = "tcp"
    server = salt.transport.ipc_publish_server("master", master_config)
    assert server.pub_host == "127.0.0.1"
    assert server.pub_port == int(master_config["tcp_master_pub_port"])
    assert server.pub_path is None
    assert server.pull_host == "127.0.0.1"
    assert server.pull_port == int(master_config["tcp_master_pull_port"])
    assert server.pull_path is None


def test_minion_ipc_server_tcp(minion_config, sock_dir):
    minion_config["ipc_mode"] = "tcp"
    server = salt.transport.ipc_publish_server("minion", minion_config)
    assert server.pub_host == "127.0.0.1"
    assert server.pub_port == int(minion_config["tcp_pub_port"])
    assert server.pub_path is None
    assert server.pull_host == "127.0.0.1"
    assert server.pull_port == int(minion_config["tcp_pull_port"])
    assert server.pull_path is None
