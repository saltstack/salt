import hashlib
import urllib.parse

import pytest
from tornado.httpclient import HTTPError, HTTPRequest
from tornado.websocket import websocket_connect

import salt.netapi.rest_tornado as rest_tornado
import salt.utils.json
import salt.utils.yaml
from salt.config import DEFAULT_HASH_TYPE

pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
]


@pytest.fixture
def app(client_config, io_loop):
    client_config.setdefault("rest_tornado", {})["websockets"] = True
    return rest_tornado.get_application(client_config)


@pytest.fixture
def http_server_port(http_server):
    return http_server.port


async def test_websocket_handler_upgrade_to_websocket(
    http_client,
    auth_creds,
    content_type_map,
    http_server_port,
    io_loop,
):
    response = await http_client.fetch(
        "/login",
        method="POST",
        body=urllib.parse.urlencode(auth_creds),
        headers={"Content-Type": content_type_map["form"]},
    )
    token = salt.utils.json.loads(response.body)["return"][0]["token"]

    url = f"ws://127.0.0.1:{http_server_port}/all_events/{token}"
    request = HTTPRequest(
        url, headers={"Origin": "http://example.com", "Host": "example.com"}
    )
    ws = await websocket_connect(request, connect_timeout=None)
    await ws.write_message("websocket client ready")
    ws.close()


async def test_websocket_handler_bad_token(client_config, http_server, io_loop):
    """
    A bad token should returns a 401 during a websocket connect
    """
    token = "A" * len(
        getattr(
            hashlib, client_config.get("hash_type", DEFAULT_HASH_TYPE)
        )().hexdigest()
    )

    url = f"ws://127.0.0.1:{http_server.port}/all_events/{token}"
    request = HTTPRequest(
        url, headers={"Origin": "http://example.com", "Host": "example.com"}
    )
    with pytest.raises(HTTPError) as exc:
        await websocket_connect(request)
    assert exc.value.code == 401


async def test_websocket_handler_cors_origin_wildcard(
    app, http_client, auth_creds, content_type_map, http_server_port, io_loop
):
    app.mod_opts["cors_origin"] = "*"
    response = await http_client.fetch(
        "/login",
        method="POST",
        body=urllib.parse.urlencode(auth_creds),
        headers={"Content-Type": content_type_map["form"]},
    )
    token = salt.utils.json.loads(response.body)["return"][0]["token"]

    url = f"ws://127.0.0.1:{http_server_port}/all_events/{token}"
    request = HTTPRequest(
        url, headers={"Origin": "http://foo.bar", "Host": "example.com"}
    )
    ws = await websocket_connect(request)
    ws.write_message("websocket client ready")
    ws.close()


async def test_cors_origin_single(
    app, http_client, auth_creds, content_type_map, http_server_port, io_loop
):
    app.mod_opts["cors_origin"] = "http://example.com"
    response = await http_client.fetch(
        "/login",
        method="POST",
        body=urllib.parse.urlencode(auth_creds),
        headers={"Content-Type": content_type_map["form"]},
    )
    token = salt.utils.json.loads(response.body)["return"][0]["token"]

    url = f"ws://127.0.0.1:{http_server_port}/all_events/{token}"

    # Example.com should works
    request = HTTPRequest(
        url, headers={"Origin": "http://example.com", "Host": "example.com"}
    )
    ws = await websocket_connect(request)
    ws.write_message("websocket client ready")
    ws.close()

    # But foo.bar not
    request = HTTPRequest(
        url, headers={"Origin": "http://foo.bar", "Host": "example.com"}
    )
    with pytest.raises(HTTPError) as exc:
        await websocket_connect(request)
    assert exc.value.code == 403


async def test_cors_origin_multiple(
    app, http_client, auth_creds, content_type_map, http_server_port, io_loop
):
    app.mod_opts["cors_origin"] = ["http://example.com", "http://foo.bar"]

    response = await http_client.fetch(
        "/login",
        method="POST",
        body=urllib.parse.urlencode(auth_creds),
        headers={"Content-Type": content_type_map["form"]},
    )
    token = salt.utils.json.loads(response.body)["return"][0]["token"]

    url = f"ws://127.0.0.1:{http_server_port}/all_events/{token}"

    # Example.com should works
    request = HTTPRequest(
        url, headers={"Origin": "http://example.com", "Host": "example.com"}
    )
    ws = await websocket_connect(request)
    ws.write_message("websocket client ready")
    ws.close()

    # But foo.bar not
    request = HTTPRequest(
        url, headers={"Origin": "http://foo.bar", "Host": "example.com"}
    )

    ws = await websocket_connect(request)
    ws.write_message("websocket client ready")
    ws.close()
