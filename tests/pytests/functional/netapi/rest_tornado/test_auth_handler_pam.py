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
def auth_creds(auth_creds):
    auth_creds["eauth"] = "pam"
    return auth_creds


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
    Test valid logins, service ``auto``
    """
    eauth = auth_creds["eauth"]
    username = auth_creds["username"]
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
        perms_config = client_config["external_auth"][eauth][username]
        assert set(perms) == set(perms_config)
        assert "token" in response_obj  # TODO: verify that its valid?
        assert response_obj["user"] == username
        assert response_obj["eauth"] == eauth

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
        perms_config = client_config["external_auth"][eauth][username]
        assert set(perms) == set(perms_config)
        assert "token" in response_obj  # TODO: verify that its valid?
        assert response_obj["user"] == username
        assert response_obj["eauth"] == eauth

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
        perms_config = client_config["external_auth"][eauth][username]
        assert set(perms) == set(perms_config)
        assert "token" in response_obj  # TODO: verify that its valid?
        assert response_obj["user"] == username
        assert response_obj["eauth"] == eauth


@pytest.mark.parametrize("service", ["chsh", "login"])
async def test_bad_pwd_pam_chsh_service(
    http_client, auth_creds, content_type_map, service
):
    """
    Test login while specifying `chsh` or `login` service with bad passwd
    This test ensures this PR is working correctly:
    https://github.com/saltstack/salt/pull/31826
    """
    auth_creds["service"] = service
    auth_creds["password"] = "wrong_password"
    with pytest.raises(HTTPError) as exc:
        await http_client.fetch(
            "/login",
            method="POST",
            body=urllib.parse.urlencode(auth_creds),
            headers={"Content-Type": content_type_map["form"]},
        )
    assert exc.value.code == 401


@pytest.mark.parametrize("service", ["chsh", "login"])
async def test_good_pwd_pam_chsh_service(
    http_client, auth_creds, content_type_map, service
):
    """
    Test login while specifying `chsh` and `login` service with good passwd
    This test ensures this PR is working correctly:
    https://github.com/saltstack/salt/pull/31826
    """
    auth_creds["service"] = service
    response = await http_client.fetch(
        "/login",
        method="POST",
        body=urllib.parse.urlencode(auth_creds),
        headers={"Content-Type": content_type_map["form"]},
    )
    assert response.code == 200
