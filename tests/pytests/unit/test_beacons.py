"""
unit tests for the beacon_module parameter
"""

import logging

import salt.config
from tests.support.mock import MagicMock, call, patch

log = logging.getLogger(__name__)


def test_beacon_process():
    """
    Test the process function in the beacon class
    returns the correct information when an exception
    occurs
    """
    mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
    mock_opts["id"] = "minion"
    mock_opts["__role"] = "minion"
    mock_opts["beacons"] = {
        "watch_apache": [
            {"processes": {"apache2": "stopped"}},
            {"beacon_module": "ps"},
        ]
    }
    beacon_mock = MagicMock(side_effect=Exception("Global Thermonuclear War"))
    beacon_mock.__globals__ = {}

    beacon = salt.beacons.Beacon(mock_opts, [])

    found = "ps.beacon" in beacon.beacons
    beacon.beacons["ps.beacon"] = beacon_mock
    ret = beacon.process(mock_opts["beacons"], mock_opts["grains"])

    _expected = [
        {
            "tag": "salt/beacon/minion/watch_apache/",
            "error": "Global Thermonuclear War",
            "data": {},
            "beacon_name": "ps",
        }
    ]
    assert ret == _expected


def test_beacon_module():
    """
    Test that beacon_module parameter for beacon configuration
    """
    mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
    mock_opts["id"] = "minion"
    mock_opts["__role"] = "minion"
    mock_opts["beacons"] = {
        "watch_apache": [
            {"processes": {"apache2": "stopped"}},
            {"beacon_module": "ps"},
        ]
    }
    beacon = salt.beacons.Beacon(mock_opts, [])
    ret = beacon.process(mock_opts["beacons"], mock_opts["grains"])

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
        beacon.process(mock_opts["beacons"], mock_opts["grains"])
        patched[name].assert_has_calls(calls)
