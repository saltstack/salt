import asyncio
import gc
import os
import socket
import warnings
import weakref

import attr
import pytest
import tornado
import tornado.concurrent
import tornado.ioloop
import tornado.iostream
from pytestshellutils.utils import ports

import salt.channel.server
import salt.exceptions
import salt.transport.tcp
import salt.utils.platform
from tests.support.mock import AsyncMock, MagicMock, PropertyMock, patch

pytestmark = [
    pytest.mark.core_test,
]


@pytest.fixture
def _fake_keys():
    with patch("salt.crypt.AsyncAuth.get_keys", autospec=True):
        yield


@pytest.fixture
def fake_crypto():
    with patch("salt.transport.tcp.PKCS1_OAEP", create=True) as fake_crypto:
        yield fake_crypto


@pytest.fixture
def _fake_authd(io_loop):
    async def return_nothing(*args, **kwargs):
        return None

    with patch(
        "salt.crypt.AsyncAuth.authenticated", new_callable=PropertyMock
    ) as mock_authed, patch(
        "salt.crypt.AsyncAuth.authenticate",
        autospec=True,
        side_effect=return_nothing,
    ), patch(
        "salt.crypt.AsyncAuth.gen_token", autospec=True, return_value=42
    ):
        mock_authed.return_value = False
        yield


@pytest.fixture
def _fake_crypticle():
    with patch("salt.crypt.Crypticle") as fake_crypticle:
        fake_crypticle.generate_key_string.return_value = "fakey fake"
        yield fake_crypticle


@pytest.fixture
def _squash_exepected_message_client_warning():
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="MessageClient has been deprecated and will be removed.",
            category=DeprecationWarning,
            module="salt.transport.tcp",
        )
        yield


@attr.s(frozen=True, slots=True)
class ClientSocket:
    listen_on = attr.ib(init=False, default="127.0.0.1")
    port = attr.ib(init=False, default=attr.Factory(ports.get_unused_localhost_port))
    sock = attr.ib(init=False, repr=False)

    @sock.default
    def _sock_default(self):
        return socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def __enter__(self):
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.listen_on, self.port))
        self.sock.listen(1)
        return self

    def __exit__(self, *args):
        self.sock.close()


@pytest.fixture
def client_socket():
    with ClientSocket() as _client_socket:
        yield _client_socket


def test_get_socket():
    socket = salt.transport.tcp._get_socket({"ipv6": True})

    if salt.utils.platform.is_windows():
        assert int(socket.family) == 23
    else:
        assert int(socket.family) == 10

    socket = salt.transport.tcp._get_socket({"ipv6": False})
    assert int(socket.family) == 2


def test_get_bind_addr():
    opts = {"interface": "192.168.0.1", "tcp": 1}
    res = salt.transport.tcp._get_bind_addr(opts=opts, port_type="tcp")
    assert res == ("192.168.0.1", 1)


def test_tcppuller_start_ipv4():
    """TCPPuller uses AF_INET when host is an IPv4 address."""
    puller = salt.transport.tcp.TCPPuller(host="127.0.0.1", port=4511)
    created_sockets = []

    def fake_socket(family, *args, **kwargs):
        sock = MagicMock()
        sock.family = family
        created_sockets.append(sock)
        return sock

    with patch("salt.transport.tcp.socket.socket", side_effect=fake_socket):
        with patch("tornado.netutil.add_accept_handler"):
            puller.start()

    assert len(created_sockets) == 1
    assert created_sockets[0].family == socket.AF_INET


def test_tcppuller_start_ipv6():
    """TCPPuller uses AF_INET6 when host is an IPv6 address."""
    puller = salt.transport.tcp.TCPPuller(host="::1", port=4511)
    created_sockets = []

    def fake_socket(family, *args, **kwargs):
        sock = MagicMock()
        sock.family = family
        created_sockets.append(sock)
        return sock

    with patch("salt.transport.tcp.socket.socket", side_effect=fake_socket):
        with patch("tornado.netutil.add_accept_handler"):
            puller.start()

    assert len(created_sockets) == 1
    assert created_sockets[0].family == socket.AF_INET6


def test_tcppubserverpublisher_connect_ipv4():
    """_TCPPubServerPublisher uses AF_INET when connecting to an IPv4 address."""
    io_loop = tornado.ioloop.IOLoop()
    publisher = salt.transport.tcp._TCPPubServerPublisher(
        host="127.0.0.1", port=4511, path=None, io_loop=io_loop
    )
    captured_family = []

    def fake_socket(family, *args, **kwargs):
        captured_family.append(family)
        raise OSError("test abort")

    publisher._connecting_future = tornado.concurrent.Future()

    with patch("salt.transport.tcp.socket.socket", fake_socket):
        try:
            io_loop.run_sync(publisher._connect, timeout=3)
        except OSError:
            pass

    io_loop.close()
    assert captured_family == [socket.AF_INET]


def test_tcppubserverpublisher_connect_ipv6():
    """_TCPPubServerPublisher uses AF_INET6 when connecting to an IPv6 address."""
    io_loop = tornado.ioloop.IOLoop()
    publisher = salt.transport.tcp._TCPPubServerPublisher(
        host="::1", port=4511, path=None, io_loop=io_loop
    )
    captured_family = []

    def fake_socket(family, *args, **kwargs):
        captured_family.append(family)
        raise OSError("test abort")

    publisher._connecting_future = tornado.concurrent.Future()

    with patch("salt.transport.tcp.socket.socket", fake_socket):
        try:
            io_loop.run_sync(publisher._connect, timeout=3)
        except OSError:
            pass

    io_loop.close()
    assert captured_family == [socket.AF_INET6]


async def test_tcppubserverpublisher_close_during_connect_no_attribute_error_69187(
    io_loop,
):
    """
    Regression test for #69187.

    ``_TCPPubServerPublisher.close()`` nulls ``self._connecting_future`` while
    a concurrent ``_connect()`` coroutine is awaiting ``stream.connect()``.
    When the await resumes (succeeds or raises), ``_connect()`` calls
    ``self._connecting_future.set_result(True)`` or
    ``self._connecting_future.set_exception(e)`` on ``None`` and crashes with
    ``AttributeError: 'NoneType' object has no attribute 'set_result'`` (or
    ``set_exception``). The original future is then orphaned and tornado
    logs the misleading ``Future <...> exception was never retrieved``
    message described in the issue.

    This test drives the close-during-connect race both ways:

    1. ``stream.connect()`` raises (the path that originally caused
       ``set_exception`` to be called on ``None``).
    2. ``stream.connect()`` succeeds (the ``set_result`` path).
    """

    # ----- 1. close-during-failed-connect (set_exception path) -----
    publisher = salt.transport.tcp._TCPPubServerPublisher(
        host="127.0.0.1", port=4511, path=None, io_loop=io_loop
    )
    publisher._connecting_future = tornado.concurrent.Future()
    connect_started = asyncio.Event()
    let_connect_finish = asyncio.Event()

    class _FakeStream:
        def __init__(self, *args, **kwargs):
            self._closed = False

        async def connect(self, addr):
            connect_started.set()
            await let_connect_finish.wait()
            raise tornado.iostream.StreamClosedError("Stream is closed")

        def closed(self):
            return self._closed

        def close(self):
            self._closed = True

    with patch("salt.transport.tcp.socket.socket", lambda *a, **kw: MagicMock()):
        with patch("salt.transport.tcp.tornado.iostream.IOStream", _FakeStream):
            # timeout=None means the retry-loop's "should I keep retrying?"
            # check (``timeout is None or time.monotonic() > timeout_at``)
            # always selects the "give up, set_exception" branch — which is
            # the exact branch that crashes in the issue's stack trace
            # (legacy ipc.py line 343).
            connect_task = asyncio.ensure_future(publisher._connect(timeout=None))
            try:
                await connect_started.wait()
                # close() nulls _connecting_future while _connect is awaiting
                publisher.close()
                # Now release the awaited stream.connect() so _connect resumes
                # and walks into the buggy ``set_exception`` line.
                let_connect_finish.set()
                # If the bug is present, the connect_task fails with
                # AttributeError ("'NoneType' object has no attribute
                # 'set_exception'"). If the bug is fixed, the task completes
                # cleanly.
                await asyncio.wait_for(connect_task, timeout=5)
            finally:
                if not connect_task.done():
                    connect_task.cancel()
                    try:
                        await connect_task
                    except asyncio.CancelledError:
                        pass

    # ----- 2. close-during-successful-connect (set_result path) -----
    publisher2 = salt.transport.tcp._TCPPubServerPublisher(
        host="127.0.0.1", port=4511, path=None, io_loop=io_loop
    )
    publisher2._connecting_future = tornado.concurrent.Future()
    connect_started2 = asyncio.Event()
    let_connect_finish2 = asyncio.Event()

    class _FakeStreamOk:
        def __init__(self, *args, **kwargs):
            self._closed = False

        async def connect(self, addr):
            connect_started2.set()
            await let_connect_finish2.wait()
            # successful connect — _connect will fall through to set_result
            return None

        def closed(self):
            return self._closed

        def close(self):
            self._closed = True

    with patch("salt.transport.tcp.socket.socket", lambda *a, **kw: MagicMock()):
        with patch("salt.transport.tcp.tornado.iostream.IOStream", _FakeStreamOk):
            connect_task2 = asyncio.ensure_future(publisher2._connect(timeout=5))
            try:
                await connect_started2.wait()
                publisher2.close()
                let_connect_finish2.set()
                await asyncio.wait_for(connect_task2, timeout=5)
            finally:
                if not connect_task2.done():
                    connect_task2.cancel()
                    try:
                        await connect_task2
                    except asyncio.CancelledError:
                        pass


