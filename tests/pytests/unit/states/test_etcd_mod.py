"""
    Test cases for salt.states.etcd_mod

    Note: No functional tests are required as of now, as all of the
    functional pieces are already tested in utils.test_etcd_utils
    If the contents of this state were to add more logic besides
    essentially acting as a wrapper, then functional tests would be required.

    :codeauthor: Caleb Beard
"""

import pytest

import salt.states.etcd_mod as etcd_state
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def configure_loader_modules():
    return {etcd_state: {"__opts__": {"test": False}}}


def test_set():
    """
    Test the etcd_mod.set state function
    """
    get_mock = MagicMock()
    set_mock = MagicMock()
    dunder_salt = {
        "etcd.get": get_mock,
        "etcd.set": set_mock,
    }

    with patch.dict(etcd_state.__salt__, dunder_salt):
        # Test new key creation
        get_mock.return_value = None
        set_mock.return_value = "new value"
        expected = {
            "name": "new_key",
            "comment": "New key created",
            "result": True,
            "changes": {"new_key": "new value"},
        }
        assert etcd_state.set_("new_key", "new value", profile="test") == expected

        # Test key updating
        get_mock.return_value = "old value"
        set_mock.return_value = "new value"
        expected = {
            "name": "new_key",
            "comment": "Key value updated",
            "result": True,
            "changes": {"new_key": "new value"},
        }
        assert etcd_state.set_("new_key", "new value", profile="test") == expected

        # Test setting the same value to a key does not write it again
        set_mock.reset_mock()
        get_mock.return_value = "value"
        expected = {
            "name": "key",
            "comment": "Key contains correct value",
            "result": True,
            "changes": {},
        }
        assert etcd_state.set_("key", "value", profile="test") == expected
        set_mock.assert_not_called()

        # A new key can be created without a profile
        get_mock.return_value = None
        assert etcd_state.set_("new_key", "new value")["result"] is True


def test_set_test_mode():
    get_mock = MagicMock(return_value=None)
    set_mock = MagicMock()
    dunder_salt = {"etcd.get": get_mock, "etcd.set": set_mock}
    with patch.dict(etcd_state.__salt__, dunder_salt), patch.dict(
        etcd_state.__opts__, {"test": True}
    ):
        assert etcd_state.set_("key", "value", profile="test") == {
            "name": "key",
            "comment": "Key would be created",
            "result": None,
            "changes": {"key": "value"},
        }
        get_mock.return_value = "old"
        assert etcd_state.set_("key", "value")["comment"] == "Key would be updated"
        set_mock.assert_not_called()


def test_set_error():
    get_mock = MagicMock(side_effect=CommandExecutionError("etcd3: cannot read key"))
    set_mock = MagicMock()
    dunder_salt = {"etcd.get": get_mock, "etcd.set": set_mock}
    with patch.dict(etcd_state.__salt__, dunder_salt):
        assert etcd_state.set_("key", "value", profile="test") == {
            "name": "key",
            "comment": "etcd3: cannot read key",
            "result": False,
            "changes": {},
        }
        set_mock.assert_not_called()


def test_wait_set():
    """
    Test the etcd_mod.wait_set state function
    """
    expected = {
        "name": "key",
        "changes": {},
        "result": True,
        "comment": "",
    }
    assert etcd_state.wait_set("key", "any value", profile="test") == expected


def test_directory():
    """
    etcd v3 has no directories, so the directory state always fails.
    """
    set_mock = MagicMock()
    with patch.dict(etcd_state.__salt__, {"etcd.set": set_mock}):
        ret = etcd_state.directory("new_dir", profile="test")
    assert ret["result"] is False
    assert ret["changes"] == {}
    assert "no directories" in ret["comment"]
    set_mock.assert_not_called()


