"""
    tests.pytests.unit.beacons.test_load
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Load beacon test cases
"""

import pytest

import salt.beacons.load as load
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {load: {"__context__": {}, "__salt__": {}}}


def test_non_list_config():
    config = {}

    ret = load.validate(config)
    assert ret == (False, "Configuration for load beacon must be a list.")


def test_empty_config():
    config = [{}]

    ret = load.validate(config)
    assert ret == (False, "Averages configuration is required for load beacon.")


@pytest.mark.skip_on_windows(reason="os.getloadavg not available on Windows")
def test_load_match():
    with patch("os.getloadavg", MagicMock(return_value=(1.82, 1.84, 1.56))):
        config = [
            {
                "averages": {"1m": [0.0, 2.0], "5m": [0.0, 1.5], "15m": [0.0, 1.0]},
                "emitatstartup": True,
                "onchangeonly": False,
            }
        ]

        ret = load.validate(config)
        assert ret == (True, "Valid beacon configuration")

        _expected_return = [{"1m": 1.82, "5m": 1.84, "15m": 1.56}]
        ret = load.beacon(config)
        assert ret == _expected_return
