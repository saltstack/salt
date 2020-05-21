# -*- coding: utf-8 -*-
"""
Unit tests for salt/modules/salt_version.py
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import salt.modules.salt_version as salt_version
import salt.version

# Import Salt libs
from salt.ext import six
from tests.support.mock import MagicMock, patch

# Import Salt Testing libs
from tests.support.unit import TestCase


class SaltVersionTestCase(TestCase):
    """
    Test cases for salt.modules.salt_version
    """

    def test_mocked_objects(self):
        """
        Test that the mocked objects actually have what we expect.

        For example, earlier tests incorrectly mocked the
        salt.version.SaltStackVersion.LNAMES dict using upper-case indexes
        """
        assert isinstance(salt.version.SaltStackVersion.LNAMES, dict)
        sv = salt.version.SaltStackVersion(*salt.version.__version_info__)
        for k, v in salt.version.SaltStackVersion.LNAMES.items():
            assert k == k.lower()
            assert isinstance(v, tuple)
            if sv.new_version(major=v[0]):
                assert len(v) == 1
            else:
                assert len(v) == 2

        sv = sv.__str__()
        assert isinstance(sv, six.string_types)

        with patch("salt.version.SaltStackVersion.LNAMES", {"neon": (2019, 8)}):
            sv = salt.version.SaltStackVersion.from_name("Neon")
            self.assertEqual(sv.string, "2019.8.0")

    # get_release_number tests: 3

    def test_get_release_number_no_codename(self):
        """
        Test that None is returned when the codename isn't found.
        """
        assert salt_version.get_release_number("foo") is None

    @patch("salt.version.SaltStackVersion.LNAMES", {"foo": (12345, 0)})
    def test_get_release_number_unassigned(self):
        """
        Test that a string is returned when a version is found, but unassigned.
        """
        mock_str = "No version assigned."
        assert salt_version.get_release_number("foo") == mock_str

    def test_get_release_number_success(self):
        """
        Test that a version is returned for a released codename
        """
        assert salt_version.get_release_number("Oxygen") == "2018.3"

    def test_get_release_number_success_new_version(self):
        """
        Test that a version is returned for new versioning (3000)
        """
        assert salt_version.get_release_number("Neon") == "3000"

    # equal tests: 3

    @patch("salt.version.SaltStackVersion.LNAMES", {"foo": (1900, 5)})
    @patch("salt.version.SaltStackVersion", MagicMock(return_value="1900.5.0"))
    def test_equal_success(self):
        """
        Test that the current version is equal to the codename
        """
        assert salt_version.equal("foo") is True

    @patch("salt.version.SaltStackVersion.LNAMES", {"foo": (3000,)})
    @patch("salt.version.SaltStackVersion", MagicMock(return_value="3000.1"))
    def test_equal_success_new_version(self):
        """
        Test that the current version is equal to the codename
        while using the new versioning
        """
        assert salt_version.equal("foo") is True

    @patch(
        "salt.version.SaltStackVersion.LNAMES",
        {"oxygen": (2018, 3), "nitrogen": (2017, 7)},
    )
    @patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2"))
    def test_equal_older_codename(self):
        """
        Test that when an older codename is passed in, the function returns False.
        """
        assert salt_version.equal("Nitrogen") is False

    @patch(
        "salt.version.SaltStackVersion.LNAMES", {"neon": (3000), "nitrogen": (2017, 7)}
    )
    @patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2"))
    def test_equal_older_codename_new_version(self):
        """
        Test that when an older codename is passed in, the function returns False.
        while also testing with the new versioning.
        """
        assert salt_version.equal("Nitrogen") is False

    @patch(
        "salt.version.SaltStackVersion.LNAMES",
        {"fluorine": (salt.version.MAX_SIZE - 100, 0)},
    )
    @patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2"))
    def test_equal_newer_codename(self):
        """
        Test that when a newer codename is passed in, the function returns False
        """
        assert salt_version.equal("Fluorine") is False

    # greater_than tests: 4

    @patch(
        "salt.modules.salt_version.get_release_number", MagicMock(return_value="2017.7")
    )
    @patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2"))
    def test_greater_than_success(self):
        """
        Test that the current version is newer than the codename
        """
        assert salt_version.greater_than("Nitrogen") is True

    @patch(
        "salt.modules.salt_version.get_release_number", MagicMock(return_value="2017.7")
    )
    @patch("salt.version.SaltStackVersion", MagicMock(return_value="3000"))
    def test_greater_than_success_new_version(self):
        """
        Test that the current version is newer than the codename
        """
        assert salt_version.greater_than("Nitrogen") is True

    @patch("salt.version.SaltStackVersion.LNAMES", {"oxygen": (2018, 3)})
    @patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2"))
    def test_greater_than_with_equal_codename(self):
        """
        Test that when an equal codename is passed in, the function returns False.
        """
        assert salt_version.greater_than("Oxygen") is False

    @patch(
        "salt.version.SaltStackVersion.LNAMES",
        {"fluorine": (2019, 2), "oxygen": (2018, 3)},
    )
    @patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2"))
    def test_greater_than_with_newer_codename(self):
        """
        Test that when a newer codename is passed in, the function returns False.
        """
        assert salt_version.greater_than("Fluorine") is False

    @patch(
        "salt.modules.salt_version.get_release_number",
        MagicMock(return_value="No version assigned."),
    )
    @patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2"))
    def test_greater_than_unassigned(self):
        """
        Test that the unassigned codename is greater than the current version
        """
        assert salt_version.greater_than("Fluorine") is False

    # less_than tests: 4

    @patch(
        "salt.modules.salt_version.get_release_number", MagicMock(return_value="2019.2")
    )
    @patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2"))
    def test_less_than_success(self):
        """
        Test that when a newer codename is passed in, the function returns True.
        """
        assert salt_version.less_than("Fluorine") is True

    @patch(
        "salt.modules.salt_version.get_release_number", MagicMock(return_value="3000")
    )
    @patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2"))
    def test_less_than_success_new_version(self):
        """
        Test that when a newer codename is passed in, the function returns True
        using new version
        """
        assert salt_version.less_than("Fluorine") is True

    @patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2"))
    @patch("salt.version.SaltStackVersion.LNAMES", {"oxygen": (2018, 3)})
    def test_less_than_with_equal_codename(self):
        """
        Test that when an equal codename is passed in, the function returns False.
        """
        assert salt_version.less_than("Oxygen") is False

    @patch(
        "salt.modules.salt_version.get_release_number", MagicMock(return_value="2017.7")
    )
    @patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2"))
    def test_less_than_with_older_codename(self):
        """
        Test that the current version is less than the codename.
        """
        assert salt_version.less_than("Nitrogen") is False

    @patch(
        "salt.modules.salt_version.get_release_number",
        MagicMock(return_value="No version assigned."),
    )
    @patch("salt.version.SaltStackVersion", MagicMock(return_value="2018.3.2"))
    def test_less_than_with_unassigned_codename(self):
        """
        Test that when an unassigned codename greater than the current version.
        """
        assert salt_version.less_than("Fluorine") is True

    # _check_release_cmp tests: 2

    def test_check_release_cmp_no_codename(self):
        """
        Test that None is returned when the codename isn't found.
        """
        assert salt_version._check_release_cmp("foo") is None

    def test_check_release_cmp_success(self):
        """
        Test that an int is returned from the version compare
        """
        assert isinstance(salt_version._check_release_cmp("Oxygen"), int)
