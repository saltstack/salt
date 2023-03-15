"""
Integration tests for the rabbitmq_cluster states
"""

import logging

import pytest

import salt.modules.rabbitmq as rabbitmq
import salt.states.rabbitmq_cluster as rabbitmq_cluster

pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing(
        "docker", "dockerd", reason="Docker not installed"
    ),
]


@pytest.fixture
def configure_loader_modules(docker_cmd_run_all_wrapper):
    return {
        rabbitmq_cluster: {
            "__salt__": {
                "rabbitmq.cluster_status": rabbitmq.cluster_status,
                "rabbitmq.join_cluster": rabbitmq.join_cluster,
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


def test_joined(rabbitmq_container):
    """
    Test rabbitmq_cluster.joined
    """

    hostname = rabbitmq_container.container.attrs["Config"]["Hostname"]
    ret = rabbitmq_cluster.joined("name", host=hostname)
    expected = {
        "name": "name",
        "result": True,
        "comment": "Already in cluster",
        "changes": {},
    }
    assert ret == expected
