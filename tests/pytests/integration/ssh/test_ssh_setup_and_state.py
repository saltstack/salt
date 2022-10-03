"""
Integration tests for salt-ssh py_versions
"""
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
import time

import pytest
from pytestshellutils.utils.processes import ProcessResult, terminate_process
from saltfactories.utils import random_string

from tests.support.helpers import Keys

pytest.importorskip("docker")


log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd"),
]


@pytest.fixture(scope="module")
def ssh_keys(tmp_path_factory):
    """
    Temporary ssh key fixture
    """
    with Keys(tmp_path_factory) as keys:
        yield keys


@pytest.fixture(scope="module")
def ssh_password():
    return random_string("sshpassword")


@pytest.fixture(scope="module")
def ssh_container_name():
    return random_string("ssh-container-")


@pytest.fixture(scope="module")
def ssh_sub_container_name():
    return random_string("ssh-sub-container-")


@pytest.fixture(scope="module")
def ssh_container(salt_factories, ssh_container_name, ssh_password):
    """
    Temporary docker container with python 3.6 and ssh enabled
    """
    container = salt_factories.get_container(
        ssh_container_name,
        "dwoz1/cicd:ssh",
        container_run_kwargs={
            "ports": {
                "22/tcp": None,
            },
            "environment": {
                "SSH_USER": "centos",
                "SSH_USER_PASSWORD": ssh_password,
                "SSH_PASSWORD_AUTHENTICATION": "true",
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
def ssh_sub_container(salt_factories, ssh_sub_container_name, ssh_password):
    """
    Temporary docker container with python 3.6 and ssh enabled
    """
    container = salt_factories.get_container(
        ssh_sub_container_name,
        "dwoz1/cicd:ssh",
        container_run_kwargs={
            "ports": {
                "22/tcp": None,
            },
            "environment": {
                "SSH_USER": "centos",
                "SSH_USER_PASSWORD": ssh_password,
                "SSH_PASSWORD_AUTHENTICATION": "true",
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
def ssh_port(ssh_container):
    return ssh_container.get_host_port_binding(22, protocol="tcp")


@pytest.fixture(scope="module")
def ssh_sub_port(ssh_sub_container):
    return ssh_sub_container.get_host_port_binding(22, protocol="tcp")


@pytest.fixture(scope="module")
def salt_ssh_roster_file(
    ssh_container_name, ssh_sub_container_name, ssh_port, ssh_sub_port, salt_master
):
    """
    Temporary roster for ssh docker container
    """
    roster = """
    {}:
      host: localhost
      user: centos
      port: {}
    {}:
      host: localhost
      user: centos
      port: {}
    """.format(
        ssh_container_name, ssh_port, ssh_sub_container_name, ssh_sub_port
    )
    with pytest.helpers.temp_file(
        "setup_roster", roster, salt_master.config_dir
    ) as roster_file:
        yield roster_file


@pytest.fixture(scope="module")
def salt_ssh_cli(
    salt_master, salt_ssh_roster_file, ssh_keys, ssh_container, ssh_sub_container
):
    assert salt_master.is_running()
    assert ssh_container.is_running()
    assert ssh_sub_container.is_running()
    return salt_master.salt_ssh_cli(
        timeout=180,
        roster_file=salt_ssh_roster_file,
        client_key=str(ssh_keys.priv_path),
        base_script_args=["--ignore-host-keys"],
    )


def test_setup(salt_ssh_cli, ssh_container_name, ssh_sub_container_name, ssh_password):
    """
    Test salt-ssh grains id work for localhost.
    """
    # Provide the passwd from the CLI to allow the key deploy
    possible_ids = (ssh_container_name, ssh_sub_container_name)
    ret = salt_ssh_cli.run(
        "--passwd", ssh_password, "--key-deploy", "grains.get", "id", minion_tgt="*"
    )
    assert ret.returncode == 0
    for id in possible_ids:
        assert id in ret.data
        assert ret.data[id] == id

    # Run it again without the key deploy
    ret = salt_ssh_cli.run("grains.get", "id", minion_tgt="*")
    assert ret.returncode == 0
    for id in possible_ids:
        assert id in ret.data
        assert ret.data[id] == id

    # Run a test.sleep and kill it
    sleep_time = 15
    cmdline = salt_ssh_cli.cmdline("test.sleep", sleep_time, minion_tgt="*")
    terminal_stdout = tempfile.SpooledTemporaryFile(512000, buffering=0)
    terminal_stderr = tempfile.SpooledTemporaryFile(512000, buffering=0)

    proc = subprocess.Popen(
        cmdline,
        shell=False,
        stdout=terminal_stdout,
        stderr=terminal_stderr,
        universal_newlines=True,
    )
    start = time.time()
    try:
        # Make sure it actually starts
        proc.wait(1)
    except subprocess.TimeoutExpired:
        pass
    else:
        terminate_process(proc.pid, kill_children=True)
        pytest.fail("The test process failed to start")

    time.sleep(2)
    # Send CTRL-C to the process
    os.kill(proc.pid, signal.SIGINT)
    with proc:
        # Wait for the process to terminate, to avoid zombies.
        # Shouldn't really take the 30 seconds
        proc.wait(sleep_time * 2)
        # poll the terminal so the right returncode is set on the popen object
        proc.poll()
        # This call shouldn't really be necessary
        proc.communicate()
    stop = time.time()

    terminal_stdout.flush()
    terminal_stdout.seek(0)
    if sys.version_info < (3, 6):  # pragma: no cover
        stdout = proc._translate_newlines(
            terminal_stdout.read(), __salt_system_encoding__
        )
    else:
        stdout = proc._translate_newlines(
            terminal_stdout.read(), __salt_system_encoding__, sys.stdout.errors
        )
    terminal_stdout.close()

    terminal_stderr.flush()
    terminal_stderr.seek(0)
    if sys.version_info < (3, 6):  # pragma: no cover
        stderr = proc._translate_newlines(
            terminal_stderr.read(), __salt_system_encoding__
        )
    else:
        stderr = proc._translate_newlines(
            terminal_stderr.read(), __salt_system_encoding__, sys.stderr.errors
        )
    terminal_stderr.close()
    ret = ProcessResult(
        returncode=proc.returncode, stdout=stdout, stderr=stderr, cmdline=proc.args
    )
    log.debug(ret)
    # If the minion ID is on stdout it means that the command finished and wasn't terminated
    for id in possible_ids:
        assert (
            id not in ret.stdout
        ), "The command wasn't actually terminated. Took {} seconds.".format(
            round(stop - start, 2)
        )


@pytest.fixture(scope="module")
def state_tree(base_env_state_tree_root_dir):
    top_file = """
    base:
      'localhost':
        - basic
      '127.0.0.1':
        - basic
    """
    map_file = """
    {%- set abc = "def" %}
    """
    state_file = """
    {%- from "map.jinja" import abc with context %}

    Ok with {{ abc }}:
      test.succeed_without_changes
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    map_tempfile = pytest.helpers.temp_file(
        "map.jinja", map_file, base_env_state_tree_root_dir
    )
    state_tempfile = pytest.helpers.temp_file(
        "test.sls", state_file, base_env_state_tree_root_dir
    )

    with top_tempfile, map_tempfile, state_tempfile:
        yield


@pytest.mark.slow_test
def test_state_with_import(salt_ssh_cli, state_tree):
    """
    verify salt-ssh can use imported map files in states
    """
    ret = salt_ssh_cli.run("state.sls", "test")
    assert ret.returncode == 0
    assert ret.data


@pytest.fixture
def nested_state_tree(base_env_state_tree_root_dir, tmp_path):
    top_file = """
    base:
      'localhost':
        - basic
      '127.0.0.1':
        - basic
    """
    state_file = """
    /{}/file.txt:
      file.managed:
        - source: salt://foo/file.jinja
        - template: jinja
    """.format(
        tmp_path
    )
    file_jinja = """
    {% from 'foo/map.jinja' import comment %}{{ comment }}
    """
    map_file = """
    {% set comment = "blah blah" %}
    """
    statedir = base_env_state_tree_root_dir / "foo"
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    map_tempfile = pytest.helpers.temp_file("map.jinja", map_file, statedir)
    file_tempfile = pytest.helpers.temp_file("file.jinja", file_jinja, statedir)
    state_tempfile = pytest.helpers.temp_file("init.sls", state_file, statedir)

    with top_tempfile, map_tempfile, state_tempfile, file_tempfile:
        yield


@pytest.mark.slow_test
def test_state_with_import_from_dir(salt_ssh_cli, nested_state_tree):
    """
    verify salt-ssh can use imported map files in states
    """
    ret = salt_ssh_cli.run(
        "--extra-filerefs=salt://foo/map.jinja", "state.apply", "foo"
    )
    assert ret.returncode == 0
    assert ret.data


@pytest.mark.slow_test
def test_state_low(salt_ssh_cli):
    """
    test state.low with salt-ssh
    """
    ret = salt_ssh_cli.run(
        "state.low", '{"state": "cmd", "fun": "run", "name": "echo blah"}'
    )
    assert (
        json.loads(ret.stdout)["localhost"]["cmd_|-echo blah_|-echo blah_|-run"][
            "changes"
        ]["stdout"]
        == "blah"
    )


@pytest.mark.slow_test
def test_state_high(salt_ssh_cli):
    """
    test state.high with salt-ssh
    """
    ret = salt_ssh_cli.run("state.high", '{"echo blah": {"cmd": ["run"]}}')
    assert (
        json.loads(ret.stdout)["localhost"]["cmd_|-echo blah_|-echo blah_|-run"][
            "changes"
        ]["stdout"]
        == "blah"
    )
