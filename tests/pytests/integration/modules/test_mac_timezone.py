"""
Integration tests for mac_timezone

If using parallels, make sure Time sync is turned off. Otherwise, parallels will
keep changing your date/time settings while the tests are running. To turn off
Time sync do the following:
    - Go to actions -> configure
    - Select options at the top and 'More Options' on the left
    - Set time to 'Do not sync'
"""

import datetime

import pytest

pytestmark = [
    pytest.mark.flaky(max_runs=4),
    pytest.mark.skip_if_binaries_missing("systemsetup"),
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="function")
def setup_teardown_vars(salt_call_cli):
    USE_NETWORK_TIME = salt_call_cli.run("timezone.get_using_network_time")
    TIME_SERVER = salt_call_cli.run("timezone.get_time_server")
    TIME_ZONE = salt_call_cli.run("timezone.get_zone")
    CURRENT_DATE = salt_call_cli.run("timezone.get_date")
    CURRENT_TIME = salt_call_cli.run("timezone.get_time")

    salt_call_cli.run("timezone.set_using_network_time", False)
    salt_call_cli.run("timezone.set_zone", "America/Denver")

    try:
        yield
    finally:
        salt_call_cli.run("timezone.set_time_server", TIME_SERVER)
        salt_call_cli.run("timezone.set_using_network_time", USE_NETWORK_TIME)
        salt_call_cli.run("timezone.set_zone", TIME_ZONE)
        if not USE_NETWORK_TIME:
            salt_call_cli.run("timezone.set_date", CURRENT_DATE)
            salt_call_cli.run("timezone.set_time", CURRENT_TIME)


@pytest.mark.skip(
    reason="Skip until we can figure out why modifying the system clock causes ZMQ errors",
)
@pytest.mark.destructive_test
def test_get_set_date(salt_call_cli):
    """
    Test timezone.get_date
    Test timezone.set_date
    """
    # Correct Functionality
    ret = salt_call_cli.run("timezone.set_date", "2/20/2011")
    assert ret.data
    ret = salt_call_cli.run("timezone.get_date")
    assert ret.data == "2/20/2011"

    # Test bad date format
    ret = salt_call_cli.run("timezone.set_date", "13/12/2014")
    assert (
        ret.stderr
        == "ERROR executing 'timezone.set_date': Invalid Date/Time Format: 13/12/2014"
    )


@pytest.mark.slow_test
def test_get_time(salt_call_cli):
    """
    Test timezone.get_time
    """
    text_time = salt_call_cli.run("timezone.get_time")
    assert text_time.data != "Invalid Timestamp"
    obj_date = datetime.datetime.strptime(text_time.data, "%H:%M:%S")
    assert isinstance(obj_date, datetime.date)


@pytest.mark.skip(
    reason="Skip until we can figure out why modifying the system clock causes ZMQ errors",
)
@pytest.mark.destructive_test
def test_set_time(salt_call_cli):
    """
    Test timezone.set_time
    """
    # Correct Functionality
    ret = salt_call_cli.run("timezone.set_time", "3:14")
    assert ret.data

    # Test bad time format
    ret = salt_call_cli.run("timezone.set_time", "3:71")
    assert (
        ret.stderr
        == "ERROR executing 'timezone.set_time': Invalid Date/Time Format: 3:71"
    )


@pytest.mark.skip(
    reason="Skip until we can figure out why modifying the system clock causes ZMQ errors",
)
@pytest.mark.destructive_test
def test_get_set_zone(salt_call_cli):
    """
    Test timezone.get_zone
    Test timezone.set_zone
    """
    # Correct Functionality
    ret = salt_call_cli.run("timezone.set_zone", "Pacific/Wake")
    assert ret.data
    assert ret.data == "Pacific/Wake"

    # Test bad time zone
    ret = salt_call_cli.run("timezone.set_zone", "spongebob")
    assert (
        ret.stderr == "ERROR executing 'timezone.set_zone': Invalid Timezone: spongebob"
    )


@pytest.mark.skip(
    reason="Skip until we can figure out why modifying the system clock causes ZMQ errors",
)
@pytest.mark.destructive_test
def test_get_offset(salt_call_cli):
    """
    Test timezone.get_offset
    """
    ret = salt_call_cli.run("timezone.set_zone", "Pacific/Wake")
    assert ret.data
    ret = salt_call_cli.run("timezone.get_offset")
    assert isinstance(ret.data, str)
    assert ret.data == "+1200"

    ret = salt_call_cli.run("timezone.set_zone", "America/Los_Angeles")
    assert ret.data
    assert isinstance(ret.data, str)
    assert ret.data == "-0700"


@pytest.mark.skip(
    reason="Skip until we can figure out why modifying the system clock causes ZMQ errors",
)
@pytest.mark.destructive_test
def test_get_set_zonecode(salt_call_cli):
    """
    Test timezone.get_zonecode
    Test timezone.set_zonecode
    """
    ret = salt_call_cli.run("timezone.set_zone", "America/Los_Angeles")
    assert ret.data
    assert isinstance(ret.data, str)
    assert ret.data == "PDT"

    ret = salt_call_cli.run("timezone.set_zone", "Pacific/Wake")
    assert ret.data
    assert isinstance(ret.data, str)
    assert ret.data == "WAKT"


@pytest.mark.slow_test
def test_list_zones(salt_call_cli):
    """
    Test timezone.list_zones
    """
    zones = salt_call_cli.run("timezone.list_zones")
    assert isinstance(zones.data, list)
    assert "America/Denver" in zones.data
    assert "America/Los_Angeles" in zones.data


@pytest.mark.skip(
    reason="Skip until we can figure out why modifying the system clock causes ZMQ errors",
)
@pytest.mark.destructive_test
def test_zone_compare(salt_call_cli):
    """
    Test timezone.zone_compare
    """
    ret = salt_call_cli.run("timezone.set_zone", "America/Denver")
    assert ret.data
    ret = salt_call_cli.run("timezone.zone_compare", "America/Denver")
    assert ret.data
    ret = salt_call_cli.run("timezone.zone_compare", "Pacific/Wake")
    assert not ret.data


@pytest.mark.skip(
    reason="Skip until we can figure out why modifying the system clock causes ZMQ errors",
)
@pytest.mark.destructive_test
def test_get_set_using_network_time(salt_call_cli):
    """
    Test timezone.get_using_network_time
    Test timezone.set_using_network_time
    """
    ret = salt_call_cli.run("timezone.set_using_network_time", True)
    assert ret.data

    ret = salt_call_cli.run("timezone.get_using_network_time")
    assert ret.data

    ret = salt_call_cli.run("timezone.set_using_network_time", False)
    assert ret.data

    ret = salt_call_cli.run("timezone.get_using_network_time")
    assert not ret.data


@pytest.mark.skip(
    reason="Skip until we can figure out why modifying the system clock causes ZMQ errors",
)
@pytest.mark.destructive_test
def test_get_set_time_server(salt_call_cli):
    """
    Test timezone.get_time_server
    Test timezone.set_time_server
    """
    ret = salt_call_cli.run("timezone.set_time_server", "spongebob.com")
    assert ret.data

    ret = salt_call_cli.run("timezone.get_time_server") == "spongebob.com"
    assert ret.data
