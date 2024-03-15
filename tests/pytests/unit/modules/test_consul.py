"""
Test case for the consul execution module
"""

import logging

import pytest

import salt.modules.consul as consul
import salt.utils.http
import salt.utils.json
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


def test_agent_maintenance():
    """
    Test consul agent maintenance
    """
    consul_url = "http://localhost:1313"
    key = "cluster/key"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        with patch.object(
            salt.modules.consul, "session_list", return_value=mock_result
        ):
            result = consul.agent_maintenance(consul_url="")
            expected = {"message": "No Consul URL found.", "res": False}
            assert expected == result

    # no required argument
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = 'Required parameter "enable" is missing.'
                result = consul.agent_maintenance(consul_url=consul_url)
                expected = {"message": msg, "res": False}
                assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Agent maintenance mode {}ed."
                value = "enabl"
                result = consul.agent_maintenance(consul_url=consul_url, enable=value)
                expected = {"message": msg.format(value), "res": True}
                assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result_false):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Unable to change maintenance mode for agent."
                value = "enabl"
                result = consul.agent_maintenance(consul_url=consul_url, enable=value)
                expected = {"message": msg, "res": True}
                assert expected == result


def test_agent_join():
    """
    Test consul agent join
    """
    consul_url = "http://localhost:1313"
    key = "cluster/key"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        with patch.object(
            salt.modules.consul, "session_list", return_value=mock_result
        ):
            result = consul.agent_join(consul_url="")
            expected = {"message": "No Consul URL found.", "res": False}
            assert expected == result

    # no required argument
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = 'Required parameter "address" is missing.'
                pytest.raises(
                    SaltInvocationError, consul.agent_join, consul_url=consul_url
                )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Agent joined the cluster"
                result = consul.agent_join(consul_url=consul_url, address="test")
                expected = {"message": msg, "res": True}
                assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result_false):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Unable to join the cluster."
                value = "enabl"
                result = consul.agent_join(consul_url=consul_url, address="test")
                expected = {"message": msg, "res": False}
                assert expected == result


def test_agent_leave():
    """
    Test consul agent leave
    """
    consul_url = "http://localhost:1313"
    key = "cluster/key"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        with patch.object(
            salt.modules.consul, "session_list", return_value=mock_result
        ):
            result = consul.agent_join(consul_url="")
            expected = {"message": "No Consul URL found.", "res": False}
            assert expected == result

    node = "node1"

    # no required argument
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                pytest.raises(
                    SaltInvocationError, consul.agent_leave, consul_url=consul_url
                )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Node {} put in leave state."
                result = consul.agent_leave(consul_url=consul_url, node=node)
                expected = {"message": msg.format(node), "res": True}
                assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result_false):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Unable to change state for {}."
                result = consul.agent_leave(consul_url=consul_url, node=node)
                expected = {"message": msg.format(node), "res": False}
                assert expected == result


def test_agent_check_register():
    """
    Test consul agent check register
    """
    consul_url = "http://localhost:1313"
    key = "cluster/key"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        with patch.object(
            salt.modules.consul, "session_list", return_value=mock_result
        ):
            result = consul.agent_check_register(consul_url="")
            expected = {"message": "No Consul URL found.", "res": False}
            assert expected == result

    name = "name1"

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                pytest.raises(
                    SaltInvocationError,
                    consul.agent_check_register,
                    consul_url=consul_url,
                )

                # missing script, or http
                msg = 'Required parameter "script" or "http" is missing.'
                result = consul.agent_check_register(consul_url=consul_url, name=name)
                expected = {"message": msg, "res": False}
                assert expected == result

                # missing interval
                msg = 'Required parameter "interval" is missing.'
                result = consul.agent_check_register(
                    consul_url=consul_url,
                    name=name,
                    script="test",
                    http="test",
                    ttl="test",
                )
                expected = {"message": msg, "res": False}
                assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Check {} added to agent."
                result = consul.agent_check_register(
                    consul_url=consul_url,
                    name=name,
                    script="test",
                    http="test",
                    ttl="test",
                    interval="test",
                )
                expected = {"message": msg.format(name), "res": True}
                assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result_false):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Unable to add check to agent."
                result = consul.agent_check_register(
                    consul_url=consul_url,
                    name=name,
                    script="test",
                    http="test",
                    ttl="test",
                    interval="test",
                )
                expected = {"message": msg.format(name), "res": False}
                assert expected == result


