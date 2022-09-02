"""
    tests.pytests.unit.beacons.test_bonjour_announce
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Bonjour announce beacon test cases
"""
import pytest

import salt.beacons.bonjour_announce as bonjour_announce


@pytest.fixture
def configure_loader_modules():
    return {
        bonjour_announce: {"last_state": {}, "last_state_extra": {"no_devices": False}}
    }


def test_non_list_config():
    config = {}

    ret = bonjour_announce.validate(config)
    assert ret == (False, "Configuration for bonjour_announce beacon must be a list.")


def test_empty_config():
    config = [{}]

    ret = bonjour_announce.validate(config)
    assert ret == (
        False,
        "Configuration for bonjour_announce beacon must contain servicetype, port and"
        " txt items.",
    )
