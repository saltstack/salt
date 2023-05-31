"""
unit tests for the beacon_module parameter
"""

import logging

import salt.beacons
from tests.support.mock import MagicMock, call, patch

log = logging.getLogger(__name__)


def test_beacon_process(minion_opts):
    """
    Test the process function in the beacon class
    returns the correct information when an exception
    occurs
    """
    minion_opts["id"] = "minion"
    minion_opts["__role"] = "minion"
    minion_opts["beacons"] = {
        "watch_apache": [
            {"processes": {"apache2": "stopped"}},
            {"beacon_module": "ps"},
        ]
    }
    beacon_mock = MagicMock(side_effect=Exception("Global Thermonuclear War"))
    beacon_mock.__globals__ = {}

    beacon = salt.beacons.Beacon(minion_opts, [])

    found = "ps.beacon" in beacon.beacons
    beacon.beacons["ps.beacon"] = beacon_mock
    ret = beacon.process(minion_opts["beacons"], minion_opts["grains"])

    _expected = [
        {
            "tag": "salt/beacon/minion/watch_apache/",
            "error": "Global Thermonuclear War",
            "data": {},
            "beacon_name": "ps",
        }
    ]
    assert ret == _expected


def test_beacon_process_invalid(minion_opts):
    """
    Test the process function in the beacon class
    when the configuration is invalid.
    """
    minion_opts["id"] = "minion"
    minion_opts["__role"] = "minion"

    minion_opts["beacons"] = {"status": {}}

    beacon = salt.beacons.Beacon(minion_opts, [])

    with patch.object(salt.beacons, "log") as log_mock, patch.object(
        salt.beacons.log, "error"
    ) as log_error_mock:
        ret = beacon.process(minion_opts["beacons"], minion_opts["grains"])
        log_error_mock.assert_called_with(
            "Beacon %s configuration invalid, not running.\n%s",
            "status",
            "Configuration for status beacon must be a list.",
        )

    minion_opts["beacons"] = {"mybeacon": {}}

    beacon = salt.beacons.Beacon(minion_opts, [])

    with patch.object(salt.beacons.log, "warning") as log_warn_mock, patch.object(
        salt.beacons.log, "error"
    ) as log_error_mock:
        ret = beacon.process(minion_opts["beacons"], minion_opts["grains"])
        log_warn_mock.assert_called_with(
            "No validate function found for %s, running basic beacon validation.",
            "mybeacon",
        )
        log_error_mock.assert_called_with("Configuration for beacon must be a list.")


def test_beacon_module(minion_opts):
    """
    Test that beacon_module parameter for beacon configuration
    """
    minion_opts["id"] = "minion"
    minion_opts["__role"] = "minion"
    minion_opts["beacons"] = {
        "watch_apache": [
            {"processes": {"apache2": "stopped"}},
            {"beacon_module": "ps"},
        ]
    }
    beacon = salt.beacons.Beacon(minion_opts, [])
    ret = beacon.process(minion_opts["beacons"], minion_opts["grains"])

    _expected = [
        {
            "tag": "salt/beacon/minion/watch_apache/",
            "data": {"id": "minion", "apache2": "Stopped"},
            "beacon_name": "ps",
        }
    ]
    assert ret == _expected

    # Ensure that "beacon_name" is available in the call to the beacon function
    name = "ps.beacon"
    mocked = {name: MagicMock(return_value=_expected)}
    mocked[name].__globals__ = {}
    calls = [
        call(
            [
                {"processes": {"apache2": "stopped"}},
                {"beacon_module": "ps"},
                {"_beacon_name": "watch_apache"},
            ]
        )
    ]
    with patch.object(beacon, "beacons", mocked) as patched:
        beacon.process(minion_opts["beacons"], minion_opts["grains"])
        patched[name].assert_has_calls(calls)
