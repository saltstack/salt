"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.rabbitmq_plugin as rabbitmq_plugin
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {rabbitmq_plugin: {}}


# 'enabled' function tests: 1


def test_enabled():
    """
    Test to ensure the RabbitMQ plugin is enabled.
    """
    name = "some_plugin"

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    mock = MagicMock(side_effect=[True, False])
    with patch.dict(rabbitmq_plugin.__salt__, {"rabbitmq.plugin_is_enabled": mock}):
        comment = "Plugin 'some_plugin' is already enabled."
        ret.update({"comment": comment})
        assert rabbitmq_plugin.enabled(name) == ret

        with patch.dict(rabbitmq_plugin.__opts__, {"test": True}):
            comment = "Plugin 'some_plugin' is set to be enabled."
            changes = {"new": "some_plugin", "old": ""}
            ret.update({"comment": comment, "result": None, "changes": changes})
            assert rabbitmq_plugin.enabled(name) == ret


# 'disabled' function tests: 1


def test_disabled():
    """
    Test to ensure the RabbitMQ plugin is disabled.
    """
    name = "some_plugin"

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    mock = MagicMock(side_effect=[False, True])
    with patch.dict(rabbitmq_plugin.__salt__, {"rabbitmq.plugin_is_enabled": mock}):
        comment = "Plugin 'some_plugin' is already disabled."
        ret.update({"comment": comment})
        assert rabbitmq_plugin.disabled(name) == ret

        with patch.dict(rabbitmq_plugin.__opts__, {"test": True}):
            comment = "Plugin 'some_plugin' is set to be disabled."
            changes = {"new": "", "old": "some_plugin"}
            ret.update({"comment": comment, "result": None, "changes": changes})
            assert rabbitmq_plugin.disabled(name) == ret