def test_agent_check_deregister():
    """
    Test consul agent check register
    """
    consul_url = "http://localhost:1313"
    key = "cluster/key"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        with patch.object(
            salt.modules.consul, "session_list", return_value=mock_result
        ):
            result = consul.agent_check_register(consul_url="")
            expected = {"message": "No Consul URL found.", "res": False}
            assert expected == result

    checkid = "id1"

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                pytest.raises(
                    SaltInvocationError,
                    consul.agent_check_deregister,
                    consul_url=consul_url,
                )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Check {} removed from agent."
                result = consul.agent_check_deregister(
                    consul_url=consul_url, checkid=checkid
                )
                expected = {"message": msg.format(checkid), "res": True}
                assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result_false):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Unable to remove check from agent."
                result = consul.agent_check_deregister(
                    consul_url=consul_url, checkid=checkid
                )
                expected = {"message": msg.format(checkid), "res": False}
                assert expected == result


def test_agent_check_pass():
    """
    Test consul agent check pass
    """
    consul_url = "http://localhost:1313"
    key = "cluster/key"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        with patch.object(
            salt.modules.consul, "session_list", return_value=mock_result
        ):
            result = consul.agent_check_register(consul_url="")
            expected = {"message": "No Consul URL found.", "res": False}
            assert expected == result

    checkid = "id1"

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                pytest.raises(
                    SaltInvocationError,
                    consul.agent_check_pass,
                    consul_url=consul_url,
                )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Check {} marked as passing."
                result = consul.agent_check_pass(consul_url=consul_url, checkid=checkid)
                expected = {"message": msg.format(checkid), "res": True}
                assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result_false):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Unable to update check {}."
                result = consul.agent_check_pass(consul_url=consul_url, checkid=checkid)
                expected = {"message": msg.format(checkid), "res": False}
                assert expected == result


def test_agent_check_warn():
    """
    Test consul agent check warn
    """
    consul_url = "http://localhost:1313"
    key = "cluster/key"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        with patch.object(
            salt.modules.consul, "session_list", return_value=mock_result
        ):
            result = consul.agent_check_register(consul_url="")
            expected = {"message": "No Consul URL found.", "res": False}
            assert expected == result

    checkid = "id1"

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                pytest.raises(
                    SaltInvocationError,
                    consul.agent_check_warn,
                    consul_url=consul_url,
                )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Check {} marked as warning."
                result = consul.agent_check_warn(consul_url=consul_url, checkid=checkid)
                expected = {"message": msg.format(checkid), "res": True}
                assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result_false):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Unable to update check {}."
                result = consul.agent_check_warn(consul_url=consul_url, checkid=checkid)
                expected = {"message": msg.format(checkid), "res": False}
                assert expected == result


def test_agent_check_fail():
    """
    Test consul agent check warn
    """
    consul_url = "http://localhost:1313"
    key = "cluster/key"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        with patch.object(
            salt.modules.consul, "session_list", return_value=mock_result
        ):
            result = consul.agent_check_register(consul_url="")
            expected = {"message": "No Consul URL found.", "res": False}
            assert expected == result

    checkid = "id1"

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                pytest.raises(
                    SaltInvocationError,
                    consul.agent_check_fail,
                    consul_url=consul_url,
                )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Check {} marked as critical."
                result = consul.agent_check_fail(consul_url=consul_url, checkid=checkid)
                expected = {"message": msg.format(checkid), "res": True}
                assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result_false):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Unable to update check {}."
                result = consul.agent_check_fail(consul_url=consul_url, checkid=checkid)
                expected = {"message": msg.format(checkid), "res": False}
                assert expected == result


def test_agent_service_register():
    """
    Test consul agent service register
    """
    consul_url = "http://localhost:1313"
    key = "cluster/key"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        with patch.object(
            salt.modules.consul, "session_list", return_value=mock_result
        ):
            result = consul.agent_service_register(consul_url="")
            expected = {"message": "No Consul URL found.", "res": False}
            assert expected == result

    name = "name1"

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                pytest.raises(
                    SaltInvocationError,
                    consul.agent_service_register,
                    consul_url=consul_url,
                )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Service {} registered on agent."
                result = consul.agent_service_register(
                    consul_url=consul_url,
                    name=name,
                    script="test",
                    http="test",
                    ttl="test",
                    interval="test",
                )
                expected = {"message": msg.format(name), "res": True}
                assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result_false):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Unable to register service {}."
                result = consul.agent_service_register(
                    consul_url=consul_url,
                    name=name,
                    script="test",
                    http="test",
                    ttl="test",
                    interval="test",
                )
                expected = {"message": msg.format(name), "res": False}
                assert expected == result


