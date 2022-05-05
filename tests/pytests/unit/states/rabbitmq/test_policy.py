"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.rabbitmq_policy as rabbitmq_policy
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {rabbitmq_policy: {}}


# 'present' function tests: 1


def test_present():
    """
    Test to ensure the RabbitMQ policy exists.
    """
    name = "HA"
    pattern = ".*"
    definition = '{"ha-mode":"all"}'

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    mock = MagicMock(
        side_effect=[
            {
                "/": {
                    name: {"pattern": pattern, "definition": definition, "priority": 0}
                }
            },
            {},
        ]
    )
    with patch.dict(rabbitmq_policy.__salt__, {"rabbitmq.list_policies": mock}):
        comt = "Policy / HA is already present"
        ret.update({"comment": comt})
        assert rabbitmq_policy.present(name, pattern, definition) == ret

        with patch.dict(rabbitmq_policy.__opts__, {"test": True}):
            comment = "Policy / HA is set to be created"
            changes = {"new": "HA", "old": {}}
            ret.update({"comment": comment, "result": None, "changes": changes})
            assert rabbitmq_policy.present(name, pattern, definition) == ret


# 'absent' function tests: 1


def test_absent():
    """
    Test to ensure the named policy is absent.
    """
    name = "HA"

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    mock = MagicMock(side_effect=[False, True])
    with patch.dict(rabbitmq_policy.__salt__, {"rabbitmq.policy_exists": mock}):
        comment = "Policy '/ HA' is not present."
        ret.update({"comment": comment})
        assert rabbitmq_policy.absent(name) == ret

        with patch.dict(rabbitmq_policy.__opts__, {"test": True}):
            comment = "Policy '/ HA' will be removed."
            changes = {"new": "", "old": "HA"}
            ret.update({"comment": comment, "result": None, "changes": changes})
            assert rabbitmq_policy.absent(name) == ret
