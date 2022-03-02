import asyncio
import logging
import socket

import attr
import pytest
import salt.exceptions
import salt.ext.tornado
import salt.transport.tcp
from saltfactories.utils.ports import get_unused_localhost_port
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@attr.s(frozen=True, slots=True)
class ClientSocket:
    listen_on = attr.ib(init=False, default="127.0.0.1")
    port = attr.ib(init=False, default=attr.Factory(get_unused_localhost_port))
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


async def test_message_client_cleanup_on_close(client_socket, temp_salt_master):
    """
    test message client cleanup on close
    """
    # orig_loop = salt.ext.tornado.ioloop.IOLoop()
    # orig_loop.make_current()
    orig_loop = asyncio.get_event_loop()

    opts = dict(temp_salt_master.config.copy(), transport="tcp")
    client = salt.transport.tcp.MessageClient(
        opts, client_socket.listen_on, client_socket.port
    )
    assert client.io_loop == orig_loop
    try:
        await client.connect()
        assert client._reader is not None
        assert client._writer is not None
        # This is no longer a thing
        # assert orig_loop.stop_called is True
    finally:
        client.close()


# XXX: Test channel for this
# def test_tcp_pub_server_channel_publish_filtering(temp_salt_master):
#    opts = dict(
#        temp_salt_master.config.copy(),
#        sign_pub_messages=False,
#        transport="tcp",
#        acceptance_wait_time=5,
#        acceptance_wait_time_max=5,
#    )
#    with patch("salt.master.SMaster.secrets") as secrets, patch(
#        "salt.crypt.Crypticle"
#    ) as crypticle, patch("salt.utils.asynchronous.SyncWrapper") as SyncWrapper:
#        channel = salt.transport.tcp.TCPPubServerChannel(opts)
#        wrap = MagicMock()
#        crypt = MagicMock()
#        crypt.dumps.return_value = {"test": "value"}
#
#        secrets.return_value = {"aes": {"secret": None}}
#        crypticle.return_value = crypt
#        SyncWrapper.return_value = wrap
#
#        # try simple publish with glob tgt_type
#        channel.publish({"test": "value", "tgt_type": "glob", "tgt": "*"})
#        payload = wrap.send.call_args[0][0]
#
#        # verify we send it without any specific topic
#        assert "topic_lst" not in payload
#
#        # try simple publish with list tgt_type
#        channel.publish({"test": "value", "tgt_type": "list", "tgt": ["minion01"]})
#        payload = wrap.send.call_args[0][0]
#
#        # verify we send it with correct topic
#        assert "topic_lst" in payload
#        assert payload["topic_lst"] == ["minion01"]
#
#        # try with syndic settings
#        opts["order_masters"] = True
#        channel.publish({"test": "value", "tgt_type": "list", "tgt": ["minion01"]})
#        payload = wrap.send.call_args[0][0]
#
#        # verify we send it without topic for syndics
#        assert "topic_lst" not in payload


# def test_tcp_pub_server_channel_publish_filtering_str_list(temp_salt_master):
#    opts = dict(
#        temp_salt_master.config.copy(),
#        transport="tcp",
#        sign_pub_messages=False,
#        acceptance_wait_time=5,
#        acceptance_wait_time_max=5,
#    )
#    with patch("salt.master.SMaster.secrets") as secrets, patch(
#        "salt.crypt.Crypticle"
#    ) as crypticle, patch("salt.utils.asynchronous.SyncWrapper") as SyncWrapper, patch(
#        "salt.utils.minions.CkMinions.check_minions"
#    ) as check_minions:
#        channel = salt.transport.tcp.TCPPubServerChannel(opts)
#        wrap = MagicMock()
#        crypt = MagicMock()
#        crypt.dumps.return_value = {"test": "value"}
#
#        secrets.return_value = {"aes": {"secret": None}}
#        crypticle.return_value = crypt
#        SyncWrapper.return_value = wrap
#        check_minions.return_value = {"minions": ["minion02"]}
#
#        # try simple publish with list tgt_type
#        channel.publish({"test": "value", "tgt_type": "list", "tgt": "minion02"})
#        payload = wrap.send.call_args[0][0]
#
#        # verify we send it with correct topic
#        assert "topic_lst" in payload
#        assert payload["topic_lst"] == ["minion02"]
#
#        # verify it was correctly calling check_minions
#        check_minions.assert_called_with("minion02", tgt_type="list")


@pytest.fixture(scope="function")
def salt_message_client():
    io_loop_mock = MagicMock(spec=asyncio.get_event_loop())
    io_loop_mock.call_later.side_effect = lambda *args, **kwargs: (args, kwargs)

    client = salt.transport.tcp.MessageClient(
        {}, "127.0.0.1", get_unused_localhost_port(), io_loop=io_loop_mock
    )

    try:
        yield client
    finally:
        client.close()


# XXX we don't reutnr a future anymore, this needs a different way of testing.
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


def test_timeout_message_unknown_future(salt_message_client):
    #    # test we don't fail on unknown message_id
    #    salt_message_client.timeout_message(-1, "message")

    # if we do have the actual future stored under the id, but it's none
    # we shouldn't fail as well
    message_id = 1
    future = salt.ext.tornado.concurrent.Future()
    future.attempts = 1
    future.tries = 1
    salt_message_client.send_future_map[message_id] = future

    salt_message_client.timeout_message(message_id, "message")

    assert message_id not in salt_message_client.send_future_map


def xtest_client_reconnect_backoff(client_socket):
    opts = {"tcp_reconnect_backoff": 5}

    client = salt.transport.tcp.MessageClient(
        opts, client_socket.listen_on, client_socket.port
    )

    def _sleep(t):
        client.close()
        assert t == 5
        return
        # return salt.ext.tornado.gen.sleep()

    @salt.ext.tornado.gen.coroutine
    def connect(*args, **kwargs):
        raise Exception("err")

    client._tcp_client.connect = connect

    try:
        with patch("salt.ext.tornado.gen.sleep", side_effect=_sleep):
            client.io_loop.run_sync(client.connect)
    finally:
        client.close()
