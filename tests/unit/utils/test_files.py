# -*- coding: utf-8 -*-
"""
Unit Tests for functions located in salt/utils/files.py
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import copy
import os

# Import Salt libs
import salt.utils.files
from salt.ext import six

# Import Salt Testing libs
from tests.support.helpers import with_tempdir
from tests.support.mock import patch
from tests.support.unit import TestCase, skipIf


class FilesTestCase(TestCase):
    """
    Test case for files util.
    """

    def test_safe_rm(self):
        with patch("os.remove") as os_remove_mock:
            salt.utils.files.safe_rm("dummy_tgt")
            self.assertTrue(os_remove_mock.called)

    @skipIf(
        os.path.exists("/tmp/no_way_this_is_a_file_nope.sh"),
        "Test file exists! Skipping safe_rm_exceptions test!",
    )
    def test_safe_rm_exceptions(self):
        error = False
        try:
            salt.utils.files.safe_rm("/tmp/no_way_this_is_a_file_nope.sh")
        except (IOError, OSError):
            error = True
        self.assertFalse(
            error, "salt.utils.files.safe_rm raised exception when it should not have"
        )

    @with_tempdir()
    def test_safe_walk_symlink_recursion(self, tmp):
        if os.stat(tmp).st_ino == 0:
            self.skipTest("inodes not supported in {0}".format(tmp))
        os.mkdir(os.path.join(tmp, "fax"))
        os.makedirs(os.path.join(tmp, "foo", "bar"))
        os.symlink(os.path.join("..", ".."), os.path.join(tmp, "foo", "bar", "baz"))
        os.symlink("foo", os.path.join(tmp, "root"))
        expected = [
            (os.path.join(tmp, "root"), ["bar"], []),
            (os.path.join(tmp, "root", "bar"), ["baz"], []),
            (os.path.join(tmp, "root", "bar", "baz"), ["fax", "foo", "root"], []),
            (os.path.join(tmp, "root", "bar", "baz", "fax"), [], []),
        ]
        paths = []
        for root, dirs, names in salt.utils.files.safe_walk(os.path.join(tmp, "root")):
            paths.append((root, sorted(dirs), names))
        if paths != expected:
            raise AssertionError(
                "\n".join(
                    ["got:"]
                    + [repr(p) for p in paths]
                    + ["", "expected:"]
                    + [repr(p) for p in expected]
                )
            )

    @skipIf(not six.PY3, "This test only applies to Python 3")
    def test_fopen_with_disallowed_fds(self):
        """
        This is safe to have as a unit test since we aren't going to actually
        try to read or write. We want to ensure that we are raising a
        TypeError. Python 3's open() builtin will treat the booleans as file
        descriptor numbers and try to open stdin/stdout. We also want to test
        fd 2 which is stderr.
        """
        for invalid_fn in (False, True, 0, 1, 2):
            try:
                with salt.utils.files.fopen(invalid_fn):
                    pass
            except TypeError:
                # This is expected. We aren't using an assertRaises here
                # because we want to ensure that if we did somehow open the
                # filehandle, that it doesn't remain open.
                pass
            else:
                # We probably won't even get this far if we actually opened
                # stdin/stdout as a file descriptor. It is likely to cause the
                # integration suite to die since, news flash, closing
                # stdin/stdout/stderr is usually not a wise thing to do in the
                # middle of a program's execution.
                self.fail(
                    "fopen() should have been prevented from opening a file "
                    "using {0} as the filename".format(invalid_fn)
                )

    def _create_temp_structure(self, temp_directory, structure):
        for folder, files in six.iteritems(structure):
            current_directory = os.path.join(temp_directory, folder)
            os.makedirs(current_directory)
            for name, content in six.iteritems(files):
                path = os.path.join(temp_directory, folder, name)
                with salt.utils.files.fopen(path, "w+") as fh:
                    fh.write(content)

    def _validate_folder_structure_and_contents(
        self, target_directory, desired_structure
    ):
        for folder, files in six.iteritems(desired_structure):
            for name, content in six.iteritems(files):
                path = os.path.join(target_directory, folder, name)
                with salt.utils.files.fopen(path) as fh:
                    assert fh.read().strip() == content

    @with_tempdir()
    @with_tempdir()
    def test_recursive_copy(self, src, dest):
        src_structure = {
            "foo": {"foofile.txt": "fooSTRUCTURE"},
            "bar": {"barfile.txt": "barSTRUCTURE"},
        }
        dest_structure = {
            "foo": {"foo.txt": "fooTARGET_STRUCTURE"},
            "baz": {"baz.txt": "bazTARGET_STRUCTURE"},
        }

        # Create the file structures in both src and dest dirs
        self._create_temp_structure(src, src_structure)
        self._create_temp_structure(dest, dest_structure)

        # Perform the recursive copy
        salt.utils.files.recursive_copy(src, dest)

        # Confirm results match expected results
        desired_structure = copy.copy(dest_structure)
        desired_structure.update(src_structure)
        self._validate_folder_structure_and_contents(dest, desired_structure)
