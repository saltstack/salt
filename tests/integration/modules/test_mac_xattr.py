"""
integration tests for mac_xattr
"""

import os

import pytest
from tests.support.case import ModuleCase
from tests.support.helpers import runs_on
from tests.support.runtests import RUNTIME_VARS


@runs_on(kernel="Darwin")
@pytest.mark.skip_if_binaries_missing("xattr")
class MacXattrModuleTest(ModuleCase):
    """
    Validate the mac_xattr module
    """

    @classmethod
    def setUpClass(cls):
        cls.test_file = os.path.join(RUNTIME_VARS.TMP, "xattr_test_file.txt")
        cls.no_file = os.path.join(RUNTIME_VARS.TMP, "xattr_no_file.txt")

    def setUp(self):
        """
        Create test file for testing extended attributes
        """
        self.run_function("file.touch", [self.test_file])

    def tearDown(self):
        """
        Clean up test file
        """
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    @pytest.mark.slow_test
    def test_list_no_xattr(self):
        """
        Make sure there are no attributes
        """
        # Clear existing attributes
        self.assertTrue(self.run_function("xattr.clear", [self.test_file]))

        # Test no attributes
        self.assertEqual(self.run_function("xattr.list", [self.test_file]), {})

        # Test file not found
        self.assertEqual(
            self.run_function("xattr.list", [self.no_file]),
            "ERROR: File not found: {}".format(self.no_file),
        )

    @pytest.mark.slow_test
    def test_write(self):
        """
        Write an attribute
        """
        # Clear existing attributes
        self.assertTrue(self.run_function("xattr.clear", [self.test_file]))

        # Write some attributes
        self.assertTrue(
            self.run_function(
                "xattr.write", [self.test_file, "spongebob", "squarepants"]
            )
        )
        self.assertTrue(
            self.run_function("xattr.write", [self.test_file, "squidward", "plankton"])
        )
        self.assertTrue(
            self.run_function("xattr.write", [self.test_file, "crabby", "patty"])
        )

        # Test that they were actually added
        self.assertEqual(
            self.run_function("xattr.list", [self.test_file]),
            {"spongebob": "squarepants", "squidward": "plankton", "crabby": "patty"},
        )

        # Test file not found
        self.assertEqual(
            self.run_function("xattr.write", [self.no_file, "patrick", "jellyfish"]),
            "ERROR: File not found: {}".format(self.no_file),
        )

    @pytest.mark.slow_test
    def test_read(self):
        """
        Test xattr.read
        """
        # Clear existing attributes
        self.assertTrue(self.run_function("xattr.clear", [self.test_file]))

        # Write an attribute
        self.assertTrue(
            self.run_function(
                "xattr.write", [self.test_file, "spongebob", "squarepants"]
            )
        )

        # Read the attribute
        self.assertEqual(
            self.run_function("xattr.read", [self.test_file, "spongebob"]),
            "squarepants",
        )

        # Test file not found
        self.assertEqual(
            self.run_function("xattr.read", [self.no_file, "spongebob"]),
            "ERROR: File not found: {}".format(self.no_file),
        )

        # Test attribute not found
        self.assertEqual(
            self.run_function("xattr.read", [self.test_file, "patrick"]),
            "ERROR: Attribute not found: patrick",
        )

    @pytest.mark.slow_test
    def test_delete(self):
        """
        Test xattr.delete
        """
        # Clear existing attributes
        self.assertTrue(self.run_function("xattr.clear", [self.test_file]))

        # Write some attributes
        self.assertTrue(
            self.run_function(
                "xattr.write", [self.test_file, "spongebob", "squarepants"]
            )
        )
        self.assertTrue(
            self.run_function("xattr.write", [self.test_file, "squidward", "plankton"])
        )
        self.assertTrue(
            self.run_function("xattr.write", [self.test_file, "crabby", "patty"])
        )

        # Delete an attribute
        self.assertTrue(
            self.run_function("xattr.delete", [self.test_file, "squidward"])
        )

        # Make sure it was actually deleted
        self.assertEqual(
            self.run_function("xattr.list", [self.test_file]),
            {"spongebob": "squarepants", "crabby": "patty"},
        )

        # Test file not found
        self.assertEqual(
            self.run_function("xattr.delete", [self.no_file, "spongebob"]),
            "ERROR: File not found: {}".format(self.no_file),
        )

        # Test attribute not found
        self.assertEqual(
            self.run_function("xattr.delete", [self.test_file, "patrick"]),
            "ERROR: Attribute not found: patrick",
        )

    @pytest.mark.slow_test
    def test_clear(self):
        """
        Test xattr.clear
        """
        # Clear existing attributes
        self.assertTrue(self.run_function("xattr.clear", [self.test_file]))

        # Write some attributes
        self.assertTrue(
            self.run_function(
                "xattr.write", [self.test_file, "spongebob", "squarepants"]
            )
        )
        self.assertTrue(
            self.run_function("xattr.write", [self.test_file, "squidward", "plankton"])
        )
        self.assertTrue(
            self.run_function("xattr.write", [self.test_file, "crabby", "patty"])
        )

        # Test Clear
        self.assertTrue(self.run_function("xattr.clear", [self.test_file]))

        # Test file not found
        self.assertEqual(
            self.run_function("xattr.clear", [self.no_file]),
            "ERROR: File not found: {}".format(self.no_file),
        )
