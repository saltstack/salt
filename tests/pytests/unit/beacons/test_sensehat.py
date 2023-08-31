import pytest

import salt.beacons.sensehat as sensehat
from tests.support.mock import MagicMock


@pytest.fixture
def configure_loader_modules():
    return {
        sensehat: {
            "__salt__": {
                "sensehat.get_humidity": MagicMock(return_value=80),
                "sensehat.get_temperature": MagicMock(return_value=30),
                "sensehat.get_pressure": MagicMock(return_value=1500),
            },
        }
    }


def test_non_list_config():
    config = {}

    ret = sensehat.validate(config)

    assert ret == (False, "Configuration for sensehat beacon must be a list.")


def test_empty_config():
    config = [{}]

    ret = sensehat.validate(config)

    assert ret == (False, "Configuration for sensehat beacon requires sensors.")


def test_sensehat_humidity_match():

    config = [{"sensors": {"humidity": "70%"}}]

    ret = sensehat.validate(config)
    assert ret == (True, "Valid beacon configuration")

    ret = sensehat.beacon(config)
    assert ret == [{"tag": "sensehat/humidity", "humidity": 80}]

    # Test without the percent
    config = [{"sensors": {"humidity": "70%"}}]

    ret = sensehat.validate(config)
    assert ret == (True, "Valid beacon configuration")

    ret = sensehat.beacon(config)
    assert ret == [{"tag": "sensehat/humidity", "humidity": 80}]


def test_sensehat_temperature_match():

    config = [{"sensors": {"temperature": 20}}]

    ret = sensehat.validate(config)
    assert ret == (True, "Valid beacon configuration")

    ret = sensehat.beacon(config)
    assert ret == [{"tag": "sensehat/temperature", "temperature": 30}]


def test_sensehat_temperature_match_range():

    config = [{"sensors": {"temperature": [20, 29]}}]

    ret = sensehat.validate(config)
    assert ret == (True, "Valid beacon configuration")

    ret = sensehat.beacon(config)
    assert ret == [{"tag": "sensehat/temperature", "temperature": 30}]


def test_sensehat_pressure_match():

    config = [{"sensors": {"pressure": "1400"}}]

    ret = sensehat.validate(config)
    assert ret == (True, "Valid beacon configuration")

    ret = sensehat.beacon(config)
    assert ret == [{"tag": "sensehat/pressure", "pressure": 1500}]


def test_sensehat_no_match():

    config = [{"sensors": {"pressure": "1600"}}]

    ret = sensehat.validate(config)
    assert ret == (True, "Valid beacon configuration")

    ret = sensehat.beacon(config)
    assert ret == []
