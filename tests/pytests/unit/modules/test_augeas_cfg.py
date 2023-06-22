"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.augeas_cfg
"""
import pytest

import salt.modules.augeas_cfg as augeas_cfg
from salt.exceptions import SaltInvocationError
from tests.support.mock import MagicMock, patch

# Make sure augeas python interface is installed
if augeas_cfg.HAS_AUGEAS:
    from augeas import Augeas as _Augeas


pytestmark = [
    pytest.mark.skipif(
        augeas_cfg.HAS_AUGEAS is False,
        reason="python-augeas is required for this test case",
    )
]


@pytest.fixture
def configure_loader_modules():
    return {augeas_cfg: {}}


def test_execute():
    """
    Test if it execute Augeas commands
    """
    assert augeas_cfg.execute() == {"retval": True}


def test_execute_io_error():
    """
    Test if it execute Augeas commands
    """
    ret = {"error": "Command  is not supported (yet)", "retval": False}
    assert augeas_cfg.execute(None, None, [" "]) == ret


def test_execute_value_error():
    """
    Test if it execute Augeas commands
    """
    ret = {
        "retval": False,
        "error": "Invalid formatted command, see debug log for details: ",
    }
    assert augeas_cfg.execute(None, None, ["set "]) == ret


# 'get' function tests: 1


def test_get():
    """
    Test if it get a value for a specific augeas path
    """
    mock = MagicMock(side_effect=RuntimeError("error"))
    with patch.object(_Augeas, "match", mock):
        assert augeas_cfg.get("/etc/hosts") == {"error": "error"}

    mock = MagicMock(return_value=True)
    with patch.object(_Augeas, "match", mock):
        assert augeas_cfg.get("/etc/hosts") == {"/etc/hosts": None}


# 'setvalue' function tests: 4


def test_setvalue():
    """
    Test if it set a value for a specific augeas path
    """
    assert augeas_cfg.setvalue("prefix=/etc/hosts") == {"retval": True}


def test_setvalue_io_error():
    """
    Test if it set a value for a specific augeas path
    """
    mock = MagicMock(side_effect=IOError(""))
    with patch.object(_Augeas, "save", mock):
        assert augeas_cfg.setvalue("prefix=/files/etc/") == {
            "retval": False,
            "error": "",
        }


def test_setvalue_uneven_path():
    """
    Test if it set a value for a specific augeas path
    """
    mock = MagicMock(side_effect=RuntimeError("error"))
    with patch.object(_Augeas, "match", mock):
        pytest.raises(
            SaltInvocationError,
            augeas_cfg.setvalue,
            ["/files/etc/hosts/1/canonical", "localhost"],
        )


def test_setvalue_one_prefix():
    """
    Test if it set a value for a specific augeas path
    """
    pytest.raises(
        SaltInvocationError,
        augeas_cfg.setvalue,
        "prefix=/files",
        "10.18.1.1",
        "prefix=/etc",
        "test",
    )


# 'match' function tests: 2


def test_match():
    """
    Test if it matches for path expression
    """
    assert augeas_cfg.match("/etc/service", "ssh") == {}


def test_match_runtime_error():
    """
    Test if it matches for path expression
    """
    mock = MagicMock(side_effect=RuntimeError("error"))
    with patch.object(_Augeas, "match", mock):
        assert augeas_cfg.match("/etc/service-name", "ssh") == {}


# 'remove' function tests: 2


def test_remove():
    """
    Test if it removes for path expression
    """
    assert augeas_cfg.remove("/etc/service") == {"count": 0, "retval": True}


def test_remove_io_runtime_error():
    """
    Test if it removes for path expression
    """
    mock = MagicMock(side_effect=RuntimeError("error"))
    with patch.object(_Augeas, "save", mock):
        assert augeas_cfg.remove("/etc/service-name") == {
            "count": 0,
            "error": "error",
            "retval": False,
        }


# 'ls' function tests: 1


def test_ls():
    """
    Test if it list the direct children of a node
    """
    assert augeas_cfg.ls("/etc/passwd") == {}


# 'tree' function tests: 1


def test_tree():
    """
    Test if it returns recursively the complete tree of a node
    """
    assert augeas_cfg.tree("/etc/") == {"/etc": None}
