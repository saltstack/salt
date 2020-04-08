# -*- coding: utf-8 -*-
"""
Tests for win_path states
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import copy

# Import Salt Libs
import salt.states.win_path as win_path

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, Mock, patch
from tests.support.unit import TestCase

NAME = "salt"


class WinPathTestCase(TestCase, LoaderModuleMockMixin):
    """
    Validate the win_path state
    """

    def setup_loader_modules(self):
        return {win_path: {}}

    def test_absent(self):
        """
        Test various cases for win_path.absent
        """
        ret_base = {"name": NAME, "result": True, "changes": {}}

        def _mock(retval):
            # Return a new MagicMock for each test case
            return MagicMock(side_effect=retval)

        # We don't really want to run the remove func
        with patch.dict(win_path.__salt__, {"win_path.remove": Mock()}):

            # Test mode OFF
            with patch.dict(win_path.__opts__, {"test": False}):

                # Test already absent
                with patch.dict(win_path.__salt__, {"win_path.exists": _mock([False])}):
                    ret = copy.deepcopy(ret_base)
                    ret["comment"] = "{0} is not in the PATH".format(NAME)
                    ret["result"] = True
                    self.assertDictEqual(win_path.absent(NAME), ret)

                # Test successful removal
                with patch.dict(
                    win_path.__salt__, {"win_path.exists": _mock([True, False])}
                ):
                    ret = copy.deepcopy(ret_base)
                    ret["comment"] = "Removed {0} from the PATH".format(NAME)
                    ret["changes"]["removed"] = NAME
                    ret["result"] = True
                    self.assertDictEqual(win_path.absent(NAME), ret)

                # Test unsucessful removal
                with patch.dict(
                    win_path.__salt__, {"win_path.exists": _mock([True, True])}
                ):
                    ret = copy.deepcopy(ret_base)
                    ret["comment"] = "Failed to remove {0} from the PATH".format(NAME)
                    ret["result"] = False
                    self.assertDictEqual(win_path.absent(NAME), ret)

            # Test mode ON
            with patch.dict(win_path.__opts__, {"test": True}):

                # Test already absent
                with patch.dict(win_path.__salt__, {"win_path.exists": _mock([False])}):
                    ret = copy.deepcopy(ret_base)
                    ret["comment"] = "{0} is not in the PATH".format(NAME)
                    ret["result"] = True
                    self.assertDictEqual(win_path.absent(NAME), ret)

                # Test the test-mode return
                with patch.dict(win_path.__salt__, {"win_path.exists": _mock([True])}):
                    ret = copy.deepcopy(ret_base)
                    ret["comment"] = "{0} would be removed from the PATH".format(NAME)
                    ret["result"] = None
                    self.assertDictEqual(win_path.absent(NAME), ret)

    def test_exists_invalid_index(self):
        """
        Tests win_path.exists when a non-integer index is specified.
        """
        ret = win_path.exists(NAME, index="foo")
        self.assertDictEqual(
            ret,
            {
                "name": NAME,
                "changes": {},
                "result": False,
                "comment": "Index must be an integer",
            },
        )

    def test_exists_add_no_index_success(self):
        """
        Tests win_path.exists when the directory isn't already in the PATH and
        no index is specified (successful run).
        """
        add_mock = MagicMock(return_value=True)
        rehash_mock = MagicMock(return_value=True)
        dunder_salt = {
            "win_path.get_path": MagicMock(
                side_effect=[["foo", "bar", "baz"], ["foo", "bar", "baz", NAME]]
            ),
            "win_path.add": add_mock,
            "win_path.rehash": rehash_mock,
        }
        dunder_opts = {"test": False}

        with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
            win_path.__opts__, dunder_opts
        ):
            ret = win_path.exists(NAME)

        add_mock.assert_called_once_with(NAME, index=None, rehash=False)
        self.assert_called_once(rehash_mock)
        self.assertDictEqual(
            ret,
            {
                "name": NAME,
                "changes": {"index": {"old": None, "new": 3}},
                "result": True,
                "comment": "Added {0} to the PATH.".format(NAME),
            },
        )

    def test_exists_add_no_index_failure(self):
        """
        Tests win_path.exists when the directory isn't already in the PATH and
        no index is specified (failed run).
        """
        add_mock = MagicMock(return_value=False)
        rehash_mock = MagicMock(return_value=True)
        dunder_salt = {
            "win_path.get_path": MagicMock(
                side_effect=[["foo", "bar", "baz"], ["foo", "bar", "baz"]]
            ),
            "win_path.add": add_mock,
            "win_path.rehash": rehash_mock,
        }
        dunder_opts = {"test": False}

        with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
            win_path.__opts__, dunder_opts
        ):
            ret = win_path.exists(NAME)

        add_mock.assert_called_once_with(NAME, index=None, rehash=False)
        rehash_mock.assert_not_called()
        self.assertDictEqual(
            ret,
            {
                "name": NAME,
                "changes": {},
                "result": False,
                "comment": "Failed to add {0} to the PATH.".format(NAME),
            },
        )

    def test_exists_add_no_index_failure_exception(self):
        """
        Tests win_path.exists when the directory isn't already in the PATH and
        no index is specified (failed run due to exception).
        """
        add_mock = MagicMock(side_effect=Exception("Global Thermonuclear War"))
        rehash_mock = MagicMock(return_value=True)
        dunder_salt = {
            "win_path.get_path": MagicMock(
                side_effect=[["foo", "bar", "baz"], ["foo", "bar", "baz"]]
            ),
            "win_path.add": add_mock,
            "win_path.rehash": rehash_mock,
        }
        dunder_opts = {"test": False}

        with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
            win_path.__opts__, dunder_opts
        ):
            ret = win_path.exists(NAME)

        add_mock.assert_called_once_with(NAME, index=None, rehash=False)
        rehash_mock.assert_not_called()
        self.assertDictEqual(
            ret,
            {
                "name": NAME,
                "changes": {},
                "result": False,
                "comment": "Encountered error: Global Thermonuclear War. "
                "Failed to add {0} to the PATH.".format(NAME),
            },
        )

    def test_exists_change_index_success(self):
        """
        Tests win_path.exists when the directory is already in the PATH and
        needs to be moved to a different position (successful run).
        """
        add_mock = MagicMock(return_value=True)
        rehash_mock = MagicMock(return_value=True)
        dunder_salt = {
            "win_path.get_path": MagicMock(
                side_effect=[["foo", "bar", "baz", NAME], [NAME, "foo", "bar", "baz"]]
            ),
            "win_path.add": add_mock,
            "win_path.rehash": rehash_mock,
        }
        dunder_opts = {"test": False}

        with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
            win_path.__opts__, dunder_opts
        ):
            ret = win_path.exists(NAME, index=0)

        add_mock.assert_called_once_with(NAME, index=0, rehash=False)
        self.assert_called_once(rehash_mock)
        self.assertDictEqual(
            ret,
            {
                "name": NAME,
                "changes": {"index": {"old": 3, "new": 0}},
                "result": True,
                "comment": "Moved {0} from index 3 to 0.".format(NAME),
            },
        )

    def test_exists_change_negative_index_success(self):
        """
        Tests win_path.exists when the directory is already in the PATH and
        needs to be moved to a different position (successful run).

        This tests a negative index.
        """
        add_mock = MagicMock(return_value=True)
        rehash_mock = MagicMock(return_value=True)
        dunder_salt = {
            "win_path.get_path": MagicMock(
                side_effect=[["foo", "bar", NAME, "baz"], ["foo", "bar", "baz", NAME]]
            ),
            "win_path.add": add_mock,
            "win_path.rehash": rehash_mock,
        }
        dunder_opts = {"test": False}

        with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
            win_path.__opts__, dunder_opts
        ):
            ret = win_path.exists(NAME, index=-1)

        add_mock.assert_called_once_with(NAME, index=-1, rehash=False)
        self.assert_called_once(rehash_mock)
        self.assertDictEqual(
            ret,
            {
                "name": NAME,
                "changes": {"index": {"old": -2, "new": -1}},
                "result": True,
                "comment": "Moved {0} from index -2 to -1.".format(NAME),
            },
        )

    def test_exists_change_index_add_exception(self):
        """
        Tests win_path.exists when the directory is already in the PATH but an
        exception is raised when we attempt to add the key to its new location.
        """
        add_mock = MagicMock(side_effect=Exception("Global Thermonuclear War"))
        rehash_mock = MagicMock(return_value=True)
        dunder_salt = {
            "win_path.get_path": MagicMock(
                side_effect=[["foo", "bar", "baz", NAME], ["foo", "bar", "baz", NAME]]
            ),
            "win_path.add": add_mock,
            "win_path.rehash": rehash_mock,
        }
        dunder_opts = {"test": False}

        with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
            win_path.__opts__, dunder_opts
        ):
            ret = win_path.exists(NAME, index=0)

        add_mock.assert_called_once_with(NAME, index=0, rehash=False)
        rehash_mock.assert_not_called()
        self.assertDictEqual(
            ret,
            {
                "name": NAME,
                "changes": {},
                "result": False,
                "comment": "Encountered error: Global Thermonuclear War. "
                "Failed to move {0} from index 3 to 0.".format(NAME),
            },
        )

    def test_exists_change_negative_index_add_exception(self):
        """
        Tests win_path.exists when the directory is already in the PATH but an
        exception is raised when we attempt to add the key to its new location.

        This tests a negative index.
        """
        add_mock = MagicMock(side_effect=Exception("Global Thermonuclear War"))
        rehash_mock = MagicMock(return_value=True)
        dunder_salt = {
            "win_path.get_path": MagicMock(
                side_effect=[["foo", "bar", NAME, "baz"], ["foo", "bar", NAME, "baz"]]
            ),
            "win_path.add": add_mock,
            "win_path.rehash": rehash_mock,
        }
        dunder_opts = {"test": False}

        with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
            win_path.__opts__, dunder_opts
        ):
            ret = win_path.exists(NAME, index=-1)

        add_mock.assert_called_once_with(NAME, index=-1, rehash=False)
        rehash_mock.assert_not_called()
        self.assertDictEqual(
            ret,
            {
                "name": NAME,
                "changes": {},
                "result": False,
                "comment": "Encountered error: Global Thermonuclear War. "
                "Failed to move {0} from index -2 to -1.".format(NAME),
            },
        )

    def test_exists_change_index_failure(self):
        """
        Tests win_path.exists when the directory is already in the PATH and
        needs to be moved to a different position (failed run).
        """
        add_mock = MagicMock(return_value=False)
        rehash_mock = MagicMock(return_value=True)
        dunder_salt = {
            "win_path.get_path": MagicMock(
                side_effect=[["foo", "bar", "baz", NAME], ["foo", "bar", "baz", NAME]]
            ),
            "win_path.add": add_mock,
            "win_path.rehash": rehash_mock,
        }
        dunder_opts = {"test": False}

        with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
            win_path.__opts__, dunder_opts
        ):
            ret = win_path.exists(NAME, index=0)

        add_mock.assert_called_once_with(NAME, index=0, rehash=False)
        rehash_mock.assert_not_called()
        self.assertDictEqual(
            ret,
            {
                "name": NAME,
                "changes": {},
                "result": False,
                "comment": "Failed to move {0} from index 3 to 0.".format(NAME),
            },
        )

    def test_exists_change_negative_index_failure(self):
        """
        Tests win_path.exists when the directory is already in the PATH and
        needs to be moved to a different position (failed run).

        This tests a negative index.
        """
        add_mock = MagicMock(return_value=False)
        rehash_mock = MagicMock(return_value=True)
        dunder_salt = {
            "win_path.get_path": MagicMock(
                side_effect=[["foo", "bar", NAME, "baz"], ["foo", "bar", NAME, "baz"]]
            ),
            "win_path.add": add_mock,
            "win_path.rehash": rehash_mock,
        }
        dunder_opts = {"test": False}

        with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
            win_path.__opts__, dunder_opts
        ):
            ret = win_path.exists(NAME, index=-1)

        add_mock.assert_called_once_with(NAME, index=-1, rehash=False)
        rehash_mock.assert_not_called()
        self.assertDictEqual(
            ret,
            {
                "name": NAME,
                "changes": {},
                "result": False,
                "comment": "Failed to move {0} from index -2 to -1.".format(NAME),
            },
        )

    def test_exists_change_index_test_mode(self):
        """
        Tests win_path.exists when the directory is already in the PATH and
        needs to be moved to a different position (test mode enabled).
        """
        add_mock = Mock()
        rehash_mock = MagicMock(return_value=True)
        dunder_salt = {
            "win_path.get_path": MagicMock(side_effect=[["foo", "bar", "baz", NAME]]),
            "win_path.add": add_mock,
            "win_path.rehash": rehash_mock,
        }
        dunder_opts = {"test": True}

        with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
            win_path.__opts__, dunder_opts
        ):
            ret = win_path.exists(NAME, index=0)

        add_mock.assert_not_called()
        rehash_mock.assert_not_called()
        self.assertDictEqual(
            ret,
            {
                "name": NAME,
                "changes": {"index": {"old": 3, "new": 0}},
                "result": None,
                "comment": "{0} would be moved from index 3 to 0.".format(NAME),
            },
        )

    def test_exists_change_negative_index_test_mode(self):
        """
        Tests win_path.exists when the directory is already in the PATH and
        needs to be moved to a different position (test mode enabled).
        """
        add_mock = Mock()
        rehash_mock = MagicMock(return_value=True)
        dunder_salt = {
            "win_path.get_path": MagicMock(side_effect=[["foo", "bar", NAME, "baz"]]),
            "win_path.add": add_mock,
            "win_path.rehash": rehash_mock,
        }
        dunder_opts = {"test": True}

        with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
            win_path.__opts__, dunder_opts
        ):
            ret = win_path.exists(NAME, index=-1)

        add_mock.assert_not_called()
        rehash_mock.assert_not_called()
        self.assertDictEqual(
            ret,
            {
                "name": NAME,
                "changes": {"index": {"old": -2, "new": -1}},
                "result": None,
                "comment": "{0} would be moved from index -2 to -1.".format(NAME),
            },
        )

    def _test_exists_add_already_present(self, index, test_mode):
        """
        Tests win_path.exists when the directory already exists in the PATH.
        Helper function to test both with and without and index, and with test
        mode both disabled and enabled.
        """
        current_path = ["foo", "bar", "baz"]
        if index is None:
            current_path.append(NAME)
        else:
            pos = index if index >= 0 else len(current_path) + index + 1
            current_path.insert(pos, NAME)

        add_mock = Mock()
        rehash_mock = MagicMock(return_value=True)
        dunder_salt = {
            "win_path.get_path": MagicMock(side_effect=[current_path]),
            "win_path.add": add_mock,
            "win_path.rehash": rehash_mock,
        }
        dunder_opts = {"test": test_mode}

        with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
            win_path.__opts__, dunder_opts
        ):
            ret = win_path.exists(NAME, index=index)

        add_mock.assert_not_called()
        rehash_mock.assert_not_called()
        self.assertDictEqual(
            ret,
            {
                "name": NAME,
                "changes": {},
                "result": True,
                "comment": "{0} already exists in the PATH{1}.".format(
                    NAME, " at index {0}".format(index) if index is not None else ""
                ),
            },
        )

    def test_exists_add_no_index_already_present(self):
        self._test_exists_add_already_present(None, False)

    def test_exists_add_no_index_already_present_test_mode(self):
        self._test_exists_add_already_present(None, True)

    def test_exists_add_index_already_present(self):
        self._test_exists_add_already_present(1, False)
        self._test_exists_add_already_present(2, False)
        self._test_exists_add_already_present(-1, False)
        self._test_exists_add_already_present(-2, False)

    def test_exists_add_index_already_present_test_mode(self):
        self._test_exists_add_already_present(1, True)
        self._test_exists_add_already_present(2, True)
        self._test_exists_add_already_present(-1, True)
        self._test_exists_add_already_present(-2, True)
