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
        "comment": f"Runner function '{name}' would be executed.",
    }

    with patch.dict(saltmod.__opts__, {"test": True}):
        ret = saltmod.runner(name)
        assert ret == expected


def test_runner():
    """
    Test to execute a runner module on the master
    """
    name = "state"

    expected = {
        "changes": {"return": True},
        "name": "state",
        "result": True,
        "comment": "Runner function 'state' executed.",
    }
    with patch.dict(
        saltmod.__salt__, {"saltutil.runner": MagicMock(return_value={"return": True})}
    ):
        ret = saltmod.runner(name)
        assert ret == expected
