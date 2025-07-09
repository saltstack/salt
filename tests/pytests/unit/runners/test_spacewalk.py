"""
Unit tests for Spacewalk runner
"""

import salt.runners.spacewalk as spacewalk
from tests.support.mock import Mock, call, patch


def test_api_command_must_have_namespace():
    _get_session_mock = Mock(return_value=(None, None))

    with patch.object(spacewalk, "_get_session", _get_session_mock):
        result = spacewalk.api("mocked.server", "badMethod")
        assert result == {
            "badMethod ()": (
                "Error: command must use the following format: 'namespace.method'"
            )
        }


def test_api_command_accepts_single_namespace():
    client_mock = Mock()
    _get_session_mock = Mock(return_value=(client_mock, "key"))
    getattr_mock = Mock(return_value="mocked_getattr_return")

    with patch.object(spacewalk, "_get_session", _get_session_mock):
        with patch.object(spacewalk, "getattr", getattr_mock):
            spacewalk.api("mocked.server", "system.listSystems")
            getattr_mock.assert_has_calls(
                [
                    call(client_mock, "system"),
                    call("mocked_getattr_return", "listSystems"),
                ]
            )


def test_api_command_accepts_nested_namespace():
    client_mock = Mock()
    _get_session_mock = Mock(return_value=(client_mock, "key"))
    getattr_mock = Mock(return_value="mocked_getattr_return")

    with patch.object(spacewalk, "_get_session", _get_session_mock):
        with patch.object(spacewalk, "getattr", getattr_mock):
            spacewalk.api("mocked.server", "channel.software.listChildren")
            getattr_mock.assert_has_calls(
                [
                    call(client_mock, "channel.software"),
                    call("mocked_getattr_return", "listChildren"),
                ]
            )
