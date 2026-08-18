"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import pytest

from salt.cloud.clouds import linode


@pytest.fixture
def configure_loader_modules():
    return {linode: {}}


# _validate_name tests


def test_validate_name_first_character_invalid():
    """
    Tests when name starts with an invalid character.
    """
    # Test when name begins with a hyphen
    assert linode._validate_name("-foo") is False

    # Test when name begins with an underscore
    assert linode._validate_name("_foo") is False


def test_validate_name_last_character_invalid():
    """
    Tests when name ends with an invalid character.
    """
    # Test when name ends with a hyphen
    assert linode._validate_name("foo-") is False

    # Test when name ends with an underscore
    assert linode._validate_name("foo_") is False


def test_validate_name_too_short():
    """
    Tests when name has less than three letters.
    """
    # Test when name is an empty string
    assert linode._validate_name("") is False

    # Test when name is two letters long
    assert linode._validate_name("ab") is False

    # Test when name is three letters long (valid)
    assert linode._validate_name("abc") is True


def test_validate_name_too_long():
    """
    Tests when name has more than 48 letters.
    """
    long_name = "1111-2222-3333-4444-5555-6666-7777-8888-9999-111"
    # Test when name is 48 letters long (valid)
    assert len(long_name) == 48
    assert linode._validate_name(long_name) is True

    # Test when name is more than 48 letters long
    long_name += "1"
    assert len(long_name) == 49
    assert linode._validate_name(long_name) is False


def test_validate_name_invalid_characters():
    """
    Tests when name contains invalid characters.
    """
    # Test when name contains an invalid character
    assert linode._validate_name("foo;bar") is False

    # Test when name contains non-ascii letters
    assert linode._validate_name("fooàààààbar") is False

    # Test when name contains spaces
    assert linode._validate_name("foo bar") is False


def test_validate_name_valid_characters():
    """
    Tests when name contains valid characters.
    """
    # Test when name contains letters and numbers
    assert linode._validate_name("foo123bar") is True

    # Test when name contains hyphens
    assert linode._validate_name("foo-bar") is True

    # Test when name contains underscores
    assert linode._validate_name("foo_bar") is True

    # Test when name start and end with numbers
    assert linode._validate_name("1foo") is True
    assert linode._validate_name("foo0") is True
