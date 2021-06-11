"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import os
import tempfile

import pytest
import salt.config
import salt.loader
import salt.states.saltmod as saltmod
import salt.utils.event
import salt.utils.jid
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase


class SaltmodTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.saltmod
    """

    def setup_loader_modules(self):
        utils = salt.loader.utils(
            salt.config.DEFAULT_MINION_OPTS.copy(), whitelist=["state"]
        )
        return {
            saltmod: {
                "__env__": "base",
                "__opts__": {
                    "__role": "master",
                    "file_client": "remote",
                    "sock_dir": tempfile.mkdtemp(dir=RUNTIME_VARS.TMP),
                    "transport": "tcp",
                },
                "__salt__": {"saltutil.cmd": MagicMock()},
                "__orchestration_jid__": salt.utils.jid.gen_jid({}),
                "__utils__": utils,
            }
        }

    # 'state' function tests: 1

    @pytest.mark.slow_test
    def test_state(self):
        """
        Test to invoke a state run on a given target
        """
        name = "state"
        tgt = "minion1"

        comt = "Passed invalid value for 'allow_fail', must be an int"

        ret = {"name": name, "changes": {}, "result": False, "comment": comt}

        test_ret = {
            "name": name,
            "changes": {},
            "result": True,
            "comment": "States ran successfully.",
        }

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

        self.assertDictEqual(saltmod.state(name, tgt, allow_fail="a"), ret)

        comt = "No highstate or sls specified, no execution made"
        ret.update({"comment": comt})
        self.assertDictEqual(saltmod.state(name, tgt), ret)

        comt = "Must pass in boolean for value of 'concurrent'"
        ret.update({"comment": comt})
        self.assertDictEqual(
            saltmod.state(name, tgt, highstate=True, concurrent="a"), ret
        )

        ret.update({"comment": comt, "result": None})
        with patch.dict(saltmod.__opts__, {"test": True}):
            self.assertDictEqual(saltmod.state(name, tgt, highstate=True), test_ret)

        ret.update(
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
                self.assertDictEqual(saltmod.state(name, tgt, highstate=True), ret)

        ret.update(
            {
                "comment": "States ran successfully. No changes made to minion1, minion3, minion2."
            }
        )
        del ret["__jid__"]
        with patch.dict(saltmod.__opts__, {"test": False}):
            with patch.dict(
                saltmod.__salt__,
                {"saltutil.cmd": MagicMock(return_value=test_batch_return)},
            ):
                state_run = saltmod.state(name, tgt, highstate=True)

                # Test return without checking the comment contents. Comments are tested later.
                comment = state_run.pop("comment")
                ret.pop("comment")
                self.assertDictEqual(state_run, ret)

                # Check the comment contents in a non-order specific way (ordering fails sometimes on PY3)
                self.assertIn("States ran successfully. No changes made to", comment)
                for minion in ["minion1", "minion2", "minion3"]:
                    self.assertIn(minion, comment)

    # 'function' function tests: 1

    @pytest.mark.slow_test
    def test_function(self):
        """
        Test to execute a single module function on a remote
        minion via salt or salt-ssh
        """
        name = "state"
        tgt = "larry"

        ret = {
            "name": name,
            "changes": {},
            "result": None,
            "comment": "Function state would be executed " "on target {}".format(tgt),
        }

        with patch.dict(saltmod.__opts__, {"test": True}):
            self.assertDictEqual(saltmod.function(name, tgt), ret)

        ret.update(
            {
                "result": True,
                "changes": {"out": "highstate", "ret": {tgt: ""}},
                "comment": "Function ran successfully."
                " Function state ran on {}.".format(tgt),
            }
        )
        with patch.dict(saltmod.__opts__, {"test": False}):
            mock_ret = {"larry": {"ret": "", "retcode": 0, "failed": False}}
            mock_cmd = MagicMock(return_value=mock_ret)
            with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock_cmd}):
                self.assertDictEqual(saltmod.function(name, tgt), ret)

    @pytest.mark.slow_test
    def test_function_when_no_minions_match(self):
        """
        Test to execute a single module function on a remote
        minion via salt or salt-ssh
        """
        name = "state"
        tgt = "larry"
        mock_ret = {}
        mock_cmd = MagicMock(return_value=mock_ret)

        ret = {
            "name": name,
            "changes": {},
            "result": False,
            "comment": "No minions responded",
        }

        with patch.dict(saltmod.__opts__, {"test": False}):
            with patch.dict(saltmod.__salt__, {"saltutil.cmd": mock_cmd}):
                self.assertDictEqual(saltmod.function(name, tgt), ret)

    # 'wait_for_event' function tests: 1

    def test_wait_for_event(self):
        """
        Test to watch Salt's event bus and block until a condition is met
        """
        name = "state"
        tgt = "minion1"

        comt = "Timeout value reached."

        ret = {"name": name, "changes": {}, "result": False, "comment": comt}

        class Mockevent:
            """
            Mock event class
            """

            flag = None

            def __init__(self):
                self.full = None

            def get_event(self, full):
                """
                Mock get_event method
                """
                self.full = full
                if self.flag:
                    return {"tag": name, "data": {}}
                return None

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        with patch.object(
            salt.utils.event, "get_event", MagicMock(return_value=Mockevent())
        ):
            with patch.dict(saltmod.__opts__, {"sock_dir": True, "transport": True}):
                with patch(
                    "salt.states.saltmod.time.time", MagicMock(return_value=1.0)
                ):
                    self.assertDictEqual(
                        saltmod.wait_for_event(name, "salt", timeout=-1.0), ret
                    )

                    Mockevent.flag = True
                    ret.update(
                        {"comment": "All events seen in 0.0 seconds.", "result": True}
                    )
                    self.assertDictEqual(saltmod.wait_for_event(name, ""), ret)

                    ret.update({"comment": "Timeout value reached.", "result": False})
                    self.assertDictEqual(
                        saltmod.wait_for_event(name, tgt, timeout=-1.0), ret
                    )

    # 'runner' function tests: 1

    def test_runner(self):
        """
        Test to execute a runner module on the master
        """
        name = "state"

        ret = {
            "changes": {"return": True},
            "name": "state",
            "result": True,
            "comment": "Runner function 'state' executed.",
            "__orchestration__": True,
        }
        runner_mock = MagicMock(return_value={"return": True})

        with patch.dict(saltmod.__salt__, {"saltutil.runner": runner_mock}):
            self.assertDictEqual(saltmod.runner(name), ret)

    # 'wheel' function tests: 1

    def test_wheel(self):
        """
        Test to execute a wheel module on the master
        """
        name = "state"

        ret = {
            "changes": {"return": True},
            "name": "state",
            "result": True,
            "comment": "Wheel function 'state' executed.",
            "__orchestration__": True,
        }
        wheel_mock = MagicMock(return_value={"return": True})

        with patch.dict(saltmod.__salt__, {"saltutil.wheel": wheel_mock}):
            self.assertDictEqual(saltmod.wheel(name), ret)

    @pytest.mark.slow_test
    def test_state_ssh(self):
        """
        Test saltmod passes roster to saltutil.cmd
        """
        origcmd = saltmod.__salt__["saltutil.cmd"]
        cmd_kwargs = {}
        cmd_args = []

        def cmd_mock(*args, **kwargs):
            cmd_args.extend(args)
            cmd_kwargs.update(kwargs)
            return origcmd(*args, **kwargs)

        with patch.dict(saltmod.__salt__, {"saltutil.cmd": cmd_mock}):
            ret = saltmod.state(
                "state.sls", tgt="*", ssh=True, highstate=True, roster="my_roster"
            )
        assert "roster" in cmd_kwargs
        assert cmd_kwargs["roster"] == "my_roster"


class StatemodTests(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        self.tmp_cachedir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        return {
            saltmod: {
                "__env__": "base",
                "__opts__": {
                    "id": "webserver2",
                    "argv": [],
                    "__role": "master",
                    "cachedir": self.tmp_cachedir,
                    "extension_modules": os.path.join(self.tmp_cachedir, "extmods"),
                },
                "__salt__": {"saltutil.cmd": MagicMock()},
                "__orchestration_jid__": salt.utils.jid.gen_jid({}),
            }
        }

    def test_statemod_state(self):
        """ Smoke test for for salt.states.statemod.state().  Ensures that we
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
        ret = saltmod.state(*args, **kwargs)
        expected = {
            "comment": "States ran successfully.",
            "changes": {},
            "name": "webserver_setup",
            "result": True,
        }
        self.assertEqual(ret, expected)
