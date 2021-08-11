"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.rabbitmq_vhost as rabbitmq_vhost
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {rabbitmq_vhost: {}}


# 'present' function tests: 1


def test_present():
    """
    Test to ensure the RabbitMQ VHost exists.
    """
    name = "virtual_host"

    ret = {
        "name": name,
        "changes": {"new": "virtual_host", "old": ""},
        "result": None,
        "comment": "Virtual Host 'virtual_host' will be created.",
    }

    mock = MagicMock(return_value=False)
    with patch.dict(rabbitmq_vhost.__salt__, {"rabbitmq.vhost_exists": mock}):
        with patch.dict(rabbitmq_vhost.__opts__, {"test": True}):
            assert rabbitmq_vhost.present(name) == ret


# 'absent' function tests: 1


def test_absent():
    """
    Test to ensure the named user is absent.
    """
    name = "myqueue"

    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "Virtual Host '{}' is not present.".format(name),
    }

    mock = MagicMock(return_value=False)
    with patch.dict(rabbitmq_vhost.__salt__, {"rabbitmq.vhost_exists": mock}):
        assert rabbitmq_vhost.absent(name) == ret