def test_agent_service_deregister():
    """
    Test consul agent service deregister
    """
    consul_url = "http://localhost:1313"
    key = "cluster/key"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        with patch.object(
            salt.modules.consul, "session_list", return_value=mock_result
        ):
            result = consul.agent_service_deregister(consul_url="")
            expected = {"message": "No Consul URL found.", "res": False}
            assert expected == result

    serviceid = "sid1"

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                pytest.raises(
                    SaltInvocationError,
                    consul.agent_service_deregister,
                    consul_url=consul_url,
                )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Service {} removed from agent."
                result = consul.agent_service_deregister(
                    consul_url=consul_url, serviceid=serviceid
                )
                expected = {"message": msg.format(serviceid), "res": True}
                assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result_false):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Unable to remove service {}."
                result = consul.agent_service_deregister(
                    consul_url=consul_url, serviceid=serviceid
                )
                expected = {"message": msg.format(serviceid), "res": False}
                assert expected == result


def test_agent_service_maintenance():
    """
    Test consul agent service maintenance
    """
    consul_url = "http://localhost:1313"
    key = "cluster/key"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        with patch.object(
            salt.modules.consul, "session_list", return_value=mock_result
        ):
            result = consul.agent_service_maintenance(consul_url="")
            expected = {"message": "No Consul URL found.", "res": False}
            assert expected == result

    serviceid = "sid1"

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                pytest.raises(
                    SaltInvocationError,
                    consul.agent_service_maintenance,
                    consul_url=consul_url,
                )

                # missing enable
                msg = 'Required parameter "enable" is missing.'
                result = consul.agent_service_maintenance(
                    consul_url=consul_url, serviceid=serviceid
                )
                expected = {"message": msg, "res": False}
                assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Service {} set in maintenance mode."
                result = consul.agent_service_maintenance(
                    consul_url=consul_url, serviceid=serviceid, enable=True
                )
                expected = {"message": msg.format(serviceid), "res": True}
                assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result_false):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Unable to set service {} to maintenance mode."
                result = consul.agent_service_maintenance(
                    consul_url=consul_url, serviceid=serviceid, enable=True
                )
                expected = {"message": msg.format(serviceid), "res": False}
                assert expected == result


def test_session_create():
    """
    Test consul session create
    """
    consul_url = "http://localhost:1313"
    key = "cluster/key"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        with patch.object(
            salt.modules.consul, "session_list", return_value=mock_result
        ):
            result = consul.session_create(consul_url="")
            expected = {"message": "No Consul URL found.", "res": False}
            assert expected == result

    name = "name1"

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                pytest.raises(
                    SaltInvocationError,
                    consul.session_create,
                    consul_url=consul_url,
                )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Created session {}."
                result = consul.session_create(consul_url=consul_url, name=name)
                expected = {"message": msg.format(name), "res": True}
                assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result_false):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            with patch.object(
                salt.modules.consul, "session_list", return_value=mock_result
            ):
                msg = "Unable to create session {}."
                result = consul.session_create(consul_url=consul_url, name=name)
                expected = {"message": msg.format(name), "res": False}
                assert expected == result


