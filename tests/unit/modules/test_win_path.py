# -*- coding: utf-8 -*-
"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import os

# Import Salt Libs
import salt.modules.win_path as win_path
import salt.utils.stringutils

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class WinPathTestCase(TestCase, LoaderModuleMockMixin):
    """
        Test cases for salt.modules.win_path
    """

    def setup_loader_modules(self):
        return {win_path: {}}

    def __init__(self, *args, **kwargs):
        super(WinPathTestCase, self).__init__(*args, **kwargs)
        self.pathsep = str(";")  # future lint: disable=blacklisted-function

    def assert_call_matches(self, mock_obj, new_path):
        mock_obj.assert_called_once_with(
            win_path.HIVE,
            win_path.KEY,
            win_path.VNAME,
            self.pathsep.join(new_path),
            win_path.VTYPE,
        )

    def assert_path_matches(self, env, new_path):
        self.assertEqual(
            env["PATH"], salt.utils.stringutils.to_str(self.pathsep.join(new_path))
        )

    def test_get_path(self):
        """
        Test to Returns the system path
        """
        mock = MagicMock(return_value={"vdata": "C:\\Salt"})
        with patch.dict(win_path.__salt__, {"reg.read_value": mock}):
            self.assertListEqual(win_path.get_path(), ["C:\\Salt"])

    def test_exists(self):
        """
        Test to check if the directory is configured
        """
        get_mock = MagicMock(return_value=["C:\\Foo", "C:\\Bar"])
        with patch.object(win_path, "get_path", get_mock):
            # Ensure case insensitivity respected
            self.assertTrue(win_path.exists("C:\\FOO"))
            self.assertTrue(win_path.exists("c:\\foo"))
            self.assertFalse(win_path.exists("c:\\mystuff"))

    def test_add(self):
        """
        Test to add the directory to the SYSTEM path
        """
        orig_path = ("C:\\Foo", "C:\\Bar")

        def _env(path):
            return {
                str(
                    "PATH"
                ): salt.utils.stringutils.to_str(  # future lint: disable=blacklisted-function
                    self.pathsep.join(path)
                )
            }

        def _run(name, index=None, retval=True, path=None):
            if path is None:
                path = orig_path
            env = _env(path)
            mock_get = MagicMock(return_value=list(path))
            mock_set = MagicMock(return_value=retval)
            with patch.object(win_path, "PATHSEP", self.pathsep), patch.object(
                win_path, "get_path", mock_get
            ), patch.object(os, "environ", env), patch.dict(
                win_path.__salt__, {"reg.set_value": mock_set}
            ), patch.object(
                win_path, "rehash", MagicMock(return_value=True)
            ):
                return win_path.add(name, index), env, mock_set

        # Test a successful reg update
        ret, env, mock_set = _run("c:\\salt", retval=True)
        new_path = ("C:\\Foo", "C:\\Bar", "c:\\salt")
        self.assertTrue(ret)
        self.assert_call_matches(mock_set, new_path)
        self.assert_path_matches(env, new_path)

        # Test an unsuccessful reg update
        ret, env, mock_set = _run("c:\\salt", retval=False)
        new_path = ("C:\\Foo", "C:\\Bar", "c:\\salt")
        self.assertFalse(ret)
        self.assert_call_matches(mock_set, new_path)
        # The local path should still have been modified even
        # though reg.set_value failed.
        self.assert_path_matches(env, new_path)

        # Test adding with a custom index
        ret, env, mock_set = _run("c:\\salt", index=1, retval=True)
        new_path = ("C:\\Foo", "c:\\salt", "C:\\Bar")
        self.assertTrue(ret)
        self.assert_call_matches(mock_set, new_path)
        self.assert_path_matches(env, new_path)

        # Test adding with a custom index of 0
        ret, env, mock_set = _run("c:\\salt", index=0, retval=True)
        new_path = ("c:\\salt", "C:\\Foo", "C:\\Bar")
        self.assertTrue(ret)
        self.assert_call_matches(mock_set, new_path)
        self.assert_path_matches(env, new_path)

        # Test adding path with a case-insensitive match already present, and
        # no index provided. The path should remain unchanged and we should not
        # update the registry.
        ret, env, mock_set = _run("c:\\foo", retval=True)
        self.assertTrue(ret)
        mock_set.assert_not_called()
        self.assert_path_matches(env, orig_path)

        # Test adding path with a case-insensitive match already present, and a
        # negative index provided which does not match the current index. The
        # match should be removed, and the path should be added to the end of
        # the list.
        ret, env, mock_set = _run("c:\\foo", index=-1, retval=True)
        new_path = ("C:\\Bar", "c:\\foo")
        self.assertTrue(ret)
        self.assert_call_matches(mock_set, new_path)
        self.assert_path_matches(env, new_path)

        # Test adding path with a case-insensitive match already present, and a
        # negative index provided which matches the current index. No changes
        # should be made.
        ret, env, mock_set = _run("c:\\foo", index=-2, retval=True)
        self.assertTrue(ret)
        mock_set.assert_not_called()
        self.assert_path_matches(env, orig_path)

        # Test adding path with a case-insensitive match already present, and a
        # negative index provided which is larger than the size of the list. No
        # changes should be made, since in these cases we assume an index of 0,
        # and the case-insensitive match is also at index 0.
        ret, env, mock_set = _run("c:\\foo", index=-5, retval=True)
        self.assertTrue(ret)
        mock_set.assert_not_called()
        self.assert_path_matches(env, orig_path)

        # Test adding path with a case-insensitive match already present, and a
        # negative index provided which is larger than the size of the list.
        # The match should be removed from its current location and inserted at
        # the beginning, since when a negative index is larger than the list,
        # we put it at the beginning of the list.
        ret, env, mock_set = _run("c:\\bar", index=-5, retval=True)
        new_path = ("c:\\bar", "C:\\Foo")
        self.assertTrue(ret)
        self.assert_call_matches(mock_set, new_path)
        self.assert_path_matches(env, new_path)

        # Test adding path with a case-insensitive match already present, and a
        # negative index provided which matches the current index. The path
        # should remain unchanged and we should not update the registry.
        ret, env, mock_set = _run("c:\\bar", index=-1, retval=True)
        self.assertTrue(ret)
        mock_set.assert_not_called()
        self.assert_path_matches(env, orig_path)

        # Test adding path with a case-insensitive match already present, and
        # an index provided which does not match the current index, and is also
        # larger than the size of the PATH list. The match should be removed,
        # and the path should be added to the end of the list.
        ret, env, mock_set = _run("c:\\foo", index=5, retval=True)
        new_path = ("C:\\Bar", "c:\\foo")
        self.assertTrue(ret)
        self.assert_call_matches(mock_set, new_path)
        self.assert_path_matches(env, new_path)

    def test_remove(self):
        """
        Test win_path.remove
        """
        orig_path = ("C:\\Foo", "C:\\Bar", "C:\\Baz")

        def _env(path):
            return {
                str(
                    "PATH"
                ): salt.utils.stringutils.to_str(  # future lint: disable=blacklisted-function
                    self.pathsep.join(path)
                )
            }

        def _run(name="c:\\salt", index=None, retval=True, path=None):
            if path is None:
                path = orig_path
            env = _env(path)
            mock_get = MagicMock(return_value=list(path))
            mock_set = MagicMock(return_value=retval)
            with patch.object(win_path, "PATHSEP", self.pathsep), patch.object(
                win_path, "get_path", mock_get
            ), patch.object(os, "environ", env), patch.dict(
                win_path.__salt__, {"reg.set_value": mock_set}
            ), patch.object(
                win_path, "rehash", MagicMock(return_value=True)
            ):
                return win_path.remove(name), env, mock_set

        # Test a successful reg update
        ret, env, mock_set = _run("C:\\Bar", retval=True)
        new_path = ("C:\\Foo", "C:\\Baz")
        self.assertTrue(ret)
        self.assert_call_matches(mock_set, new_path)
        self.assert_path_matches(env, new_path)

        # Test a successful reg update with a case-insensitive match
        ret, env, mock_set = _run("c:\\bar", retval=True)
        new_path = ("C:\\Foo", "C:\\Baz")
        self.assertTrue(ret)
        self.assert_call_matches(mock_set, new_path)
        self.assert_path_matches(env, new_path)

        # Test a successful reg update with multiple case-insensitive matches.
        # All matches should be removed.
        old_path = orig_path + ("C:\\BAR",)
        ret, env, mock_set = _run("c:\\bar", retval=True)
        new_path = ("C:\\Foo", "C:\\Baz")
        self.assertTrue(ret)
        self.assert_call_matches(mock_set, new_path)
        self.assert_path_matches(env, new_path)

        # Test an unsuccessful reg update
        ret, env, mock_set = _run("c:\\bar", retval=False)
        new_path = ("C:\\Foo", "C:\\Baz")
        self.assertFalse(ret)
        self.assert_call_matches(mock_set, new_path)
        # The local path should still have been modified even
        # though reg.set_value failed.
        self.assert_path_matches(env, new_path)

        # Test when no match found
        ret, env, mock_set = _run("C:\\NotThere", retval=True)
        self.assertTrue(ret)
        mock_set.assert_not_called()
        self.assert_path_matches(env, orig_path)