async def test_tcppubserverpublisher_close_resolves_connecting_future_69187(io_loop):
    """
    Regression test for #69187 (orphan-future follow-up).

    Before the fix, ``_TCPPubServerPublisher.close()`` nulled
    ``self._connecting_future`` **without** ever calling
    ``.set_result()`` or ``.set_exception()`` on it.  As a result, any
    caller that did::

        future = publisher.connect()
        await future    # no wait_for -- production callers do this

    would hang forever, because ``_connect()`` sees ``_closing`` at the
    top of its next loop iteration and breaks silently, leaving the
    original future unresolved.

    ``close()`` must resolve the future with a
    ``salt.transport.tcp.ClosingError`` before nulling it, so awaiters
    get a definitive answer.
    """
    publisher = salt.transport.tcp._TCPPubServerPublisher(
        host="127.0.0.1", port=4511, path=None, io_loop=io_loop
    )
    connect_started = asyncio.Event()
    let_connect_finish = asyncio.Event()

    class _FakeStream:
        def __init__(self, *args, **kwargs):
            self._closed = False

        async def connect(self, addr):
            connect_started.set()
            await let_connect_finish.wait()
            return None

        def closed(self):
            return self._closed

        def close(self):
            self._closed = True

    with patch("salt.transport.tcp.socket.socket", lambda *a, **kw: MagicMock()):
        with patch("salt.transport.tcp.tornado.iostream.IOStream", _FakeStream):
            future = publisher.connect(timeout=5)
            try:
                await connect_started.wait()
                publisher.close()
                # Awaiting the original future MUST NOT hang -- it should
                # resolve with ClosingError.  A short wait_for is only a
                # safety net so a regression manifests as an assertion
                # rather than a test timeout.
                try:
                    await asyncio.wait_for(future, timeout=2)
                except salt.transport.tcp.ClosingError:
                    pass
                except asyncio.TimeoutError:
                    raise AssertionError(
                        "connecting future was orphaned by close() "
                        "-- caller would hang in production"
                    )
                else:
                    raise AssertionError(
                        "connecting future should have resolved with "
                        "ClosingError but returned normally"
                    )
            finally:
                # Unpark _connect() so the create_task-backed coroutine
                # completes and isn't reported as a warning.  It sees
                # ``_closing=True`` at the top of its next loop iteration
                # and breaks cleanly.
                let_connect_finish.set()
                # Give the io_loop a chance to drain the _connect task.
                await asyncio.sleep(0.05)


@pytest.mark.usefixtures("_squash_exepected_message_client_warning")
async def test_message_client_cleanup_on_close(client_socket, temp_salt_master):
    """
    test message client cleanup on close
    """

    opts = dict(temp_salt_master.config.copy(), transport="tcp")
    client = salt.transport.tcp.MessageClient(
        opts, client_socket.listen_on, client_socket.port
    )

    assert client._closed is False
    assert client._closing is False
    assert client._stream is None

    await client.connect()

    # Ensure we are testing the _read_until_future and io_loop teardown
    assert client._stream is not None

    client.close()

    # ``close()`` now tears down synchronously (see the block comment
    # above the added tests further down): the transport, stream and
    # pending futures are cleared before returning so a caller can rely
    # on the client being fully closed the moment ``close()`` returns.
    # Previously ``close()`` scheduled a poll-loop on the IOLoop and
    # only actually closed the stream after ``send_future_map`` drained,
    # which under load could hang forever.
    assert client._closed is True
    assert client._closing is False
    assert client._stream is None


async def test_async_tcp_pub_channel_connect_publish_port(
    temp_salt_master, client_socket
):
    """
    test when publish_port is not 4506
    """
    opts = dict(
        temp_salt_master.config.copy(),
        master_uri="tcp://127.0.0.1:1234",
        master_ip="127.0.0.1",
        publish_port=1234,
        transport="tcp",
        acceptance_wait_time=5,
        acceptance_wait_time_max=5,
    )
    patch_auth = MagicMock(return_value=True)
    transport = MagicMock(spec=salt.transport.tcp.TCPPubClient)
    transport.connect = MagicMock()
    future = asyncio.Future()
    transport.connect.return_value = future
    future.set_result(True)
    with patch("salt.crypt.AsyncAuth.gen_token", patch_auth), patch(
        "salt.crypt.AsyncAuth.authenticated", patch_auth
    ), patch("salt.transport.tcp.PublishClient", transport):
        channel = salt.channel.client.AsyncPubChannel.factory(opts)
        with channel:
            # We won't be able to succeed the connection because we're not mocking the tornado coroutine
            with pytest.raises(salt.exceptions.SaltClientError):
                await channel.connect()
    # The first call to the mock is the instance's __init__, and the first argument to those calls is the opts dict
    await asyncio.sleep(0.3)
    assert channel.transport.connect.call_args[0][0] == opts["publish_port"]
    transport.close()


def test_tcp_pub_server_channel_publish_filtering(temp_salt_master):
    opts = dict(
        temp_salt_master.config.copy(),
        sign_pub_messages=False,
        transport="tcp",
        acceptance_wait_time=5,
        acceptance_wait_time_max=5,
    )
    with patch("salt.master.SMaster.secrets") as secrets, patch(
        "salt.crypt.Crypticle"
    ) as crypticle, patch("salt.utils.asynchronous.SyncWrapper") as SyncWrapper:
        channel = salt.channel.server.PubServerChannel.factory(opts)
        wrap = MagicMock()
        crypt = MagicMock()
        crypt.dumps.return_value = {"test": "value"}

        secrets.return_value = {"aes": {"secret": None}}
        crypticle.return_value = crypt
        SyncWrapper.return_value = wrap

        # try simple publish with glob tgt_type
        payload = channel.wrap_payload(
            {"test": "value", "tgt_type": "glob", "tgt": "*"}
        )

        # verify we send it without any specific topic
        assert "topic_lst" in payload
        assert payload["topic_lst"] == []  # "minion01"]

        # try simple publish with list tgt_type
        payload = channel.wrap_payload(
            {"test": "value", "tgt_type": "list", "tgt": ["minion01"]}
        )

        # verify we send it with correct topic
        assert "topic_lst" in payload
        assert payload["topic_lst"] == ["minion01"]

        # try with syndic settings
        opts["order_masters"] = True
        channel = salt.channel.server.PubServerChannel.factory(opts)
        payload = channel.wrap_payload(
            {"test": "value", "tgt_type": "list", "tgt": ["minion01"]}
        )

        # verify we send it without topic for syndics
        assert "topic_lst" not in payload


