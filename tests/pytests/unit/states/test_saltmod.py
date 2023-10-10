import copy

import pytest

import salt.modules.saltutil
import salt.states.saltmod as saltmod
import salt.utils.event
import salt.utils.jid
import salt.utils.state
from tests.support.mock import MagicMock, create_autospec, patch


class MockedEvent:
    """
    Mocked event class
    """

    def __init__(self, data):
        self.full = None
        self.flag = None
        self._data = data

    def get_event(self, full):
        """
        Mock get_event method
        """
        self.full = full
        if self.flag:
            return self._data
        return None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@pytest.fixture
def configure_loader_modules():
    return {
        saltmod: {
            "__env__": "base",
            "__opts__": {"__role": "testsuite"},
            "__salt__": {"saltutil.cmd": MagicMock()},
            "__utils__": {"state.check_result": salt.utils.state.check_result},
        },
    }


@pytest.fixture
def fake_cmd():
    _fake_cmd = create_autospec(salt.modules.saltutil.cmd)
    with patch.dict(saltmod.__salt__, {"saltutil.cmd": _fake_cmd}):
        yield _fake_cmd


@pytest.mark.parametrize(
    "exclude",
    [True, False],
)
def test_exclude_parameter_gets_passed(exclude, fake_cmd):
    """
    Smoke test for for salt.states.statemod.state().  Ensures that we
    don't take an exception if optional parameters are not specified in
    __opts__ or __env__.
    """
    args = ("webserver_setup", "webserver2")
    expected_exclude = exclude
    kwargs = {
        "tgt_type": "glob",
        "exclude": expected_exclude,
        "highstate": True,
    }

    saltmod.state(*args, **kwargs)

    call = fake_cmd.call_args[1]
    assert call["kwarg"]["exclude"] == expected_exclude


def test_exclude_parameter_is_not_passed_if_not_provided(fake_cmd):
    # Make sure we don't barf on existing behavior
    args = ("webserver_setup", "webserver2")
    kwargs_without_exclude = {
        "tgt_type": "glob",
        "highstate": True,
    }

    saltmod.state(*args, **kwargs_without_exclude)

    call = fake_cmd.call_args[1]
    assert "exclude" not in call["kwarg"]


def test_state_smoke_test():
    """
    Smoke test for for salt.states.statemod.state().  Ensures that we
    don't take an exception if optional parameters are not specified in
    __opts__ or __env__.
    """
    args = ("webserver_setup", "webserver2")
    kwargs = {
        "tgt_type": "glob",
        "fail_minions": None,
        "pillar": None,
        "top": None,
        "batch": None,
        "orchestration_jid": None,
        "sls": "vroom",
        "queue": False,
        "concurrent": False,
        "highstate": None,
        "expr_form": None,
        "ret": "",
        "ssh": False,
        "timeout": None,
        "test": False,
        "allow_fail": 0,
        "saltenv": None,
        "expect_minions": False,
    }
    with patch.dict(saltmod.__opts__, {"id": "webserver2"}):
        ret = saltmod.state(*args, **kwargs)
    expected = {
        "comment": "States ran successfully.",
        "changes": {},
        "name": "webserver_setup",
        "result": True,
    }
    assert ret == expected


