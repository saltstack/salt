import pytest

import salt.exceptions
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
