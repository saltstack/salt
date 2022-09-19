"""
    Test cases for salt.modules.etcd_mod

    Note: No functional tests are required as of now, as this is
    essentially a wrapper around salt.utils.etcd_util.
    If the contents of this module were to add more logic besides
    acting as a wrapper, then functional tests would be required.

    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""


import pytest

import salt.modules.etcd_mod as etcd_mod
import salt.utils.etcd_util as etcd_util
from tests.support.mock import MagicMock, create_autospec, patch


@pytest.fixture
def configure_loader_modules():
    return {etcd_mod: {}}


@pytest.fixture
def instance():
    return create_autospec(etcd_util.EtcdBase)


@pytest.fixture
def etcd_client_mock(instance):
    mocked_client = MagicMock()
    mocked_client.return_value = instance
    return mocked_client


# 'get_' function tests: 1


def test_get(etcd_client_mock, instance):
    """
    Test if it get a value from etcd, by direct path
    """
    with patch.dict(etcd_mod.__utils__, {"etcd_util.get_conn": etcd_client_mock}):
        instance.get.return_value = "stack"
        assert etcd_mod.get_("salt") == "stack"
        instance.get.assert_called_with("salt", recurse=False)

        instance.get.return_value = {"salt": "stack"}
        assert etcd_mod.get_("salt", recurse=True) == {"salt": "stack"}
        instance.get.assert_called_with("salt", recurse=True)

        instance.get.side_effect = Exception
        pytest.raises(Exception, etcd_mod.get_, "err")


# 'set_' function tests: 1


def test_set(etcd_client_mock, instance):
    """
    Test if it set a key in etcd, by direct path
    """
    with patch.dict(etcd_mod.__utils__, {"etcd_util.get_conn": etcd_client_mock}):
        instance.set.return_value = "stack"
        assert etcd_mod.set_("salt", "stack") == "stack"
        instance.set.assert_called_with("salt", "stack", directory=False, ttl=None)

        instance.set.return_value = True
        assert etcd_mod.set_("salt", "", directory=True) is True
        instance.set.assert_called_with("salt", "", directory=True, ttl=None)

        assert etcd_mod.set_("salt", "", directory=True, ttl=5) is True
        instance.set.assert_called_with("salt", "", directory=True, ttl=5)

        assert etcd_mod.set_("salt", "", None, 10, True) is True
        instance.set.assert_called_with("salt", "", directory=True, ttl=10)

        instance.set.side_effect = Exception
        pytest.raises(Exception, etcd_mod.set_, "err", "stack")


# 'update' function tests: 1


def test_update(etcd_client_mock, instance):
    """
    Test if can set multiple keys in etcd
    """
    with patch.dict(etcd_mod.__utils__, {"etcd_util.get_conn": etcd_client_mock}):
        args = {
            "x": {"y": {"a": "1", "b": "2"}},
            "z": "4",
            "d": {},
        }

        result = {
            "/some/path/x/y/a": "1",
            "/some/path/x/y/b": "2",
            "/some/path/z": "4",
            "/some/path/d": {},
        }
        instance.update.return_value = result
        assert etcd_mod.update(args, path="/some/path") == result
        instance.update.assert_called_with(args, "/some/path")
        assert etcd_mod.update(args) == result
        instance.update.assert_called_with(args, "")


# 'ls_' function tests: 1


def test_ls(etcd_client_mock, instance):
    """
    Test if it return all keys and dirs inside a specific path
    """
    with patch.dict(etcd_mod.__utils__, {"etcd_util.get_conn": etcd_client_mock}):
        instance.ls.return_value = {"/some-dir": {}}
        assert etcd_mod.ls_("/some-dir") == {"/some-dir": {}}
        instance.ls.assert_called_with("/some-dir")

        instance.ls.return_value = {"/": {}}
        assert etcd_mod.ls_() == {"/": {}}
        instance.ls.assert_called_with("/")

        instance.ls.side_effect = Exception
        pytest.raises(Exception, etcd_mod.ls_, "err")


# 'rm_' function tests: 1


def test_rm(etcd_client_mock, instance):
    """
    Test if it delete a key from etcd
    """
    with patch.dict(etcd_mod.__utils__, {"etcd_util.get_conn": etcd_client_mock}):
        instance.rm.return_value = False
        assert not etcd_mod.rm_("dir")
        instance.rm.assert_called_with("dir", recurse=False)

        instance.rm.return_value = True
        assert etcd_mod.rm_("dir", recurse=True)
        instance.rm.assert_called_with("dir", recurse=True)

        instance.rm.side_effect = Exception
        pytest.raises(Exception, etcd_mod.rm_, "err")


# 'tree' function tests: 1


def test_tree(etcd_client_mock, instance):
    """
    Test if it recurses through etcd and return all values
    """
    with patch.dict(etcd_mod.__utils__, {"etcd_util.get_conn": etcd_client_mock}):
        instance.tree.return_value = {}
        assert etcd_mod.tree("/some-dir") == {}
        instance.tree.assert_called_with("/some-dir")

        assert etcd_mod.tree() == {}
        instance.tree.assert_called_with("/")

        instance.tree.side_effect = Exception
        pytest.raises(Exception, etcd_mod.tree, "err")


# 'watch' function tests: 1


def test_watch(etcd_client_mock, instance):
    """
    Test if watch returns the right tuples
    """
    with patch.dict(etcd_mod.__utils__, {"etcd_util.get_conn": etcd_client_mock}):
        instance.watch.return_value = {
            "value": "stack",
            "changed": True,
            "dir": False,
            "mIndex": 1,
            "key": "/salt",
        }
        assert etcd_mod.watch("/salt") == instance.watch.return_value
        instance.watch.assert_called_with("/salt", recurse=False, timeout=0, index=None)

        instance.watch.return_value["dir"] = True
        assert (
            etcd_mod.watch("/some-dir", recurse=True, timeout=5, index=10)
            == instance.watch.return_value
        )
        instance.watch.assert_called_with(
            "/some-dir", recurse=True, timeout=5, index=10
        )

        assert (
            etcd_mod.watch("/some-dir", True, None, 5, 10)
            == instance.watch.return_value
        )
        instance.watch.assert_called_with(
            "/some-dir", recurse=True, timeout=5, index=10
        )
