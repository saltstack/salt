"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

import os

import pytest

import salt.modules.environ as environ
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {environ: {}}


def test_setval():
    """
    Test for set a single salt process environment variable. Returns True
    on success.
    """
    mock = MagicMock(return_value=None)
    with patch.dict(os.environ, {}):
        assert environ.setval("key", False, True) is None

    mock = MagicMock(side_effect=Exception())
    with patch.dict(os.environ, {}):
        assert not environ.setval("key", False, True)

    mock_environ = {}
    with patch.dict(os.environ, mock_environ):
        assert environ.setval("key", False) == ""

    with patch.dict(os.environ, mock_environ):
        assert not environ.setval("key", True)


def test_set_val_permanent():
    with patch.dict(os.environ, {}), patch.dict(
        environ.__utils__,
        {"reg.set_value": MagicMock(), "reg.delete_value": MagicMock()},
    ), patch("salt.utils.platform.is_windows", return_value=True):

        environ.setval("key", "Test", permanent=True)
        environ.__utils__["reg.set_value"].assert_called_with(
            "HKCU", "Environment", "key", "Test"
        )


def test_set_val_permanent_false_unsets():
    with patch.dict(os.environ, {}), patch.dict(
        environ.__utils__,
        {"reg.set_value": MagicMock(), "reg.delete_value": MagicMock()},
    ), patch("salt.utils.platform.is_windows", return_value=True):

        environ.setval("key", False, false_unsets=True, permanent=True)
        environ.__utils__["reg.set_value"].assert_not_called()
        environ.__utils__["reg.delete_value"].assert_called_with(
            "HKCU", "Environment", "key"
        )


def test_set_val_permanent_hklm():
    with patch.dict(os.environ, {}), patch.dict(
        environ.__utils__,
        {"reg.set_value": MagicMock(), "reg.delete_value": MagicMock()},
    ), patch("salt.utils.platform.is_windows", return_value=True):

        key = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
        environ.setval("key", "Test", permanent="HKLM")
        environ.__utils__["reg.set_value"].assert_called_with(
            "HKLM", key, "key", "Test"
        )


def test_setenv():
    """
    Set multiple salt process environment variables from a dict.
    Returns a dict.
    """
    mock_environ = {"KEY": "value"}
    with patch.dict(os.environ, mock_environ):
        assert not environ.setenv("environ")

    with patch.dict(os.environ, mock_environ):
        assert not environ.setenv({"A": True}, False, True, False)

    with patch.dict(os.environ, mock_environ):
        mock_setval = MagicMock(return_value=None)
        with patch.object(environ, "setval", mock_setval):
            assert environ.setenv({}, False, True, False)["KEY"] is None


def test_get():
    """
    Get a single salt process environment variable.
    """
    assert not environ.get(True)

    assert environ.get("key") == ""


def test_has_value():
    """
    Determine whether the key exists in the current salt process
    environment dictionary. Optionally compare the current value
    of the environment against the supplied value string.
    """
    mock_environ = {}
    with patch.dict(os.environ, mock_environ):
        assert not environ.has_value(True)

        os.environ["salty"] = "yes"
        assert environ.has_value("salty", "yes")

        os.environ["too_salty"] = "no"
        assert not environ.has_value("too_salty", "yes")

        assert not environ.has_value("key", "value")

        os.environ["key"] = "value"
        assert environ.has_value("key")


def test_item():
    """
    Get one or more salt process environment variables.
    Returns a dict.
    """
    assert environ.item(None) == {}


def test_items():
    """
    Return a dict of the entire environment set for the salt process
    """
    assert list(environ.items()) != []
