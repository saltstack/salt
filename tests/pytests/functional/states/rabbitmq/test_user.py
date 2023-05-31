"""
Integration tests for the rabbitmq_user states
"""

import logging

import pytest

import salt.modules.rabbitmq as rabbitmq
import salt.states.rabbitmq_user as rabbitmq_user

log = logging.getLogger(__name__)

pytest.importorskip("docker")

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing(
        "docker", "dockerd", reason="Docker not installed"
    ),
]


@pytest.fixture
def configure_loader_modules(docker_cmd_run_all_wrapper, docker_cmd_run_wrapper):
    return {
        rabbitmq_user: {
            "__salt__": {
                "rabbitmq.user_exists": rabbitmq.user_exists,
                "rabbitmq.add_user": rabbitmq.add_user,
                "rabbitmq.delete_user": rabbitmq.delete_user,
                "rabbitmq.list_user_permissions": rabbitmq.list_user_permissions,
                "rabbitmq.list_users": rabbitmq.list_users,
                "rabbitmq.set_user_tags": rabbitmq.set_user_tags,
                "rabbitmq.set_permissions": rabbitmq.set_permissions,
                "rabbitmq.check_password": rabbitmq.check_password,
                "rabbitmq.change_password": rabbitmq.change_password,
                "cmd.run": docker_cmd_run_wrapper,
            },
            "__opts__": {"test": False},
            "_utils__": {},
        },
        rabbitmq: {
            "__salt__": {
                "rabbitmq.user_exists": rabbitmq.user_exists,
                "rabbitmq.add_user": rabbitmq.add_user,
                "rabbitmq.list_user_permissions": rabbitmq.list_user_permissions,
                "cmd.run_all": docker_cmd_run_all_wrapper,
                "cmd.run": docker_cmd_run_wrapper,
            },
            "__opts__": {},
            "_utils__": {},
        },
    }


def test_present_absent(docker_cmd_run_all_wrapper, rabbitmq_container):
    """
    Test rabbitmq_user.present

    Create user then delete it.
    """

    # Clear the user
    ret = rabbitmq_user.present("myuser")
    expected = {
        "name": "myuser",
        "result": True,
        "comment": "'myuser' was configured.",
        "changes": {"user": {"old": "", "new": "myuser"}},
    }
    assert ret == expected

    # Delete the user
    ret = rabbitmq_user.absent("myuser")
    expected = {
        "name": "myuser",
        "result": True,
        "comment": "The user 'myuser' was removed.",
        "changes": {"name": {"old": "myuser", "new": ""}},
    }

    assert ret == expected

    ret = rabbitmq_user.present(
        "myuser",
        password="password",
        force=True,
        tags=["monitoring", "user"],
        perms=[{"/": [".*", ".*", "test$"]}],
    )

    expected = {
        "name": "myuser",
        "result": True,
        "comment": "'myuser' was configured.",
        "changes": {
            "user": {"old": "", "new": "myuser"},
            "tags": {"old": [""], "new": ["monitoring", "user"]},
            "perms": {
                "new": {"/": {"configure": ".*", "write": ".*", "read": "test$"}}
            },
        },
    }
    assert ret == expected

    ret = rabbitmq_user.present(
        "myuser",
        password="password",
        force=True,
        tags=["monitoring", "user"],
        perms=[{"/": ["", "", ".*"]}],
    )

    expected = {
        "name": "myuser",
        "result": True,
        "comment": "'myuser' was configured.",
        "changes": {
            "password": {"old": "", "new": "Set password."},
            "perms": {
                "old": {"configure": ".*", "write": ".*", "read": "test$"},
                "new": {"/": {"configure": "", "write": "", "read": ".*"}},
            },
        },
    }
    assert ret == expected

    # Delete the user
    ret = rabbitmq_user.absent("myuser")
    expected = {
        "name": "myuser",
        "result": True,
        "comment": "The user 'myuser' was removed.",
        "changes": {"name": {"old": "myuser", "new": ""}},
    }

    assert ret == expected


def test_absent(docker_cmd_run_all_wrapper, rabbitmq_container):
    """
    Test rabbitmq_user.absent
    """

    # Delete the user
    ret = rabbitmq_user.absent("myuser")
    expected = {
        "name": "myuser",
        "result": True,
        "comment": "The user 'myuser' is not present.",
        "changes": {},
    }
    assert ret == expected
