import datetime

import pytest

import salt.utils.timeutil as time


def test_utcfromtimestamp_epoch_naive():
    dt = time.utcfromtimestamp(0)
    assert dt.tzinfo is None
    assert dt == datetime.datetime(1970, 1, 1, 0, 0, 0)


def test_utcnow_is_naive():
    dt = time.utcnow()
    assert dt.tzinfo is None
    assert isinstance(dt, datetime.datetime)


@pytest.mark.parametrize(
    "inpt,expected",
    [
        (60.0, 60.0),
        (60, 60.0),
        ("60", 60.0),
        ("60s", 60.0),
        ("2m", 120.0),
        ("1h", 3600.0),
        ("1d", 86400.0),
        ("1.5s", 1.5),
        ("1.5m", 90.0),
        ("1.5h", 5400.0),
        ("7.5d", 648000.0),
    ],
)
def test_timestring_map(inpt, expected):
    assert time.timestring_map(inpt) == expected
