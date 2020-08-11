# coding: utf-8
from __future__ import absolute_import

import pytest
import salt.beacons.sensehat as sensehat
from tests.support.mock import MagicMock


@pytest.fixture(autouse=True)
def setup_loader(request):
    setup_loader_modules = {
        sensehat: {
            "__salt__": {
                "sensehat.get_humidity": MagicMock(return_value=80),
                "sensehat.get_temperature": MagicMock(return_value=30),
                "sensehat.get_pressure": MagicMock(return_value=1500),
            },
        }
    }
    with pytest.helpers.loader_mock(request, setup_loader_modules) as loader_mock:
        yield loader_mock


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
