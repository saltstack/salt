"""
Integration tests for the etcd modules
"""

import logging
import os
import subprocess
import tempfile

import pytest
import salt.utils.files
from saltfactories.utils.ports import get_unused_localhost_port
from tests.support.helpers import dedent
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)

pytestmark = [pytest.mark.skip_if_binaries_missing("dockerd")]


class Keys:
    """
    Temporary ssh key pair
    """

    def __init__(self, priv_path=None):
        if priv_path is None:
            priv_path = tempfile.mktemp()
        self.priv_path = priv_path

    def generate(self):
        subprocess.run(["ssh-keygen", "-q", "-N", "", "-f", self.priv_path], check=True)

    @property
    def pub_path(self):
        return "{}.pub".format(self.priv_path)

    @property
    def pub(self):
        with salt.utils.files.fopen(self.pub_path, "r") as fp:
            return fp.read()

    @property
    def priv(self):
        with salt.utils.files.fopen(self.priv_path, "r") as fp:
            return fp.read()

    def __enter__(self):
        self.generate()
        return self

    def __exit__(self, *args, **kwargs):
        os.remove(self.pub_path)
        os.remove(self.priv_path)


@pytest.fixture(scope="module")
def ssh_keys():
    """
    Temporary ssh key fixture
    """
    with Keys() as keys:
        yield keys


@pytest.fixture(scope="module")
def ssh_port():
    """
    Temporary ssh port fixture
    """
    return get_unused_localhost_port()


@pytest.fixture(scope="module")
def ssh_roster(ssh_port, ssh_keys, master_id):
    """
    Temporary roster for ssh docker container
    """
    roster_path = os.path.join(RUNTIME_VARS.TMP, master_id, "conf", "roster")
    with salt.utils.files.fopen(roster_path) as fp:
        orig_roster = fp.read()
    roster = orig_roster + dedent(
        """
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
    )
    with salt.utils.files.fopen(roster_path, "w") as fp:
        fp.write(roster)
    try:
        yield roster_path
    finally:
        with salt.utils.files.fopen(roster_path, "w") as fp:
            fp.write(orig_roster)


@pytest.fixture(scope="module", autouse=True)
def ssh_docker_container(salt_call_cli, ssh_port, ssh_keys):
    """
    Temporary docker container with python 3.6 and ssh enabled
    """
    container_started = False
    try:
        ret = salt_call_cli.run(
            "state.single", "docker_image.present", name="dwoz1/cicd", tag="ssh"
        )
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        ret = salt_call_cli.run(
            "state.single",
            "docker_container.running",
            name="ssh1",
            image="dwoz1/cicd:ssh",
            port_bindings='"{}:22"'.format(ssh_port),
            environment={"SSH_USER": "centos", "SSH_AUTHORIZED_KEYS": ssh_keys.pub},
            cap_add="IPC_LOCK",
            timeout=300,
        )
        assert ret.exitcode == 0
        assert ret.json
        state_run = next(iter(ret.json.values()))
        assert state_run["result"] is True
        container_started = True
        yield
    finally:
        if container_started:
            ret = salt_call_cli.run(
                "state.single", "docker_container.stopped", name="ssh1"
            )
            assert ret.exitcode == 0
            assert ret.json
            state_run = next(iter(ret.json.values()))
            assert state_run["result"] is True
            ret = salt_call_cli.run(
                "state.single", "docker_container.absent", name="ssh1"
            )
            assert ret.exitcode == 0
            assert ret.json
            state_run = next(iter(ret.json.values()))
            assert state_run["result"] is True


@pytest.mark.slow_test
def test_py36_target(salt_ssh_cli, ssh_roster):
    """
    Test that a python >3.6 master can salt ssh to a <3.6 target
    """
    ret = salt_ssh_cli.run("test.ping", minion_tgt="pyvertest")
    assert ret.exitcode == 0
    assert ret.json
