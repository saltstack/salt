import pytest

import salt.auth.rest as rest
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    """
    Rest module configuration
    """
    return {
        rest: {
            "__opts__": {
                "external_auth": {
                    "rest": {"^url": "https://test_url/rest", "fred": [".*", "@runner"]}
                }
            }
        }
    }


def test_rest_auth_config():
    ret = rest._rest_auth_setup()
    assert ret == "https://test_url/rest"


def test_fetch_call_failed():
    with patch("salt.utils.http.query", MagicMock(return_value={"status": 401})):
        ret = rest.fetch("foo", None)
        assert ret is False


def test_fetch_call_success_dict_none():
    with patch(
        "salt.utils.http.query", MagicMock(return_value={"status": 200, "dict": None})
    ):
        ret = rest.fetch("foo", None)
        assert ret == []


def test_fetch_call_success_dict_acl():
    with patch(
        "salt.utils.http.query",
        MagicMock(return_value={"status": 200, "dict": {"foo": ["@wheel"]}}),
    ):
        ret = rest.fetch("foo", None)
        assert ret == {"foo": ["@wheel"]}


def test_auth_nopass():
    ret = rest.auth("foo", None)
    assert ret is False


def test_auth_nouser():
    ret = rest.auth(None, "foo")
    assert ret is False


def test_auth_nouserandpass():
    ret = rest.auth(None, None)
    assert ret is False


def test_auth_ok():
    with patch(
        "salt.utils.http.query",
        MagicMock(return_value={"status": 200, "dict": ["@wheel"]}),
    ):
        ret = rest.auth("foo", None)
        assert ret is True


def test_acl_without_merge():
    ret = rest.acl("fred", password="password")
    assert ret == [".*", "@runner"]


def test_acl_unauthorized():
    with patch("salt.utils.http.query", MagicMock(return_value={"status": 400})):
        ret = rest.acl("foo", password="password")
        assert ret is None


def test_acl_no_merge():
    with patch(
        "salt.utils.http.query", MagicMock(return_value={"status": 200, "dict": None})
    ):
        ret = rest.acl("fred", password="password")
        assert ret == [".*", "@runner"]


def test_acl_merge():
    with patch(
        "salt.utils.http.query",
        MagicMock(return_value={"status": 200, "dict": ["@wheel"]}),
    ):
        ret = rest.acl("fred", password="password")
        assert ret == [".*", "@runner", "@wheel"]
