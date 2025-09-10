"""
    Test cases for salt.states.etcd_mod

    Note: No functional tests are required as of now, as all of the
    functional pieces are already tested in utils.test_etcd_utils
    If the contents of this state were to add more logic besides
    essentially acting as a wrapper, then functional tests would be required.

    :codeauthor: Caleb Beard <calebb@vmware.com>
"""

import pytest

import salt.states.etcd_mod as etcd_state
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {etcd_state: {}}


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

        # Test setting the same value to a key
        get_mock.return_value = "value"
        set_mock.return_value = "value"
        expected = {
            "name": "key",
            "comment": "Key contains correct value",
            "result": True,
            "changes": {},
        }
        assert etcd_state.set_("key", "value", profile="test") == expected


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
    Test the etcd_mod.directory state function
    """
    get_mock = MagicMock()
    set_mock = MagicMock()
    dunder_salt = {
        "etcd.get": get_mock,
        "etcd.set": set_mock,
    }

    with patch.dict(etcd_state.__salt__, dunder_salt):
        # Test new directory creation
        get_mock.return_value = None
        set_mock.return_value = "new_dir"
        expected = {
            "name": "new_dir",
            "comment": "New directory created",
            "result": True,
            "changes": {"new_dir": "Created"},
        }
        assert etcd_state.directory("new_dir", profile="test") == expected

        # Test creating an existing directory
        get_mock.return_value = "new_dir"
        set_mock.return_value = "new_dir"
        expected = {
            "name": "new_dir",
            "comment": "Directory exists",
            "result": True,
            "changes": {},
        }
        assert etcd_state.directory("new_dir", profile="test") == expected


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

        # Test failing to remove an existing key
        get_mock.return_value = "value"
        rm_mock.return_value = False
        expected = {
            "name": "key",
            "comment": "Unable to remove key",
            "result": True,
            "changes": {},
        }
        assert etcd_state.rm("key", profile="test") == expected

        # Test removing a nonexistent key
        get_mock.return_value = False
        expected = {
            "name": "key",
            "comment": "Key does not exist",
            "result": True,
            "changes": {},
        }
        assert etcd_state.rm("key", profile="test") == expected


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
