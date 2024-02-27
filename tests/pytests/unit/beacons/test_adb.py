"""
    tests.pytests.unit.beacons.test_adb
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    ADB beacon test cases
"""

import pytest

import salt.beacons.adb as adb
from tests.support.mock import Mock, patch


@pytest.fixture
def configure_loader_modules():
    return {adb: {"last_state": {}, "last_state_extra": {"no_devices": False}}}


def test_no_adb_command():
    with patch("salt.utils.path.which") as mock:
        mock.return_value = None

        ret = adb.__virtual__()

        mock.assert_called_once_with("adb")
        assert ret == (False, "adb is missing.")


def test_with_adb_command():
    with patch("salt.utils.path.which") as mock:
        mock.return_value = "/usr/bin/adb"

        ret = adb.__virtual__()

        mock.assert_called_once_with("adb")
        assert ret == "adb"


def test_non_list_config():
    config = {}

    ret = adb.validate(config)
    assert ret == (False, "Configuration for adb beacon must be a list.")


def test_empty_config():
    config = [{}]

    ret = adb.validate(config)
    assert ret == (False, "Configuration for adb beacon must include a states array.")


def test_invalid_states():
    config = [{"states": ["Random", "Failings"]}]

    ret = adb.validate(config)
    assert ret == (
        False,
        "Need a one of the following adb states: offline, bootloader, device, host,"
        " recovery, no permissions, sideload, unauthorized, unknown, missing",
    )


def test_device_state():
    config = [{"states": ["device"]}]

    mock = Mock(return_value="List of devices attached\nHTC\tdevice")
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        assert ret == [{"device": "HTC", "state": "device", "tag": "device"}]


def test_device_state_change():
    config = [{"states": ["offline"]}]

    out = [
        "List of devices attached\nHTC\tdevice",
        "List of devices attached\nHTC\toffline",
    ]

    mock = Mock(side_effect=out)
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        assert ret == []

        ret = adb.beacon(config)
        assert ret == [{"device": "HTC", "state": "offline", "tag": "offline"}]


def test_multiple_devices():
    config = [{"states": ["offline", "device"]}]

    out = [
        "List of devices attached\nHTC\tdevice",
        "List of devices attached\nHTC\toffline\nNexus\tdevice",
    ]

    mock = Mock(side_effect=out)
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        assert ret == [{"device": "HTC", "state": "device", "tag": "device"}]

        ret = adb.beacon(config)
        assert ret == [
            {"device": "HTC", "state": "offline", "tag": "offline"},
            {"device": "Nexus", "state": "device", "tag": "device"},
        ]


def test_no_devices_with_different_states():
    config = [{"states": ["offline"], "no_devices_event": True}]

    mock = Mock(return_value="List of devices attached\nHTC\tdevice")
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        assert ret == []


def test_no_devices_no_repeat():
    config = [{"states": ["offline", "device"], "no_devices_event": True}]

    out = [
        "List of devices attached\nHTC\tdevice",
        "List of devices attached",
        "List of devices attached",
    ]

    mock = Mock(side_effect=out)
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        assert ret == [{"device": "HTC", "state": "device", "tag": "device"}]

        ret = adb.beacon(config)
        assert ret == [{"tag": "no_devices"}]

        ret = adb.beacon(config)
        assert ret == []


def test_no_devices():
    config = [{"states": ["offline", "device"], "no_devices_event": True}]

    out = ["List of devices attached", "List of devices attached"]

    mock = Mock(side_effect=out)
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        assert ret == [{"tag": "no_devices"}]

        ret = adb.beacon(config)
        assert ret == []


def test_device_missing():
    config = [{"states": ["device", "missing"]}]

    out = [
        "List of devices attached\nHTC\tdevice",
        "List of devices attached",
        "List of devices attached\nHTC\tdevice",
        "List of devices attached\nHTC\tdevice",
    ]

    mock = Mock(side_effect=out)
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        assert ret == [{"device": "HTC", "state": "device", "tag": "device"}]

        ret = adb.beacon(config)
        assert ret == [{"device": "HTC", "state": "missing", "tag": "missing"}]

        ret = adb.beacon(config)
        assert ret == [{"device": "HTC", "state": "device", "tag": "device"}]

        ret = adb.beacon(config)
        assert ret == []


def test_with_startup():
    config = [{"states": ["device"]}]

    mock = Mock(
        return_value=(
            "* daemon started successfully *\nList of devices attached\nHTC\tdevice"
        ),
    )
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        assert ret == [{"device": "HTC", "state": "device", "tag": "device"}]


def test_with_user():
    config = [{"states": ["device"], "user": "fred"}]

    mock = Mock(
        return_value=(
            "* daemon started successfully *\nList of devices attached\nHTC\tdevice"
        )
    )
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        mock.assert_called_once_with("adb devices", runas="fred")
        assert ret == [{"device": "HTC", "state": "device", "tag": "device"}]


