"""
Unit tests for the WebSocket transport's TLS client behaviour.
"""

import ssl

import pytest

import salt.transport.ws
from tests.support.mock import AsyncMock, MagicMock, patch

pytestmark = [
    pytest.mark.core_test,
]


async def test_ws_request_client_connect_verifies_configured_master_name(
    minion_opts, io_loop
):
    """
    The WebSocket request client builds its URL from the resolved
    ``master_uri``; the TLS layer must still verify the certificate against
    the configured ``master`` hostname.
    """
    minion_opts["transport"] = "ws"
    minion_opts["master"] = "salt-master.corp.example"
    minion_opts["master_ip"] = "10.0.0.5"
    minion_opts["master_uri"] = "tcp://10.0.0.5:4506"
    minion_opts["ssl"] = {
        "certfile": "minion.crt",
        "keyfile": "minion.key",
        "ca_certs": "corp-root.crt",
        "cert_reqs": ssl.CERT_REQUIRED,
    }
    client = salt.transport.ws.RequestClient(minion_opts, io_loop)
    ctx = MagicMock()
    session = MagicMock()
    session.ws_connect = AsyncMock(return_value=MagicMock())
    session.close = AsyncMock()
    with patch("salt.transport.base.ssl_context", return_value=ctx), patch(
        "aiohttp.ClientSession", return_value=session
    ):
        await client.connect()
    session.ws_connect.assert_awaited_once_with(
        "https://10.0.0.5:4506",
        ssl=ctx,
        server_hostname="salt-master.corp.example",
    )
    client.ws = None
    client.session = None


async def test_ws_request_client_connect_without_ssl(minion_opts, io_loop):
    minion_opts["transport"] = "ws"
    minion_opts["master_uri"] = "tcp://10.0.0.5:4506"
    minion_opts["ssl"] = None
    client = salt.transport.ws.RequestClient(minion_opts, io_loop)
    session = MagicMock()
    session.ws_connect = AsyncMock(return_value=MagicMock())
    with patch("aiohttp.ClientSession", return_value=session):
        await client.connect()
    session.ws_connect.assert_awaited_once_with(
        "http://10.0.0.5:4506", ssl=None, server_hostname=None
    )
    client.ws = None
    client.session = None


async def test_ws_publish_client_getstream_verifies_configured_master_name(
    minion_opts, io_loop
):
    minion_opts["transport"] = "ws"
    minion_opts["master"] = "salt-master.corp.example"
    minion_opts["master_ip"] = "10.0.0.5"
    ssl_opts = {"ca_certs": "corp-root.crt", "cert_reqs": ssl.CERT_REQUIRED}
    client = salt.transport.ws.PublishClient(
        minion_opts, io_loop, host="10.0.0.5", port=4505, ssl=ssl_opts
    )
    ctx = MagicMock()
    ws = MagicMock()
    ws.closed = False
    session = MagicMock()
    session.ws_connect = AsyncMock(return_value=ws)
    session.close = AsyncMock()
    with patch("salt.transport.base.ssl_context", return_value=ctx), patch(
        "aiohttp.ClientSession", return_value=session
    ), patch("aiohttp.TCPConnector"):
        got_ws, got_session = await client.getstream(timeout=1)
    assert got_ws is ws
    assert got_session is session
    session.ws_connect.assert_awaited_once_with(
        "https://10.0.0.5:4505/ws",
        ssl=ctx,
        server_hostname="salt-master.corp.example",
    )