def test_session_list():
    """
    Test consul session list
    """
    consul_url = "http://localhost:1313"
    key = "cluster/key"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.session_list(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.session_list(consul_url=consul_url)
            expected = {"data": "test", "res": True}
            assert expected == result


def test_session_destroy():
    """
    Test consul session destroy
    """
    consul_url = "http://localhost:1313"
    key = "cluster/key"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    session = "sid1"
    name = "test"

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.session_destroy(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            pytest.raises(
                SaltInvocationError,
                consul.session_destroy,
                consul_url=consul_url,
            )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            msg = "Destroyed Session {}."
            result = consul.session_destroy(
                consul_url=consul_url, session=session, name="test"
            )
            expected = {"message": msg.format(session), "res": True}
            assert expected == result


def test_session_info():
    """
    Test consul session info
    """
    consul_url = "http://localhost:1313"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    session = "sid1"

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.session_info(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            pytest.raises(
                SaltInvocationError,
                consul.session_info,
                consul_url=consul_url,
            )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.session_info(consul_url=consul_url, session=session)
            expected = {"data": "test", "res": True}
            assert expected == result


def test_catalog_register():
    """
    Test consul catalog register
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"
    node = "node1"
    address = "addres1"
    nodemeta = {
        "Cpu": "blah",
        "Cpu_num": "8",
        "Memory": "1024",
        "Os": "rhel8",
        "Osarch": "x86_64",
        "Kernel": "foo.bar",
        "Kernelrelease": "foo.release",
        "localhost": "localhost",
        "nodename": node,
        "os_family": "adams",
        "lsb_distrib_description": "distro",
        "master": "master",
    }
    nodemeta_kwargs = {
        "cpu": "blah",
        "num_cpus": "8",
        "mem": "1024",
        "oscode": "rhel8",
        "osarch": "x86_64",
        "kernel": "foo.bar",
        "kernelrelease": "foo.release",
        "localhost": "localhost",
        "nodename": node,
        "os_family": "adams",
        "lsb_distrib_description": "distro",
        "master": "master",
    }

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.catalog_register(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.catalog_register(consul_url=consul_url, token=token)
            expected = {
                "message": "Required argument node argument is missing.",
                "res": False,
            }
            assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.catalog_register(
                consul_url=consul_url,
                token=token,
                node=node,
                address=address,
                **nodemeta_kwargs,
            )
            expected = {
                "data": {"Address": address, "Node": node, "NodeMeta": nodemeta},
                "message": f"Catalog registration for {node} successful.",
                "res": True,
            }

            assert expected == result


def test_catalog_deregister():
    """
    Test consul catalog deregister
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"
    node = "node1"
    address = "addres1"
    serviceid = "server1"
    checkid = "check1"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.catalog_deregister(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.catalog_deregister(consul_url=consul_url, token=token)
            expected = {"message": "Node argument required.", "res": False}
            assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.catalog_deregister(
                consul_url=consul_url,
                token=token,
                node=node,
                serviceid=serviceid,
                checkid=checkid,
            )
            expected = {
                "message": f"Catalog item {node} removed.",
                "res": True,
            }

            assert expected == result


def test_catalog_datacenters():
    """
    Test consul catalog datacenters
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.catalog_datacenters(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.catalog_datacenters(consul_url=consul_url, token=token)
            expected = {"data": "test", "res": True}
            assert expected == result


def test_catalog_nodes():
    """
    Test consul catalog nodes
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.catalog_nodes(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.catalog_nodes(consul_url=consul_url, token=token)
            expected = {"data": "test", "res": True}
            assert expected == result


def test_catalog_services():
    """
    Test consul catalog services
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.catalog_services(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.catalog_services(consul_url=consul_url, token=token)
            expected = {"data": "test", "res": True}
            assert expected == result


def test_catalog_service():
    """
    Test consul catalog service
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"
    service = "service"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.catalog_service(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            pytest.raises(
                SaltInvocationError,
                consul.catalog_service,
                consul_url=consul_url,
            )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.catalog_service(
                consul_url=consul_url, token=token, service=service
            )
            expected = {"data": "test", "res": True}
            assert expected == result


def test_catalog_node():
    """
    Test consul catalog node
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"
    node = "node"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.catalog_node(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            pytest.raises(
                SaltInvocationError,
                consul.catalog_node,
                consul_url=consul_url,
            )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.catalog_node(consul_url=consul_url, token=token, node=node)
            expected = {"data": "test", "res": True}
            assert expected == result


def test_health_node():
    """
    Test consul health node
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"
    node = "node"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.health_node(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            pytest.raises(
                SaltInvocationError,
                consul.health_node,
                consul_url=consul_url,
            )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.health_node(consul_url=consul_url, token=token, node=node)
            expected = {"data": "test", "res": True}
            assert expected == result


def test_health_checks():
    """
    Test consul health checks
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"
    service = "service"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.health_checks(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            pytest.raises(
                SaltInvocationError,
                consul.health_checks,
                consul_url=consul_url,
            )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.health_checks(
                consul_url=consul_url, token=token, service=service
            )
            expected = {"data": "test", "res": True}
            assert expected == result


def test_health_service():
    """
    Test consul health service
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"
    service = "service"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.health_service(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            pytest.raises(
                SaltInvocationError,
                consul.health_service,
                consul_url=consul_url,
            )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.health_service(
                consul_url=consul_url, token=token, service=service
            )
            expected = {"data": "test", "res": True}
            assert expected == result


def test_health_state():
    """
    Test consul health state
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"
    state = "state"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.health_state(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            pytest.raises(
                SaltInvocationError,
                consul.health_state,
                consul_url=consul_url,
            )

    # state not in allowed states
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.health_state(
                consul_url=consul_url, token=token, state=state
            )
            expected = {
                "message": "State must be any, unknown, passing, warning, or critical.",
                "res": False,
            }
            assert expected == result

    state = "warning"
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.health_state(
                consul_url=consul_url, token=token, state=state
            )
            expected = {"data": "test", "res": True}
            assert expected == result


def test_status_leader():
    """
    Test consul status leader
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.status_leader(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.status_leader(consul_url=consul_url, token=token)
            expected = {"data": "test", "res": True}
            assert expected == result


def test_status_peers():
    """
    Test consul status peers
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.status_peers(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.status_peers(consul_url=consul_url, token=token)
            expected = {"data": "test", "res": True}


def test_acl_create():
    """
    Test consul acl create
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"
    name = "name1"

    rules = [
        {
            "key": {"key": "foo/", "policy": "read"},
            "service": {"service": "bar", "policy": "write"},
        }
    ]

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.acl_create(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            pytest.raises(
                SaltInvocationError,
                consul.acl_create,
                consul_url=consul_url,
            )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.acl_create(consul_url=consul_url, token=token, name=name)
            expected = {"message": f"ACL {name} created.", "res": True}
            assert expected == result

    # test rules
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.acl_create(
                consul_url=consul_url, token=token, name=name, rules=rules
            )
            expected = {"message": f"ACL {name} created.", "res": True}
            assert expected == result


def test_acl_update():
    """
    Test consul acl update
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"
    name = "name1"
    aclid = "id1"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.acl_update(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.acl_update(consul_url=consul_url)
            expected = {
                "message": 'Required parameter "id" is missing.',
                "res": False,
            }
            assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            pytest.raises(
                SaltInvocationError,
                consul.acl_update,
                consul_url=consul_url,
                id=aclid,
            )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.acl_update(
                consul_url=consul_url, token=token, name=name, id=aclid
            )
            expected = {"message": f"ACL {name} created.", "res": True}
            assert expected == result


def test_acl_delete():
    """
    Test consul acl delete
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"
    name = "name1"
    aclid = "id1"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.acl_delete(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.acl_delete(consul_url=consul_url)
            expected = {
                "message": 'Required parameter "id" is missing.',
                "res": False,
            }
            assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.acl_delete(
                consul_url=consul_url, token=token, name=name, id=aclid
            )
            expected = {"message": f"ACL {aclid} deleted.", "res": True}
            assert expected == result


def test_acl_info():
    """
    Test consul acl info
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"
    name = "name1"
    aclid = "id1"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.acl_info(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.acl_info(consul_url=consul_url)
            expected = {
                "message": 'Required parameter "id" is missing.',
                "res": False,
            }
            assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.acl_info(
                consul_url=consul_url, token=token, name=name, id=aclid
            )
            expected = {"data": "test", "res": True}
            assert expected == result


def test_acl_clone():
    """
    Test consul acl clone
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"
    name = "name1"
    aclid = "id1"

    mock_result = aclid
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.acl_clone(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.acl_clone(consul_url=consul_url)
            expected = {
                "message": 'Required parameter "id" is missing.',
                "res": False,
            }
            assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.acl_clone(
                consul_url=consul_url, token=token, name=name, id=aclid
            )
            expected = {
                "ID": aclid,
                "message": f"ACL {name} cloned.",
                "res": True,
            }
            assert expected == result


def test_acl_list():
    """
    Test consul acl list
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"
    name = "name1"
    aclid = "id1"

    mock_result = aclid
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.acl_list(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.acl_list(
                consul_url=consul_url, token=token, name=name, id=aclid
            )
            expected = {"data": "id1", "res": True}
            assert expected == result


def test_event_fire():
    """
    Test consul event fire
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"
    name = "name1"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.event_fire(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            pytest.raises(
                SaltInvocationError,
                consul.event_fire,
                consul_url=consul_url,
            )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.event_fire(consul_url=consul_url, token=token, name=name)
            expected = {
                "data": "test",
                "message": f"Event {name} fired.",
                "res": True,
            }
            assert expected == result


def test_event_list():
    """
    Test consul event list
    """
    consul_url = "http://localhost:1313"
    token = "randomtoken"
    name = "name1"

    mock_result = "test"
    mock_http_result = {"status": 200, "dict": mock_result}
    mock_http_result_false = {"status": 204, "dict": mock_result}
    mock_url = MagicMock(return_value=consul_url)
    mock_nourl = MagicMock(return_value=None)

    # no consul url error
    with patch.dict(consul.__salt__, {"config.get": mock_nourl}):
        result = consul.event_list(consul_url="")
        expected = {"message": "No Consul URL found.", "res": False}
        assert expected == result

    # no required arguments
    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            pytest.raises(
                SaltInvocationError,
                consul.event_list,
                consul_url=consul_url,
            )

    with patch.object(salt.utils.http, "query", return_value=mock_http_result):
        with patch.dict(consul.__salt__, {"config.get": mock_url}):
            result = consul.event_list(consul_url=consul_url, token=token, name=name)
            expected = {"data": "test", "res": True}
            assert expected == result
