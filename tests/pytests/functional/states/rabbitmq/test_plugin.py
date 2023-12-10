"""
Integration tests for the rabbitmq_plugin states
"""

import logging

import pytest

import salt.modules.rabbitmq as rabbitmq
import salt.states.rabbitmq_plugin as rabbitmq_plugin
from tests.support.mock import patch

log = logging.getLogger(__name__)

pytest.importorskip("docker")

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing(
        "docker", "dockerd", reason="Docker not installed"
    ),
]


def mock_get_rabbitmq_plugin():
    return "/opt/rabbitmq/sbin/rabbitmq-plugins"


@pytest.fixture
def configure_loader_modules(docker_cmd_run_all_wrapper):
    return {
        rabbitmq_plugin: {
            "__salt__": {
                "rabbitmq.plugin_is_enabled": rabbitmq.plugin_is_enabled,
                "rabbitmq.enable_plugin": rabbitmq.enable_plugin,
                "rabbitmq.disable_plugin": rabbitmq.disable_plugin,
            },
            "__opts__": {"test": False},
            "_utils__": {},
        },
        rabbitmq: {
            "__salt__": {"cmd.run_all": docker_cmd_run_all_wrapper},
            "__opts__": {},
            "_utils__": {},
        },
    }


def test_enabled_enabled_disabled(rabbitmq_container):
    """
    Test rabbitmq_plugin.enabled and rabbitmq_plugin_disabled

    First enable the plugin.

    Second try to enable the plugin again.

    Third, try to disable the plugin.
    """

    with patch.object(rabbitmq, "_get_rabbitmq_plugin", mock_get_rabbitmq_plugin):
        # Enable the plugin
        ret = rabbitmq_plugin.enabled("rabbitmq_auth_backend_http")
        expected = {
            "name": "rabbitmq_auth_backend_http",
            "result": True,
            "comment": "Plugin 'rabbitmq_auth_backend_http' was enabled.",
            "changes": {"old": "", "new": "rabbitmq_auth_backend_http"},
        }
        assert ret == expected

        # Try to enable the plugin again
        ret = rabbitmq_plugin.enabled("rabbitmq_auth_backend_http")
        expected = {
            "name": "rabbitmq_auth_backend_http",
            "result": True,
            "comment": "Plugin 'rabbitmq_auth_backend_http' is already enabled.",
            "changes": {},
        }
        assert ret == expected

        # Disable the plugin
        ret = rabbitmq_plugin.disabled("rabbitmq_auth_backend_http")
        expected = {
            "name": "rabbitmq_auth_backend_http",
            "result": True,
            "comment": "Plugin 'rabbitmq_auth_backend_http' was disabled.",
            "changes": {"new": "", "old": "rabbitmq_auth_backend_http"},
        }
        assert ret == expected


def test_disabled(rabbitmq_container):
    """
    Test rabbitmq_plugin.enabled and rabbitmq_plugin_disabled

    First try to disable the plugin.

    Second enable the plugin again.

    Third disable the plugin.
    """

    with patch.object(rabbitmq, "_get_rabbitmq_plugin", mock_get_rabbitmq_plugin):
        # Try to disable the plugin
        ret = rabbitmq_plugin.disabled("rabbitmq_auth_backend_http")
        expected = {
            "name": "rabbitmq_auth_backend_http",
            "result": True,
            "comment": "Plugin 'rabbitmq_auth_backend_http' is already disabled.",
            "changes": {},
        }
        assert ret == expected

        # Enable the plugin
        ret = rabbitmq_plugin.enabled("rabbitmq_auth_backend_http")
        expected = {
            "name": "rabbitmq_auth_backend_http",
            "result": True,
            "comment": "Plugin 'rabbitmq_auth_backend_http' was enabled.",
            "changes": {"old": "", "new": "rabbitmq_auth_backend_http"},
        }
        assert ret == expected

        # Disable the plugin
        ret = rabbitmq_plugin.disabled("rabbitmq_auth_backend_http")
        expected = {
            "name": "rabbitmq_auth_backend_http",
            "result": True,
            "comment": "Plugin 'rabbitmq_auth_backend_http' was disabled.",
            "changes": {"new": "", "old": "rabbitmq_auth_backend_http"},
        }
        assert ret == expected
