"""
Integration tests for the rabbitmq_user states
"""

import logging

import pytest
import salt.modules.rabbitmq as rabbitmq
import salt.states.rabbitmq_vhost as rabbitmq_vhost

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_freebsd(reason="No Docker on FreeBSD available"),
    pytest.mark.skip_if_binaries_missing(
        "docker", "dockerd", reason="Docker not installed"
    ),
]


@pytest.fixture
def configure_loader_modules(docker_cmd_run_all_wrapper):
    return {
        rabbitmq_vhost: {
            "__salt__": {
                "rabbitmq.vhost_exists": rabbitmq.vhost_exists,
                "rabbitmq.add_vhost": rabbitmq.add_vhost,
                "rabbitmq.delete_vhost": rabbitmq.delete_vhost,
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


@pytest.mark.slow_test
def test_present_absent(docker_cmd_run_all_wrapper):
    """
    Test rabbitmq_vhost.present
    """

    # Clear the user
    ret = rabbitmq_vhost.present("vhost")
    expected = {
        "name": "vhost",
        "result": True,
        "comment": 'Adding vhost "vhost" ...\n',
        "changes": {"old": "", "new": "vhost"},
    }
    assert ret == expected

    # Delete the user
    ret = rabbitmq_vhost.absent("vhost")
    expected = {
        "name": "vhost",
        "result": True,
        "comment": 'Deleting vhost "vhost" ...\n',
        "changes": {"old": "vhost", "new": ""},
    }

    assert ret == expected


def test_absent(docker_cmd_run_all_wrapper):
    """
    Test rabbitmq_vhost.present
    """

    # Delete the user
    ret = rabbitmq_vhost.absent("vhost")
    expected = {
        "name": "vhost",
        "result": True,
        "comment": "Virtual Host 'vhost' is not present.",
        "changes": {},
    }
    assert ret == expected
