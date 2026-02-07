import pytest

from salt.netapi.rest_cherrypy import parse_timeout


@pytest.mark.parametrize(
    "value, expected",
    [
        ("60", 60),
        (60, 60),
        ("2.5", 2.5),
        ("0", 0),
        ("None", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_timeout_valid(value, expected):
    assert parse_timeout(value) == expected


@pytest.mark.parametrize("value", ["nope", {}, [], True, -1, "-5"])
def test_parse_timeout_invalid(value):
    with pytest.raises(ValueError):
        parse_timeout(value)

