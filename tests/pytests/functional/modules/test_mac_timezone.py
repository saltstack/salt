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


@pytest.fixture
def _reset_time_server(timezone):
    ret = timezone.get_time_server()
    try:
        yield
    finally:
        if timezone.get_time_server() != ret:
            timezone.set_time_server(ret)


@pytest.fixture
def _reset_using_network_time(timezone):
    ret = timezone.get_using_network_time()
    try:
        timezone.set_using_network_time(False)
        yield ret
    finally:
        timezone.set_using_network_time(ret)


@pytest.fixture
def _reset_time(timezone, _reset_using_network_time):
    ret = timezone.get_time()
    try:
        yield
    finally:
        if not _reset_using_network_time:
            timezone.set_time(ret)


@pytest.fixture
def _reset_date(timezone, _reset_using_network_time):
    ret = timezone.get_date()
    try:
        yield
    finally:
        if not _reset_using_network_time:
            timezone.set_date(ret)


@pytest.fixture
def _reset_zone(timezone):
    ret = timezone.get_zone()
    try:
        timezone.set_zone("America/Denver")
        yield
    finally:
        timezone.set_zone(ret)


@pytest.mark.usefixtures("_reset_date")
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


@pytest.mark.usefixtures("_reset_time")
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


@pytest.mark.usefixtures("_reset_zone")
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


@pytest.mark.usefixtures("_reset_zone")
def test_get_offset(timezone):
    """
    Test timezone.get_offset
    """
    pytz = pytest.importorskip("pytz")
    now = datetime.datetime.now(tz=pytz.UTC)

    ret = timezone.set_zone("Pacific/Wake")
    assert ret
    ret = timezone.get_offset()
    assert isinstance(ret, str)
    assert ret == "+1200"

    ret = timezone.set_zone("America/Los_Angeles")
    assert ret
    ret = timezone.get_offset()
    assert isinstance(ret, str)

    if now.astimezone(pytz.timezone("America/Los_Angeles")).dst():
        assert ret == "-0700"
    else:
        assert ret == "-0800"


@pytest.mark.usefixtures("_reset_zone")
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


@pytest.mark.usefixtures("_reset_zone")
def test_zone_compare(timezone):
    """
    Test timezone.zone_compare
    """
    ret = timezone.zone_compare("America/Denver")
    assert ret
    ret = timezone.zone_compare("Pacific/Wake")
    assert not ret


@pytest.mark.usefixtures("_reset_using_network_time")
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


@pytest.mark.usefixtures("_reset_time_server")
def test_get_set_time_server(timezone):
    """
    Test timezone.get_time_server
    Test timezone.set_time_server
    """
    ret = timezone.set_time_server("spongebob.com")
    assert ret

    ret = timezone.get_time_server()
    assert ret == "spongebob.com"
