import datetime

import pytest

import salt.modules.win_event as win_event

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture(scope="function")
def application_events():
    # This deletes the contents of the Application event log
    win_event.clear("Application")
    win_event.add("Application", 2011, event_type="Information")
    win_event.add("Application", 2011, event_type="Information")
    win_event.add("Application", 2011, event_type="Information")
    win_event.add("Application", 2011, event_type="Information")
    win_event.add("Application", 2020, event_type="Warning")
    win_event.add("Application", 2020, event_type="Warning")
    yield
    # This deletes the contents of the Application event log
    win_event.clear("Application")


def test__to_bytes_utf8():
    data = {"key1": "item1", "key2": [1, 2, "item2"], "key3": 45, 45: str}

    new_data = win_event._to_bytes(data, "utf-8", False)

    assert "key1" in new_data

    assert new_data["key1"] == b"item1"
    assert new_data["key2"][2] == b"item2"


def test__to_bytes_cp1252():
    data = {"key1": "item1", "key2": [1, 2, "item2"], "key3": 45, 45: str}

    new_data = win_event._to_bytes(data, "CP1252", True)

    assert b"key1" in new_data
    assert b"key2" in new_data
    assert b"key3" in new_data

    assert new_data["key1".encode("CP1252")] == "item1".encode("CP1252")
    assert new_data["key2".encode("CP1252")][2] == "item2".encode("CP1252")


def test__raw_time():
    raw_time = win_event._raw_time(datetime.datetime(2019, 7, 2, 10, 8, 19))
    assert raw_time == (2019, 7, 2, 10, 8, 19)


@pytest.mark.destructive_test
def test_count(application_events):
    """
    Test win_event.count
    """
    ret = win_event.count("Application")
    assert ret == 6


@pytest.mark.destructive_test
def test_get(application_events):
    ret = win_event.get("Application")
    assert len(ret) == 6


@pytest.mark.destructive_test
def test_query(application_events):
    ret = win_event.query("Application")
    assert len(ret) == 6


@pytest.mark.destructive_test
def test_query_records(application_events):
    ret = win_event.query("Application", records=3)
    for item in ret:
        assert isinstance(item, dict)
    assert len(ret) == 3


@pytest.mark.destructive_test
def test_query_raw(application_events):
    ret = win_event.query("Application", raw=True)
    for item in ret:
        assert isinstance(item, str)
    assert len(ret) == 6


@pytest.mark.destructive_test
def test_query_level(application_events):
    ret = win_event.query("Application", "*[System[(Level=3)]]")
    assert len(ret) == 2


@pytest.mark.destructive_test
def test_query_level_eventid(application_events):
    ret = win_event.query(
        "Application", "*[System[(Level=4 or Level=0) and (EventID=2011)]]"
    )
    assert len(ret) == 4


@pytest.mark.destructive_test
def test_query_last_hour(application_events):
    ret = win_event.query(
        "Application", "*[System[TimeCreated[timediff(@SystemTime) <= 3600000]]]"
    )
    assert len(ret) == 6


@pytest.mark.destructive_test
def test_get_filtered(application_events):
    ret = win_event.get_filtered("Application")
    assert len(ret) == 6


@pytest.mark.destructive_test
def test_get_filtered_event_id(application_events):
    ret = win_event.get_filtered("Application", eventID=2011)
    assert len(ret) == 4


@pytest.mark.destructive_test
def test_get_filtered_event_type(application_events):
    ret = win_event.get_filtered("Application", eventType=2)
    assert len(ret) == 2


@pytest.mark.destructive_test
def test_get_filtered_year(application_events):
    year = datetime.datetime.now().year
    ret = win_event.get_filtered("Application", year=year)
    assert len(ret) == 6


@pytest.mark.destructive_test
def test_get_filtered_year_none(application_events):
    year = 1999
    ret = win_event.get_filtered("Application", year=year)
    assert len(ret) == 0


@pytest.mark.destructive_test
def test_clear(application_events):
    assert win_event.count("Application") == 6
    win_event.clear("Application")
    assert win_event.count("Application") == 0


@pytest.mark.destructive_test
def test_clear_backup(application_events, tmp_path):
    assert win_event.count("Application") == 6
    backup_log = tmp_path / "test.bak"
    assert not backup_log.exists()
    win_event.clear("Application", str(backup_log))
    assert backup_log.exists()
    assert win_event.count("Application") == 0
