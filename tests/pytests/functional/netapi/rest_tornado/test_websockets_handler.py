import hashlib
import urllib.parse

import pytest
import salt.netapi.rest_tornado as rest_tornado
import salt.utils.json
import salt.utils.yaml
from salt.ext.tornado.httpclient import HTTPError, HTTPRequest
from salt.ext.tornado.websocket import websocket_connect


@pytest.fixture
def app(client_config):
    client_config.setdefault("rest_tornado", {})["websockets"] = True
    return rest_tornado.get_application(client_config)


@pytest.fixture
def http_server_port(http_server):
    return http_server.port


async def test_websocket_handler_upgrade_to_websocket(
    http_client, auth_creds, content_type_map, http_server_port
):
    response = await http_client.fetch(
        "/login",
        method="POST",
        body=urllib.parse.urlencode(auth_creds),
        headers={"Content-Type": content_type_map["form"]},
    )
    token = salt.utils.json.loads(response.body)["return"][0]["token"]

    url = "ws://127.0.0.1:{}/all_events/{}".format(http_server_port, token)
    request = HTTPRequest(
        url, headers={"Origin": "http://example.com", "Host": "example.com"}
    )
    ws = await websocket_connect(request)
    ws.write_message("websocket client ready")
    ws.close()


async def test_websocket_handler_bad_token(client_config, http_server):
    """
    A bad token should returns a 401 during a websocket connect
    """
    token = "A" * len(
        getattr(hashlib, client_config.get("hash_type", "md5"))().hexdigest()
    )

    url = "ws://127.0.0.1:{}/all_events/{}".format(http_server.port, token)
    request = HTTPRequest(
        url, headers={"Origin": "http://example.com", "Host": "example.com"}
    )
    with pytest.raises(HTTPError) as exc:
        await websocket_connect(request)
    assert exc.value.code == 401


async def test_websocket_handler_cors_origin_wildcard(
    app, http_client, auth_creds, content_type_map, http_server_port
):
    app.mod_opts["cors_origin"] = "*"
    response = await http_client.fetch(
        "/login",
        method="POST",
        body=urllib.parse.urlencode(auth_creds),
        headers={"Content-Type": content_type_map["form"]},
    )
    token = salt.utils.json.loads(response.body)["return"][0]["token"]

    url = "ws://127.0.0.1:{}/all_events/{}".format(http_server_port, token)
    request = HTTPRequest(
        url, headers={"Origin": "http://foo.bar", "Host": "example.com"}
    )
    ws = await websocket_connect(request)
    ws.write_message("websocket client ready")
    ws.close()


async def test_cors_origin_single(
    app, http_client, auth_creds, content_type_map, http_server_port
):
    app.mod_opts["cors_origin"] = "http://example.com"
    response = await http_client.fetch(
        "/login",
        method="POST",
        body=urllib.parse.urlencode(auth_creds),
        headers={"Content-Type": content_type_map["form"]},
    )
    token = salt.utils.json.loads(response.body)["return"][0]["token"]

    url = "ws://127.0.0.1:{}/all_events/{}".format(http_server_port, token)

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
    app, http_client, auth_creds, content_type_map, http_server_port
):
    app.mod_opts["cors_origin"] = ["http://example.com", "http://foo.bar"]

    response = await http_client.fetch(
        "/login",
        method="POST",
        body=urllib.parse.urlencode(auth_creds),
        headers={"Content-Type": content_type_map["form"]},
    )
    token = salt.utils.json.loads(response.body)["return"][0]["token"]

    url = "ws://127.0.0.1:{}/all_events/{}".format(http_server_port, token)

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
