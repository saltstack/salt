import urllib.parse

import pytest

import salt.utils.json
import salt.utils.yaml
from tests.support.mock import patch

pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
]


@pytest.fixture
def app(app):
    app.wsgi_application.config["global"]["tools.hypermedia_in.on"] = True
    return app


@pytest.fixture
def token(http_client, auth_creds, content_type_map, io_loop):
    response = io_loop.run_sync(
        lambda: http_client.fetch(
            "/login",
            method="POST",
            body=urllib.parse.urlencode(auth_creds),
            headers={"Content-Type": content_type_map["form"]},
        )
    )
    assert response.code == 200
    return response.headers["X-Auth-Token"]


@pytest.fixture
def client_headers(token, content_type_map):
    return {
        "Accept": content_type_map["json"],
        "X-Auth-Token": token,
        "Content-Type": content_type_map["form"],
    }


async def test_urlencoded_ctype(http_client, client_headers, content_type_map):
    low = {"client": "local", "fun": "test.ping", "tgt": "jerry"}
    body = urllib.parse.urlencode(low)
    client_headers["Content-Type"] = content_type_map["form"]

    with patch(
        "salt.client.LocalClient.run_job",
        return_value={"jid": "20131219215650131543", "minions": ["jerry"]},
    ):
        # We don't really want to run the job, hence the patch
        response = await http_client.fetch(
            "/", method="POST", body=body, headers=client_headers
        )
    assert response.code == 200
    assert response.body == '{"return": [{"jerry": false}]}'


async def test_json_ctype(http_client, client_headers, content_type_map):
    low = {"client": "local", "fun": "test.ping", "tgt": "jerry"}
    body = salt.utils.json.dumps(low)
    client_headers["Content-Type"] = content_type_map["json"]

    with patch(
        "salt.client.LocalClient.run_job",
        return_value={"jid": "20131219215650131543", "minions": ["jerry"]},
    ):
        # We don't really want to run the job, hence the patch
        response = await http_client.fetch(
            "/", method="POST", body=body, headers=client_headers
        )
    assert response.code == 200
    assert response.body == '{"return": [{"jerry": false}]}'


async def test_json_as_text_out(http_client, client_headers):
    """
    Some service send JSON as text/plain for compatibility purposes
    """
    low = {"client": "local", "fun": "test.ping", "tgt": "jerry"}
    body = salt.utils.json.dumps(low)
    client_headers["Content-Type"] = "text/plain"

    with patch(
        "salt.client.LocalClient.run_job",
        return_value={"jid": "20131219215650131543", "minions": ["jerry"]},
    ):
        # We don't really want to run the job, hence the patch
        response = await http_client.fetch(
            "/", method="POST", body=body, headers=client_headers
        )
    assert response.code == 200
    assert response.body == '{"return": [{"jerry": false}]}'


async def test_yaml_ctype(http_client, client_headers, content_type_map):
    low = {"client": "local", "fun": "test.ping", "tgt": "jerry"}
    body = salt.utils.yaml.safe_dump(low)
    client_headers["Content-Type"] = content_type_map["yaml"]

    with patch(
        "salt.client.LocalClient.run_job",
        return_value={"jid": "20131219215650131543", "minions": ["jerry"]},
    ):
        # We don't really want to run the job, hence the patch
        response = await http_client.fetch(
            "/", method="POST", body=body, headers=client_headers
        )
    assert response.code == 200
    assert response.body == '{"return": [{"jerry": false}]}'