def test_tcp_pub_server_channel_publish_filtering_str_list(temp_salt_master):
    opts = dict(
        temp_salt_master.config.copy(),
        transport="tcp",
        sign_pub_messages=False,
        acceptance_wait_time=5,
        acceptance_wait_time_max=5,
    )
    with patch("salt.master.SMaster.secrets") as secrets, patch(
        "salt.crypt.Crypticle"
    ) as crypticle, patch("salt.utils.asynchronous.SyncWrapper") as SyncWrapper, patch(
        "salt.utils.minions.CkMinions.check_minions"
    ) as check_minions:
        channel = salt.channel.server.PubServerChannel.factory(opts)
        wrap = MagicMock()
        crypt = MagicMock()
        crypt.dumps.return_value = {"test": "value"}

        secrets.return_value = {"aes": {"secret": None}}
        crypticle.return_value = crypt
        SyncWrapper.return_value = wrap
        check_minions.return_value = {"minions": ["minion02"]}

        # try simple publish with list tgt_type
        payload = channel.wrap_payload(
            {"test": "value", "tgt_type": "list", "tgt": "minion02"}
        )

        # verify we send it with correct topic
        assert "topic_lst" in payload
        assert payload["topic_lst"] == ["minion02"]

        # verify it was correctly calling check_minions
        check_minions.assert_called_with("minion02", tgt_type="list")


@pytest.fixture(scope="function")
def salt_message_client(io_loop):
    client = salt.transport.tcp.MessageClient(
        {}, "127.0.0.1", ports.get_unused_localhost_port(), io_loop=io_loop
    )

    try:
        yield client
    finally:
        client.close()


# XXX we don't return a future anymore, this needs a different way of testing.
# def test_send_future_set_retry(salt_message_client):
#    future = salt_message_client.send({"some": "message"}, tries=10, timeout=30)
#
#    # assert we have proper props in future
#    assert future.tries == 10
#    assert future.timeout == 30
#    assert future.attempts == 0
#
#    # assert the timeout callback was created
#    assert len(salt_message_client.send_queue) == 1
#    message_id = salt_message_client.send_queue.pop()[0]
#
#    assert message_id in salt_message_client.send_timeout_map
#
#    timeout = salt_message_client.send_timeout_map[message_id]
#    assert timeout[0][0] == 30
#    assert timeout[0][2] == message_id
#    assert timeout[0][3] == {"some": "message"}
#
#    # try again, now with set future
#    future.attempts = 1
#
#    future = salt_message_client.send(
#        {"some": "message"}, tries=10, timeout=30, future=future
#    )
#
#    # assert we have proper props in future
#    assert future.tries == 10
#    assert future.timeout == 30
#    assert future.attempts == 1
#
#    # assert the timeout callback was created
#    assert len(salt_message_client.send_queue) == 1
#    message_id_new = salt_message_client.send_queue.pop()[0]
#
#    # check new message id is generated
#    assert message_id != message_id_new
#
#    assert message_id_new in salt_message_client.send_timeout_map
#
#    timeout = salt_message_client.send_timeout_map[message_id_new]
#    assert timeout[0][0] == 30
#    assert timeout[0][2] == message_id_new
#    assert timeout[0][3] == {"some": "message"}


# def test_timeout_message_retry(salt_message_client):
#    # verify send is triggered with first retry
#    msg = {"some": "message"}
#    future = salt_message_client.send(msg, tries=1, timeout=30)
#    assert future.attempts == 0
#
#    timeout = next(iter(salt_message_client.send_timeout_map.values()))
#    message_id_1 = timeout[0][2]
#    message_body_1 = timeout[0][3]
#
#    assert message_body_1 == msg
#
#    # trigger timeout callback
#    salt_message_client.timeout_message(message_id_1, message_body_1)
#
#    # assert send got called, yielding potentially new message id, but same message
#    future_new = next(iter(salt_message_client.send_future_map.values()))
#    timeout_new = next(iter(salt_message_client.send_timeout_map.values()))
#
#    message_id_2 = timeout_new[0][2]
#    message_body_2 = timeout_new[0][3]
#
#    assert future_new.attempts == 1
#    assert future.tries == future_new.tries
#    assert future.timeout == future_new.timeout
#
#    assert message_body_1 == message_body_2
#
#    # now try again, should not call send
#    with contextlib.suppress(salt.exceptions.SaltReqTimeoutError):
#        salt_message_client.timeout_message(message_id_2, message_body_2)
#        raise future_new.exception()
#
#    # assert it's really "consumed"
#    assert message_id_2 not in salt_message_client.send_future_map
#    assert message_id_2 not in salt_message_client.send_timeout_map


@pytest.mark.usefixtures("_squash_exepected_message_client_warning")
def test_timeout_message_unknown_future(salt_message_client):
    #    # test we don't fail on unknown message_id
    #    salt_message_client.timeout_message(-1, "message")

    # if we do have the actual future stored under the id, but it's none
    # we shouldn't fail as well
    message_id = 1
    future = tornado.concurrent.Future()
    future.attempts = 1
    future.tries = 1
    salt_message_client.send_future_map[message_id] = future

    salt_message_client.timeout_message(message_id, "message")

    assert message_id not in salt_message_client.send_future_map


@pytest.mark.usefixtures("_squash_exepected_message_client_warning")
def xtest_client_reconnect_backoff(client_socket):
    opts = {"tcp_reconnect_backoff": 5}

    client = salt.transport.tcp.MessageClient(
        opts, client_socket.listen_on, client_socket.port
    )

    async def _sleep(t):
        client.close()
        assert t == 5
        return
        # return asyncio.sleep()

    async def connect(*args, **kwargs):
        raise Exception("err")

    client._tcp_client.connect = connect

    try:
        with patch("asyncio.sleep", side_effect=_sleep):
            client.io_loop.run_sync(client.connect)
    finally:
        client.close()


@pytest.mark.usefixtures("_fake_crypticle", "_fake_keys")
async def test_when_async_req_channel_with_syndic_role_should_use_syndic_master_pub_file_to_verify_master_sig(
    fake_crypto,
):
    # Syndics use the minion pki dir, but they also create a syndic_master.pub
    # file for comms with the Salt master
    expected_pubkey_path = os.path.join("/etc/salt/pki/minion", "syndic_master.pub")
    fake_crypto.new.return_value.decrypt.return_value = "decrypted_return_value"
    mockloop = MagicMock()
    opts = {
        "master_uri": "tcp://127.0.0.1:4506",
        "interface": "127.0.0.1",
        "ret_port": 4506,
        "ipv6": False,
        "sock_dir": ".",
        "pki_dir": "/etc/salt/pki/minion",
        "id": "syndic",
        "__role": "syndic",
        "keysize": 4096,
        "transport": "tcp",
        "acceptance_wait_time": 30,
        "acceptance_wait_time_max": 30,
        "signing_algorithm": "MOCK",
        "keys.cache_driver": "localfs_key",
    }
    client = salt.channel.client.ReqChannel.factory(opts, io_loop=mockloop)
    assert client.master_pubkey_path == expected_pubkey_path
    # verify_signature routes through PublicKey.from_file so the syndic
    # master pubkey path shows up on the from_file classmethod call.
    with patch("salt.crypt.PublicKey.from_file", return_value=MagicMock()) as mock:
        client.verify_signature("mockdata", "mocksig")
        assert mock.call_args_list[0][0][0] == expected_pubkey_path


