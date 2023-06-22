"""
Integration tests for the rabbitmq_policy states
"""

import logging

import pytest

import salt.modules.rabbitmq as rabbitmq
import salt.states.rabbitmq_policy as rabbitmq_policy
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)

pytest.importorskip("docker")

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing(
        "docker", "dockerd", reason="Docker not installed"
    ),
]


@pytest.fixture
def configure_loader_modules(docker_cmd_run_all_wrapper):
    return {
        rabbitmq_policy: {
            "__salt__": {
                "rabbitmq.set_policy": rabbitmq.set_policy,
                "rabbitmq.delete_policy": rabbitmq.delete_policy,
                "rabbitmq.policy_exists": rabbitmq.policy_exists,
                "rabbitmq.list_policies": rabbitmq.list_policies,
            },
            "__opts__": {"test": False},
            "_utils__": {},
        },
        rabbitmq: {
            "__salt__": {
                "rabbitmq.list_policies": rabbitmq.list_policies,
                "cmd.run_all": docker_cmd_run_all_wrapper,
            },
            "__grains__": {"os_family": "Linux"},
            "__opts__": {},
            "_utils__": {},
        },
    }


def test_present_absent(rabbitmq_container):
    """
    Test rabbitmq_policy.present and rabbitmq_policy.absent
    """

    with patch.dict(rabbitmq.__salt__, {"pkg.version": MagicMock(return_value="3.8")}):
        # Clear the policy
        ret = rabbitmq_policy.present(
            name="HA", pattern=".*", definition={"ha-mode": "all"}
        )
        expected = {
            "name": "HA",
            "result": True,
            "comment": (
                'Setting policy "HA" for pattern ".*" to "{"ha-mode": "all"}" with'
                ' priority "0" for vhost "/" ...\n'
            ),
            "changes": {"old": {}, "new": "HA"},
        }
        assert ret == expected

        # Delete the policy
        ret = rabbitmq_policy.absent("HA")
        expected = {
            "name": "HA",
            "result": True,
            "comment": "Deleted",
            "changes": {"new": "", "old": "HA"},
        }

        assert ret == expected


def test_absent(rabbitmq_container):
    """
    Test rabbitmq_policy.absent
    """

    with patch.dict(rabbitmq.__salt__, {"pkg.version": MagicMock(return_value="3.8")}):
        # Delete the policy
        ret = rabbitmq_policy.absent("HA")
        expected = {
            "name": "HA",
            "result": True,
            "comment": "Policy '/ HA' is not present.",
            "changes": {},
        }

        assert ret == expected
