import pytest

from salt.utils import win_runas


@pytest.mark.parametrize(
    "input_value, expected",
    [
        ("test_user", ("test_user", ".")),  # Simple system name
        ("domain\\test_user", ("test_user", "domain")),  # Sam name
        ("domain.com\\test_user", ("test_user", "domain.com")),  # Sam name with com
        ("test_user@domain", ("test_user", "domain")),  # UPN Name
        ("test_user@domain.com", ("test_user", "domain.com")),  # UPN Name with com
    ],
)
def test_split_username(input_value, expected):
    """
    Test that the username is parsed properly from various domain/username
    combinations
    """
    result = win_runas.split_username(input_value)
    assert result == expected
