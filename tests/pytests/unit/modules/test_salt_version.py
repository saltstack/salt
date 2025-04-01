"""
Unit tests for salt/modules/salt_version.py
"""

import pytest

import salt.modules.salt_version as salt_version
import salt.version
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


def test_mocked_objects():
    """
    Test that the mocked objects actually have what we expect.

    For example, earlier tests incorrectly mocked the
    salt.version.SaltStackVersion.LNAMES dict using upper-case indexes
    """
    assert isinstance(salt.version.SaltStackVersion.LNAMES, dict)
    sv = salt.version.SaltStackVersion(  # pylint: disable=no-value-for-parameter
        *salt.version.__version_info__
    )
    for k, v in salt.version.SaltStackVersion.LNAMES.items():
        assert k == k.lower()
        assert isinstance(v, tuple)
        if sv.new_version(major=v[0]):
            assert len(v) == 1
        else:
            assert len(v) == 2

    assert isinstance(str(sv), str)

    with patch("salt.version.SaltStackVersion.LNAMES", {"neon": (2019, 8)}):
        sv = salt.version.SaltStackVersion.from_name("Neon")
        assert sv.string == "2019.8.0"


def test_get_release_number_no_codename():
    """
    Test that None is returned when the codename isn't found.
    """
    assert salt_version.get_release_number("foo") is None


def test_get_release_number_unassigned():
    """
    Test that a string is returned when a version is found, but unassigned.
    """
    with patch("salt.version.SaltStackVersion.LNAMES", {"foo": (12345, 0)}):
        mock_str = "No version assigned."
        assert salt_version.get_release_number("foo") == mock_str


def test_get_release_number_success():
    """
    Test that a version is returned for a released codename
    """
    assert salt_version.get_release_number("Oxygen") == "2018.3"


def test_get_release_number_success_new_version():
    """
    Test that a version is returned for new versioning (3000)
    """
    assert salt_version.get_release_number("Neon") == "3000"


def test_get_release_number_success_new_version_with_dot():
    """
    Test that a version is returned for new versioning (3006)
    """
    assert salt_version.get_release_number("Sulfur") == "3006"


def test_equal_success():
    """
    Test that the current version is equal to the codename
    """
    with patch("salt.version.SaltStackVersion", MagicMock(return_value="1900.5.0")):
        with patch("salt.version.SaltStackVersion.LNAMES", {"foo": (1900, 5)}):
            assert salt_version.equal("foo") is True


def test_equal_success_new_version():
    """
    Test that the current version is equal to the codename
    while using the new versioning
    """
    with patch("salt.version.SaltStackVersion", MagicMock(return_value="3000.1")):
        with patch("salt.version.SaltStackVersion.LNAMES", {"foo": (3000,)}):
            assert salt_version.equal("foo") is True


def test_equal_success_new_version_with_dot():
    """
    Test that the current version is equal to the codename
    while using the new versioning
    """
    with patch("salt.version.SaltStackVersion", MagicMock(return_value="3006.1")):
        with patch("salt.version.SaltStackVersion.LNAMES", {"foo": (3006,)}):
            assert salt_version.equal("foo") is True


def test_equal_older_codename():
    """
    Test that when an older codename is passed in, the function returns False.
    """
    with patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2")):
        with patch(
            "salt.version.SaltStackVersion.LNAMES",
            {"oxygen": (2018, 3), "nitrogen": (2017, 7)},
        ):
            assert salt_version.equal("Nitrogen") is False


def test_equal_older_codename_new_version():
    """
    Test that when an older codename is passed in, the function returns False.
    while also testing with the new versioning.
    """
    with patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2")):
        with patch(
            "salt.version.SaltStackVersion.LNAMES",
            {"neon": (3000), "nitrogen": (2017, 7)},
        ):
            assert salt_version.equal("Nitrogen") is False


def test_equal_newer_codename():
    """
    Test that when a newer codename is passed in, the function returns False
    """
    with patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2")):
        with patch(
            "salt.version.SaltStackVersion.LNAMES",
            {"fluorine": (salt.version.MAX_SIZE - 100, 0)},
        ):
            assert salt_version.equal("Fluorine") is False


