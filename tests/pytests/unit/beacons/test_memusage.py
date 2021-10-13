"""
    tests.pytests.unit.beacons.test_memusage
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Memory usage beacon test cases
"""
from collections import namedtuple

import pytest
import salt.beacons.memusage as memusage
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {}


@pytest.fixture
def stub_memory_usage():
    return namedtuple(
        "vmem",
        "total available percent used free active inactive buffers cached shared",
    )(
        15722012672,
        9329594368,
        40.7,
        5137018880,
        4678086656,
        6991405056,
        2078953472,
        1156378624,
        4750528512,
        898908160,
    )


def test_non_list_config():
    config = {}

    ret = memusage.validate(config)
    assert ret == (False, "Configuration for memusage beacon must be a list.")


def test_empty_config():
    config = [{}]

    ret = memusage.validate(config)
    assert ret == (False, "Configuration for memusage beacon requires percent.")


def test_memusage_match(stub_memory_usage):
    with patch("psutil.virtual_memory", MagicMock(return_value=stub_memory_usage)):

        config = [{"percent": "40%"}, {"interval": 30}]

        ret = memusage.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = memusage.beacon(config)
        assert ret == [{"memusage": 40.7}]

        # Test without the percent
        config = [{"percent": 40}, {"interval": 30}]

        ret = memusage.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = memusage.beacon(config)
        assert ret == [{"memusage": 40.7}]


def test_memusage_nomatch(stub_memory_usage):
    with patch("psutil.virtual_memory", MagicMock(return_value=stub_memory_usage)):

        config = [{"percent": "70%"}]

        ret = memusage.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = memusage.beacon(config)
        assert ret != [{"memusage": 40.7}]
