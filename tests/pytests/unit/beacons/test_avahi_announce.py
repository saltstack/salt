"""
    tests.pytests.unit.beacons.test_avahi_announce
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Avahi announce beacon test cases
"""
import pytest

import salt.beacons.avahi_announce as avahi_announce


@pytest.fixture
def configure_loader_modules():
    return {
        avahi_announce: {"last_state": {}, "last_state_extra": {"no_devices": False}}
    }


def test_non_list_config():
    config = {}

    ret = avahi_announce.validate(config)
    assert ret == (False, "Configuration for avahi_announce beacon must be a list.")


def test_empty_config():
    config = [{}]

    ret = avahi_announce.validate(config)
    assert ret == (
        False,
        "Configuration for avahi_announce beacon must contain servicetype, port and txt"
        " items.",
    )
