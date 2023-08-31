"""
Integration tests for the docker_container states
"""
import logging

import pytest
from saltfactories.utils import random_string
from saltfactories.utils.functional import StateResult

pytest.importorskip("docker")

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("docker", "dockerd", check_all=False),
]


@pytest.fixture(scope="module")
def state_tree(state_tree):
    top_sls = """
    base:
      '*':
        - core
    """
    core_state = """
    /tmp/foo/testfile:
      file:
        - managed
        - source: salt://testfile
        - makedirs: true
    """
    testfile = "foo"

    with pytest.helpers.temp_file(
        "top.sls", top_sls, state_tree
    ), pytest.helpers.temp_file(
        "core.sls", core_state, state_tree
    ), pytest.helpers.temp_file(
        "testfile", testfile, state_tree
    ):
        yield state_tree


@pytest.fixture(scope="module")
def container(salt_factories, state_tree):

    factory = salt_factories.get_container(
        random_string("python-3-"),
        image_name="ghcr.io/saltstack/salt-ci-containers/python:3",
        container_run_kwargs={
            "ports": {"8500/tcp": None},
            "entrypoint": "tail -f /dev/null",
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )

    with factory.started():
        yield factory


@pytest.fixture
def docker(modules, container):
    return modules.docker


def test_docker_call(docker, container):
    """
    check that docker.call works, and works with a container not running as root
    """
    ret = docker.call(container.name, "test.ping")
    assert ret is True


def test_docker_sls(docker, container, state_tree, tmp_path):
    """
    check that docker.sls works, and works with a container not running as root
    """
    ret = StateResult(docker.apply(container.name, "core"))
    assert ret.result is True


def test_docker_highstate(docker, container, state_tree, tmp_path):
    """
    check that docker.highstate works, and works with a container not running as root
    """
    ret = StateResult(docker.apply(container.name))
    assert ret.result is True
