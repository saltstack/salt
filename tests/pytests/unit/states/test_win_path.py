"""
Tests for win_path states
"""

import copy

import pytest
import salt.states.win_path as win_path
from tests.support.mock import MagicMock, Mock, patch


@pytest.fixture
def name():
    return "salt"


@pytest.fixture
def configure_loader_modules():
    return {win_path: {}}


def test_absent(name):
    """
    Test various cases for win_path.absent
    """
    ret_base = {"name": name, "result": True, "changes": {}}

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
                ret["comment"] = "{} is not in the PATH".format(name)
                ret["result"] = True
                assert win_path.absent(name) == ret

            # Test successful removal
            with patch.dict(
                win_path.__salt__, {"win_path.exists": _mock([True, False])}
            ):
                ret = copy.deepcopy(ret_base)
                ret["comment"] = "Removed {} from the PATH".format(name)
                ret["changes"]["removed"] = name
                ret["result"] = True
                assert win_path.absent(name) == ret

            # Test unsucessful removal
            with patch.dict(
                win_path.__salt__, {"win_path.exists": _mock([True, True])}
            ):
                ret = copy.deepcopy(ret_base)
                ret["comment"] = "Failed to remove {} from the PATH".format(name)
                ret["result"] = False
                assert win_path.absent(name) == ret

        # Test mode ON
        with patch.dict(win_path.__opts__, {"test": True}):

            # Test already absent
            with patch.dict(win_path.__salt__, {"win_path.exists": _mock([False])}):
                ret = copy.deepcopy(ret_base)
                ret["comment"] = "{} is not in the PATH".format(name)
                ret["result"] = True
                assert win_path.absent(name) == ret

            # Test the test-mode return
            with patch.dict(win_path.__salt__, {"win_path.exists": _mock([True])}):
                ret = copy.deepcopy(ret_base)
                ret["comment"] = "{} would be removed from the PATH".format(name)
                ret["result"] = None
                assert win_path.absent(name) == ret


def test_exists_invalid_index(name):
    """
    Tests win_path.exists when a non-integer index is specified.
    """
    ret = win_path.exists(name, index="foo")
    assert ret == {
        "name": name,
        "changes": {},
        "result": False,
        "comment": "Index must be an integer",
    }


def test_exists_add_no_index_success(name):
    """
    Tests win_path.exists when the directory isn't already in the PATH and
    no index is specified (successful run).
    """
    add_mock = MagicMock(return_value=True)
    rehash_mock = MagicMock(return_value=True)
    dunder_salt = {
        "win_path.get_path": MagicMock(
            side_effect=[["foo", "bar", "baz"], ["foo", "bar", "baz", name]]
        ),
        "win_path.add": add_mock,
        "win_path.rehash": rehash_mock,
    }
    dunder_opts = {"test": False}

    with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
        win_path.__opts__, dunder_opts
    ):
        ret = win_path.exists(name)

    add_mock.assert_called_once_with(name, index=None, rehash=False)
    rehash_mock.assert_called_once_with()
    assert ret == {
        "name": name,
        "changes": {"index": {"old": None, "new": 3}},
        "result": True,
        "comment": "Added {} to the PATH.".format(name),
    }


def test_exists_add_no_index_failure(name):
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
        ret = win_path.exists(name)

    add_mock.assert_called_once_with(name, index=None, rehash=False)
    rehash_mock.assert_not_called()
    assert ret == {
        "name": name,
        "changes": {},
        "result": False,
        "comment": "Failed to add {} to the PATH.".format(name),
    }


def test_exists_add_no_index_failure_exception(name):
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
        ret = win_path.exists(name)

    add_mock.assert_called_once_with(name, index=None, rehash=False)
    rehash_mock.assert_not_called()
    assert ret == {
        "name": name,
        "changes": {},
        "result": False,
        "comment": (
            "Encountered error: Global Thermonuclear War. "
            "Failed to add {} to the PATH.".format(name)
        ),
    }


