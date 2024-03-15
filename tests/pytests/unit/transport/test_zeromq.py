import logging

import msgpack
import pytest
import zmq.eventloop.future

import salt.config
import salt.transport.base
import salt.transport.zeromq
import salt.utils.platform
import salt.utils.process
import salt.utils.stringutils
from tests.support.mock import AsyncMock, MagicMock

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.core_test,
]


async def test_req_server_garbage_request(io_loop):
    """
    Validate invalid msgpack messages will not raise exceptions in the
    RequestServers's message handler.
    """
    opts = salt.config.master_config("")
    request_server = salt.transport.zeromq.RequestServer(opts)

    def message_handler(payload):
        return payload

    request_server.post_fork(message_handler, io_loop)

    byts = msgpack.dumps({"foo": "bar"})
    badbyts = byts[:3] + b"^M" + byts[3:]

    try:
        ret = await request_server.handle_message(None, badbyts)
    except Exception as exc:  # pylint: disable=broad-except
        pytest.fail(f"Exception was raised {exc}")
    finally:
        request_server.close()

    assert ret == {"msg": "bad load"}


async def test_client_timeout_msg(minion_opts):
    client = salt.transport.zeromq.AsyncReqMessageClient(
        minion_opts, "tcp://127.0.0.1:4506"
    )
    client.connect()
    try:
        with pytest.raises(salt.exceptions.SaltReqTimeoutError):
            await client.send({"meh": "bah"}, 1)
    finally:
        client.close()


async def test_client_send_recv_on_cancelled_error(minion_opts):
    client = salt.transport.zeromq.AsyncReqMessageClient(
        minion_opts, "tcp://127.0.0.1:4506"
    )

    mock_future = MagicMock(**{"done.return_value": True})

    try:
        client.socket = AsyncMock()
        client.socket.recv.side_effect = zmq.eventloop.future.CancelledError
        await client._send_recv({"meh": "bah"}, mock_future)

        mock_future.set_exception.assert_not_called()
    finally:
        client.close()


async def test_client_send_recv_on_exception(minion_opts):
    client = salt.transport.zeromq.AsyncReqMessageClient(
        minion_opts, "tcp://127.0.0.1:4506"
    )

    mock_future = MagicMock(**{"done.return_value": True})

    try:
        client.socket = None
        await client._send_recv({"meh": "bah"}, mock_future)

        mock_future.set_exception.assert_not_called()
    finally:
        client.close()


def test_pub_client_init(minion_opts, io_loop):
    minion_opts["id"] = "minion"
    minion_opts["__role"] = "syndic"
    minion_opts["master_ip"] = "127.0.0.1"
    minion_opts["zmq_filtering"] = True
    minion_opts["zmq_monitor"] = True
    with salt.transport.zeromq.PublishClient(
        minion_opts, io_loop, host=minion_opts["master_ip"], port=121212
    ) as client:
        client.send(b"asf")


async def test_unclosed_request_client(minion_opts, io_loop):
    minion_opts["master_uri"] = "tcp://127.0.0.1:4506"
    client = salt.transport.zeromq.RequestClient(minion_opts, io_loop)
    await client.connect()
    try:
        assert client._closing is False
        with pytest.warns(salt.transport.base.TransportWarning):
            client.__del__()  # pylint: disable=unnecessary-dunder-call
    finally:
        client.close()


async def test_unclosed_publish_client(minion_opts, io_loop):
    minion_opts["id"] = "minion"
    minion_opts["__role"] = "minion"
    minion_opts["master_ip"] = "127.0.0.1"
    minion_opts["zmq_filtering"] = True
    minion_opts["zmq_monitor"] = True
    client = salt.transport.zeromq.PublishClient(
        minion_opts, io_loop, host=minion_opts["master_ip"], port=121212
    )
    await client.connect()
    try:
        assert client._closing is False
        with pytest.warns(salt.transport.base.TransportWarning):
            client.__del__()  # pylint: disable=unnecessary-dunder-call
    finally:
        client.close()
