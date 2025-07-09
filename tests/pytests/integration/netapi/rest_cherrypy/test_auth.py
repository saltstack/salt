import urllib.parse

import pytest

import salt.utils.json
from salt.ext.tornado.httpclient import HTTPError


async def test_get_root_noauth(http_client):
    """
    GET requests to the root URL should not require auth
    """
    response = await http_client.fetch("/")
    assert response.code == 200


async def test_post_root_auth(http_client):
    """
    POST requests to the root URL redirect to login
    """
    with pytest.raises(HTTPError) as exc:
        await http_client.fetch("/", method="POST", body=salt.utils.json.dumps({}))
    assert exc.value.code == 401


async def test_login_noauth(http_client):
    """
    GET requests to the login URL should not require auth
    """
    response = await http_client.fetch("/login")
    assert response.code == 200


async def test_webhook_auth(http_client):
    """
    Requests to the webhook URL require auth by default
    """
    with pytest.raises(HTTPError) as exc:
        await http_client.fetch("/hook", method="POST", body=salt.utils.json.dumps({}))
    assert exc.value.code == 401


async def test_good_login(http_client, auth_creds, content_type_map, client_config):
    """
    Test logging in
    """
    response = await http_client.fetch(
        "/login",
        method="POST",
        body=urllib.parse.urlencode(auth_creds),
        headers={"Content-Type": content_type_map["form"]},
    )
    assert response.code == 200
    cookies = response.headers["Set-Cookie"]
    response_obj = salt.utils.json.loads(response.body)["return"][0]
    token = response_obj["token"]
    assert f"session_id={token}" in cookies
    perms = response_obj["perms"]
    perms_config = client_config["external_auth"]["auto"][auth_creds["username"]]
    assert set(perms) == set(perms_config)
    assert "token" in response_obj  # TODO: verify that its valid?
    assert response_obj["user"] == auth_creds["username"]
    assert response_obj["eauth"] == auth_creds["eauth"]


async def test_bad_login(http_client, content_type_map):
    """
    Test logging in
    """
    with pytest.raises(HTTPError) as exc:
        body = urllib.parse.urlencode({"totally": "invalid_creds"})
        await http_client.fetch(
            "/login",
            method="POST",
            body=body,
            headers={"Content-Type": content_type_map["form"]},
        )
    assert exc.value.code == 401


async def test_logout(http_client, auth_creds, content_type_map):
    response = await http_client.fetch(
        "/login",
        method="POST",
        body=urllib.parse.urlencode(auth_creds),
        headers={"Content-Type": content_type_map["form"]},
    )
    assert response.code == 200
    token = response.headers["X-Auth-Token"]

    body = urllib.parse.urlencode({})
    response = await http_client.fetch(
        "/logout",
        method="POST",
        body=body,
        headers={"content-type": content_type_map["form"], "X-Auth-Token": token},
    )
    assert response.code == 200