@pytest.mark.usefixtures("_fake_authd", "_fake_crypticle", "_fake_keys")
async def test_mixin_should_use_correct_path_when_syndic():
    mockloop = asyncio.get_running_loop()
    expected_pubkey_path = os.path.join("/etc/salt/pki/minion", "syndic_master.pub")
    opts = {
        "master_uri": "tcp://127.0.0.1:4506",
        "interface": "127.0.0.1",
        "ret_port": 4506,
        "ipv6": False,
        "sock_dir": ".",
        "pki_dir": "/etc/salt/pki/minion",
        "id": "syndic",
        "__role": "syndic",
        "keysize": 4096,
        "sign_pub_messages": True,
        "transport": "tcp",
        "keys.cache_driver": "localfs_key",
    }
    client = salt.channel.client.AsyncPubChannel.factory(opts, io_loop=mockloop)
    client.master_pubkey_path = expected_pubkey_path
    payload = {
        "sig": "abc",
        "load": {"foo": "bar"},
        "sig_algo": salt.crypt.PKCS1v15_SHA224,
    }
    with patch("salt.crypt.verify_signature") as mock:
        client._verify_master_signature(payload)
        assert mock.call_args_list[0][0][0] == expected_pubkey_path


@pytest.mark.usefixtures("_squash_exepected_message_client_warning")
def test_presence_events_callback_passed(temp_salt_master, salt_message_client):
    opts = dict(temp_salt_master.config.copy(), transport="tcp", presence_events=True)
    channel = salt.channel.server.PubServerChannel.factory(opts)
    channel.transport = salt.transport.tcp.TCPPublishServer(opts)
    mock_publish_daemon = MagicMock()
    with patch(
        "salt.transport.tcp.TCPPublishServer.publish_daemon", mock_publish_daemon
    ):
        channel._publish_daemon()
        mock_publish_daemon.assert_called_with(
            channel.publish_payload,
            channel.presence_callback,
            channel.remove_presence_callback,
            secrets=None,
            started=None,
        )


async def test_presence_removed_on_stream_closed():
    opts = {"presence_events": True}

    io_loop_mock = MagicMock(spec=tornado.ioloop.IOLoop)
    # Add asyncio_loop attribute for aioloop() compatibility
    io_loop_mock.asyncio_loop = MagicMock()

    with patch("salt.master.AESFuncs.__init__", return_value=None):
        server = salt.transport.tcp.PubServer(opts, io_loop=io_loop_mock)
        server._closing = True
        server.remove_presence_callback = MagicMock()

    client = salt.transport.tcp.Subscriber(tornado.iostream.IOStream, "1.2.3.4")
    client._closing = True
    server.clients = {client}

    io_loop = tornado.ioloop.IOLoop.current()
    package = {
        "topic_lst": [],
        "payload": "test-payload",
    }

    with patch("salt.transport.frame.frame_msg", return_value="framed-payload"):
        with patch(
            "tornado.iostream.BaseIOStream.write",
            side_effect=tornado.iostream.StreamClosedError(),
        ):
            await server.publish_payload(package, None)

            server.remove_presence_callback.assert_called_with(client)


async def test_tcp_pub_client_decode_dict(minion_opts, io_loop, tmp_path):
    dmsg = {"meh": "bah"}
    with salt.transport.tcp.TCPPubClient(minion_opts, io_loop, path=tmp_path) as client:
        ret = client._decode_messages(dmsg)
        assert ret == dmsg


async def test_tcp_pub_client_decode_msgpack(minion_opts, io_loop, tmp_path):
    dmsg = {"meh": "bah"}
    msg = salt.payload.dumps(dmsg)
    with salt.transport.tcp.TCPPubClient(minion_opts, io_loop, path=tmp_path) as client:
        ret = client._decode_messages(msg)
        assert ret == dmsg


def test_tcp_pub_client_close(minion_opts, io_loop, tmp_path):
    client = salt.transport.tcp.TCPPubClient(minion_opts, io_loop, path=tmp_path)

    stream = MagicMock()

    client._stream = stream
    client.close()
    assert client._closing is True
    assert client._stream is None
    client.close()
    stream.close.assert_called_once_with()


async def test_pub_server__stream_read(master_opts, io_loop):

    messages = [salt.transport.frame.frame_msg({"foo": "bar"})]

    class Stream:
        def __init__(self, messages):
            self.messages = messages

        def read_bytes(self, *args, **kwargs):
            if self.messages:
                msg = self.messages.pop(0)
                future = tornado.concurrent.Future()
                future.set_result(msg)
                return future
            raise tornado.iostream.StreamClosedError()

    client = MagicMock()
    client.stream = Stream(messages)
    client.address = "client address"
    server = salt.transport.tcp.PubServer(master_opts, io_loop)
    await server._stream_read(client)
    client.close.assert_called_once()


async def test_pub_server__stream_read_exception(master_opts, io_loop):
    client = MagicMock()
    client.stream = MagicMock()
    client.stream.read_bytes = MagicMock(
        side_effect=[
            Exception("Something went wrong"),
            tornado.iostream.StreamClosedError(),
        ]
    )
    client.address = "client address"
    server = salt.transport.tcp.PubServer(master_opts, io_loop)
    await server._stream_read(client)
    client.close.assert_called_once()


async def test_salt_message_server(master_opts):

    received = []

    def handler(stream, body, header):

        received.append(body)

    server = salt.transport.tcp.SaltMessageServer(handler)
    msg = {"foo": "bar"}
    messages = [salt.transport.frame.frame_msg(msg)]

    class Stream:
        def __init__(self, messages):
            self.messages = messages

        def read_bytes(self, *args, **kwargs):
            if self.messages:
                msg = self.messages.pop(0)
                future = tornado.concurrent.Future()
                future.set_result(msg)
                return future
            raise tornado.iostream.StreamClosedError()

    stream = Stream(messages)
    address = "client address"

    await server.handle_stream(stream, address)

    # Let loop iterate so callback gets called
    await asyncio.sleep(0.01)

    assert received
    assert [msg] == received


async def test_salt_message_server_recreates_unpacker_on_disconnect(monkeypatch):

    class TrackingUnpacker:
        created = 0
        living = weakref.WeakSet()

        def __init__(self, *args, **kwargs):
            TrackingUnpacker.created += 1
            TrackingUnpacker.living.add(self)

        def feed(self, data):  # pylint: disable=unused-argument
            return None

        def __iter__(self):
            return iter(())

    monkeypatch.setattr(salt.utils.msgpack, "Unpacker", TrackingUnpacker)

    def handler(stream, body, header):  # pylint: disable=unused-argument
        return None

    server = salt.transport.tcp.SaltMessageServer(handler)

    class Stream:
        def __init__(self, reads):
            self.reads = reads

        def read_bytes(self, *args, **kwargs):
            if self.reads:
                self.reads -= 1
                future = tornado.concurrent.Future()
                future.set_result(b"x")
                return future
            raise tornado.iostream.StreamClosedError()

        def close(self):
            return None

    stream = Stream(reads=1)
    await server.handle_stream(stream, "client-1")
    await tornado.gen.sleep(0.01)
    gc.collect()

    assert TrackingUnpacker.created == 2  # initial + reset on disconnect
    assert not TrackingUnpacker.living

    stream = Stream(reads=1)
    await server.handle_stream(stream, "client-2")
    await tornado.gen.sleep(0.01)
    gc.collect()

    # second connection: initial + reset again
    assert TrackingUnpacker.created == 4
    assert not TrackingUnpacker.living


