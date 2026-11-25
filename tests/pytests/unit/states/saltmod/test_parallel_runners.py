import pytest

import salt.exceptions
import salt.loader.context
import salt.loader.lazy
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


def test_runners():
    name = "runner-name"
    runner_1 = "runner-1"
    runner_1_ret = {
        "jid": "20170406104341210934",
        "retcode": 0,
        "ret": {
            "test_|-notify_me_|-this is a name 1_|-show_notification": {
                "comment": f"Notify me: {runner_1}",
                "name": "this is a name 1",
                "start_time": "10:43:41.487565",
                "result": True,
                "duration": 0.35,
                "__run_num__": 0,
                "__sls__": "demo",
                "changes": {},
                "__id__": "notify_me",
            }
        },
        "failed": True,
        "out": "highstate",
    }

    expected = {
        "name": name,
        "changes": {
            "ret": {
                runner_1: runner_1_ret,
            }
        },
        "result": True,
        "comment": "All runner functions executed successfully.",
    }
    mock = MagicMock(side_effect=[{"return": runner_1_ret}])
    with patch.dict(saltmod.__salt__, {"saltutil.runner": mock}):
        ret = saltmod.parallel_runners(name, runner_1)
        assert ret == expected

    runner_2 = "runner-2"
    runner_2_ret = {
        "jid": "20170406104341210934",
        "retcode": 0,
        "ret": {
            "test_|-notify_me_|-this is a name 2_|-show_notification": {
                "comment": f"Notify me: {runner_2}",
                "name": "this is a name 2",
                "start_time": "10:43:41.487565",
                "result": True,
                "duration": 0.35,
                "__run_num__": 0,
                "__sls__": "demo",
                "changes": {},
                "__id__": "notify_me",
            }
        },
        "failed": True,
        "out": "highstate",
    }
    expected["changes"]["ret"][runner_2] = runner_2_ret
    mock = MagicMock(side_effect=[{"return": runner_1_ret}, {"return": runner_2_ret}])
    with patch.dict(saltmod.__salt__, {"saltutil.runner": mock}):
        ret = saltmod.parallel_runners(
            name, {runner_1: {"name": name}, runner_2: {"name": name}}
        )
        assert ret == expected

    expected = {
        "name": name,
        "result": False,
        "changes": {},
        "comment": "The runners parameter must be a string or dict.",
    }
    ret = saltmod.parallel_runners(name, [runner_1, runner_2])
    assert ret == expected


def test_exception():
    name = "runner-name"
    runner_1 = "runner-1"
    runner_1_ret = {
        "jid": "20170406104341210934",
        "retcode": 0,
        "ret": {
            "test_|-notify_me_|-this is a name_|-show_notification": {
                "comment": "Notify me",
                "name": "this is a name",
                "start_time": "10:43:41.487565",
                "result": True,
                "duration": 0.35,
                "__run_num__": 0,
                "__sls__": "demo",
                "changes": {},
                "__id__": "notify_me",
            }
        },
        "failed": True,
        "out": "highstate",
    }

    expected = {
        "name": name,
        "result": False,
        "changes": {},
        "comment": "One of the runners raised an exception: An Exception!",
        "success": False,
    }
    runner_2 = "runner-2"
    mock = MagicMock(
        side_effect=[
            {"return": runner_1_ret},
            salt.exceptions.SaltException("An Exception!"),
        ]
    )
    with patch.dict(saltmod.__salt__, {"saltutil.runner": mock}):
        ret = saltmod.parallel_runners(
            name, {runner_1: {"name": name}, runner_2: {"name": name}}
        )
        assert ret == expected