def test_exists_change_index_success(name):
    """
    Tests win_path.exists when the directory is already in the PATH and
    needs to be moved to a different position (successful run).
    """
    add_mock = MagicMock(return_value=True)
    rehash_mock = MagicMock(return_value=True)
    dunder_salt = {
        "win_path.get_path": MagicMock(
            side_effect=[["foo", "bar", "baz", name], [name, "foo", "bar", "baz"]]
        ),
        "win_path.add": add_mock,
        "win_path.rehash": rehash_mock,
    }
    dunder_opts = {"test": False}

    with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
        win_path.__opts__, dunder_opts
    ):
        ret = win_path.exists(name, index=0)

    add_mock.assert_called_once_with(name, index=0, rehash=False)
    rehash_mock.assert_called_once()
    assert ret == {
        "name": name,
        "changes": {"index": {"old": 3, "new": 0}},
        "result": True,
        "comment": "Moved {} from index 3 to 0.".format(name),
    }


def test_exists_change_negative_index_success(name):
    """
    Tests win_path.exists when the directory is already in the PATH and
    needs to be moved to a different position (successful run).

    This tests a negative index.
    """
    add_mock = MagicMock(return_value=True)
    rehash_mock = MagicMock(return_value=True)
    dunder_salt = {
        "win_path.get_path": MagicMock(
            side_effect=[["foo", "bar", name, "baz"], ["foo", "bar", "baz", name]]
        ),
        "win_path.add": add_mock,
        "win_path.rehash": rehash_mock,
    }
    dunder_opts = {"test": False}

    with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
        win_path.__opts__, dunder_opts
    ):
        ret = win_path.exists(name, index=-1)

    add_mock.assert_called_once_with(name, index=-1, rehash=False)
    rehash_mock.assert_called_once()
    assert ret == {
        "name": name,
        "changes": {"index": {"old": -2, "new": -1}},
        "result": True,
        "comment": "Moved {} from index -2 to -1.".format(name),
    }


def test_exists_change_index_add_exception(name):
    """
    Tests win_path.exists when the directory is already in the PATH but an
    exception is raised when we attempt to add the key to its new location.
    """
    add_mock = MagicMock(side_effect=Exception("Global Thermonuclear War"))
    rehash_mock = MagicMock(return_value=True)
    dunder_salt = {
        "win_path.get_path": MagicMock(
            side_effect=[["foo", "bar", "baz", name], ["foo", "bar", "baz", name]]
        ),
        "win_path.add": add_mock,
        "win_path.rehash": rehash_mock,
    }
    dunder_opts = {"test": False}

    with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
        win_path.__opts__, dunder_opts
    ):
        ret = win_path.exists(name, index=0)

    add_mock.assert_called_once_with(name, index=0, rehash=False)
    rehash_mock.assert_not_called()
    assert ret == {
        "name": name,
        "changes": {},
        "result": False,
        "comment": (
            "Encountered error: Global Thermonuclear War. "
            "Failed to move {} from index 3 to 0.".format(name)
        ),
    }


def test_exists_change_negative_index_add_exception(name):
    """
    Tests win_path.exists when the directory is already in the PATH but an
    exception is raised when we attempt to add the key to its new location.

    This tests a negative index.
    """
    add_mock = MagicMock(side_effect=Exception("Global Thermonuclear War"))
    rehash_mock = MagicMock(return_value=True)
    dunder_salt = {
        "win_path.get_path": MagicMock(
            side_effect=[["foo", "bar", name, "baz"], ["foo", "bar", name, "baz"]]
        ),
        "win_path.add": add_mock,
        "win_path.rehash": rehash_mock,
    }
    dunder_opts = {"test": False}

    with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
        win_path.__opts__, dunder_opts
    ):
        ret = win_path.exists(name, index=-1)

    add_mock.assert_called_once_with(name, index=-1, rehash=False)
    rehash_mock.assert_not_called()
    assert ret == {
        "name": name,
        "changes": {},
        "result": False,
        "comment": (
            "Encountered error: Global Thermonuclear War. "
            "Failed to move {} from index -2 to -1.".format(name)
        ),
    }


def test_exists_change_index_failure(name):
    """
    Tests win_path.exists when the directory is already in the PATH and
    needs to be moved to a different position (failed run).
    """
    add_mock = MagicMock(return_value=False)
    rehash_mock = MagicMock(return_value=True)
    dunder_salt = {
        "win_path.get_path": MagicMock(
            side_effect=[["foo", "bar", "baz", name], ["foo", "bar", "baz", name]]
        ),
        "win_path.add": add_mock,
        "win_path.rehash": rehash_mock,
    }
    dunder_opts = {"test": False}

    with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
        win_path.__opts__, dunder_opts
    ):
        ret = win_path.exists(name, index=0)

    add_mock.assert_called_once_with(name, index=0, rehash=False)
    rehash_mock.assert_not_called()
    assert ret == {
        "name": name,
        "changes": {},
        "result": False,
        "comment": "Failed to move {} from index 3 to 0.".format(name),
    }


