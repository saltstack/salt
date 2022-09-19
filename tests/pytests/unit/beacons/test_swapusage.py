"""
    tests.pytests.unit.beacons.test_swapusage
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Swap usage beacon test cases
"""
from collections import namedtuple

import pytest

import salt.beacons.swapusage as swapusage
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {}


@pytest.fixture
def stub_swap_usage():
    return namedtuple("sswap", "total used free percent sin sout")(
        17179865088,
        1674412032,
        15505453056,
        9.7,
        1572110336,
        3880046592,
    )


def test_non_list_config():
    config = {}

    ret = swapusage.validate(config)
    assert ret == (False, "Configuration for swapusage beacon must be a list.")


def test_empty_config():
    config = [{}]

    ret = swapusage.validate(config)
    assert ret == (False, "Configuration for swapusage beacon requires percent.")


def test_swapusage_match(stub_swap_usage):
    with patch("psutil.swap_memory", MagicMock(return_value=stub_swap_usage)):

        config = [{"percent": "9%"}, {"interval": 30}]

        ret = swapusage.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = swapusage.beacon(config)
        assert ret == [{"swapusage": 9.7}]

        # Test without the percent
        config = [{"percent": 9}, {"interval": 30}]

        ret = swapusage.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = swapusage.beacon(config)
        assert ret == [{"swapusage": 9.7}]


def test_swapusage_nomatch(stub_swap_usage):
    with patch("psutil.swap_memory", MagicMock(return_value=stub_swap_usage)):

        config = [{"percent": "10%"}]

        ret = swapusage.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = swapusage.beacon(config)
        assert ret != [{"swapusage": 9.7}]
