"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.modules.sensors as sensors
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {sensors: {}}


def test_sense():
    """
    Test to gather lm-sensors data from a given chip
    """
    with patch.dict(
        sensors.__salt__, {"cmd.run": MagicMock(return_value="A:a B:b C:c D:d")}
    ):
        assert sensors.sense("chip") == {"A": "a B"}
