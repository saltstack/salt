import pytest

from salt.utils import win_runas


@pytest.mark.parametrize(
    "input_value, expected",
    [
        ("test_user", "test_user"),  # Simple system name
        ("domain\\test_user", "test_user"),  # Sam name
        ("domain.com\\test_user", "test_user"),  # Sam name with com
        ("test_user@domain", "test_user"),  # UPN Name
        ("test_user@domain.com", "test_user"),  # UPN Name with dom
    ]
)
def test_get_username(input_value, expected):
    result = win_runas.get_username(input_value)
    assert result == expected
