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

from salt.exceptions import SaltInvocationError

pytestmark = [
    pytest.mark.skip_if_binaries_missing("systemsetup"),
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="module")
def timezone(modules):
    return modules.timezone


@pytest.fixture(scope="function", autouse=True)
def _setup_teardown_vars(timezone):
    USE_NETWORK_TIME = timezone.get_using_network_time()
    TIME_SERVER = timezone.get_time_server()
    TIME_ZONE = timezone.get_zone()
    CURRENT_DATE = timezone.get_date()
    CURRENT_TIME = timezone.get_time()

    timezone.set_using_network_time(False)
    timezone.set_zone("America/Denver")

    try:
        yield
    finally:
        timezone.set_time_server(TIME_SERVER)
        timezone.set_using_network_time(USE_NETWORK_TIME)
        timezone.set_zone(TIME_ZONE)
        if not USE_NETWORK_TIME:
            timezone.set_date(CURRENT_DATE)
            timezone.set_time(CURRENT_TIME)


@pytest.mark.destructive_test
def test_get_set_date(timezone):
    """
    Test timezone.get_date
    Test timezone.set_date
    """
    # Correct Functionality
    ret = timezone.set_date("2/20/2011")
    assert ret
    ret = timezone.get_date()
    assert ret == "2/20/2011"

    # Test bad date format
    with pytest.raises(SaltInvocationError) as exc:
        ret = timezone.set_date("13/12/2014")
        assert (
            "ERROR executing 'timezone.set_date': Invalid Date/Time Format: 13/12/2014"
            in str(exc.value)
        )


@pytest.mark.slow_test
def test_get_time(timezone):
    """
    Test timezone.get_time
    """
    text_time = timezone.get_time()
    assert text_time != "Invalid Timestamp"
    obj_date = datetime.datetime.strptime(text_time, "%H:%M:%S")
    assert isinstance(obj_date, datetime.date)


@pytest.mark.destructive_test
def test_set_time(timezone):
    """
    Test timezone.set_time
    """
    # Correct Functionality
    ret = timezone.set_time("3:14")
    assert ret

    # Test bad time format
    with pytest.raises(SaltInvocationError) as exc:
        ret = timezone.set_time("3:71")
        assert (
            "ERROR executing 'timezone.set_time': Invalid Date/Time Format: 3:71"
            in str(exc.value)
        )


@pytest.mark.destructive_test
def test_get_set_zone(timezone):
    """
    Test timezone.get_zone
    Test timezone.set_zone
    """
    # Correct Functionality
    ret = timezone.set_zone("Pacific/Wake")
    assert ret

    ret = timezone.get_zone()
    assert ret == "Pacific/Wake"

    # Test bad time zone
    with pytest.raises(SaltInvocationError) as exc:
        ret = timezone.set_zone("spongebob")
        assert (
            "ERROR executing 'timezone.set_zone': Invalid Timezone: spongebob"
            in str(exc.value)
        )


@pytest.mark.destructive_test
def test_get_offset(timezone):
    """
    Test timezone.get_offset
    """
    ret = timezone.set_zone("Pacific/Wake")
    assert ret
    ret = timezone.get_offset()
    assert isinstance(ret, str)
    assert ret == "+1200"

    ret = timezone.set_zone("America/Los_Angeles")
    assert ret
    ret = timezone.get_offset()
    assert isinstance(ret, str)
    assert ret == "-0800"


@pytest.mark.destructive_test
def test_get_set_zonecode(timezone):
    """
    Test timezone.get_zonecode
    Test timezone.set_zonecode
    """
    ret = timezone.set_zone("America/Los_Angeles")
    assert ret
    ret = timezone.get_zone()
    assert isinstance(ret, str)
    assert ret == "America/Los_Angeles"

    ret = timezone.set_zone("Pacific/Wake")
    assert ret
    ret = timezone.get_zone()
    assert isinstance(ret, str)
    assert ret == "Pacific/Wake"


@pytest.mark.slow_test
def test_list_zones(timezone):
    """
    Test timezone.list_zones
    """
    zones = timezone.list_zones()
    assert isinstance(zones, list)
    assert "America/Denver" in zones
    assert "America/Los_Angeles" in zones


@pytest.mark.destructive_test
def test_zone_compare(timezone):
    """
    Test timezone.zone_compare
    """
    ret = timezone.set_zone("America/Denver")
    assert ret
    ret = timezone.zone_compare("America/Denver")
    assert ret
    ret = timezone.zone_compare("Pacific/Wake")
    assert not ret


@pytest.mark.destructive_test
def test_get_set_using_network_time(timezone):
    """
    Test timezone.get_using_network_time
    Test timezone.set_using_network_time
    """
    ret = timezone.set_using_network_time(True)
    assert ret

    ret = timezone.get_using_network_time()
    assert ret

    ret = timezone.set_using_network_time(False)
    assert ret

    ret = timezone.get_using_network_time()
    assert not ret


@pytest.mark.destructive_test
def test_get_set_time_server(timezone):
    """
    Test timezone.get_time_server
    Test timezone.set_time_server
    """
    ret = timezone.set_time_server("spongebob.com")
    assert ret

    ret = timezone.get_time_server()
    assert ret == "spongebob.com"
