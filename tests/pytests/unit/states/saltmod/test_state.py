import pytest

import salt.modules.saltutil
import salt.states.saltmod as saltmod
import salt.utils.event
import salt.utils.jid
import salt.utils.state
from tests.support.mock import MagicMock, create_autospec, patch


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {
        saltmod: {
            "__opts__": minion_opts,
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
        "comment": "No highstate or sls specified, no execution made",
    }
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

    silver_ret = {
        "test_|-notify_me_|-this is a name_|-show_notification": {
            "comment": "Notify me",
            "name": "this is a name",
            "start_time": "10:43:41.487565",
            "result": True,
            "duration": 0.35,
            "__run_num__": 0,
            "__sls__": "demo",
            "changes": {"foo": "bar"},
            "__id__": "notify_me",
        }
    }
    expected.update(
        {
            "comment": "States ran successfully. Updating silver.",
            "result": None,
            "__jid__": "20170406104341210934",
            "changes": {
                "out": "highstate",
                "ret": {"silver": silver_ret},
            },
        }
    )
    with patch.dict(saltmod.__opts__, {"test": True}):
        mock = MagicMock(
            return_value={
                "silver": {
                    "jid": "20170406104341210934",
                    "retcode": 0,
                    "ret": silver_ret,
                    "out": "highstate",
                }
            }
        )
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.state(name, tgt, highstate=True)
            assert ret == expected
        mock.assert_called_once()

    expected.update(
        {
            "comment": "States ran successfully. No changes made to silver.",
            "result": True,
            "__jid__": "20170406104341210934",
            "changes": {},
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
        mock.assert_called_once()

        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.state(name, tgt, top="the-top")
            assert "arg" in mock.call_args.kwargs
            assert "the-top" in mock.call_args.kwargs["arg"]

        for pass_kw in ("ret_config", "ret_kwargs", "batch", "subset"):
            with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
                kwargs = {pass_kw: f"{pass_kw}_value"}
                ret = saltmod.state(name, tgt, highstate=True, **{pass_kw: kwargs})
            assert pass_kw in mock.call_args.kwargs
            if pass_kw == "batch":
                assert mock.call_args.kwargs[pass_kw] == str(kwargs)
            else:
                assert mock.call_args.kwargs[pass_kw] == kwargs
            assert ret == expected

        for pass_kw in ("pillar", "pillarenv", "saltenv"):
            with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
                kwargs = {pass_kw: f"{pass_kw}_value"}
                ret = saltmod.state(name, tgt, highstate=True, **{pass_kw: kwargs})
            assert "kwarg" in mock.call_args.kwargs
            assert pass_kw in mock.call_args.kwargs["kwarg"]
            assert mock.call_args.kwargs["kwarg"][pass_kw] == kwargs
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


def test_state_masterless():
    """
    Test to invoke a state run masterless
    """
    name = "state"
    minion_id = "masterless-minion"

    expected = {
        "name": name,
        "changes": {},
        "comment": f"States ran successfully. No changes made to {minion_id}.",
        "result": True,
    }
    with patch.dict(
        saltmod.__opts__,
        {"test": False, "__role": "minion", "file_client": "local", "id": minion_id},
    ):
        mock = MagicMock(
            return_value={
                minion_id: {
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
        with patch.dict(saltmod.__salt__, {"state.highstate": mock}):
            ret = saltmod.state(name, minion_id, highstate=True)
            assert ret == expected
            mock.assert_called_once()
        with patch.dict(saltmod.__salt__, {"state.top": mock}):
            ret = saltmod.state(name, minion_id, top="the-top")
            assert ret == expected
            assert "topfn" in mock.call_args.kwargs
            assert mock.call_args.kwargs["topfn"] == "the-top"
        with patch.dict(saltmod.__salt__, {"state.sls": mock}):
            ret = saltmod.state(name, minion_id, sls="the-sls")
            assert ret == expected
            assert "mods" in mock.call_args.kwargs
            assert mock.call_args.kwargs["mods"] == "the-sls"
        with patch.dict(saltmod.__salt__, {"state.sls": mock}):
            ret = saltmod.state(name, minion_id, sls=["the-sls-1", "the-sls-2"])
            assert ret == expected
            assert "mods" in mock.call_args.kwargs
            assert mock.call_args.kwargs["mods"] == "the-sls-1,the-sls-2"


def test_state_failhard():

    name = "state"
    tgt = "minion1"

    expected = {
        "name": name,
        "changes": {},
        "comment": "States ran successfully. No changes made to silver.",
        "result": True,
        "__jid__": "20170406104341210934",
    }
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
            ret = saltmod.state(name, tgt, highstate=True, failhard=True)
            assert ret == expected
        mock.assert_called_once()
        assert "failhard" in mock.call_args.kwargs
        assert mock.call_args.kwargs["failhard"] is True

    with patch.dict(saltmod.__opts__, {"test": False, "failhard": True}):
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
        mock.assert_called_once()
        assert "failhard" in mock.call_args.kwargs
        assert mock.call_args.kwargs["failhard"] is True


def test_state_no_returns():

    name = "state"
    tgt = "minion1"

    expected = {
        "name": name,
        "changes": {},
        "result": False,
        "comment": "No minions returned",
    }
    with patch.dict(saltmod.__opts__, {"test": False}):
        mock = MagicMock(return_value={})
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.state(name, tgt, highstate=True)
            assert ret == expected
        mock.assert_called_once()


def test_state_failed_and_expected_minions():

    name = "state"
    tgt = "minion1"

    expected = {
        "name": name,
        "changes": {"out": "highstate", "ret": {"silver": False}},
        "comment": "Run failed on minions: silver",
        "result": False,
        "__jid__": "20170406104341210934",
    }
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
                    "failed": True,
                    "out": "highstate",
                },
                "gold": {
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
                },
            }
        )
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.state(name, tgt, highstate=True)
            assert ret == expected
        mock.assert_called_once()

    expected.update(
        {
            "changes": {
                "out": "highstate",
                "ret": {"bronze": False, "charcoal": False, "silver": False},
            },
            "comment": "Run failed on minions: silver, bronze",
        }
    )
    with patch.dict(saltmod.__opts__, {"test": False}):
        mock = MagicMock(
            return_value={
                "charcoal": {
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
                },
                "bronze": {
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
                },
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
                    "failed": True,
                    "out": "highstate",
                },
                "gold": {
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
                },
            }
        )
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.state(name, tgt, highstate=True, fail_minions="charcoal")
            ret_comment = ret.pop("comment")
            expected.pop("comment")
            assert ret == expected
            # The order can be different, hence asserting like this
            assert "Run failed on minions: " in ret_comment
            assert "silver" in ret_comment
            assert "bronze" in ret_comment
        mock.assert_called_once()

    expected.update(
        {
            "changes": {
                "out": "highstate",
                "ret": {"bronze": False, "charcoal": False, "silver": False},
            },
            "comment": "Run failed on minions: silver",
        }
    )
    with patch.dict(saltmod.__opts__, {"test": False}):
        mock = MagicMock(
            return_value={
                "charcoal": {
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
                },
                "bronze": {
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
                },
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
                    "failed": True,
                    "out": "highstate",
                },
                "gold": {
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
                },
            }
        )
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.state(
                name, tgt, highstate=True, fail_minions="bronze,charcoal"
            )
            assert ret == expected
        mock.assert_called_once()
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.state(
                name, tgt, highstate=True, fail_minions=["bronze", "charcoal"]
            )
            assert ret == expected

    expected.pop("__jid__")
    expected.update(
        {
            "result": True,
            "changes": {},
            "comment": "States ran successfully.",
            "warnings": [
                "'fail_minions' needs to be a list or a comma separated string. Ignored.",
            ],
        }
    )
    ret = saltmod.state(name, tgt, highstate=True, fail_minions={})
    assert ret == expected


def test_state_allow_fail():

    name = "state"
    tgt = "minion1"

    expected = {
        "name": name,
        "changes": {"out": "highstate", "ret": {"silver": False}},
        "comment": "States ran successfully. Updating silver. No changes made to gold.",
        "result": True,
        "__jid__": "20170406104341210934",
    }
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
                    "failed": True,
                    "out": "highstate",
                },
                "gold": {
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
                },
            }
        )
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.state(name, tgt, highstate=True, allow_fail=1)
            assert ret == expected
        mock.assert_called_once()

    gold_ret = {
        "test_|-notify_me_|-this is a name_|-show_notification": {
            "comment": "Notify me",
            "name": "this is a name",
            "start_time": "10:43:41.487565",
            "result": True,
            "duration": 0.35,
            "__run_num__": 0,
            "__sls__": "demo",
            "changes": {"foo": "bar"},
            "__id__": "notify_me",
        }
    }

    expected["changes"]["ret"]["gold"] = gold_ret

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
                    "failed": True,
                    "out": "highstate",
                },
                "gold": {
                    "jid": "20170406104341210934",
                    "retcode": 0,
                    "ret": gold_ret,
                    "out": "highstate",
                },
            }
        )
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.state(name, tgt, highstate=True, allow_fail=1)
            ret_comment = ret.pop("comment")
            expected.pop("comment")
            assert ret == expected
            # The order can be different, hence asserting like this
            assert "States ran successfully. Updating " in ret_comment
            assert "silver" in ret_comment
            assert "gold" in ret_comment
        mock.assert_called_once()

    expected.update(
        {
            "changes": {
                "out": "highstate",
                "ret": {"bronze": False, "charcoal": False, "silver": False},
            },
            "comment": "Run failed on minions: silver, bronze",
            "result": False,
        }
    )
    with patch.dict(saltmod.__opts__, {"test": False}):
        mock = MagicMock(
            return_value={
                "charcoal": {
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
                },
                "bronze": {
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
                },
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
                    "failed": True,
                    "out": "highstate",
                },
                "gold": {
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
                },
            }
        )
        with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock}):
            ret = saltmod.state(name, tgt, highstate=True, allow_fail=1)
            ret_comment = ret.pop("comment")
            expected.pop("comment")
            assert ret == expected
            # The order can be different, hence asserting like this
            assert "Run failed on minions: " in ret_comment
            assert "silver" in ret_comment
            assert "bronze" in ret_comment
        mock.assert_called_once()

    expected = {
        "name": name,
        "changes": {},
        "result": False,
        "comment": "Passed invalid value for 'allow_fail', must be an int",
    }
    ret = saltmod.state(name, tgt, allow_fail="a")
    assert ret == expected


def test_roster():
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
