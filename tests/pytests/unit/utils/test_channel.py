"""Pool routing uses the common transport factories and the caller's loop."""

import asyncio

import pytest

import salt.utils.channel
from tests.support.mock import patch


@pytest.mark.parametrize("transport", ["tcp", "zeromq", "ws"])
@pytest.mark.parametrize("routing", [None, "workers_ipc_name", "pool_name"])
async def test_create_client_transport(transport, routing):
    opts = {"transport": transport}
    if routing:
        opts[routing] = "pool"
    loop = asyncio.get_running_loop()
    expected = "RequestClient" if routing else "PublishClient"
    with patch(f"salt.transport.{transport}.{expected}") as client:
        result = salt.utils.channel.create_client_transport(opts, loop)
        assert result is client.return_value
        assert client.call_args.args[0] is opts
        passed_loop = client.call_args.kwargs.get("io_loop")
        if passed_loop is None:
            passed_loop = client.call_args.args[1]
        assert passed_loop is loop


@pytest.mark.parametrize("transport", ["tcp", "zeromq", "ws"])
async def test_create_request_client_defaults_to_current_loop(transport):
    opts = {"transport": transport}
    with patch(f"salt.transport.{transport}.RequestClient") as client:
        assert salt.utils.channel.create_request_client(opts) is client.return_value
        assert client.call_args.kwargs["io_loop"] is asyncio.get_running_loop()


@pytest.mark.parametrize("transport", ["tcp", "zeromq", "ws"])
def test_create_server_transport(transport):
    opts = {"transport": transport}
    with patch(f"salt.transport.{transport}.RequestServer") as server:
        assert salt.utils.channel.create_server_transport(opts) is server.return_value
        server.assert_called_once_with(opts)


@pytest.mark.parametrize(
    "factory",
    [
        salt.utils.channel.create_server_transport,
        salt.utils.channel.create_client_transport,
        salt.utils.channel.create_request_client,
    ],
)
def test_unsupported_transport(factory, io_loop):
    args = (io_loop,) if factory is salt.utils.channel.create_client_transport else ()
    with pytest.raises(ValueError, match="Unsupported transport type: unknown"):
        factory({"transport": "unknown"}, *args)
