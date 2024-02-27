import pytest

import salt.states.saltmod as saltmod
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {
        saltmod: {
            "__opts__": minion_opts,
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
        "comment": f"Function state would be executed on target {tgt}",
    }

    with patch.dict(saltmod.__opts__, {"test": True}):
        ret = saltmod.function(name, tgt)
    assert ret == expected

    expected.update(
        {
            "result": True,
            "changes": {"ret": {tgt: ""}},
            "comment": (f"Function ran successfully. Function state ran on {tgt}."),
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


def test_arg():
    name = "state"
    tgt = "larry"

    expected = {
        "name": name,
        "changes": {"ret": {tgt: ""}},
        "result": True,
        "comment": f"Function ran successfully. Function state ran on {tgt}.",
        "warnings": ["Please specify 'arg' as a list of arguments."],
    }

    with patch.dict(saltmod.__opts__, {"test": False}):
        mock = MagicMock(
            return_value={
                tgt: {
                    "ret": "",
                    "retcode": 0,
                    "failed": False,
                },
            },
        )
        args = ["foo", "bar"]
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.function(name, tgt, arg=" ".join(args))
            assert ret == expected
        mock.assert_called_once()
        assert "arg" in mock.call_args.kwargs
        assert mock.call_args.kwargs["arg"] == args

    expected.pop("warnings")
    with patch.dict(saltmod.__opts__, {"test": False}):
        mock = MagicMock(
            return_value={
                tgt: {
                    "ret": "",
                    "retcode": 0,
                    "failed": False,
                },
            },
        )
        args = ["foo", "bar"]
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.function(name, tgt, arg=args)
            assert ret == expected
        mock.assert_called_once()
        assert "arg" in mock.call_args.kwargs
        assert mock.call_args.kwargs["arg"] == args


def test_batch():
    name = "state"
    tgt = "larry"

    expected = {
        "name": name,
        "changes": {"ret": {tgt: ""}},
        "result": True,
        "comment": f"Function ran successfully. Function state ran on {tgt}.",
    }

    with patch.dict(saltmod.__opts__, {"test": False}):
        mock = MagicMock(
            return_value={
                tgt: {
                    "ret": "",
                    "retcode": 0,
                    "failed": False,
                },
            },
        )
        batch = "yes"
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.function(name, tgt, batch=batch)
            assert ret == expected
        mock.assert_called_once()
        assert "batch" in mock.call_args.kwargs
        assert mock.call_args.kwargs["batch"] == batch

        batch = ["yes", "no"]
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.function(name, tgt, batch=batch)
            assert ret == expected
        assert "batch" in mock.call_args.kwargs
        assert mock.call_args.kwargs["batch"] == str(batch)


def test_subset():
    name = "state"
    tgt = "larry"

    expected = {
        "name": name,
        "changes": {"ret": {tgt: ""}},
        "result": True,
        "comment": f"Function ran successfully. Function state ran on {tgt}.",
    }

    with patch.dict(saltmod.__opts__, {"test": False}):
        mock = MagicMock(
            return_value={
                tgt: {
                    "ret": "",
                    "retcode": 0,
                    "failed": False,
                },
            },
        )
        subset = "yes"
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.function(name, tgt, subset=subset)
            assert ret == expected
        mock.assert_called_once()
        assert "subset" in mock.call_args.kwargs
        assert mock.call_args.kwargs["subset"] == subset


def test_ret_config():
    name = "state"
    tgt = "larry"

    expected = {
        "name": name,
        "changes": {"ret": {tgt: ""}},
        "result": True,
        "comment": f"Function ran successfully. Function state ran on {tgt}.",
    }

    with patch.dict(saltmod.__opts__, {"test": False}):
        mock = MagicMock(
            return_value={
                tgt: {
                    "ret": "",
                    "retcode": 0,
                    "failed": False,
                },
            },
        )
        ret_config = {"yes": "no"}
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.function(name, tgt, ret_config=ret_config)
            assert ret == expected
        mock.assert_called_once()
        assert "ret_config" in mock.call_args.kwargs
        assert mock.call_args.kwargs["ret_config"] == ret_config


def test_ret_kwargs():
    name = "state"
    tgt = "larry"

    expected = {
        "name": name,
        "changes": {"ret": {tgt: ""}},
        "result": True,
        "comment": f"Function ran successfully. Function state ran on {tgt}.",
    }

    with patch.dict(saltmod.__opts__, {"test": False}):
        mock = MagicMock(
            return_value={
                tgt: {
                    "ret": "",
                    "retcode": 0,
                    "failed": False,
                },
            },
        )
        ret_kwargs = {"yes": "no"}
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.function(name, tgt, ret_kwargs=ret_kwargs)
            assert ret == expected
        mock.assert_called_once()
        assert "ret_kwargs" in mock.call_args.kwargs
        assert mock.call_args.kwargs["ret_kwargs"] == ret_kwargs


def test_failhard():
    name = "state"
    tgt = "larry"

    expected = {
        "name": name,
        "changes": {"ret": {tgt: ""}},
        "result": True,
        "comment": f"Function ran successfully. Function state ran on {tgt}.",
    }

    with patch.dict(saltmod.__opts__, {"test": False}):
        mock = MagicMock(
            return_value={
                tgt: {
                    "ret": "",
                    "retcode": 0,
                    "failed": False,
                },
            },
        )
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.function(name, tgt, failhard=True)
            assert ret == expected
        mock.assert_called_once()
        assert "failhard" in mock.call_args.kwargs
        assert mock.call_args.kwargs["failhard"] is True

    with patch.dict(saltmod.__opts__, {"test": False, "failhard": True}):
        mock = MagicMock(
            return_value={
                tgt: {
                    "ret": "",
                    "retcode": 0,
                    "failed": False,
                },
            },
        )
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.function(name, tgt)
            assert ret == expected
        mock.assert_called_once()
        assert "failhard" in mock.call_args.kwargs
        assert mock.call_args.kwargs["failhard"] is True


def test_fail_minions():
    name = "state"
    tgt = "larry"

    expected = {
        "name": name,
        "changes": {
            "ret": {
                tgt: "",
                "red": "red",
                "green": "green",
                "blue": "blue",
            },
        },
        "result": True,
    }

    with patch.dict(saltmod.__opts__, {"test": False}):
        mock = MagicMock(
            return_value={
                tgt: {
                    "ret": "",
                    "retcode": 0,
                    "failed": False,
                },
                "red": {
                    "ret": "red",
                    "retcode": 0,
                    "failed": False,
                },
                "green": {
                    "ret": "green",
                    "retcode": 0,
                    "failed": False,
                },
                "blue": {
                    "ret": "blue",
                    "retcode": 0,
                    "failed": False,
                },
            },
        )
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.function(name, tgt, fail_minions="red")
            ret_comment = ret.pop("comment")
            assert ret == expected
            assert "Function ran successfully. Function state ran on " in ret_comment
            for part in (tgt, "red", "green", "blue"):
                assert part in ret_comment

        mock.assert_called_once()

        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.function(name, tgt, fail_minions="red,green")
            ret_comment = ret.pop("comment")
            assert ret == expected
            assert "Function ran successfully. Function state ran on " in ret_comment
            for part in (tgt, "red", "green", "blue"):
                assert part in ret_comment

        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.function(name, tgt, fail_minions=["red", "green"])
            ret_comment = ret.pop("comment")
            assert ret == expected
            assert "Function ran successfully. Function state ran on " in ret_comment
            for part in (tgt, "red", "green", "blue"):
                assert part in ret_comment

        expected["warnings"] = [
            "'fail_minions' needs to be a list or a comma separated string. Ignored."
        ]
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.function(name, tgt, fail_minions=())
            ret_comment = ret.pop("comment")
            assert ret == expected
            assert "Function ran successfully. Function state ran on " in ret_comment
            for part in (tgt, "red", "green", "blue"):
                assert part in ret_comment

    expected.pop("warnings")
    expected["changes"]["ret"]["red"] = False
    with patch.dict(saltmod.__opts__, {"test": False}):
        mock = MagicMock(
            return_value={
                tgt: {
                    "ret": "",
                    "retcode": 0,
                    "failed": False,
                },
                "red": {
                    "ret": "red",
                    "retcode": 0,
                    "failed": True,
                },
                "green": {
                    "ret": "green",
                    "retcode": 0,
                    "failed": False,
                },
                "blue": {
                    "ret": "blue",
                    "retcode": 0,
                    "failed": False,
                },
            },
        )
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.function(name, tgt, fail_minions="red")
            ret_comment = ret.pop("comment")
            assert ret == expected
            assert "Function ran successfully. Function state ran on " in ret_comment
            for part in (tgt, "red", "green", "blue"):
                assert part in ret_comment

        mock.assert_called_once()

    expected["result"] = False
    expected["changes"]["ret"]["green"] = False
    with patch.dict(saltmod.__opts__, {"test": False}):
        mock = MagicMock(
            return_value={
                tgt: {
                    "ret": "",
                    "retcode": 0,
                    "failed": False,
                },
                "red": {
                    "ret": "red",
                    "retcode": 0,
                    "failed": True,
                },
                "green": {
                    "ret": "green",
                    "retcode": 0,
                    "failed": True,
                },
                "blue": {
                    "ret": "blue",
                    "retcode": 0,
                    "failed": False,
                },
            },
        )
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.function(name, tgt, fail_minions="red")
            ret_comment = ret.pop("comment")
            assert ret == expected
            assert "Running function state failed on minions: green " in ret_comment
            assert "Function state ran on " in ret_comment
            for part in (tgt, "red", "green", "blue"):
                assert part in ret_comment

        mock.assert_called_once()

    with patch.dict(saltmod.__opts__, {"test": False}):
        mock = MagicMock(
            return_value={
                tgt: {
                    "ret": "",
                    "retcode": 0,
                    "failed": False,
                },
                "red": {
                    "ret": "red",
                    "retcode": 1,
                    "failed": True,
                },
                "green": {
                    "ret": "green",
                    "retcode": 1,
                    "failed": True,
                },
                "blue": {
                    "ret": "blue",
                    "retcode": 0,
                    "failed": False,
                },
            },
        )
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.function(name, tgt, fail_minions="red")
            ret_comment = ret.pop("comment")
            assert ret == expected
            try:
                assert (
                    "Running function state failed on minions: green, red"
                    in ret_comment
                )
            except AssertionError:
                assert (
                    "Running function state failed on minions: red, green"
                    in ret_comment
                )
            assert "Function state ran on " in ret_comment
            for part in (tgt, "red", "green", "blue"):
                assert part in ret_comment

        mock.assert_called_once()


def test_exception_raised():
    name = "state"
    tgt = "larry"

    expected = {
        "name": name,
        "changes": {},
        "result": False,
        "comment": "I'm an exception!",
    }

    with patch.dict(saltmod.__opts__, {"test": False}):
        mock = MagicMock(side_effect=Exception("I'm an exception!"))
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.function(name, tgt, failhard=True)
            assert ret == expected
        mock.assert_called_once()
        assert "failhard" in mock.call_args.kwargs
        assert mock.call_args.kwargs["failhard"] is True
