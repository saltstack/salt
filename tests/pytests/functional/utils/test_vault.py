import logging

import pytest
import requests.exceptions

# pylint: disable=unused-import
from tests.support.pytest.vault import (
    vault_container_version,
    vault_delete_secret,
    vault_environ,
    vault_list_secrets,
    vault_read_secret,
    vault_write_secret,
)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd", "vault", "getent"),
]

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def minion_config_overrides(vault_port):
    return {
        "vault": {
            "auth": {
                "method": "token",
                "token": "testsecret",
            },
            "server": {
                "url": f"http://127.0.0.1:{vault_port}",
            },
        }
    }


@pytest.fixture
def vault(loaders):
    return loaders.utils.vault


@pytest.fixture(scope="module", autouse=True)
def vault_testing_data(vault_container_version):
    vault_write_secret("secret/utils/read", success="yup")
    vault_write_secret("secret/utils/deleteme", success="nope")
    try:
        yield
    finally:
        secret_path = "secret/utils"
        for secret in vault_list_secrets(secret_path):
            vault_delete_secret(f"{secret_path}/{secret}", metadata=True)


def test_make_request_get_unauthd(vault):
    """
    Test that unauthenticated GET requests are possible
    """
    res = vault.make_request("GET", "/v1/sys/health")
    assert res.status_code == 200
    assert res.json()
    assert "initialized" in res.json()


def test_make_request_get_authd(vault, vault_container_version):
    """
    Test that authenticated GET requests are possible
    """
    endpoint = "secret/utils/read"
    if vault_container_version in ["1.3.1", "latest"]:
        endpoint = "secret/data/utils/read"

    res = vault.make_request("GET", f"/v1/{endpoint}")
    assert res.status_code == 200
    data = res.json()["data"]
    if vault_container_version in ["1.3.1", "latest"]:
        data = data["data"]
    assert "success" in data
    assert data["success"] == "yup"


def test_make_request_post_json(vault, vault_container_version):
    """
    Test that POST requests are possible with json param
    """
    data = {"success": "yup"}
    endpoint = "secret/utils/write"

    if vault_container_version in ["1.3.1", "latest"]:
        data = {"data": data}
        endpoint = "secret/data/utils/write"
    res = vault.make_request("POST", f"/v1/{endpoint}", json=data)
    assert res.status_code in [200, 204]
    assert vault_read_secret("secret/utils/write") == {"success": "yup"}


def test_make_request_post_data(vault, vault_container_version):
    """
    Test that POST requests are possible with data param
    """
    data = '{"success": "yup_data"}'
    endpoint = "secret/utils/write"

    if vault_container_version in ["1.3.1", "latest"]:
        data = '{"data": {"success": "yup_data"}}'
        endpoint = "secret/data/utils/write"
    res = vault.make_request("POST", f"/v1/{endpoint}", data=data)
    assert res.status_code in [200, 204]
    assert vault_read_secret("secret/utils/write") == {"success": "yup_data"}


def test_make_request_delete(vault, vault_container_version):
    """
    Test that DELETE requests are possible
    """
    endpoint = "secret/utils/deleteme"
    if vault_container_version in ["1.3.1", "latest"]:
        endpoint = "secret/data/utils/deleteme"

    res = vault.make_request("DELETE", f"/v1/{endpoint}")
    assert res.status_code in [200, 204]
    assert vault_read_secret("secret/utils/deleteme") is None


def test_make_request_list(vault, vault_container_version):
    """
    Test that LIST requests are possible
    """
    endpoint = "secret/utils"
    if vault_container_version in ["1.3.1", "latest"]:
        endpoint = "secret/metadata/utils"

    res = vault.make_request("LIST", f"/v1/{endpoint}")
    assert res.status_code == 200
    assert res.json()["data"]["keys"] == vault_list_secrets("secret/utils")


def test_make_request_token_override(vault, vault_container_version):
    """
    Test that overriding the token in use is possible
    """
    endpoint = "secret/utils/read"
    if vault_container_version in ["1.3.1", "latest"]:
        endpoint = "secret/data/utils/read"

    res = vault.make_request("GET", f"/v1/{endpoint}", token="invalid")
    assert res.status_code == 403


def test_make_request_url_override(vault, vault_container_version):
    """
    Test that overriding the server URL is possible
    """
    endpoint = "secret/utils/read"
    if vault_container_version in ["1.3.1", "latest"]:
        endpoint = "secret/data/utils/read"

    with pytest.raises(
        requests.exceptions.ConnectionError, match=".*Max retries exceeded with url:.*"
    ):
        vault.make_request(
            "GET", f"/v1/{endpoint}", vault_url="http://127.0.0.1:1", timeout=2
        )
