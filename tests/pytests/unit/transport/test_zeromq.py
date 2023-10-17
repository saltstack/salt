import msgpack
import pytest
import tornado.concurrent

import salt.config
import salt.transport.zeromq
from tests.support.mock import MagicMock


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
    assert hasattr(client, "_future")
    assert client._future is None
    future = tornado.concurrent.Future()
    client._future = future
    client.timeout_message(future)
    with pytest.raises(salt.exceptions.SaltReqTimeoutError):
        await future
    assert client._future is None

    future_a = tornado.concurrent.Future()
    future_b = tornado.concurrent.Future()
    future_b.set_exception = MagicMock()
    client._future = future_a
    client.timeout_message(future_b)

    assert client._future == future_a
    future_b.set_exception.assert_not_called()
