"""Filtered publications for children sharing a DeltaProxy subscription."""

import hashlib

import pytest
import zmq

import salt.payload
import salt.transport.zeromq
from tests.support.mock import AsyncMock, MagicMock, call, patch

pytestmark = [pytest.mark.core_test]


def topic(minion_id):
    return hashlib.sha1(minion_id.encode()).hexdigest().encode()


@pytest.fixture
def client(minion_opts, io_loop):
    opts = dict(
        minion_opts,
        id="controller",
        zmq_filtering=True,
        zmq_monitor=False,
        recon_randomize=False,
    )
    with patch("zmq.asyncio.Context"), patch("zmq.Poller"):
        with salt.transport.zeromq.PublishClient(
            opts, io_loop, host="127.0.0.1", port=4506
        ) as transport:
            yield transport


def test_child_subscriptions(client):
    """Additional child IDs are subscribed and accepted by the decoder."""
    children = ["child-one", "child-two", "child-ü"]
    client.add_subscriptions(children)
    for child in children:
        assert (
            call(zmq.SUBSCRIBE, topic(child))
            in client._socket.setsockopt.call_args_list
        )
        payload = {"enc": "aes", "load": "encrypted-job"}
        assert (
            client._decode_messages([topic(child), salt.payload.dumps(payload)])
            == payload
        )
    assert client._decode_messages([topic("unrelated"), b"invalid"]) is None


def test_child_subscriptions_are_idempotent(client):
    client.add_subscriptions(["child-one"])
    client._socket.setsockopt.reset_mock()
    client.add_subscriptions(["child-one", "controller"])
    client._socket.setsockopt.assert_not_called()


def test_unsubscribed_child_is_rejected(client):
    assert client._decode_messages([topic("child-one"), b"invalid"]) is None


@pytest.mark.parametrize("timeout", [None, 0, 0.3])
@pytest.mark.parametrize("frames", [[b"payload"], [b"broadcast", b"payload"]])
async def test_receive_preserves_multipart(client, timeout, frames):
    """A topic and its payload must be consumed as one publication."""
    client._socket.recv_multipart = AsyncMock(return_value=frames)
    client._socket.recv = AsyncMock(return_value=frames[0])
    client._socket.poll = AsyncMock(return_value=1)
    client.poller.poll = MagicMock(return_value=[(client._socket, zmq.POLLIN)])
    expected = frames[0] if len(frames) == 1 else frames
    assert await client.recv(timeout=timeout) == expected
    client._socket.recv_multipart.assert_awaited_once_with()
    client._socket.recv.assert_not_awaited()


@pytest.mark.parametrize("timeout", [0, 0.3])
async def test_receive_timeout_does_not_consume(client, timeout):
    client._socket.recv_multipart = AsyncMock()
    client._socket.poll = AsyncMock(return_value=0)
    client.poller.poll = MagicMock(return_value=[])
    assert await client.recv(timeout=timeout) is None
    client._socket.recv_multipart.assert_not_awaited()


def test_monitor_stop_handles_zmq_errors():
    socket = MagicMock()
    socket.disable_monitor.side_effect = zmq.ZMQError(zmq.ENOTSOCK)
    socket.get_monitor_socket.return_value.close.side_effect = zmq.ZMQError(
        zmq.ENOTSOCK
    )
    monitor = salt.transport.zeromq.ZeroMQSocketMonitor(socket)
    monitor.stop()
    assert monitor._socket is None
    assert monitor._monitor_socket is None