async def test_salt_message_server_resets_unpacker_on_general_exception(monkeypatch):
    """
    Ensure that a general exception from the stream causes the server to reset its
    unpacker, preventing the previous buffer from leaking.
    """

    class TrackingUnpacker:
        living = weakref.WeakSet()
        created = 0

        def __init__(self, *args, **kwargs):
            self.max_buffer_size = kwargs.get("max_buffer_size")
            TrackingUnpacker.created += 1
            TrackingUnpacker.living.add(self)

        def feed(self, data):
            return None

        def __iter__(self):
            return self

        def __next__(self):
            raise StopIteration

    monkeypatch.setattr(salt.utils.msgpack, "Unpacker", TrackingUnpacker)

    def handler(stream, body, header):  # pylint: disable=unused-argument

        return None

    server = salt.transport.tcp.SaltMessageServer(handler)
    chunk = b"x" * 4096

    class FailingStream:
        def __init__(self):
            self.calls = 0
            self.closed = False

        def read_bytes(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                future = tornado.concurrent.Future()
                future.set_result(chunk)
                return future
            raise RuntimeError("boom")

        def close(self):
            self.closed = True

    try:
        stream = FailingStream()
        await server.handle_stream(stream, "failing-client")
        await tornado.gen.sleep(0.01)
        gc.collect()
        assert stream.closed
        # initial creation + reset on exception
        assert TrackingUnpacker.created == 2
        assert not TrackingUnpacker.living
    finally:
        server.close()

    gc.collect()

    assert TrackingUnpacker.created == 2


def test_salt_message_server_close_removes_all_clients(monkeypatch):

    closed = []

    class DummyStream:
        def __init__(self, name):
            self.name = name

        def close(self):
            closed.append(self.name)

    def handler(stream, body, header):  # pylint: disable=unused-argument
        return None

    server = salt.transport.tcp.SaltMessageServer(handler)
    monkeypatch.setattr(server, "stop", MagicMock())

    client_streams = [
        DummyStream("first"),
        DummyStream("second"),
        DummyStream("third"),
    ]
    server.clients = [
        (stream, f"addr-{idx}") for idx, stream in enumerate(client_streams)
    ]

    server.close()

    assert not server.clients
    assert set(closed) == {"first", "second", "third"}
    assert server._closing is True


async def test_salt_message_server_exception(master_opts, io_loop):
    received = []

    def handler(stream, body, header):

        received.append(body)

    stream = MagicMock()
    stream.read_bytes = MagicMock(
        side_effect=[
            Exception("Something went wrong"),
        ]
    )
    address = "client address"
    server = salt.transport.tcp.SaltMessageServer(handler)
    await server.handle_stream(stream, address)
    stream.close.assert_called_once()


@pytest.mark.usefixtures("_squash_exepected_message_client_warning")
async def test_message_client_stream_return_exception(minion_opts, io_loop):
    msg = {"foo": "bar"}
    payload = salt.transport.frame.frame_msg(msg)
    future = tornado.concurrent.Future()
    future.set_result(payload)
    client = salt.transport.tcp.MessageClient(
        minion_opts,
        "127.0.0.1",
        12345,
        connect_callback=MagicMock(),
        disconnect_callback=MagicMock(),
    )
    client._stream = MagicMock()
    client._stream.read_bytes.side_effect = [
        future,
    ]
    try:
        io_loop.add_callback(client._stream_return)
        await asyncio.sleep(0.01)
        client.close()
        await asyncio.sleep(0.01)
        assert client._stream is None
    finally:
        client.close()


def test_tcp_pub_server_pre_fork(master_opts):
    process_manager = MagicMock()
    server = salt.transport.tcp.TCPPublishServer(master_opts)
    server.pre_fork(process_manager)


async def test_pub_server_publish_payload(master_opts, io_loop):
    server = salt.transport.tcp.PubServer(master_opts, io_loop=io_loop)
    package = {"foo": "bar"}
    topic_list = ["meh"]
    future = tornado.concurrent.Future()
    future.set_result(None)
    client = MagicMock()
    client.stream = MagicMock()
    client.stream.write.side_effect = [future]
    client.id_ = "meh"
    server.clients = [client]
    await server.publish_payload(package, topic_list)
    client.stream.write.assert_called_once()


async def test_pub_server_publish_payload_closed_stream(master_opts, io_loop):
    server = salt.transport.tcp.PubServer(master_opts, io_loop=io_loop)
    package = {"foo": "bar"}
    topic_list = ["meh"]
    client = MagicMock()
    client.stream = MagicMock()
    client.stream.write.side_effect = [
        tornado.iostream.StreamClosedError("mock"),
    ]
    client.id_ = "meh"
    server.clients = {client}
    await server.publish_payload(package, topic_list)
    assert server.clients == set()


async def test_pub_server_paths_no_perms(master_opts, io_loop):
    def publish_payload(payload):
        return payload

    pubserv = salt.transport.tcp.PublishServer(
        master_opts,
        pub_host="127.0.0.1",
        pub_port=5151,
        pull_host="127.0.0.1",
        pull_port=5152,
    )
    assert pubserv.pull_path is None
    assert pubserv.pub_path is None
    with patch("os.chmod") as p:
        await pubserv.publisher(publish_payload)
        assert p.call_count == 0


@pytest.mark.skip_on_windows()
async def test_pub_server_publisher_pull_path_perms(master_opts, io_loop, tmp_path):
    def publish_payload(payload):
        return payload

    pull_path = str(tmp_path / "pull.ipc")
    pull_path_perms = 0o664
    pubserv = salt.transport.tcp.PublishServer(
        master_opts,
        pub_host="127.0.0.1",
        pub_port=5151,
        pull_host=None,
        pull_port=None,
        pull_path=pull_path,
        pull_path_perms=pull_path_perms,
    )
    assert pubserv.pull_path == pull_path
    assert pubserv.pull_path_perms == pull_path_perms
    assert pubserv.pull_host is None
    assert pubserv.pull_port is None
    with patch("os.chmod") as p:
        await pubserv.publisher(publish_payload)
        assert p.call_count == 1
        assert p.call_args.args == (pubserv.pull_path, pubserv.pull_path_perms)


@pytest.mark.skip_on_windows()
async def test_pub_server_publisher_pub_path_perms(master_opts, io_loop, tmp_path):
    def publish_payload(payload):
        return payload

    pub_path = str(tmp_path / "pub.ipc")
    pub_path_perms = 0o664
    pubserv = salt.transport.tcp.PublishServer(
        master_opts,
        pub_host=None,
        pub_port=None,
        pub_path=pub_path,
        pub_path_perms=pub_path_perms,
        pull_host="127.0.0.1",
        pull_port=5151,
        pull_path=None,
    )
    assert pubserv.pub_path == pub_path
    assert pubserv.pub_path_perms == pub_path_perms
    assert pubserv.pub_host is None
    assert pubserv.pub_port is None
    with patch("os.chmod") as p:
        await pubserv.publisher(publish_payload)
        assert p.call_count == 1
        assert p.call_args.args == (pubserv.pub_path, pubserv.pub_path_perms)


def test_pub_server_close_clears_clients(master_opts, io_loop):
    server = salt.transport.tcp.PubServer(master_opts, io_loop=io_loop)

    class DummyClient:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    clients = {DummyClient(), DummyClient(), DummyClient()}
    server.clients = clients.copy()

    server.close()

    assert all(client.closed for client in clients)
    assert server.clients == set()
    assert server._closing is True


def test_pub_server_discard_on_close_prunes_subscribers(master_opts, io_loop):
    """
    A subscriber whose stream closes must be pruned from
    ``PubServer.clients`` immediately -- not when the reader loop's
    next ``read_bytes`` returns or when ``publish_payload`` throws on
    the next write.  Without this, passive subscribers (which never
    write anything) accumulate in the set from the moment their peer
    disconnects, and the ``Subscriber`` / ``IOStream`` /
    ``_read_buffer`` / ``_write_buffer`` graph stays pinned in memory.
    """
    server = salt.transport.tcp.PubServer(master_opts, io_loop=io_loop)

    removed_from_presence = []

    def _remove_presence(client):
        removed_from_presence.append(client)

    server.remove_presence_callback = _remove_presence

    class DummyClient:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    a = DummyClient()
    b = DummyClient()
    server.clients = {a, b}

    # Simulate the underlying IOStream's on-close firing the callback we
    # registered from handle_stream via ``stream.set_close_callback``.
    server._discard_on_close(a)()

    assert a not in server.clients
    assert b in server.clients
    assert removed_from_presence == [a]

    # Second call is a no-op (idempotent on a stale registration).
    server._discard_on_close(a)()
    assert b in server.clients


# ---------------------------------------------------------------------------
# MessageClient synchronous close.
#
# The previous close() scheduled ``check_close`` on the IOLoop and polled
# ``send_future_map`` at 1 s intervals for it to empty, only actually
# tearing the transport down once no in-flight sends remained.  A single
# orphaned future -- e.g. an awaiting coroutine cancelled by CherryPy
# mid-request -- kept the map non-empty forever, so under salt-api load
# MessageClient objects (with their Unpacker + IOStream + LazyLoader
# graphs) leaked at ~18/s.  close() now runs synchronously: it cancels
# pending futures with SaltReqTimeoutError, closes the tcp client and
# stream, and sets ``_closed=True`` before returning.  connect() then
# refuses to reset ``_closing``/``_closed`` if the client was closed
# while ``getstream`` was awaiting, so a late reconnect from
# ``_stream_return`` cannot revive a torn-down client.
# ---------------------------------------------------------------------------


def _make_message_client(minion_opts):
    return salt.transport.tcp.MessageClient(minion_opts, "127.0.0.1", 4506)


def test_message_client_close_synchronously_tears_down(minion_opts):
    client = _make_message_client(minion_opts)
    fake_stream = MagicMock()
    fake_stream.closed.return_value = False
    client._stream = fake_stream
    client._tcp_client = MagicMock()

    client.close()

    assert client._closed is True
    assert client._closing is False
    assert client._stream is None
    client._tcp_client.close.assert_called_once_with()
    fake_stream.close.assert_called_once_with()


def test_message_client_close_cancels_pending_futures(minion_opts):
    client = _make_message_client(minion_opts)
    client._tcp_client = MagicMock()
    client._stream = MagicMock()

    pending = asyncio.get_event_loop_policy().new_event_loop().create_future()
    done = asyncio.get_event_loop_policy().new_event_loop().create_future()
    done.set_result("already-done")
    client.send_future_map = {1: pending, 2: done}

    try:
        client.close()

        assert pending.done() is True
        assert isinstance(pending.exception(), salt.exceptions.SaltReqTimeoutError)
        # A future that was already resolved before close() must not be
        # touched.
        assert done.done() is True
        assert done.result() == "already-done"
        assert client.send_future_map == {}
        assert client._closed is True
    finally:
        pending.get_loop().close()
        done.get_loop().close()


def test_message_client_close_is_idempotent(minion_opts):
    client = _make_message_client(minion_opts)
    client._tcp_client = MagicMock()
    client._stream = MagicMock()

    client.close()
    client.close()

    client._tcp_client.close.assert_called_once_with()


async def test_message_client_connect_noop_after_close(minion_opts):
    """
    If ``close()`` runs while ``connect()`` is awaiting ``getstream()``
    (e.g. ``_stream_return`` saw StreamClosedError and called us to
    reconnect), connect() must not clobber the close flags -- otherwise
    _stream_return keeps running past the intended shutdown and the
    client stays reachable.
    """
    client = _make_message_client(minion_opts)
    client._tcp_client = MagicMock()

    client.close()
    assert client._closed is True

    async def _should_not_be_called(*args, **kwargs):
        raise AssertionError(
            "getstream() must not run when connect() is called on a closed client"
        )

    client.getstream = _should_not_be_called

    await client.connect()

    assert client._closed is True
    assert client._closing is False
    assert client._stream is None


# ---------------------------------------------------------------------------
# TCPPuller.handle_stream backpressure.
#
# ``handle_stream`` used to fire the payload handler via
# ``self.io_loop.create_task`` and immediately loop back to read the next
# framed message.  Under sustained publish load (~5000 events/sec on the
# stress rig) tasks accumulated in the io_loop faster than they could
# complete: 909,120 pending tasks / 10 GB RSS on the EventPublisher
# process after ~5 min.  The 3006.x equivalent path
# (``IPCMessagePublisher._write``) solved the same accumulation by
# switching from ``@gen.coroutine`` to ``future.add_done_callback``; the
# 3008.x fix is simpler -- await the handler inline so the reader
# throttles when publishes back up, giving the pull-side kernel socket
# and the peer's ``fire_event`` writes natural TCP backpressure.
# ---------------------------------------------------------------------------


async def test_tcp_puller_handle_stream_awaits_payload_handler(master_opts):
    """
    The reader loop must await the payload handler inline so no more than
    one payload is in-flight per pull connection at a time.  Regression
    guard: if this reverts to ``create_task(...)`` fire-and-forget, tasks
    accumulate under load and drive the EventPublisher OOM observed in
    #69857.
    """
    import asyncio
    import struct

    handler_started = asyncio.Event()
    handler_release = asyncio.Event()
    handled = []

    async def slow_handler(body):
        handler_started.set()
        # Block until the test lets us finish.  If handle_stream had
        # fire-and-forget'd us, it would already be reading the next
        # message; if it awaits, it's parked on this future.
        await handler_release.wait()
        handled.append(body)

    puller = salt.transport.tcp.TCPPuller(payload_handler=slow_handler)

    # Build two framed messages so we can prove only one runs at a time.
    def _frame(body):
        payload = salt.utils.msgpack.packb({"body": body}, use_bin_type=True)
        return struct.pack(">I", len(payload)) + payload

    class FakeStream:
        def __init__(self, chunks):
            self._buf = b"".join(chunks)
            self._closed = False

        async def read_bytes(self, n):
            if len(self._buf) < n:
                # No more data; simulate close.
                self._closed = True
                raise tornado.iostream.StreamClosedError()
            chunk, self._buf = self._buf[:n], self._buf[n:]
            return chunk

        def closed(self):
            return self._closed

    stream = FakeStream([_frame("first"), _frame("second")])

    reader_task = asyncio.get_event_loop().create_task(puller.handle_stream(stream))

    # Handler for message 1 starts and blocks.  If handle_stream
    # fire-and-forget'd, it would already be reading message 2 -- and
    # since our second frame is queued, it would either have called
    # slow_handler a second time (started once already) or already tried
    # to schedule the second task.  The single-handler-active
    # invariant is the whole point of the fix.
    await asyncio.wait_for(handler_started.wait(), timeout=2)
    await asyncio.sleep(0.05)
    assert handled == [], "reader should be parked on the first handler"

    # Release; handler 1 completes, handler 2 starts and completes, then
    # the stream returns EOF and handle_stream exits.
    handler_release.set()
    await asyncio.wait_for(reader_task, timeout=5)

    # PR #70052 switched the outer-frame unpack to ``raw=True`` so
    # ``body`` values arrive as bytes.
    assert handled == [b"first", b"second"]


async def test_tcp_puller_handle_stream_survives_handler_exception(master_opts):
    """
    A misbehaving payload handler must not break the reader loop; a
    single bad event is logged and dropped, subsequent events are still
    delivered.
    """
    import asyncio
    import struct

    handled = []

    async def handler(body):
        # PR #70052 switched the outer-frame unpack to ``raw=True`` so
        # ``body`` values arrive as bytes.
        if body == b"boom":
            raise RuntimeError("simulated handler failure")
        handled.append(body)

    puller = salt.transport.tcp.TCPPuller(payload_handler=handler)

    def _frame(body):
        payload = salt.utils.msgpack.packb({"body": body}, use_bin_type=True)
        return struct.pack(">I", len(payload)) + payload

    class FakeStream:
        def __init__(self, chunks):
            self._buf = b"".join(chunks)
            self._closed = False

        async def read_bytes(self, n):
            if len(self._buf) < n:
                self._closed = True
                raise tornado.iostream.StreamClosedError()
            chunk, self._buf = self._buf[:n], self._buf[n:]
            return chunk

        def closed(self):
            return self._closed

    stream = FakeStream([_frame("ok1"), _frame("boom"), _frame("ok2")])

    await asyncio.wait_for(puller.handle_stream(stream), timeout=5)

    # The "boom" was dropped by the except-log-and-continue guard; the
    # other two got through.
    assert handled == [b"ok1", b"ok2"]


# ---------------------------------------------------------------------------
# issue #69930: ipc_write_buffer wired through to per-stream cap.
# ---------------------------------------------------------------------------


async def test_salt_message_server_applies_ipc_write_buffer(master_opts):
    """
    ``SaltMessageServer.handle_stream`` must set the accepted stream's
    ``max_write_buffer_size`` to the ``ipc_write_buffer`` value passed
    in.  Without this wiring (regression on 3008.x after the legacy
    ``salt.transport.ipc`` module was dropped), setting
    ``ipc_write_buffer`` in ``master.conf`` was a no-op and the
    outbound IOStream buffer grew without bound under slow-consumer
    conditions.  See issue #69930.
    """

    def handler(stream, body, header):  # pylint: disable=unused-argument
        return None

    cap = 12345
    server = salt.transport.tcp.SaltMessageServer(handler, max_write_buffer_size=cap)

    class Stream:
        def __init__(self):
            self.max_write_buffer_size = None

        def read_bytes(self, *args, **kwargs):
            raise tornado.iostream.StreamClosedError()

    stream = Stream()
    await server.handle_stream(stream, "client-cap")

    assert stream.max_write_buffer_size == cap


async def test_salt_message_server_no_cap_by_default(master_opts):
    """
    Not passing ``max_write_buffer_size`` (or passing 0) must leave the
    stream untouched -- preserves Tornado's default (unlimited) and
    matches prior behavior when ``ipc_write_buffer`` is not set in
    ``master.conf``.
    """

    def handler(stream, body, header):  # pylint: disable=unused-argument
        return None

    server = salt.transport.tcp.SaltMessageServer(handler)
    assert server.max_write_buffer_size is None

    server_zero = salt.transport.tcp.SaltMessageServer(handler, max_write_buffer_size=0)
    assert server_zero.max_write_buffer_size is None

    class Stream:
        def __init__(self):
            self.max_write_buffer_size = "sentinel"

        def read_bytes(self, *args, **kwargs):
            raise tornado.iostream.StreamClosedError()

    stream = Stream()
    await server.handle_stream(stream, "client-nocap")
    # Untouched -- the sentinel is still there.
    assert stream.max_write_buffer_size == "sentinel"


def test_pub_server_applies_ipc_write_buffer(master_opts, io_loop):
    """
    ``PubServer.handle_stream`` must set the accepted stream's
    ``max_write_buffer_size`` to ``opts['ipc_write_buffer']`` when set.
    See issue #69930.
    """
    master_opts["ipc_write_buffer"] = 54321
    server = salt.transport.tcp.PubServer(master_opts, io_loop=io_loop)

    class Stream:
        def __init__(self):
            self.max_write_buffer_size = None
            self.socket = MagicMock()
            self.socket.getpeercert.return_value = None
            self._closed = False

        def set_close_callback(self, cb):
            pass

        def close(self):
            self._closed = True

        def closed(self):
            return self._closed

    stream = Stream()
    try:
        with patch.object(
            server, "_stream_read", MagicMock(return_value=None)
        ), patch.object(server.io_loop, "create_task"):
            server.handle_stream(stream, ("127.0.0.1", 12345))
    finally:
        server.close()

    assert stream.max_write_buffer_size == 54321


def test_pub_server_no_cap_when_ipc_write_buffer_zero(master_opts, io_loop):
    """
    ``ipc_write_buffer == 0`` (the default when the operator hasn't
    opted in) must leave the stream's ``max_write_buffer_size``
    untouched -- preserving Tornado's unlimited-write-buffer default.
    """
    master_opts["ipc_write_buffer"] = 0
    server = salt.transport.tcp.PubServer(master_opts, io_loop=io_loop)

    class Stream:
        def __init__(self):
            self.max_write_buffer_size = "sentinel"
            self.socket = MagicMock()
            self.socket.getpeercert.return_value = None
            self._closed = False

        def set_close_callback(self, cb):
            pass

        def close(self):
            self._closed = True

        def closed(self):
            return self._closed

    stream = Stream()
    try:
        with patch.object(
            server, "_stream_read", MagicMock(return_value=None)
        ), patch.object(server.io_loop, "create_task"):
            server.handle_stream(stream, ("127.0.0.1", 12345))
    finally:
        server.close()

    assert stream.max_write_buffer_size == "sentinel"


def test_pub_server_apply_write_buffer_cap_helper(master_opts, io_loop):
    """
    ``_apply_write_buffer_cap`` is the shared helper used by both the
    plaintext ``handle_stream`` path and the SSL-delayed
    ``_validate_ssl_and_add_client`` path.  Verify the helper's contract
    directly so both call sites are covered.
    """
    master_opts["ipc_write_buffer"] = 99999
    server = salt.transport.tcp.PubServer(master_opts, io_loop=io_loop)

    class Stream:
        max_write_buffer_size = None

    stream = Stream()
    server._apply_write_buffer_cap(stream)
    assert stream.max_write_buffer_size == 99999

    master_opts["ipc_write_buffer"] = 0
    server2 = salt.transport.tcp.PubServer(master_opts, io_loop=io_loop)

    class Stream2:
        max_write_buffer_size = "sentinel"

    stream2 = Stream2()
    server2._apply_write_buffer_cap(stream2)
    assert stream2.max_write_buffer_size == "sentinel"


# ---------------------------------------------------------------------------
# PR #70052: EventPublisher fan-out raw_payload passthrough.
#
# Under a burst of returns the EP fan-out did one msgpack.dumps per event
# (inside ``frame_msg(package)``) even though the wire bytes were already
# in hand from the pull-socket read.  ``PubServer.publish_payload`` and
# ``PublishServer.publish_payload`` now accept ``raw_payload=<bytes>`` and,
# when supplied, write those bytes directly to subscribers instead of
# re-framing.  ``TCPPuller.handle_stream`` passes the wire bytes through
# as ``raw_payload=payload`` with a ``TypeError`` fallback for older
# handlers that don't accept the kwarg.
# ---------------------------------------------------------------------------


async def test_pub_server_publish_payload_uses_raw_payload_when_supplied(
    master_opts, io_loop
):
    """
    When ``publish_payload`` is called with ``raw_payload=<bytes>`` those
    bytes are written to subscribers verbatim -- ``frame_msg`` is NOT
    called.  This is the PR #70052 fast path that removes one
    ``msgpack.dumps`` per event on the EP hot path.
    """
    server = salt.transport.tcp.PubServer(master_opts, io_loop=io_loop)
    package = {"foo": "bar"}
    raw = b"pre-framed-wire-bytes"

    future = tornado.concurrent.Future()
    future.set_result(None)
    client = MagicMock()
    client.stream = MagicMock()
    client.stream.write.side_effect = [future]
    client.id_ = "meh"
    server.clients = [client]

    with patch(
        "salt.transport.frame.frame_msg", side_effect=AssertionError("must not reframe")
    ) as fake_frame:
        await server.publish_payload(package, raw_payload=raw)

    fake_frame.assert_not_called()
    client.stream.write.assert_called_once_with(raw)


async def test_pub_server_publish_payload_frames_when_no_raw_payload(
    master_opts, io_loop
):
    """
    Backwards compatibility: when ``raw_payload`` is not supplied,
    ``publish_payload`` must still frame the outgoing package via
    ``frame_msg`` and write the framed bytes to subscribers.
    """
    server = salt.transport.tcp.PubServer(master_opts, io_loop=io_loop)
    package = {"foo": "bar"}
    framed = b"framed-bytes-sentinel"

    future = tornado.concurrent.Future()
    future.set_result(None)
    client = MagicMock()
    client.stream = MagicMock()
    client.stream.write.side_effect = [future]
    client.id_ = "meh"
    server.clients = [client]

    with patch("salt.transport.frame.frame_msg", return_value=framed) as fake_frame:
        await server.publish_payload(package)

    fake_frame.assert_called_once_with(package)
    client.stream.write.assert_called_once_with(framed)


async def test_pub_server_publish_payload_raw_bypass_with_topic_list(
    master_opts, io_loop
):
    """
    ``raw_payload`` bypass must apply on the topic-filtered path too --
    the fast path is chosen based solely on ``raw_payload``, not on the
    presence or absence of ``topic_list``.
    """
    server = salt.transport.tcp.PubServer(master_opts, io_loop=io_loop)
    raw = b"topic-raw-bytes"

    future = tornado.concurrent.Future()
    future.set_result(None)
    client = MagicMock()
    client.stream = MagicMock()
    client.stream.write.side_effect = [future]
    client.id_ = "target"
    server.clients = [client]

    with patch(
        "salt.transport.frame.frame_msg", side_effect=AssertionError("must not reframe")
    ):
        await server.publish_payload(
            {"foo": "bar"}, topic_list=["target"], raw_payload=raw
        )

    client.stream.write.assert_called_once_with(raw)


async def test_publish_server_publish_payload_forwards_raw_payload(
    master_opts, io_loop
):
    """
    ``PublishServer.publish_payload`` is a thin wrapper that must
    forward ``raw_payload`` through to ``self.pub_server.publish_payload``
    -- otherwise the fast path never reaches the layer that actually
    writes to subscribers.
    """
    pubserv = salt.transport.tcp.PublishServer(
        master_opts,
        pub_host="127.0.0.1",
        pub_port=5151,
        pull_host="127.0.0.1",
        pull_port=5152,
    )
    pubserv.pub_server = MagicMock()
    pubserv.pub_server.publish_payload = AsyncMock(return_value=None)

    raw = b"raw-wire-bytes"
    await pubserv.publish_payload({"foo": "bar"}, ["t1"], raw_payload=raw)

    pubserv.pub_server.publish_payload.assert_awaited_once_with(
        {"foo": "bar"}, ["t1"], raw_payload=raw
    )


async def test_publish_server_publish_payload_default_raw_payload_none(
    master_opts, io_loop
):
    """
    When ``PublishServer.publish_payload`` is called without a
    ``raw_payload`` kwarg (older callers) it must still forward the
    default ``raw_payload=None`` -- ensuring the underlying pub server
    falls back to its ``frame_msg`` path.
    """
    pubserv = salt.transport.tcp.PublishServer(
        master_opts,
        pub_host="127.0.0.1",
        pub_port=5151,
        pull_host="127.0.0.1",
        pull_port=5152,
    )
    pubserv.pub_server = MagicMock()
    pubserv.pub_server.publish_payload = AsyncMock(return_value=None)

    await pubserv.publish_payload({"foo": "bar"})

    pubserv.pub_server.publish_payload.assert_awaited_once_with(
        {"foo": "bar"}, None, raw_payload=None
    )


async def test_tcp_puller_handle_stream_passes_raw_payload_kwarg(master_opts):
    """
    ``TCPPuller.handle_stream`` reads the length-prefixed frame with
    ``raw=True`` (dict keys are bytes) and passes the original wire
    bytes as ``raw_payload=payload`` to the handler.  Verify the handler
    receives both ``body`` and ``raw_payload=<wire bytes>``.
    """
    import struct

    received = []

    async def handler(body, raw_payload=None):
        received.append((body, raw_payload))

    puller = salt.transport.tcp.TCPPuller(payload_handler=handler)

    def _frame(body):
        payload = salt.utils.msgpack.packb({"body": body}, use_bin_type=True)
        return struct.pack(">I", len(payload)) + payload, payload

    frame_bytes, raw_wire = _frame(b"hello-world")

    class FakeStream:
        def __init__(self, chunks):
            self._buf = b"".join(chunks)
            self._closed = False

        async def read_bytes(self, n):
            if len(self._buf) < n:
                self._closed = True
                raise tornado.iostream.StreamClosedError()
            chunk, self._buf = self._buf[:n], self._buf[n:]
            return chunk

        def closed(self):
            return self._closed

    stream = FakeStream([frame_bytes])
    await asyncio.wait_for(puller.handle_stream(stream), timeout=5)

    assert len(received) == 1
    body, raw = received[0]
    # ``raw=True`` unpack keeps bytes keys/values, so ``body`` is bytes.
    assert body == b"hello-world"
    # The original wire bytes (msgpack of the framed dict, no length
    # prefix) are what we handed off as ``raw_payload``.
    assert raw == raw_wire


async def test_tcp_puller_handle_stream_typeerror_fallback(master_opts):
    """
    Older payload handlers only accept ``(body,)`` and raise
    ``TypeError`` when called with ``raw_payload=...``.  The reader must
    catch that ``TypeError`` and retry without the kwarg so pre-#70052
    handlers keep working.
    """
    import struct

    call_log = []

    async def async_handler_no_raw(body):
        # This is the successful path.
        call_log.append(("handled", body))

    def wrapping_handler(body, *, raw_payload=None):
        # First call: raises TypeError, mimicking a handler whose
        # signature doesn't accept ``raw_payload``.  The reader is
        # expected to fall back to ``payload_handler(body)`` (a fresh
        # call), which returns the coroutine we await.
        call_log.append(("raw-call", raw_payload is not None))
        raise TypeError("handler does not accept raw_payload")

    # Combine into one callable so the reader's first call raises and
    # the second call succeeds.
    calls = {"count": 0}

    def payload_handler(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            # First invocation: kwarg present -> raise TypeError.
            call_log.append(("raw-call", "raw_payload" in kwargs))
            raise TypeError("handler does not accept raw_payload")
        # Second invocation: positional only -> return an awaitable.
        return async_handler_no_raw(*args)

    puller = salt.transport.tcp.TCPPuller(payload_handler=payload_handler)

    def _frame(body):
        payload = salt.utils.msgpack.packb({"body": body}, use_bin_type=True)
        return struct.pack(">I", len(payload)) + payload

    class FakeStream:
        def __init__(self, chunks):
            self._buf = b"".join(chunks)
            self._closed = False

        async def read_bytes(self, n):
            if len(self._buf) < n:
                self._closed = True
                raise tornado.iostream.StreamClosedError()
            chunk, self._buf = self._buf[:n], self._buf[n:]
            return chunk

        def closed(self):
            return self._closed

    stream = FakeStream([_frame(b"fallback-body")])
    await asyncio.wait_for(puller.handle_stream(stream), timeout=5)

    # Two calls total: one that raised TypeError, one that succeeded.
    assert calls["count"] == 2
    assert call_log == [
        ("raw-call", True),
        ("handled", b"fallback-body"),
    ]


async def test_tcp_puller_handle_stream_unpacks_with_raw_true(master_opts):
    """
    The outer-frame unpack now uses ``raw=True`` so dict keys are bytes
    (``framed_msg[b"body"]``).  A message whose ``body`` value contains
    non-ASCII bytes must still be routed correctly through
    ``payload_handler`` -- proves the ``raw=True`` switch didn't break
    ``body`` extraction.
    """
    import struct

    received = []

    async def handler(body, raw_payload=None):
        received.append(body)

    puller = salt.transport.tcp.TCPPuller(payload_handler=handler)

    # Non-ASCII body to exercise ``raw=True`` bytes handling.
    body = b"\x81\xa3foo\xa3bar"
    payload = salt.utils.msgpack.packb({"body": body}, use_bin_type=True)
    frame = struct.pack(">I", len(payload)) + payload

    class FakeStream:
        def __init__(self, chunks):
            self._buf = b"".join(chunks)
            self._closed = False

        async def read_bytes(self, n):
            if len(self._buf) < n:
                self._closed = True
                raise tornado.iostream.StreamClosedError()
            chunk, self._buf = self._buf[:n], self._buf[n:]
            return chunk

        def closed(self):
            return self._closed

    stream = FakeStream([frame])
    await asyncio.wait_for(puller.handle_stream(stream), timeout=5)

    assert received == [body]
