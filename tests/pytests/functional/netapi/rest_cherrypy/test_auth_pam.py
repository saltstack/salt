import urllib.parse

import pytest
from tornado.httpclient import HTTPError

pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
]


@pytest.fixture
def auth_creds(auth_creds):
    auth_creds["eauth"] = "pam"
    return auth_creds


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