def test_rm():
    """
    Test the etcd_mod.set state function
    """
    get_mock = MagicMock()
    rm_mock = MagicMock()
    dunder_salt = {
        "etcd.get": get_mock,
        "etcd.rm": rm_mock,
    }

    with patch.dict(etcd_state.__salt__, dunder_salt):
        # Test removing a key
        get_mock.return_value = "value"
        rm_mock.return_value = True
        expected = {
            "name": "key",
            "comment": "Key removed",
            "result": True,
            "changes": {"key": "Deleted"},
        }
        assert etcd_state.rm("key", profile="test") == expected

        # The key was gone by the time it was removed
        get_mock.return_value = "value"
        rm_mock.return_value = False
        expected = {
            "name": "key",
            "comment": "Key does not exist",
            "result": True,
            "changes": {},
        }
        assert etcd_state.rm("key", profile="test") == expected

        # recurse is used for both the lookup and the removal
        get_mock.reset_mock()
        rm_mock.reset_mock()
        get_mock.return_value = {"child": "value"}
        rm_mock.return_value = True
        etcd_state.rm("key", recurse=True, profile="test")
        get_mock.assert_called_once_with("key", recurse=True, profile="test")
        rm_mock.assert_called_once_with("key", recurse=True, profile="test")

        # An etcd error fails the state
        rm_mock.side_effect = CommandExecutionError("etcd3: cannot delete key")
        assert etcd_state.rm("key", profile="test") == {
            "name": "key",
            "comment": "etcd3: cannot delete key",
            "result": False,
            "changes": {},
        }

        # Test removing a nonexistent key
        rm_mock.side_effect = None
        get_mock.return_value = None
        expected = {
            "name": "key",
            "comment": "Key does not exist",
            "result": True,
            "changes": {},
        }
        assert etcd_state.rm("key", profile="test") == expected


def test_rm_test_mode():
    get_mock = MagicMock(return_value="value")
    rm_mock = MagicMock()
    dunder_salt = {"etcd.get": get_mock, "etcd.rm": rm_mock}
    with patch.dict(etcd_state.__salt__, dunder_salt), patch.dict(
        etcd_state.__opts__, {"test": True}
    ):
        assert etcd_state.rm("key", profile="test") == {
            "name": "key",
            "comment": "Key would be removed",
            "result": None,
            "changes": {"key": "Deleted"},
        }
    rm_mock.assert_not_called()


def test_wait_rm():
    """
    Test the etcd_mod.wait_rm state function
    """
    expected = {
        "name": "key",
        "changes": {},
        "result": True,
        "comment": "",
    }
    assert etcd_state.wait_rm("key", profile="test") == expected


def test_mod_watch():
    """
    Test the watch requisite function etcd_mod.mod_watch
    """
    get_mock = MagicMock()
    set_mock = MagicMock()
    rm_mock = MagicMock()
    dunder_salt = {
        "etcd.get": get_mock,
        "etcd.set": set_mock,
        "etcd.rm": rm_mock,
    }

    with patch.dict(etcd_state.__salt__, dunder_salt):
        # Test watch with wait_set
        get_mock.return_value = None
        set_mock.return_value = "value"
        expected = {
            "name": "key",
            "comment": "New key created",
            "result": True,
            "changes": {"key": "value"},
        }
        assert (
            etcd_state.mod_watch("key", value="value", sfun="wait_set", profile={})
            == expected
        )
        assert (
            etcd_state.mod_watch("key", value="value", sfun="wait_set_key", profile={})
            == expected
        )

        # Test watch with wait_rm
        get_mock.return_value = "value"
        rm_mock.return_value = True
        expected = {
            "name": "key",
            "comment": "Key removed",
            "result": True,
            "changes": {"key": "Deleted"},
        }
        assert etcd_state.mod_watch("key", sfun="wait_rm", profile={}) == expected
        assert etcd_state.mod_watch("key", sfun="wait_rm_key", profile={}) == expected

        # recurse and connection overrides reach the removal
        rm_mock.reset_mock()
        etcd_state.mod_watch(
            "key",
            sfun="wait_rm",
            recurse=True,
            profile="test",
            host="etcd.example",
            __reqs__={},
        )
        assert rm_mock.call_args == call(
            "key", recurse=True, profile="test", host="etcd.example"
        )

        # Test watch with bad sfun
        kwargs = {"sfun": "bad_sfun"}
        expected = {
            "name": "key",
            "changes": {},
            "comment": (
                "etcd.{0[sfun]} does not work with the watch requisite, "
                "please use etcd.wait_set or etcd.wait_rm".format(kwargs)
            ),
            "result": False,
        }
        assert etcd_state.mod_watch("key", **kwargs) == expected
        assert etcd_state.mod_watch("key", **kwargs) == expected
