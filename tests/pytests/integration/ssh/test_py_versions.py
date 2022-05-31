"""
Integration tests for salt-ssh py_versions
"""
import logging
import shutil
import subprocess

import pytest
from saltfactories.utils import random_string

pytest.importorskip("docker")


log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
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
        "dwoz1/cicd:ssh",
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
    with container.started() as factory:
        yield factory


@pytest.fixture(scope="module")
def ssh_port(ssh_docker_container):
    return ssh_docker_container.get_host_port_binding(22, protocol="tcp")


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
    assert ret.returncode == 0
    assert ret.data
    assert ret.data is True