def test_failed():

    name = "runner-name"
    runner_1 = "runner-1"
    runner_1_ret = {
        "jid": "20170406104341210934",
        "retcode": 0,
        "ret": {
            "test_|-notify_me_|-this is a name 1_|-show_notification": {
                "comment": f"Notify me: {runner_1}",
                "name": "this is a name 1",
                "start_time": "10:43:41.487565",
                "result": True,
                "duration": 0.35,
                "__run_num__": 0,
                "__sls__": "demo",
                "changes": {"foo": "bar"},
                "__id__": "notify_me",
            }
        },
        "failed": True,
        "out": "highstate",
        "exit_code": 1,
    }
    runner_2 = "runner-2"
    runner_2_ret = {
        "jid": "20170406104341210934",
        "retcode": 1,
        "ret": {
            "test_|-notify_me_|-this is a name 2_|-show_notification": {
                "comment": f"Notify me: {runner_2}",
                "name": "this is a name 2",
                "start_time": "10:43:41.487565",
                "result": False,
                "duration": 0.35,
                "__run_num__": 0,
                "__sls__": "demo",
                "changes": {},
                "__id__": "notify_me",
            }
        },
        "failed": True,
        "out": "highstate",
        "exit_code": 0,
    }

    expected = {
        "name": name,
        "changes": {
            "ret": {
                runner_1: runner_1_ret,
            }
        },
        "result": False,
        "comment": f"Runner {runner_1} failed.",
    }
    mock = MagicMock(side_effect=[{"return": runner_1_ret}])
    with patch.dict(saltmod.__salt__, {"saltutil.runner": mock}):
        ret = saltmod.parallel_runners(name, runner_1)
        assert ret == expected

    expected["changes"]["ret"][runner_2] = runner_2_ret
    mock = MagicMock(side_effect=[{"return": runner_1_ret}, {"return": runner_2_ret}])
    with patch.dict(saltmod.__salt__, {"saltutil.runner": mock}):
        ret = saltmod.parallel_runners(
            name, {runner_1: {"name": name}, runner_2: {"name": name}}
        )
        assert ret == expected

    runner_3 = "runner-3"
    runner_3_ret = {
        "jid": "20170406104341210934",
        "retcode": 1,
        "ret": {
            "test_|-notify_me_|-this is a name 2_|-show_notification": {
                "comment": f"Notify me: {runner_2}",
                "name": "this is a name 2",
                "start_time": "10:43:41.487565",
                "result": False,
                "duration": 0.35,
                "__run_num__": 0,
                "__sls__": "demo",
                "changes": {},
                "__id__": "notify_me",
            }
        },
        "failed": True,
        "out": "highstate",
        "exit_code": 1,
    }

    expected["changes"]["ret"][runner_3] = runner_3_ret
    expected.pop("comment")
    mock = MagicMock(
        side_effect=[
            {"return": runner_1_ret},
            {"return": runner_2_ret},
            {"return": runner_3_ret},
        ]
    )
    with patch.dict(saltmod.__salt__, {"saltutil.runner": mock}):
        ret = saltmod.parallel_runners(
            name,
            {
                runner_1: {"name": name},
                runner_2: {"name": name},
                runner_3: {"name": name},
            },
        )
        ret_comment = ret.pop("comment")
        assert ret == expected
        assert "Runners " in ret_comment
        assert " failed." in ret_comment
        assert runner_1 in ret_comment
        assert runner_3 in ret_comment
        assert runner_2 not in ret_comment


def _loader_with_salt(salt_pack):
    """Build a loader whose ``__salt__`` pack is visible via loader context."""
    return salt.loader.lazy.LazyLoader(["/foo"], pack={"__salt__": salt_pack})


def test_parallel_map_propagates_loader_context():
    """
    Worker threads must see the loader context that was current in the caller.

    ``_parallel_map`` used to start a bare ``threading.Thread``. Context
    variables are not copied into that thread, so ``NamedLoaderContext``
    resolves to ``None`` and ``__salt__["saltutil.runner"]`` raises
    ``TypeError`` (#66022, #70742).
    """
    marker = object()
    pack = {"saltutil.runner": marker, "token": "from-caller"}
    loader = _loader_with_salt(pack)
    named = salt.loader.context.LoaderContext().named_context("__salt__")
    seen = {}

    def worker(item):
        seen[item] = {
            "loader": salt.loader.context.loader_ctxvar.get(),
            "value": named.value(),
            "runner": named["saltutil.runner"],
            "token": named["token"],
        }
        return item

    with salt.loader.context.loader_context(loader):
        result = saltmod._parallel_map(worker, ["a", "b"])
        assert salt.loader.context.loader_ctxvar.get() is loader

    assert result == ["a", "b"]
    for item in ("a", "b"):
        assert seen[item]["loader"] is loader
        assert seen[item]["value"] is pack
        assert seen[item]["runner"] is marker
        assert seen[item]["token"] == "from-caller"