def test_device_low_battery():
    config = [{"states": ["device"], "battery_low": 30}]

    out = [
        "List of devices attached\nHTC\tdevice",
        "25",
    ]

    mock = Mock(side_effect=out)
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        assert ret == [
            {"device": "HTC", "state": "device", "tag": "device"},
            {"device": "HTC", "battery_level": 25, "tag": "battery_low"},
        ]


def test_device_no_repeat():
    config = [{"states": ["device"], "battery_low": 30}]

    out = [
        "List of devices attached\nHTC\tdevice",
        "25",
        "List of devices attached\nHTC\tdevice",
        "25",
    ]

    mock = Mock(side_effect=out)
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        assert ret == [
            {"device": "HTC", "state": "device", "tag": "device"},
            {"device": "HTC", "battery_level": 25, "tag": "battery_low"},
        ]

        ret = adb.beacon(config)
        assert ret == []


def test_device_no_repeat_capacity_increase():
    config = [{"states": ["device"], "battery_low": 75}]

    out = [
        "List of devices attached\nHTC\tdevice",
        "25",
        "List of devices attached\nHTC\tdevice",
        "30",
    ]

    mock = Mock(side_effect=out)
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        assert ret == [
            {"device": "HTC", "state": "device", "tag": "device"},
            {"device": "HTC", "battery_level": 25, "tag": "battery_low"},
        ]

        ret = adb.beacon(config)
        assert ret == []


def test_device_no_repeat_with_not_found_state():
    config = [{"states": ["offline"], "battery_low": 30}]

    out = [
        "List of devices attached\nHTC\tdevice",
        "25",
        "List of devices attached\nHTC\tdevice",
        "25",
    ]

    mock = Mock(side_effect=out)
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        assert ret == [{"device": "HTC", "battery_level": 25, "tag": "battery_low"}]

        ret = adb.beacon(config)
        assert ret == []


def test_device_battery_charged():
    config = [{"states": ["device"], "battery_low": 30}]

    out = [
        "List of devices attached\nHTC\tdevice",
        "100",
    ]

    mock = Mock(side_effect=out)
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        assert ret == [{"device": "HTC", "state": "device", "tag": "device"}]


def test_device_low_battery_equal():
    config = [{"states": ["device"], "battery_low": 25}]

    out = [
        "List of devices attached\nHTC\tdevice",
        "25",
    ]

    mock = Mock(side_effect=out)
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        assert ret == [
            {"device": "HTC", "state": "device", "tag": "device"},
            {"device": "HTC", "battery_level": 25, "tag": "battery_low"},
        ]


def test_device_battery_not_found():
    config = [{"states": ["device"], "battery_low": 25}]

    out = [
        "List of devices attached\nHTC\tdevice",
        "/system/bin/sh: cat: /sys/class/power_supply/*/capacity: No such file or"
        " directory",
    ]

    mock = Mock(side_effect=out)
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        assert ret == [{"device": "HTC", "state": "device", "tag": "device"}]


def test_device_repeat_multi():
    config = [{"states": ["offline"], "battery_low": 35}]

    out = [
        "List of devices attached\nHTC\tdevice",
        "25",
        "List of devices attached\nHTC\tdevice",
        "40",
        "List of devices attached\nHTC\tdevice",
        "25",
        "List of devices attached\nHTC\tdevice",
        "80",
    ]

    mock = Mock(side_effect=out)
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        assert ret == [{"device": "HTC", "battery_level": 25, "tag": "battery_low"}]

        ret = adb.beacon(config)
        assert ret == []

        ret = adb.beacon(config)
        assert ret == [{"device": "HTC", "battery_level": 25, "tag": "battery_low"}]

        ret = adb.beacon(config)
        assert ret == []


def test_weird_batteries():
    config = [{"states": ["device"], "battery_low": 25}]

    out = [
        "List of devices attached\nHTC\tdevice",
        "-9000",
    ]

    mock = Mock(side_effect=out)
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        assert ret == [{"device": "HTC", "state": "device", "tag": "device"}]


def test_multiple_batteries():
    config = [{"states": ["device"], "battery_low": 30}]

    out = [
        "List of devices attached\nHTC\tdevice",
        "25\n40",
    ]

    mock = Mock(side_effect=out)
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        assert ret == [
            {"device": "HTC", "state": "device", "tag": "device"},
            {"device": "HTC", "battery_level": 25, "tag": "battery_low"},
        ]


def test_multiple_low_batteries():
    config = [{"states": ["device"], "battery_low": 30}]

    out = [
        "List of devices attached\nHTC\tdevice",
        "25\n14",
    ]

    mock = Mock(side_effect=out)
    with patch.dict(adb.__salt__, {"cmd.run": mock}):
        ret = adb.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = adb.beacon(config)
        assert ret == [
            {"device": "HTC", "state": "device", "tag": "device"},
            {"device": "HTC", "battery_level": 25, "tag": "battery_low"},
        ]
