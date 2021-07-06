import os

import pytest
import salt.modules.environ as envmodule
import salt.modules.reg
import salt.states.environ as envstate
import salt.utils.platform
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    loader_globals = {
        "__env__": "base",
        "__opts__": {"test": False},
        "__salt__": {"environ.setenv": envmodule.setenv},
    }
    return {envstate: loader_globals, envmodule: loader_globals}


def test_setenv():
    """
    test that a subsequent calls of setenv changes nothing
    """
    ret = envstate.setenv("test", "value")
    assert ret["changes"] == {"test": "value"}

    ret = envstate.setenv("test", "other")
    assert ret["changes"] == {"test": "other"}

    # once again with the same value
    ret = envstate.setenv("test", "other")
    assert ret["changes"] == {}


@pytest.mark.skip_unless_on_windows
def test_setenv_permanent():
    """
    test that we can set permanent environment variables (requires pywin32)
    """
    with patch.dict(
        envmodule.__utils__,
        {
            "reg.set_value": MagicMock(),
            "reg.delete_value": MagicMock(),
            "win_functions.broadcast_setting_change": MagicMock(),
        },
    ):
        ret = envstate.setenv("test", "value", permanent=True)
        assert ret["changes"] == {"test": "value"}
        envmodule.__utils__["reg.set_value"].assert_called_with(
            "HKCU", "Environment", "test", "value"
        )

        ret = envstate.setenv("test", False, false_unsets=True, permanent=True)
        assert ret["changes"] == {"test": None}
        envmodule.__utils__["reg.delete_value"].assert_called_with(
            "HKCU", "Environment", "test"
        )


def test_setenv_dict():
    """
    test that setenv can be invoked with dict
    """
    ret = envstate.setenv("notimportant", {"test": "value"})
    assert ret["changes"] == {"test": "value"}


def test_setenv_int():
    """
    test that setenv can not be invoked with int
    (actually it's anything other than strings and dict)
    """
    ret = envstate.setenv("test", 1)
    assert ret["result"] is False


def test_setenv_unset():
    """
    test that ``false_unsets`` option removes variable from environment
    """
    with patch.dict(os.environ, {"INITIAL": "initial"}, clear=True):
        ret = envstate.setenv("test", "value")
        assert ret["changes"] == {"test": "value"}

        ret = envstate.setenv("notimportant", {"test": False}, false_unsets=True)
        assert ret["changes"] == {"test": None}
        assert envstate.os.environ == {"INITIAL": "initial"}


def test_setenv_clearall():
    """
    test that ``clear_all`` option sets other values to ''
    """
    with patch.dict(os.environ, {"INITIAL": "initial"}, clear=True):
        ret = envstate.setenv("test", "value", clear_all=True)
        assert ret["changes"] == {"test": "value", "INITIAL": ""}
        if salt.utils.platform.is_windows():
            assert envstate.os.environ == {"TEST": "value", "INITIAL": ""}
        else:
            assert envstate.os.environ == {"test": "value", "INITIAL": ""}


def test_setenv_clearall_with_unset():
    """
    test that ``clear_all`` option combined with ``false_unsets``
    unsets other values from environment
    """
    with patch.dict(os.environ, {"INITIAL": "initial"}, clear=True):
        ret = envstate.setenv("test", "value", false_unsets=True, clear_all=True)
        assert ret["changes"] == {"test": "value", "INITIAL": None}
        if salt.utils.platform.is_windows():
            assert envstate.os.environ == {"TEST": "value"}
        else:
            assert envstate.os.environ == {"test": "value"}


def test_setenv_unset_multi():
    """
    test basically same things that above tests but with multiple values passed
    """
    with patch.dict(os.environ, {"INITIAL": "initial"}, clear=True):
        ret = envstate.setenv("notimportant", {"foo": "bar"})
        assert ret["changes"] == {"foo": "bar"}

        with patch.dict(envstate.__utils__, {"reg.read_value": MagicMock()}):
            ret = envstate.setenv(
                "notimportant", {"test": False, "foo": "baz"}, false_unsets=True
            )
        assert ret["changes"] == {"test": None, "foo": "baz"}
        if salt.utils.platform.is_windows():
            assert envstate.os.environ == {"INITIAL": "initial", "FOO": "baz"}
        else:
            assert envstate.os.environ == {"INITIAL": "initial", "foo": "baz"}

        with patch.dict(envstate.__utils__, {"reg.read_value": MagicMock()}):
            ret = envstate.setenv("notimportant", {"test": False, "foo": "bax"})
        assert ret["changes"] == {"test": "", "foo": "bax"}
        if salt.utils.platform.is_windows():
            assert envstate.os.environ == {
                "INITIAL": "initial",
                "FOO": "bax",
                "TEST": "",
            }
        else:
            assert envstate.os.environ == {
                "INITIAL": "initial",
                "foo": "bax",
                "test": "",
            }


def test_setenv_test_mode():
    """
    test that imitating action returns good values
    """
    with patch.dict(os.environ, {"INITIAL": "initial"}, clear=True):
        with patch.dict(envstate.__opts__, {"test": True}):
            ret = envstate.setenv("test", "value")
            assert ret["changes"] == {"test": "value"}
            ret = envstate.setenv("INITIAL", "initial")
            assert ret["changes"] == {}
