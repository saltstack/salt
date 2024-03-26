import urllib.parse

import pytest

import salt.utils.json
import salt.utils.yaml
from salt.ext.tornado.httpclient import HTTPError
from salt.netapi.rest_tornado import saltnado

pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
]


@pytest.fixture
def app_urls():
    return [
        ("/login", saltnado.SaltAuthHandler),
    ]


async def test_get(http_client):
    """
    We don't allow gets, so assert we get 401s
    """
    with pytest.raises(HTTPError) as exc:
        await http_client.fetch("/login")
    assert exc.value.code == 401


async def test_login(
    http_client, content_type_map, auth_creds, subtests, client_config
):
    """
    Test valid logins
    """
    with subtests.test("Test in form encoded"):
        response = await http_client.fetch(
            "/login",
            method="POST",
            body=urllib.parse.urlencode(auth_creds),
            headers={"Content-Type": content_type_map["form"]},
        )

        cookies = response.headers["Set-Cookie"]
        assert response.code == 200
        response_obj = salt.utils.json.loads(response.body)["return"][0]
        token = response_obj["token"]
        assert f"session_id={token}" in cookies
        perms = response_obj["perms"]
        perms_config = client_config["external_auth"]["auto"][auth_creds["username"]]
        assert set(perms) == set(perms_config)
        assert "token" in response_obj  # TODO: verify that its valid?
        assert response_obj["user"] == auth_creds["username"]
        assert response_obj["eauth"] == auth_creds["eauth"]

    with subtests.test("Test in JSON"):
        response = await http_client.fetch(
            "/login",
            method="POST",
            body=salt.utils.json.dumps(auth_creds),
            headers={"Content-Type": content_type_map["json"]},
        )

        cookies = response.headers["Set-Cookie"]
        assert response.code == 200
        response_obj = salt.utils.json.loads(response.body)["return"][0]
        token = response_obj["token"]
        assert f"session_id={token}" in cookies
        perms = response_obj["perms"]
        perms_config = client_config["external_auth"]["auto"][auth_creds["username"]]
        assert set(perms) == set(perms_config)
        assert "token" in response_obj  # TODO: verify that its valid?
        assert response_obj["user"] == auth_creds["username"]
        assert response_obj["eauth"] == auth_creds["eauth"]

    with subtests.test("Test in YAML"):
        response = await http_client.fetch(
            "/login",
            method="POST",
            body=salt.utils.yaml.safe_dump(auth_creds),
            headers={"Content-Type": content_type_map["yaml"]},
        )

        cookies = response.headers["Set-Cookie"]
        assert response.code == 200
        response_obj = salt.utils.json.loads(response.body)["return"][0]
        token = response_obj["token"]
        assert f"session_id={token}" in cookies
        perms = response_obj["perms"]
        perms_config = client_config["external_auth"]["auto"][auth_creds["username"]]
        assert set(perms) == set(perms_config)
        assert "token" in response_obj  # TODO: verify that its valid?
        assert response_obj["user"] == auth_creds["username"]
        assert response_obj["eauth"] == auth_creds["eauth"]


async def test_login_missing_password(http_client, auth_creds, content_type_map):
    """
    Test logins with bad/missing passwords
    """
    bad_creds = []
    for key, val in auth_creds.items():
        if key == "password":
            continue
        bad_creds.append((key, val))
    with pytest.raises(HTTPError) as exc:
        await http_client.fetch(
            "/login",
            method="POST",
            body=urllib.parse.urlencode(bad_creds),
            headers={"Content-Type": content_type_map["form"]},
        )

    assert exc.value.code == 400


async def test_login_bad_creds(http_client, content_type_map, auth_creds):
    """
    Test logins with bad/missing passwords
    """
    bad_creds = []
    for key, val in auth_creds.items():
        if key == "username":
            val = val + "foo"
        if key == "eauth":
            val = "sharedsecret"
        bad_creds.append((key, val))

    with pytest.raises(HTTPError) as exc:
        await http_client.fetch(
            "/login",
            method="POST",
            body=urllib.parse.urlencode(bad_creds),
            headers={"Content-Type": content_type_map["form"]},
        )

    assert exc.value.code == 401


async def test_login_invalid_data_structure(http_client, content_type_map, auth_creds):
    """
    Test logins with either list or string JSON payload
    """
    with pytest.raises(HTTPError) as exc:
        await http_client.fetch(
            "/login",
            method="POST",
            body=salt.utils.json.dumps(auth_creds),
            headers={"Content-Type": content_type_map["form"]},
        )

    assert exc.value.code == 400

    with pytest.raises(HTTPError) as exc:
        await http_client.fetch(
            "/login",
            method="POST",
            body=salt.utils.json.dumps(42),
            headers={"Content-Type": content_type_map["form"]},
        )

    assert exc.value.code == 400

    with pytest.raises(HTTPError) as exc:
        await http_client.fetch(
            "/login",
            method="POST",
            body=salt.utils.json.dumps("mystring42"),
            headers={"Content-Type": content_type_map["form"]},
        )

    assert exc.value.code == 400
