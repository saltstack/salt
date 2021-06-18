"""
Integration tests for salt-ssh py_versions
"""
import logging
import shutil
import subprocess

import pytest
from saltfactories.daemons.container import Container
from saltfactories.utils import random_string
from saltfactories.utils.ports import get_unused_localhost_port

docker = pytest.importorskip("docker")
from docker.errors import (  # isort:skip pylint: disable=3rd-party-module-not-gated
    DockerException,
)


log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_if_binaries_missing("dockerd"),
]


class Keys:
    """
    Temporary ssh key pair
    """

    def __init__(self, tmp_path_factory):
        priv_path = tmp_path_factory.mktemp(".ssh") / "key"
        self.priv_path = priv_path

    def generate(self):
        subprocess.run(
            ["ssh-keygen", "-q", "-N", "", "-f", str(self.priv_path)], check=True
        )

    @property
    def pub_path(self):
        return self.priv_path.with_name("{}.pub".format(self.priv_path.name))

    @property
    def pub(self):
        return self.pub_path.read_text()

    @property
    def priv(self):
        return self.priv_path.read_text()

    def __enter__(self):
        self.generate()
        return self

    def __exit__(self, *_):
        shutil.rmtree(str(self.priv_path.parent), ignore_errors=True)


@pytest.fixture(scope="module")
def docker_client():
    try:
        client = docker.from_env()
    except DockerException:
        pytest.skip("Failed to get a connection to docker running on the system")
    connectable = Container.client_connectable(client)
    if connectable is not True:  # pragma: nocover
        pytest.skip(connectable)
    return client


@pytest.fixture(scope="module")
def ssh_keys(tmp_path_factory):
    """
    Temporary ssh key fixture
    """
    with Keys(tmp_path_factory) as keys:
        yield keys


@pytest.fixture(scope="module")
def ssh_port():
    """
    Temporary ssh port fixture
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="module")
def salt_ssh_roster_file(ssh_port, ssh_keys, salt_master):
    """
    Temporary roster for ssh docker container
    """
    roster = """
    pyvertest:
      host: localhost
      user: centos
      port: {}
      priv: {}
      ssh_options:
        - StrictHostKeyChecking=no
        - UserKnownHostsFile=/dev/null
    """.format(
        ssh_port, ssh_keys.priv_path
    )
    with pytest.helpers.temp_file(
        "py_versions_roster", roster, salt_master.config_dir
    ) as roster_file:
        yield roster_file


@pytest.fixture(scope="module")
def ssh_docker_container(salt_factories, docker_client, ssh_port, ssh_keys):
    """
    Temporary docker container with python 3.6 and ssh enabled
    """
    container = salt_factories.get_container(
        random_string("ssh-py_versions-"),
        "dwoz1/cicd:ssh",
        docker_client=docker_client,
        check_ports=[ssh_port],
        container_run_kwargs={
            "ports": {"22/tcp": ssh_port},
            "environment": {"SSH_USER": "centos", "SSH_AUTHORIZED_KEYS": ssh_keys.pub},
            "cap_add": "IPC_LOCK",
        },
    )
    with container.started() as factory:
        yield factory


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


@pytest.mark.slow_test
def test_py36_target(salt_ssh_cli):
    """
    Test that a python >3.6 master can salt ssh to a <3.6 target
    """
    ret = salt_ssh_cli.run("test.ping", minion_tgt="pyvertest")
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json is True
