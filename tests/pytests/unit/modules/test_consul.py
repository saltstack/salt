"""
Test case for the consul execution module
"""


import logging

import pytest
import salt.modules.consul as consul
import salt.utils.platform
from salt.exceptions import SaltInvocationError
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {
        consul: {
            "__opts__": {"consul": {"url": "http://127.0.0.1", "token": "test_token"}},
            "__grains__": {"id": "test-minion"},
        }
    }


def test_list():
    """
    Test salt.modules.consul.list function
    """
    mock_query = MagicMock(return_value={"data": ["foo"], "res": True})
    with patch.object(consul, "_query", mock_query):
        consul_return = consul.list_(consul_url="http://127.0.0.1", token="test_token")

    assert consul_return == {"data": ["foo"], "res": True}


def test_get():
    """
    Test salt.modules.consul.get function
    """
    #
    # No key argument results in SaltInvocationError, exception
    #
    with pytest.raises(SaltInvocationError):
        consul.put(consul_url="http://127.0.0.1", token="test_token")

    mock_query = MagicMock(
        return_value={
            "data": [
                {
                    "LockIndex": 0,
                    "Key": "foo",
                    "Flags": 0,
                    "Value": "YmFy",
                    "CreateIndex": 128,
                    "ModifyIndex": 128,
                },
            ],
            "res": True,
        }
    )
    with patch.object(consul, "_query", mock_query):
        consul_return = consul.get(
            consul_url="http://127.0.0.1", key="foo", token="test_token"
        )
    _expected = {
        "data": [
            {
                "CreateIndex": 128,
                "Flags": 0,
                "Key": "foo",
                "LockIndex": 0,
                "ModifyIndex": 128,
                "Value": "YmFy",
            }
        ],
        "res": True,
    }

    assert consul_return == _expected

    mock_query = MagicMock(
        return_value={
            "data": [
                {
                    "LockIndex": 0,
                    "Key": "foo",
                    "Flags": 0,
                    "Value": "b'bar'",
                    "CreateIndex": 128,
                    "ModifyIndex": 128,
                },
            ],
            "res": True,
        }
    )
    with patch.object(consul, "_query", mock_query):
        consul_return = consul.get(
            consul_url="http://127.0.0.1", key="foo", token="test_token"
        )
    _expected = {
        "data": [
            {
                "CreateIndex": 128,
                "Flags": 0,
                "Key": "foo",
                "LockIndex": 0,
                "ModifyIndex": 128,
                "Value": "b'bar'",
            }
        ],
        "res": True,
    }

    assert consul_return == _expected


def test_put():
    """
    Test salt.modules.consul.put function
    """
    #
    # No key argument results in SaltInvocationError, exception
    #
    with pytest.raises(SaltInvocationError):
        consul.put(consul_url="http://127.0.0.1", token="test_token")

    #
    # Test when we're unable to connect to Consul
    #
    mock_consul_get = {
        "data": [
            {
                "LockIndex": 0,
                "Key": "web/key1",
                "Flags": 0,
                "Value": "ImhlbGxvIHRoZXJlIg==",
                "CreateIndex": 299,
                "ModifyIndex": 299,
            }
        ],
        "res": True,
    }
    with patch.object(consul, "session_list", MagicMock(return_value=[])):
        with patch.object(consul, "get", MagicMock(return_value=mock_consul_get)):
            ret = consul.put(
                consul_url="http://127.0.0.1:8501",
                token="test_token",
                key="web/key1",
                value="Hello world",
            )
    expected_res = (False,)
    expected_data = "Unable to add key web/key1 with value Hello world."
    if salt.utils.platform.is_windows():
        expected_error = "Unknown error"
    else:
        expected_error = "Connection refused"
    assert not ret["res"]
    assert expected_data == ret["data"]
    assert expected_error in ret["error"]

    #
    # Working as expected
    #
    mock_query = MagicMock(
        return_value={
            "data": [
                {
                    "LockIndex": 0,
                    "Key": "foo",
                    "Flags": 0,
                    "Value": "YmFy",
                    "CreateIndex": 128,
                    "ModifyIndex": 128,
                },
            ],
            "res": True,
        }
    )
    with patch.object(consul, "session_list", MagicMock(return_value=[])):
        with patch.object(consul, "get", MagicMock(return_value=mock_consul_get)):
            with patch.object(consul, "_query", mock_query):
                ret = consul.put(
                    consul_url="http://127.0.0.1:8500",
                    token="test_token",
                    key="web/key1",
                    value="Hello world",
                )
    _expected = {"res": True, "data": "Added key web/key1 with value Hello world."}
    assert ret == _expected


def test_delete():
    """
    Test salt.modules.consul.delete function
    """
    #
    # No key argument results in SaltInvocationError, exception
    #
    with pytest.raises(SaltInvocationError):
        consul.put(consul_url="http://127.0.0.1", token="test_token")

    #
    # Test when we're unable to connect to Consul
    #
    ret = consul.delete(
        consul_url="http://127.0.0.1:8501",
        token="test_token",
        key="web/key1",
        value="Hello world",
    )
    expected_res = (False,)
    expected_data = "Unable to delete key web/key1."
    if salt.utils.platform.is_windows():
        expected_error = "Unknown error"
    else:
        expected_error = "Connection refused"
    assert not ret["res"]
    assert expected_data == ret["message"]
    assert expected_error in ret["error"]

    #
    # Working as expected
    #
    mock_query = MagicMock(return_value={"data": True, "res": True})
    with patch.object(consul, "_query", mock_query):
        ret = consul.delete(
            consul_url="http://127.0.0.1:8500",
            token="test_token",
            key="web/key1",
            value="Hello world",
        )
    _expected = {"res": True, "message": "Deleted key web/key1."}
    assert ret == _expected
