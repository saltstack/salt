import pytest

import salt.states.saltmod as saltmod
import salt.utils.state
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {
        saltmod: {
            "__env__": "base",
            "__opts__": minion_opts,
            "__utils__": {"state.check_result": salt.utils.state.check_result},
        },
    }


def test_function():
    """
    Test to execute a single module function on a remote
    minion via salt or salt-ssh
    """
    name = "state"
    tgt = "larry"

    expected = {
        "name": name,
        "changes": {},
        "result": None,
        "comment": "Function state would be executed on target {}".format(tgt),
    }

    with patch.dict(saltmod.__opts__, {"test": True}):
        ret = saltmod.function(name, tgt)
    assert ret == expected

    expected.update(
        {
            "result": True,
            "changes": {"ret": {tgt: ""}},
            "comment": (
                "Function ran successfully. Function state ran on {}.".format(tgt)
            ),
        }
    )
    with patch.dict(saltmod.__opts__, {"test": False}):
        mock_ret = {"larry": {"ret": "", "retcode": 0, "failed": False}}
        mock_cmd = MagicMock(return_value=mock_ret)
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock_cmd}):
            ret = saltmod.function(name, tgt)
        assert ret == expected


def test_function_when_no_minions_match():
    """
    Test to execute a single module function on a remote
    minion via salt or salt-ssh
    """
    name = "state"
    tgt = "larry"

    expected = {
        "name": name,
        "changes": {},
        "result": False,
        "comment": "No minions responded",
    }

    with patch.dict(saltmod.__opts__, {"test": False}):
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": MagicMock(return_value={})}):
            ret = saltmod.function(name, tgt)
            assert ret == expected


def test_function_ssh():
    """
    Test saltmod function passes roster to saltutil.cmd
    """
    cmd_mock = MagicMock()
    with patch.dict(saltmod.__opts__, {"test": False}), patch.dict(
        saltmod.__salt__, {"saltutil.cmd": cmd_mock}
    ):
        saltmod.function("state", tgt="*", ssh=True, roster="my_roster")
    assert "roster" in cmd_mock.call_args.kwargs
    assert cmd_mock.call_args.kwargs["roster"] == "my_roster"
