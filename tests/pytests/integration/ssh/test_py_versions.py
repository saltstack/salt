"""
Integration tests for salt-ssh py_versions
"""

import logging
import socket
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


def check_container_started(timeout_at, container):
    sleeptime = 2
    while time.time() <= timeout_at:
        time.sleep(sleeptime)
        try:
            if not container.is_running():
                return False
            sock = socket.socket()
            sock.connect(("localhost", container.get_check_ports()[22]))
            return True
        except Exception as err:  # pylint: disable=broad-except
            break
        finally:
            sock.close()
        time.sleep(sleeptime)
        sleeptime *= 2
    else:
        return False
    return False


@pytest.fixture(scope="module")
def ssh_keys(tmp_path_factory):
    """
    Temporary ssh key fixture
    """
    with Keys(tmp_path_factory) as keys:
        yield keys


@pytest.fixture(scope="module")
def ssh_docker_container(salt_factories, ssh_keys):
    """
    Temporary docker container with python 3.6 and ssh enabled
    """
    container = salt_factories.get_container(
        random_string("ssh-py_versions-"),
        "ghcr.io/saltstack/salt-ci-containers/ssh-minion:latest",
        container_run_kwargs={
            "ports": {
                "22/tcp": None,
            },
            "environment": {
                "SSH_USER": "centos",
                "SSH_AUTHORIZED_KEYS": ssh_keys.pub,
            },
            "cap_add": "IPC_LOCK",
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    container.container_start_check(check_container_started, container)
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module")
def ssh_port(ssh_docker_container):
    return ssh_docker_container.get_host_port_binding(22, protocol="tcp")


@pytest.fixture(scope="module")
def salt_ssh_roster_file(ssh_port, ssh_keys, salt_master, known_hosts_file):
    """
    Temporary roster for ssh docker container
    """
    roster = f"""
    pyvertest:
      host: localhost
      user: centos
      port: {ssh_port}
      priv: {ssh_keys.priv_path}
      ssh_options:
        - UserKnownHostsFile={known_hosts_file}
    """
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
        client_key=str(ssh_keys.priv_path),
        base_script_args=["--ignore-host-keys"],
    )


def test_py36_target(salt_ssh_cli):
    """
    Test that a python >3.6 master can salt ssh to a <3.6 target
    """
    ret = salt_ssh_cli.run("test.ping", minion_tgt="pyvertest")
    if "kex_exchange_identification" in ret.stdout:
        pytest.skip("Container closed ssh connection, skipping for now")
    assert ret.returncode == 0
    assert ret.data is True
