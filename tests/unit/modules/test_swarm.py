# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.swarm

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase


class SwarmTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.swarm
    """

    def setup_loader_modules(self):
        return {salt.modules.swarm: {}}

    def test___virtual___valid_docker_module(self):
        """
        Test that __virtual__ requires a proper loaded docker library
        """

        class ValidDockerModule(object):
            class APIClient:
                pass

            def from_env(self):
                pass

        with patch(
            "salt.modules.swarm.HAS_DOCKER",
            salt.modules.swarm._is_docker_module(ValidDockerModule()),
        ):
            self.assertEqual(
                salt.modules.swarm.__virtual__(), salt.modules.swarm.__virtualname__
            )

    def test___virtual___not_valid_docker_module(self):
        class NotValidDockerModule(object):
            pass

        with patch(
            "salt.modules.swarm.HAS_DOCKER",
            salt.modules.swarm._is_docker_module(NotValidDockerModule()),
        ):
            ret = salt.modules.swarm.__virtual__()
            self.assertEqual(len(ret), 2)
            self.assertFalse(ret[0])
