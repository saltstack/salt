"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import pytest

import salt.modules.aliases as aliases
from salt.exceptions import SaltInvocationError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def mock_alias():
    return [("foo", "bar@example.com", "")]


@pytest.fixture
def mock_alias_mult():
    return [
        ("foo", "bar@example.com", ""),
        ("hello", "world@earth.com, earth@world.com", ""),
    ]


@pytest.fixture
def configure_loader_modules():
    return {aliases: {}}


def test_list_aliases(mock_alias):
    """
    Tests the return of a file containing one alias
    """
    with patch(
        "salt.modules.aliases.__parse_aliases",
        MagicMock(return_value=mock_alias),
    ):
        ret = {"foo": "bar@example.com"}
        assert aliases.list_aliases() == ret


def test_list_aliases_mult(mock_alias_mult):
    """
    Tests the return of a file containing multiple aliases
    """
    with patch(
        "salt.modules.aliases.__parse_aliases",
        MagicMock(return_value=mock_alias_mult),
    ):
        ret = {
            "foo": "bar@example.com",
            "hello": "world@earth.com, earth@world.com",
        }
        assert aliases.list_aliases() == ret


def test_get_target(mock_alias):
    """
    Tests the target returned by an alias with one target
    """
    with patch(
        "salt.modules.aliases.__parse_aliases",
        MagicMock(return_value=mock_alias),
    ):
        ret = "bar@example.com"
        assert aliases.get_target("foo") == ret


def test_get_target_mult(mock_alias_mult):
    """
    Tests the target returned by an alias with multiple targets
    """
    with patch(
        "salt.modules.aliases.__parse_aliases",
        MagicMock(return_value=mock_alias_mult),
    ):
        ret = "world@earth.com, earth@world.com"
        assert aliases.get_target("hello") == ret


def test_get_target_no_alias(mock_alias):
    """
    Tests return of an alias doesn't exist
    """
    with patch(
        "salt.modules.aliases.__parse_aliases",
        MagicMock(return_value=mock_alias),
    ):
        assert aliases.get_target("pizza") == ""


def test_has_target(mock_alias):
    """
    Tests simple return known alias and target
    """
    with patch(
        "salt.modules.aliases.__parse_aliases",
        MagicMock(return_value=mock_alias),
    ):
        ret = aliases.has_target("foo", "bar@example.com")
        assert ret


def test_has_target_no_alias(mock_alias):
    """
    Tests return of empty alias and known target
    """
    with patch(
        "salt.modules.aliases.__parse_aliases",
        MagicMock(return_value=mock_alias),
    ):
        ret = aliases.has_target("", "bar@example.com")
        assert not ret


def test_has_target_no_target():
    """
    Tests return of known alias and empty target
    """
    pytest.raises(SaltInvocationError, aliases.has_target, "foo", "")


def test_has_target_mult(mock_alias_mult):
    """
    Tests return of multiple targets to one alias
    """
    with patch(
        "salt.modules.aliases.__parse_aliases",
        MagicMock(return_value=mock_alias_mult),
    ):
        ret = aliases.has_target("hello", "world@earth.com, earth@world.com")
        assert ret


def test_has_target_mult_differs(mock_alias_mult):
    """
    Tests return of multiple targets to one alias in opposite order
    """
    with patch(
        "salt.modules.aliases.__parse_aliases",
        MagicMock(return_value=mock_alias_mult),
    ):
        ret = aliases.has_target("hello", "earth@world.com, world@earth.com")
        assert not ret


def test_has_target_list_mult(mock_alias_mult):
    """
    Tests return of target as same list to know alias
    """
    with patch(
        "salt.modules.aliases.__parse_aliases",
        MagicMock(return_value=mock_alias_mult),
    ):
        ret = aliases.has_target("hello", ["world@earth.com", "earth@world.com"])
        assert ret


def test_has_target_list_mult_differs(mock_alias_mult):
    """
    Tests return of target as differing list to known alias
    """
    with patch(
        "salt.modules.aliases.__parse_aliases",
        MagicMock(return_value=mock_alias_mult),
    ):
        ret = aliases.has_target("hello", ["world@earth.com", "mars@space.com"])
        assert not ret


def test_set_target_equal():
    """
    Tests return when target is already present
    """
    with patch(
        "salt.modules.aliases.get_target", MagicMock(return_value="bar@example.com")
    ):
        alias = "foo"
        target = "bar@example.com"
        ret = aliases.set_target(alias, target)
        assert ret


def test_set_target_empty_alias():
    """
    Tests return of empty alias
    """
    pytest.raises(SaltInvocationError, aliases.set_target, "", "foo")


def test_set_target_empty_target():
    """
    Tests return of known alias and empty target
    """
    pytest.raises(SaltInvocationError, aliases.set_target, "foo", "")


def test_rm_alias_absent():
    """
    Tests return when alias is not present
    """
    with patch("salt.modules.aliases.get_target", MagicMock(return_value="")):
        ret = aliases.rm_alias("foo")
        assert ret