def test_exists_change_negative_index_failure(name):
    """
    Tests win_path.exists when the directory is already in the PATH and
    needs to be moved to a different position (failed run).

    This tests a negative index.
    """
    add_mock = MagicMock(return_value=False)
    rehash_mock = MagicMock(return_value=True)
    dunder_salt = {
        "win_path.get_path": MagicMock(
            side_effect=[["foo", "bar", name, "baz"], ["foo", "bar", name, "baz"]]
        ),
        "win_path.add": add_mock,
        "win_path.rehash": rehash_mock,
    }
    dunder_opts = {"test": False}

    with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
        win_path.__opts__, dunder_opts
    ):
        ret = win_path.exists(name, index=-1)

    add_mock.assert_called_once_with(name, index=-1, rehash=False)
    rehash_mock.assert_not_called()
    assert ret == {
        "name": name,
        "changes": {},
        "result": False,
        "comment": "Failed to move {} from index -2 to -1.".format(name),
    }


def test_exists_change_index_test_mode(name):
    """
    Tests win_path.exists when the directory is already in the PATH and
    needs to be moved to a different position (test mode enabled).
    """
    add_mock = Mock()
    rehash_mock = MagicMock(return_value=True)
    dunder_salt = {
        "win_path.get_path": MagicMock(side_effect=[["foo", "bar", "baz", name]]),
        "win_path.add": add_mock,
        "win_path.rehash": rehash_mock,
    }
    dunder_opts = {"test": True}

    with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
        win_path.__opts__, dunder_opts
    ):
        ret = win_path.exists(name, index=0)

    add_mock.assert_not_called()
    rehash_mock.assert_not_called()
    assert ret == {
        "name": name,
        "changes": {"index": {"old": 3, "new": 0}},
        "result": None,
        "comment": "{} would be moved from index 3 to 0.".format(name),
    }


def test_exists_change_negative_index_test_mode(name):
    """
    Tests win_path.exists when the directory is already in the PATH and
    needs to be moved to a different position (test mode enabled).
    """
    add_mock = Mock()
    rehash_mock = MagicMock(return_value=True)
    dunder_salt = {
        "win_path.get_path": MagicMock(side_effect=[["foo", "bar", name, "baz"]]),
        "win_path.add": add_mock,
        "win_path.rehash": rehash_mock,
    }
    dunder_opts = {"test": True}

    with patch.dict(win_path.__salt__, dunder_salt), patch.dict(
        win_path.__opts__, dunder_opts
    ):
        ret = win_path.exists(name, index=-1)

    add_mock.assert_not_called()
    rehash_mock.assert_not_called()
    assert ret == {
        "name": name,
        "changes": {"index": {"old": -2, "new": -1}},
        "result": None,
        "comment": "{} would be moved from index -2 to -1.".format(name),
    }


def _test_exists_add_already_present(index, test_mode, name):
    """
    Tests win_path.exists when the directory already exists in the PATH.
    Helper function to test both with and without and index, and with test
    mode both disabled and enabled.
    """
    current_path = ["foo", "bar", "baz"]
    if index is None:
        current_path.append(name)
    else:
        pos = index if index >= 0 else len(current_path) + index + 1
        current_path.insert(pos, name)

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
        ret = win_path.exists(name, index=index)

    add_mock.assert_not_called()
    rehash_mock.assert_not_called()
    assert ret == {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "{} already exists in the PATH{}.".format(
            name, " at index {}".format(index) if index is not None else ""
        ),
    }


def test_exists_add_no_index_already_present(name):
    _test_exists_add_already_present(None, False, name)


def test_exists_add_no_index_already_present_test_mode(name):
    _test_exists_add_already_present(None, True, name)


def test_exists_add_index_already_present(name):
    _test_exists_add_already_present(1, False, name)
    _test_exists_add_already_present(2, False, name)
    _test_exists_add_already_present(-1, False, name)
    _test_exists_add_already_present(-2, False, name)


def test_exists_add_index_already_present_test_mode(name):
    _test_exists_add_already_present(1, True, name)
    _test_exists_add_already_present(2, True, name)
    _test_exists_add_already_present(-1, True, name)
    _test_exists_add_already_present(-2, True, name)
