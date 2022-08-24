import datetime

import pytest
import salt.modules.win_event as win_event

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.destructive_test,
]


def test__to_bytes_utf8():
    data = {'key1': 'item1',
            'key2': [1, 2, 'item2'],
            'key3': 45,
            45: str}

    new_data = win_event._to_bytes(data, 'utf-8', False)

    assert 'key1' in new_data

    assert new_data['key1'] == 'item1'.encode('utf-8')
    assert new_data['key2'][2] == 'item2'.encode('utf-8')


def test__to_bytes_cp1252():
    data = {'key1': 'item1',
            'key2': [1, 2, 'item2'],
            'key3': 45,
            45: str}

    new_data = win_event._to_bytes(data, 'CP1252', True)

    assert b'key1' in new_data
    assert b'key2' in new_data
    assert b'key3' in new_data

    assert new_data['key1'.encode('CP1252')] == 'item1'.encode('CP1252')
    assert new_data['key2'.encode('CP1252')][2] == 'item2'.encode('CP1252')


def test__raw_time():
    raw_time = win_event._raw_time(datetime.datetime(2019, 7, 2, 10, 8, 19))
    assert raw_time == (2019, 7, 2, 10, 8, 19)


def test_count():
    """
    Test win_event.count
    """
    ret = win_event.count("System")
    assert ret > 0


def test_security():
    ret = win_event.get("Security")
    print(len(ret))
    assert len(ret) > 0


def test_windows_powershell():
    ret = win_event.get("Windows PowerShell")
    print(len(ret))
    assert len(ret) > 0


def test_operational():
    ret = win_event.get("Operational")
    print(len(ret))
    assert len(ret) > 0


def test_query():

    ret = win_event.query("Microsoft-Windows-TerminalServices-LocalSessionManager/Operational", 22)
    print(len(ret))
    assert len(ret) > 0