def test_state():
    """
    Test to invoke a state run on a given target
    """
    name = "state"
    tgt = "minion1"

    expected = {
        "name": name,
        "changes": {},
        "result": False,
        "comment": "Passed invalid value for 'allow_fail', must be an int",
    }

    ret = saltmod.state(name, tgt, allow_fail="a")
    assert ret == expected

    expected.update({"comment": "No highstate or sls specified, no execution made"})
    ret = saltmod.state(name, tgt)
    assert ret == expected

    expected.update({"comment": "Must pass in boolean for value of 'concurrent'"})
    ret = saltmod.state(name, tgt, highstate=True, concurrent="a")
    assert ret == expected

    expected.update(
        {
            "result": True,
            "comment": "States ran successfully.",
        }
    )
    with patch.dict(saltmod.__opts__, {"test": True}):
        ret = saltmod.state(name, tgt, highstate=True)
    assert ret == expected

    expected.update(
        {
            "comment": "States ran successfully. No changes made to silver.",
            "result": True,
            "__jid__": "20170406104341210934",
        }
    )
    with patch.dict(saltmod.__opts__, {"test": False}):
        mock = MagicMock(
            return_value={
                "silver": {
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
                    "out": "highstate",
                }
            }
        )
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.state(name, tgt, highstate=True)
        assert ret == expected

    test_batch_return = {
        "minion1": {
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
                },
                "retcode": 0,
            },
            "out": "highstate",
        },
        "minion2": {
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
                },
                "retcode": 0,
            },
            "out": "highstate",
        },
        "minion3": {
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
                },
                "retcode": 0,
            },
            "out": "highstate",
        },
    }
    expected.update(
        {
            "comment": (
                "States ran successfully. No changes made to minion1, minion3,"
                " minion2."
            )
        }
    )
    del expected["__jid__"]
    with patch.dict(saltmod.__opts__, {"test": False}):
        with patch.dict(
            saltmod.__salt__,
            {"saltutil.cmd": MagicMock(return_value=test_batch_return)},
        ):
            state_run = saltmod.state(name, tgt, highstate=True)

            # Test return without checking the comment contents. Comments are tested later.
            comment = state_run.pop("comment")
            expected.pop("comment")
            assert state_run == expected

            # Check the comment contents in a non-order specific way (ordering fails sometimes on PY3)
            assert "States ran successfully. No changes made to" in comment
            for minion in ["minion1", "minion2", "minion3"]:
                assert minion in comment


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


def test_wait_for_event():
    """
    Test to watch Salt's event bus and block until a condition is met
    """
    name = "state"
    tgt = "minion1"

    ret = {
        "name": name,
        "changes": {},
        "result": False,
        "comment": "Timeout value reached.",
    }

    mocked_event = MockedEvent({"tag": name, "data": {}})
    with patch.object(
        salt.utils.event, "get_event", MagicMock(return_value=mocked_event)
    ):
        with patch.dict(saltmod.__opts__, {"sock_dir": True, "transport": True}):
            with patch("salt.states.saltmod.time.time", MagicMock(return_value=1.0)):
                assert saltmod.wait_for_event(name, "salt", timeout=-1.0) == ret

                mocked_event.flag = True
                ret.update(
                    {"comment": "All events seen in 0.0 seconds.", "result": True}
                )
                assert saltmod.wait_for_event(name, "") == ret

                ret.update({"comment": "Timeout value reached.", "result": False})
                assert saltmod.wait_for_event(name, tgt, timeout=-1.0) == ret


def test_wait_for_event_list_single_event():
    """
    Test to watch Salt's event bus and block until a condition is met
    """
    name = "presence"
    event_id = "lost"
    tgt = ["minion_1", "minion_2", "minion_3"]

    expected = {
        "name": name,
        "changes": {},
        "result": False,
        "comment": "Timeout value reached.",
    }

    mocked_event = MockedEvent({"tag": name, "data": {"lost": tgt}})
    with patch.object(
        salt.utils.event, "get_event", MagicMock(return_value=mocked_event)
    ):
        with patch.dict(saltmod.__opts__, {"sock_dir": True, "transport": True}):
            with patch("salt.states.saltmod.time.time", MagicMock(return_value=1.0)):
                expected.update({"comment": "Timeout value reached.", "result": False})
                ret = saltmod.wait_for_event(name, tgt, event_id=event_id, timeout=-1.0)
                assert ret == expected

                mocked_event.flag = True
                expected.update(
                    {
                        "name": name,
                        "changes": {"minions_seen": tgt},
                        "result": True,
                        "comment": "All events seen in 0.0 seconds.",
                    }
                )
                ret = saltmod.wait_for_event(
                    name, copy.deepcopy(tgt), event_id="lost", timeout=1.0
                )
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


def test_state_ssh():
    """
    Test saltmod state passes roster to saltutil.cmd
    """
    cmd_mock = MagicMock()
    with patch.dict(saltmod.__salt__, {"saltutil.cmd": cmd_mock}):
        ret = saltmod.state(
            "state.sls", tgt="*", ssh=True, highstate=True, roster="my_roster"
        )
    assert "roster" in cmd_mock.call_args.kwargs
    assert cmd_mock.call_args.kwargs["roster"] == "my_roster"


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
