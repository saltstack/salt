import pytest

import salt.states.saltmod as saltmod
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {
        saltmod: {
            "__env__": "base",
            "__opts__": minion_opts,
        },
    }


def test_test_mode():
    name = "bah"

    expected = {
        "name": name,
        "changes": {},
        "result": None,
        "comment": f"Wheel function '{name}' would be executed.",
    }

    with patch.dict(saltmod.__opts__, {"test": True}):
        ret = saltmod.wheel(name)
        assert ret == expected


def test_wheel():
    """
    Test to execute a wheel module on the master
    """
    name = "state"

    expected = {
        "changes": {"return": True},
        "name": "state",
        "result": True,
        "comment": "Wheel function 'state' executed.",
    }
    with patch.dict(
        saltmod.__salt__, {"saltutil.wheel": MagicMock(return_value={"return": True})}
    ):
        ret = saltmod.wheel(name)
        assert ret == expected


def test_test_error_in_return():
    name = "bah"

    jid = "20170406104341210934"
    func_ret = {"Error": "This is an Error!"}
    expected = {
        "name": name,
        "changes": {"return": func_ret},
        "result": False,
        "comment": f"Wheel function '{name}' failed.",
        "__jid__": jid,
    }

    mock = MagicMock(return_value={"return": func_ret, "jid": jid})
    with patch.dict(saltmod.__salt__, {"saltutil.wheel": mock}):
        ret = saltmod.wheel(name)
        assert ret == expected
        mock.assert_called_once()
