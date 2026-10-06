"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.modules.data as data
from tests.support.mock import MagicMock, mock_open, patch


@pytest.fixture
def configure_loader_modules():
    return {data: {}}


# 'clear' function tests: 1


def test_clear():
    """
    Test if it clear out all of the data in the minion datastore
    """
    with patch("os.remove", MagicMock(return_value="")):
        with patch.dict(data.__opts__, {"cachedir": ""}):
            assert data.clear()


# 'load' function tests: 1


def test_load():
    """
    Test if it return all of the data in the minion datastore
    """
    mocked_fopen = MagicMock(return_value=True)
    mocked_fopen.__enter__ = MagicMock(return_value=mocked_fopen)
    mocked_fopen.__exit__ = MagicMock()
    with patch("salt.utils.files.fopen", MagicMock(return_value=mocked_fopen)):
        with patch("salt.payload.loads", MagicMock(return_value=True)):
            with patch.dict(data.__opts__, {"cachedir": "/"}):
                assert data.load()


# 'dump' function tests: 3


def test_dump():
    """
    Test if it replace the entire datastore with a passed data structure
    """
    with patch.dict(data.__opts__, {"cachedir": "/"}):
        with patch("salt.utils.files.fopen", mock_open()):
            assert data.dump('{"eggs": "spam"}')


def test_dump_isinstance():
    """
    Test if it replace the entire datastore with a passed data structure
    """
    with patch("ast.literal_eval", MagicMock(return_value="")):
        assert not data.dump("salt")


def test_dump_ioerror():
    """
    Test if it replace the entire datastore with a passed data structure
    """
    with patch.dict(data.__opts__, {"cachedir": "/"}):
        mock = MagicMock(side_effect=IOError(""))
        with patch("salt.utils.files.fopen", mock):
            assert not data.dump('{"eggs": "spam"}')


# 'update' function tests: 1


def test_update():
    """
    Test if it update a key with a value in the minion datastore
    """
    with patch("salt.modules.data.load", MagicMock(return_value={})), patch(
        "salt.modules.data.dump", MagicMock(return_value=True)
    ):
        assert data.update("foo", "salt")


# 'get' function tests: 2


def test_get():
    """
    Test if it gets a value from the minion datastore
    """
    with patch("salt.modules.data.load", MagicMock(return_value={"salt": "SALT"})):
        assert data.get("salt") == "SALT"


def test_get_vals():
    """
    Test if it gets values from the minion datastore
    """
    with patch(
        "salt.modules.data.load",
        MagicMock(return_value={"salt": "SALT", "salt1": "SALT1"}),
    ):
        assert data.get(["salt", "salt1"]) == ["SALT", "SALT1"]


# 'cas' function tests: 1


def test_cas_not_load():
    """
    Test if it check and set a value in the minion datastore
    """
    with patch(
        "salt.modules.data.load",
        MagicMock(return_value={"salt": "SALT", "salt1": "SALT1"}),
    ):
        assert not data.cas("salt3", "SALT", "SALTSTACK")


def test_cas_not_equal():
    """
    Test if it check and set a value in the minion datastore
    """
    with patch(
        "salt.modules.data.load",
        MagicMock(return_value={"salt": "SALT", "salt1": "SALT1"}),
    ):
        assert not data.cas("salt", "SALT", "SALTSTACK")


def test_cas():
    """
    Test if it check and set a value in the minion datastore
    """
    with patch(
        "salt.modules.data.load",
        MagicMock(return_value={"salt": "SALT", "salt1": "SALT1"}),
    ), patch("salt.modules.data.dump", MagicMock(return_value=True)):
        assert data.cas("salt", "SALTSTACK", "SALT")
