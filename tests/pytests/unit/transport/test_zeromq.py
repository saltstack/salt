import msgpack
import pytest

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

    valid_response = msgpack.dumps("Invalid payload")

    stream = MagicMock()
    request_server.stream = stream

    try:
        await request_server.handle_message(stream, badbyts)
    except Exception as exc:  # pylint: disable=broad-except
        pytest.fail(f"Exception was raised {exc}")

    request_server.stream.send.assert_called_once_with(valid_response)
