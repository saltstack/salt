import msgpack
import pytest

import salt.config
import salt.transport.zeromq


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
