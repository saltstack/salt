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


def test_close_beacons_calls_close_on_modules(minion_opts):
    """
    Test that close_beacons() calls the close function on each beacon
    module that provides one, releasing resources like inotify fds.

    See: https://github.com/saltstack/salt/issues/66449
    """
    minion_opts["id"] = "minion"
    minion_opts["__role"] = "minion"
    minion_opts["beacons"] = {
        "inotify": [
            {"files": {"/etc/fstab": {}}},
        ],
    }

    beacon = salt.beacons.Beacon(minion_opts, [])

    close_mock = MagicMock()
    beacon.beacons["inotify.close"] = close_mock

    beacon.close_beacons()

    close_mock.assert_called_once()
    call_args = close_mock.call_args[0][0]
    assert isinstance(call_args, list)
    assert {"_beacon_name": "inotify"} in call_args


def test_close_beacons_with_beacon_module_override(minion_opts):
    """
    Test that close_beacons() respects beacon_module and calls close
    on the correct underlying module name.
    """
    minion_opts["id"] = "minion"
    minion_opts["__role"] = "minion"
    minion_opts["beacons"] = {
        "watch_apache": [
            {"processes": {"apache2": "stopped"}},
            {"beacon_module": "ps"},
        ],
    }

    beacon = salt.beacons.Beacon(minion_opts, [])

    close_mock = MagicMock()
    beacon.beacons["ps.close"] = close_mock

    beacon.close_beacons()

    close_mock.assert_called_once()
    call_args = close_mock.call_args[0][0]
    assert {"_beacon_name": "watch_apache"} in call_args


def test_close_beacons_skips_modules_without_close(minion_opts):
    """
    Test that close_beacons() gracefully skips beacons that don't
    have a close function.
    """
    minion_opts["id"] = "minion"
    minion_opts["__role"] = "minion"
    minion_opts["beacons"] = {
        "status": [
            {"time": ["all"]},
        ],
    }

    beacon = salt.beacons.Beacon(minion_opts, [])

    assert "status.close" not in beacon.beacons
    beacon.close_beacons()


def test_delete_beacon_calls_close(minion_opts):
    """
    Test that delete_beacon() calls the beacon's close function before
    removing it, so resources like inotify file descriptors are released.
    """
    minion_opts["id"] = "minion"
    minion_opts["__role"] = "minion"
    minion_opts["beacons"] = {
        "inotify": [
            {"files": {"/etc/fstab": {}}},
        ],
    }

    beacon = salt.beacons.Beacon(minion_opts, [])
    close_mock = MagicMock()
    beacon.beacons["inotify.close"] = close_mock

    with patch("salt.utils.event.get_event"):
        beacon.delete_beacon("inotify")

    close_mock.assert_called_once()
    call_args = close_mock.call_args[0][0]
    assert isinstance(call_args, list)
    assert {"_beacon_name": "inotify"} in call_args
    assert "inotify" not in minion_opts["beacons"]


def test_delete_beacon_calls_close_with_beacon_module(minion_opts):
    """
    Test that delete_beacon() respects beacon_module and calls close
    on the correct underlying module.
    """
    minion_opts["id"] = "minion"
    minion_opts["__role"] = "minion"
    minion_opts["beacons"] = {
        "watch_apache": [
            {"processes": {"apache2": "stopped"}},
            {"beacon_module": "ps"},
        ],
    }

    beacon = salt.beacons.Beacon(minion_opts, [])
    close_mock = MagicMock()
    beacon.beacons["ps.close"] = close_mock

    with patch("salt.utils.event.get_event"):
        beacon.delete_beacon("watch_apache")

    close_mock.assert_called_once()
    call_args = close_mock.call_args[0][0]
    assert {"_beacon_name": "watch_apache"} in call_args
    assert "watch_apache" not in minion_opts["beacons"]


def test_delete_beacon_without_close(minion_opts):
    """
    Test that delete_beacon() works when the beacon module has no close function.
    """
    minion_opts["id"] = "minion"
    minion_opts["__role"] = "minion"
    minion_opts["beacons"] = {
        "status": [
            {"time": ["all"]},
        ],
    }

    beacon = salt.beacons.Beacon(minion_opts, [])
    assert "status.close" not in beacon.beacons

    with patch("salt.utils.event.get_event"):
        beacon.delete_beacon("status")

    assert "status" not in minion_opts["beacons"]