def test_parallel_runners_reads_saltutil_from_loader_context():
    """
    ``parallel_runners`` must call ``saltutil.runner`` from the worker thread.

    Patching a plain dict over ``__salt__`` hides the bug: a dict is visible
    to every thread. Production ``__salt__`` is a ``NamedLoaderContext`` that
    reads the loader contextvar, which a bare thread does not have.
    """
    name = "parallel-state"
    runner_ret = {"ret": True, "exit_code": 0}
    mock = MagicMock(return_value={"return": runner_ret})
    loader = _loader_with_salt({"saltutil.runner": mock})
    named = salt.loader.context.LoaderContext().named_context("__salt__")
    runners = {
        "my_runner_1": [{"name": "test.sleep"}, {"kwarg": {"s_time": 0.1}}],
        "my_runner_2": [{"name": "test.sleep"}, {"kwarg": {"s_time": 0.1}}],
    }
    expected = {
        "name": name,
        "changes": {
            "ret": {
                "my_runner_1": runner_ret,
                "my_runner_2": runner_ret,
            }
        },
        "result": True,
        "comment": "All runner functions executed successfully.",
    }

    with salt.loader.context.loader_context(loader):
        with patch.object(saltmod, "__salt__", named):
            ret = saltmod.parallel_runners(name, runners)

    assert ret == expected
    assert mock.call_count == 2
    assert [call.args[0] for call in mock.call_args_list] == [
        "test.sleep",
        "test.sleep",
    ]
    for call in mock.call_args_list:
        assert call.kwargs["s_time"] == 0.1
        assert call.kwargs["full_return"] is True


def test_non_dict_runner_returns():
    """
    ``test.sleep`` returns ``True`` and ``test.stdout_print`` returns a string.

    ``parallel_runners`` used to call ``.get`` on that payload and raise
    ``AttributeError`` once the loader-context crash was out of the way
    (#66022).
    """
    name = "parallel-state"
    mock = MagicMock(side_effect=[{"return": True}, {"return": "bar"}])
    runners = {
        "my_runner_1": [{"name": "test.sleep"}, {"kwarg": {"s_time": 0.1}}],
        "my_runner_2": [{"name": "test.stdout_print"}],
    }
    expected = {
        "name": name,
        "result": True,
        "changes": {"ret": {"my_runner_1": True, "my_runner_2": "bar"}},
        "comment": "All runner functions executed successfully.",
    }
    with patch.dict(saltmod.__salt__, {"saltutil.runner": mock}):
        ret = saltmod.parallel_runners(name, runners)
    assert ret == expected


def test_non_dict_return_does_not_mask_failed_runner():
    """A boolean return must not hide a sibling runner that set ``exit_code``."""
    name = "parallel-state"
    failed = {"ret": False, "exit_code": 1}
    mock = MagicMock(side_effect=[{"return": True}, {"return": failed}])
    runners = {
        "my_runner_1": [{"name": "test.sleep"}],
        "my_runner_2": [{"name": "state.orchestrate"}],
    }
    with patch.dict(saltmod.__salt__, {"saltutil.runner": mock}):
        ret = saltmod.parallel_runners(name, runners)

    assert ret["result"] is False
    assert ret["name"] == name
    assert ret["changes"] == {"ret": {"my_runner_1": True, "my_runner_2": failed}}
    assert ret["comment"] == "Runner my_runner_2 failed."