def test_greater_than_success():
    """
    Test that the current version is newer than the codename
    """
    with patch(
        "salt.modules.salt_version.get_release_number", MagicMock(return_value="2017.7")
    ):
        with patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2")):
            assert salt_version.greater_than("Nitrogen") is True


def test_greater_than_success_new_version():
    """
    Test that the current version is newer than the codename
    """
    with patch(
        "salt.modules.salt_version.get_release_number", MagicMock(return_value="2017.7")
    ):
        with patch("salt.version.SaltStackVersion", MagicMock(return_value="3000")):
            assert salt_version.greater_than("Nitrogen") is True


def test_greater_than_success_new_version_with_dot():
    """
    Test that the current version is newer than the codename
    """
    with patch(
        "salt.modules.salt_version.get_release_number", MagicMock(return_value="3000")
    ):
        with patch("salt.version.SaltStackVersion", MagicMock(return_value="3006.0")):
            assert salt_version.greater_than("Neon") is True


def test_greater_than_with_equal_codename():
    """
    Test that when an equal codename is passed in, the function returns False.
    """
    with patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2")):
        with patch("salt.version.SaltStackVersion.LNAMES", {"oxygen": (2018, 3)}):
            assert salt_version.greater_than("Oxygen") is False


def test_greater_than_with_newer_codename():
    """
    Test that when a newer codename is passed in, the function returns False.
    """
    with patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2")):
        with patch(
            "salt.version.SaltStackVersion.LNAMES",
            {"fluorine": (2019, 2), "oxygen": (2018, 3)},
        ):
            assert salt_version.greater_than("Fluorine") is False


def test_greater_than_unassigned():
    """
    Test that the unassigned codename is greater than the current version
    """
    with patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2")):
        with patch(
            "salt.modules.salt_version.get_release_number",
            MagicMock(return_value="No version assigned."),
        ):
            assert salt_version.greater_than("Fluorine") is False


def test_less_than_success():
    """
    Test that when a newer codename is passed in, the function returns True.
    """
    with patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2")):
        with patch(
            "salt.modules.salt_version.get_release_number",
            MagicMock(return_value="2019.2"),
        ):
            assert salt_version.less_than("Fluorine") is True


def test_less_than_success_new_version():
    """
    Test that when a newer codename is passed in, the function returns True
    using new version
    """
    with patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2")):
        with patch(
            "salt.modules.salt_version.get_release_number",
            MagicMock(return_value="3000"),
        ):
            assert salt_version.less_than("Fluorine") is True


def test_less_than_success_new_version_with_dot():
    """
    Test that when a newer codename is passed in, the function returns True
    using new version
    """
    with patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2")):
        with patch(
            "salt.modules.salt_version.get_release_number",
            MagicMock(return_value="3006"),
        ):
            assert salt_version.less_than("Fluorine") is True


def test_less_than_do_not_crash_when_input_is_a_number():
    """
    Test that less_than do not crash when unexpected inputs
    """
    with patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2")):
        with pytest.raises(CommandExecutionError):
            salt_version.less_than(1234)


def test_less_than_with_equal_codename():
    """
    Test that when an equal codename is passed in, the function returns False.
    """
    with patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2")):
        with patch("salt.version.SaltStackVersion.LNAMES", {"oxygen": (2018, 3)}):
            assert salt_version.less_than("Oxygen") is False


def test_less_than_with_older_codename():
    """
    Test that the current version is less than the codename.
    """
    with patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2")):
        with patch(
            "salt.modules.salt_version.get_release_number",
            MagicMock(return_value="2017.7"),
        ):
            assert salt_version.less_than("Nitrogen") is False


def test_less_than_with_unassigned_codename():
    """
    Test that when an unassigned codename greater than the current version.
    """
    with patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2")):
        with patch(
            "salt.modules.salt_version.get_release_number",
            MagicMock(return_value="No version assigned."),
        ):
            assert salt_version.less_than("Fluorine") is True


def test_check_release_cmp_no_codename():
    """
    Test that None is returned when the codename isn't found.
    """
    assert salt_version._check_release_cmp("foo") is None


def test_check_release_cmp_success():
    """
    Test that an int is returned from the version compare
    """
    assert isinstance(salt_version._check_release_cmp("Oxygen"), int)
