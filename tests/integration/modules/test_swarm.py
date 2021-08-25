"""
Integration tests for the docker swarm modules
"""

import pytest
import salt.utils.path
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.unit import skipIf


@skipIf(
    not any(salt.utils.path.which(exe) for exe in ("dockerd", "docker")),
    "Docker not installed",
)
@pytest.mark.destructive_test
class SwarmCallTestCase(ModuleCase, SaltReturnAssertsMixin):
    """
    Test docker swarm states
    """

    @pytest.mark.slow_test
    def test_swarm_init(self):
        """
        check that swarm.swarm_init works when a swarm exists
        """
        self.run_function("swarm.swarm_init", ["127.0.0.1", "0.0.0.0", False])
        ret = self.run_function("swarm.swarm_init", ["127.0.0.1", "0.0.0.0", False])
        expected = {
            "Comment": (
                'This node is already part of a swarm. Use "docker swarm leave" to'
                " leave this swarm and join another one."
            ),
            "result": False,
        }
        self.assertEqual(expected, ret)
