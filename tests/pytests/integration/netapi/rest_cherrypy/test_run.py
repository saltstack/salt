import urllib.parse

import pytest
from tornado.httpclient import HTTPError


@pytest.mark.netapi_client_data(["local"])
async def test_run_good_login(http_client, auth_creds):
    """
    Test the run URL with good auth credentials
    """
    low = {"client": "local", "tgt": "*", "fun": "test.ping", **auth_creds}
    body = urllib.parse.urlencode(low)

    response = await http_client.fetch("/run", method="POST", body=body)
    assert response.code == 200


async def test_run_netapi_client_not_set(http_client, auth_creds):
    """
    Test the run URL with good auth credentials
    """
    low = {"client": "local", "tgt": "*", "fun": "test.ping", **auth_creds}
    body = urllib.parse.urlencode(low)

    response = await http_client.fetch(
        "/run", method="POST", body=body, raise_error=False
    )
    assert response.code == 400
    assert (
        "Client disabled: 'local'. Add to 'netapi_enable_clients' master config option to enable"
        in response.body
    )


@pytest.mark.netapi_client_data(["local"])
async def test_run_bad_login(http_client):
    """
    Test the run URL with bad auth credentials
    """
    low = {
        "client": "local",
        "tgt": "*",
        "fun": "test.ping",
        **{"totally": "invalid_creds"},
    }
    body = urllib.parse.urlencode(low)
    with pytest.raises(HTTPError) as exc:
        await http_client.fetch(
            "/run",
            method="POST",
            body=body,
        )
    assert exc.value.code == 401


@pytest.mark.netapi_client_data(["local"])
async def test_run_empty_token(http_client):
    """
    Test the run URL with empty token
    """
    low = {"client": "local", "tgt": "*", "fun": "test.ping", **{"token": ""}}
    body = urllib.parse.urlencode(low)
    with pytest.raises(HTTPError) as exc:
        await http_client.fetch(
            "/run",
            method="POST",
            body=body,
        )
    assert exc.value.code == 401


@pytest.mark.netapi_client_data(["local"])
async def test_run_empty_token_upercase(http_client):
    """
    Test the run URL with empty token with upercase characters
    """
    low = {"client": "local", "tgt": "*", "fun": "test.ping", **{"ToKen": ""}}
    body = urllib.parse.urlencode(low)
    with pytest.raises(HTTPError) as exc:
        await http_client.fetch(
            "/run",
            method="POST",
            body=body,
        )
    assert exc.value.code == 401


@pytest.mark.netapi_client_data(["local"])
async def test_run_wrong_token(http_client):
    """
    Test the run URL with incorrect token
    """
    low = {"client": "local", "tgt": "*", "fun": "test.ping", **{"token": "bad"}}
    body = urllib.parse.urlencode(low)
    with pytest.raises(HTTPError) as exc:
        await http_client.fetch(
            "/run",
            method="POST",
            body=body,
        )
    assert exc.value.code == 401


@pytest.mark.netapi_client_data(["local"])
async def test_run_pathname_token(http_client):
    """
    Test the run URL with path that exists in token
    """
    low = {
        "client": "local",
        "tgt": "*",
        "fun": "test.ping",
        **{"token": "/etc/passwd"},
    }
    body = urllib.parse.urlencode(low)
    with pytest.raises(HTTPError) as exc:
        await http_client.fetch(
            "/run",
            method="POST",
            body=body,
        )
    assert exc.value.code == 401


@pytest.mark.netapi_client_data(["local"])
async def test_run_pathname_not_exists_token(http_client):
    """
    Test the run URL with path that does not exist in token
    """
    low = {
        "client": "local",
        "tgt": "*",
        "fun": "test.ping",
        **{"token": "/tmp/does-not-exist"},
    }
    body = urllib.parse.urlencode(low)
    with pytest.raises(HTTPError) as exc:
        await http_client.fetch(
            "/run",
            method="POST",
            body=body,
        )
    assert exc.value.code == 401


@pytest.mark.slow_test
@pytest.mark.netapi_client_data(["local"])
async def test_run_extra_parameters(http_client, auth_creds):
    """
    Test the run URL with good auth credentials
    """
    low = {"client": "local", "tgt": "*", "fun": "test.ping", **auth_creds}
    low["id_"] = "some-minion-name"
    body = urllib.parse.urlencode(low)

    response = await http_client.fetch("/run", method="POST", body=body)
    assert response.code == 200
