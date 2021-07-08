"""
Integration tests for the docker_container states
"""

import random
import string
import sys

import pytest
import salt.utils.path
from saltfactories.utils.tempfiles import temp_file
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf


def _random_name(prefix=""):
    ret = prefix
    for _ in range(8):
        ret += random.choice(string.ascii_lowercase)
    return ret


@skipIf(not salt.utils.path.which("dockerd"), "Docker not installed")
@pytest.mark.destructive_test
class DockerCallTestCase(ModuleCase, SaltReturnAssertsMixin):
    """
    Test docker_container states
    """

    def setUp(self):
        """
        setup docker.call tests
        """
        # Create temp dir
        self.random_name = _random_name(prefix="salt_test_")
        self.image_tag = sys.version_info[0]

        self.run_state("docker_image.present", tag=self.image_tag, name="python")
        self.run_state(
            "docker_container.running",
            name=self.random_name,
            image="python:{}".format(self.image_tag),
            entrypoint="tail -f /dev/null",
        )

    def tearDown(self):
        """
        teardown docker.call tests
        """
        self.run_state("docker_container.absent", name=self.random_name, force=True)
        self.run_state(
            "docker_image.absent",
            images=["python:{}".format(self.image_tag)],
            force=True,
        )
        delattr(self, "random_name")
        delattr(self, "image_tag")

    @pytest.mark.slow_test
    def test_docker_call(self):
        """
        check that docker.call works, and works with a container not running as root
        """
        ret = self.run_function("docker.call", [self.random_name, "test.ping"])
        assert ret is True

    @pytest.mark.slow_test
    def test_docker_sls(self):
        """
        check that docker.sls works, and works with a container not running as root
        """
        core_state = """
        {}/testfile:
          file:
            - managed
            - source: salt://testfile
            - makedirs: true
            """.format(
            RUNTIME_VARS.TMP
        )

        with temp_file("core.sls", core_state, RUNTIME_VARS.TMP_BASEENV_STATE_TREE):
            ret = self.run_function("docker.apply", [self.random_name, "core"])
            self.assertSaltTrueReturn(ret)

    @pytest.mark.slow_test
    def test_docker_highstate(self):
        """
        check that docker.highstate works, and works with a container not running as root
        """
        top_sls = """
        base:
          '*':
            - core
            """

        core_state = """
        {}/testfile:
          file:
            - managed
            - source: salt://testfile
            - makedirs: true
            """.format(
            RUNTIME_VARS.TMP
        )

        with temp_file(
            "top.sls", top_sls, RUNTIME_VARS.TMP_BASEENV_STATE_TREE
        ), temp_file("core.sls", core_state, RUNTIME_VARS.TMP_BASEENV_STATE_TREE):
            ret = self.run_function("docker.apply", [self.random_name])
            self.assertSaltTrueReturn(ret)
