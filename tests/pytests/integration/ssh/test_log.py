"""
Integration tests for salt-ssh logging
"""

import logging
import time

import pytest
from saltfactories.utils import random_string

from tests.support.helpers import Keys

pytest.importorskip("docker")


log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd"),
]


@pytest.fixture(scope="module")
def ssh_auth():
    return random_string("sshpassword"), "app-admin"


@pytest.fixture(scope="module")
def ssh_keys(tmp_path_factory):
    """
    Temporary ssh key fixture
    """
    with Keys(tmp_path_factory) as keys:
        yield keys


@pytest.fixture(scope="module")
def ssh_docker_container(salt_factories, ssh_keys, ssh_auth):
    """
    Temporary docker container with python 3.6 and ssh enabled
    """
    ssh_pass, ssh_user = ssh_auth
    container = salt_factories.get_container(
        random_string("ssh-py_versions-"),
        "ghcr.io/saltstack/salt-ci-containers/ssh-minion:latest",
        container_run_kwargs={
            "ports": {
                "22/tcp": None,
            },
            "environment": {
                "SSH_USER": ssh_user,
                "SSH_AUTHORIZED_KEYS": ssh_keys.pub,
                "SSH_USER_PASSWORD": ssh_pass,
            },
            "cap_add": "IPC_LOCK",
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    with container.started() as factory:
        factory.run(f"echo {ssh_pass} | passwd {ssh_user} --stdin")
        yield factory


@pytest.fixture(scope="module")
def ssh_port(ssh_docker_container):
    return ssh_docker_container.get_host_port_binding(22, protocol="tcp")


@pytest.fixture(scope="module")
def salt_ssh_roster_file(ssh_port, ssh_keys, salt_master, ssh_auth):
    """
    Temporary roster for ssh docker container
    """
    ssh_pass, ssh_user = ssh_auth
    roster = """
    pyvertest:
      host: localhost
      user: {}
      port: {}
      passwd: {}
      sudo: True
      sudo_user: root
      tty: True
      ssh_options:
        - StrictHostKeyChecking=no
        - UserKnownHostsFile=/dev/null
    """.format(
        ssh_user, ssh_port, ssh_pass
    )
    with pytest.helpers.temp_file(
        "py_versions_roster", roster, salt_master.config_dir
    ) as roster_file:
        yield roster_file


@pytest.fixture(scope="module")
def salt_ssh_cli(salt_master, salt_ssh_roster_file, ssh_keys, ssh_docker_container):
    assert salt_master.is_running()
    assert ssh_docker_container.is_running()
    return salt_master.salt_ssh_cli(
        timeout=180,
        roster_file=salt_ssh_roster_file,
        target_host="localhost",
        base_script_args=["--ignore-host-keys"],
        ssh_user="app-admin",
    )


def test_log_password(salt_ssh_cli, caplog, ssh_auth):
    """
    Test to ensure password is not logged when
    using sudo and a password
    """
    ssh_pass, _ = ssh_auth
    with caplog.at_level(logging.TRACE):
        ret = salt_ssh_cli.run("--log-level=trace", "test.ping", minion_tgt="pyvertest")
    if "kex_exchange_identification" in ret.stdout:
        pytest.skip("Container closed ssh connection, skipping for now")
    try:
        assert ret.returncode == 0
    except AssertionError:
        time.sleep(5)
        with caplog.at_level(logging.TRACE):
            ret = salt_ssh_cli.run(
                "--log-level=trace", "test.ping", minion_tgt="pyvertest"
            )
        if "kex_exchange_identification" in ret.stdout:
            pytest.skip("Container closed ssh connection, skipping for now")
        assert ret.returncode == 0
    assert ssh_pass not in caplog.text
    assert ret.data is True
