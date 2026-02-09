import pytest

from salt.utils import win_runas
from salt.exceptions import CommandExecutionError


@pytest.mark.parametrize(
    "input_value, expected",
    [
        ("test_user", ("test_user", ".")),  # Simple system name
        ("domain\\test_user", ("test_user", "domain")),  # Sam name
        ("domain.com\\test_user", ("test_user", "domain.com")),  # Sam name with .com
        ("test_user@domain", ("test_user", "domain")),  # UPN Name
        ("test_user@domain.com", ("test_user", "domain.com")),  # UPN Name with .com
        ("test_user@domain.local", ("test_user", "domain")),  # UPN Name with .local
    ],
)
def test_split_username(input_value, expected):
    """
    Test that the username is parsed properly from various domain/username
    combinations
    """
    result = win_runas.split_username(input_value)
    assert result == expected


def test_validate_username_returns_false(monkeypatch):
    def _raise(_):
        raise CommandExecutionError("lookup failed")

    monkeypatch.setattr(win_runas, "resolve_logon_credentials", _raise)
    assert win_runas.validate_username("DOMAIN\\user") is False


def test_validate_username_raises(monkeypatch):
    def _raise(_):
        raise CommandExecutionError("lookup failed")

    monkeypatch.setattr(win_runas, "resolve_logon_credentials", _raise)
    with pytest.raises(CommandExecutionError):
        win_runas.validate_username("DOMAIN\\user", raise_on_error=True)


@pytest.mark.skipif(
    not win_runas.HAS_WIN32, reason="win32 libraries are required for this test"
)
def test_resolve_logon_credentials_upn(monkeypatch):
    def _lookup(_, username):
        return "sid", "DOMAIN", 1

    monkeypatch.setattr(win_runas.win32security, "LookupAccountName", _lookup)
    result = win_runas.resolve_logon_credentials("user@domain.com")
    assert result["user_name"] == "user"
    assert result["domain_name"] == "domain.com"
    assert result["logon_name"] == "user@domain.com"
    assert result["logon_domain"] == ""
