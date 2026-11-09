"""Pool routing uses the common transport factories and the caller's loop."""

import asyncio
import warnings

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
        result = salt.utils.channel.create_client_transport(opts)
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
        salt.utils.channel.create_client_transport,
        salt.utils.channel.create_request_client,
    ],
)
@pytest.mark.parametrize("legacy", [False, True])
async def test_pool_factory_warns_only_for_tornado_loop(factory, io_loop, legacy):
    opts = {"transport": "tcp", "pool_name": "pool"}
    with patch("salt.transport.tcp.RequestClient") as client:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            supplied = io_loop if legacy else asyncio.get_running_loop()
            assert factory(opts, supplied) is client.return_value
        assert len(caught) == int(legacy)
        if legacy:
            assert "Passing a Tornado IOLoop" in str(caught[0].message)
            assert "removed in Salt 3009.2" in str(caught[0].message)
            assert caught[0].filename == __file__
        assert client.call_args.kwargs["io_loop"] is asyncio.get_running_loop()


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


@pytest.mark.parametrize("kind", ["server", "request", "pool", "publish"])
@pytest.mark.parametrize("explicit", [None, "tcp"])
@pytest.mark.parametrize("pillar", ["ws", "unknown"])
async def test_pool_transport_selection_ignores_pillar(kind, explicit, pillar):
    secret = object()
    opts = {"pillar": {"master": {"transport": pillar}}, "secrets": secret}
    if explicit is not None:
        opts["transport"] = explicit
    if kind == "pool":
        opts["pool_name"] = "pool"
    before = opts.copy()
    selected = explicit or "zeromq"
    constructor = {
        "server": "RequestServer",
        "request": "RequestClient",
        "pool": "RequestClient",
        "publish": "PublishClient",
    }[kind]
    factory = {
        "server": salt.utils.channel.create_server_transport,
        "request": salt.utils.channel.create_request_client,
        "pool": salt.utils.channel.create_client_transport,
        "publish": salt.utils.channel.create_client_transport,
    }[kind]
    with patch(f"salt.transport.{selected}.{constructor}") as transport:
        assert factory(opts) is transport.return_value
    passed_opts = transport.call_args.args[0]
    assert passed_opts["transport"] == selected
    assert passed_opts["secrets"] is secret
    assert passed_opts["pillar"] is opts["pillar"]
    assert opts == before


@pytest.mark.parametrize("transport", ["tcp", "ws"])
async def test_pool_publish_factory_does_not_enable_tls_from_opts(transport):
    opts = {"transport": transport, "ssl": {"certfile": "unused"}}
    with patch(f"salt.transport.{transport}.PublishClient") as client:
        salt.utils.channel.create_client_transport(opts)
    assert client.call_args.kwargs["ssl"] is None
