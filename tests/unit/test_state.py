"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import os
import shutil
import tempfile

import salt.exceptions
import salt.state
import salt.utils.files
import salt.utils.platform
from salt.exceptions import CommandExecutionError
from salt.utils.decorators import state as statedecorators
from salt.utils.odict import OrderedDict
from tests.support.helpers import slowTest, with_tempfile
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf

try:
    import pytest
except ImportError as err:
    pytest = None


class StateCompilerTestCase(TestCase, AdaptedConfigurationTestCaseMixin):
    """
    TestCase for the state compiler.
    """

    def test_format_log_non_ascii_character(self):
        """
        Tests running a non-ascii character through the state.format_log
        function. See Issue #33605.
        """
        # There is no return to test against as the format_log
        # function doesn't return anything. However, we do want
        # to make sure that the function doesn't stacktrace when
        # called.
        ret = {
            "changes": {"Français": {"old": "something old", "new": "something new"}},
            "result": True,
        }
        salt.state.format_log(ret)

    @slowTest
    def test_render_error_on_invalid_requisite(self):
        """
        Test that the state compiler correctly deliver a rendering
        exception when a requisite cannot be resolved
        """
        with patch("salt.state.State._gather_pillar") as state_patch:
            high_data = {
                "git": OrderedDict(
                    [
                        (
                            "pkg",
                            [
                                OrderedDict(
                                    [
                                        (
                                            "require",
                                            [
                                                OrderedDict(
                                                    [
                                                        (
                                                            "file",
                                                            OrderedDict(
                                                                [("test1", "test")]
                                                            ),
                                                        )
                                                    ]
                                                )
                                            ],
                                        )
                                    ]
                                ),
                                "installed",
                                {"order": 10000},
                            ],
                        ),
                        ("__sls__", "issue_35226"),
                        ("__env__", "base"),
                    ]
                )
            }
            minion_opts = self.get_temp_config("minion")
            minion_opts["pillar"] = {"git": OrderedDict([("test1", "test")])}
            state_obj = salt.state.State(minion_opts)
            with self.assertRaises(salt.exceptions.SaltRenderError):
                state_obj.call_high(high_data)

    def test_verify_onlyif_parse(self):
        low_data = {
            "onlyif": [{"fun": "test.arg", "args": ["arg1", "arg2"]}],
            "name": "mysql-server-5.7",
            "state": "debconf",
            "__id__": "set root password",
            "fun": "set",
            "__env__": "base",
            "__sls__": "debconf",
            "data": {
                "mysql-server/root_password": {"type": "password", "value": "temp123"}
            },
            "order": 10000,
        }
        expected_result = {"comment": "onlyif condition is true", "result": False}

        with patch("salt.state.State._gather_pillar") as state_patch:
            minion_opts = self.get_temp_config("minion")
            state_obj = salt.state.State(minion_opts)
            return_result = state_obj._run_check_onlyif(low_data, "")
            self.assertEqual(expected_result, return_result)

    def test_verify_onlyif_parse_deep_return(self):
        low_data = {
            "state": "test",
            "name": "foo",
            "__sls__": "consol",
            "__env__": "base",
            "__id__": "test",
            "onlyif": [
                {
                    "fun": "test.arg",
                    "get_return": "kwargs:deep:return",
                    "deep": {"return": "true"},
                }
            ],
            "order": 10000,
            "fun": "nop",
        }
        expected_result = {"comment": "onlyif condition is true", "result": False}

        with patch("salt.state.State._gather_pillar") as state_patch:
            minion_opts = self.get_temp_config("minion")
            state_obj = salt.state.State(minion_opts)
            return_result = state_obj._run_check_onlyif(low_data, "")
            self.assertEqual(expected_result, return_result)

    def test_verify_onlyif_cmd_error(self):
        """
        Simulates a failure in cmd.retcode from onlyif
        This could occur is runas is specified with a user that does not exist
        """
        low_data = {
            "onlyif": "somecommand",
            "runas": "doesntexist",
            "name": "echo something",
            "state": "cmd",
            "__id__": "this is just a test",
            "fun": "run",
            "__env__": "base",
            "__sls__": "sometest",
            "order": 10000,
        }
        expected_result = {
            "comment": "onlyif condition is false",
            "result": True,
            "skip_watch": True,
        }

        with patch("salt.state.State._gather_pillar") as state_patch:
            minion_opts = self.get_temp_config("minion")
            state_obj = salt.state.State(minion_opts)
            mock = MagicMock(side_effect=CommandExecutionError("Boom!"))
            with patch.dict(state_obj.functions, {"cmd.retcode": mock}):
                #  The mock handles the exception, but the runas dict is being passed as it would actually be
                return_result = state_obj._run_check_onlyif(
                    low_data, {"runas": "doesntexist"}
                )
                self.assertEqual(expected_result, return_result)

    def test_verify_unless_cmd_error(self):
        """
        Simulates a failure in cmd.retcode from unless
        This could occur is runas is specified with a user that does not exist
        """
        low_data = {
            "unless": "somecommand",
            "runas": "doesntexist",
            "name": "echo something",
            "state": "cmd",
            "__id__": "this is just a test",
            "fun": "run",
            "__env__": "base",
            "__sls__": "sometest",
            "order": 10000,
        }
        expected_result = {
            "comment": "unless condition is true",
            "result": True,
            "skip_watch": True,
        }

        with patch("salt.state.State._gather_pillar") as state_patch:
            minion_opts = self.get_temp_config("minion")
            state_obj = salt.state.State(minion_opts)
            mock = MagicMock(side_effect=CommandExecutionError("Boom!"))
            with patch.dict(state_obj.functions, {"cmd.retcode": mock}):
                #  The mock handles the exception, but the runas dict is being passed as it would actually be
                return_result = state_obj._run_check_unless(
                    low_data, {"runas": "doesntexist"}
                )
                self.assertEqual(expected_result, return_result)

    def test_verify_unless_parse(self):
        low_data = {
            "unless": [{"fun": "test.arg", "args": ["arg1", "arg2"]}],
            "name": "mysql-server-5.7",
            "state": "debconf",
            "__id__": "set root password",
            "fun": "set",
            "__env__": "base",
            "__sls__": "debconf",
            "data": {
                "mysql-server/root_password": {"type": "password", "value": "temp123"}
            },
            "order": 10000,
        }
        expected_result = {
            "comment": "unless condition is true",
            "result": True,
            "skip_watch": True,
        }

        with patch("salt.state.State._gather_pillar") as state_patch:
            minion_opts = self.get_temp_config("minion")
            state_obj = salt.state.State(minion_opts)
            return_result = state_obj._run_check_unless(low_data, "")
            self.assertEqual(expected_result, return_result)

    def test_verify_unless_parse_deep_return(self):
        low_data = {
            "state": "test",
            "name": "foo",
            "__sls__": "consol",
            "__env__": "base",
            "__id__": "test",
            "unless": [
                {
                    "fun": "test.arg",
                    "get_return": "kwargs:deep:return",
                    "deep": {"return": False},
                }
            ],
            "order": 10000,
            "fun": "nop",
        }
        expected_result = {"comment": "unless condition is false", "result": False}

        with patch("salt.state.State._gather_pillar") as state_patch:
            minion_opts = self.get_temp_config("minion")
            state_obj = salt.state.State(minion_opts)
            return_result = state_obj._run_check_unless(low_data, "")
            self.assertEqual(expected_result, return_result)

    def test_verify_creates(self):
        low_data = {
            "state": "cmd",
            "name": 'echo "something"',
            "__sls__": "tests.creates",
            "__env__": "base",
            "__id__": "do_a_thing",
            "creates": "/tmp/thing",
            "order": 10000,
            "fun": "run",
        }

        with patch("salt.state.State._gather_pillar") as state_patch:
            minion_opts = self.get_temp_config("minion")
            state_obj = salt.state.State(minion_opts)
            with patch("os.path.exists") as path_mock:
                path_mock.return_value = True
                expected_result = {
                    "comment": "/tmp/thing exists",
                    "result": True,
                    "skip_watch": True,
                }
                return_result = state_obj._run_check_creates(low_data)
                self.assertEqual(expected_result, return_result)

                path_mock.return_value = False
                expected_result = {
                    "comment": "Creates files not found",
                    "result": False,
                }
                return_result = state_obj._run_check_creates(low_data)
                self.assertEqual(expected_result, return_result)

    def test_verify_creates_list(self):
        low_data = {
            "state": "cmd",
            "name": 'echo "something"',
            "__sls__": "tests.creates",
            "__env__": "base",
            "__id__": "do_a_thing",
            "creates": ["/tmp/thing", "/tmp/thing2"],
            "order": 10000,
            "fun": "run",
        }

        with patch("salt.state.State._gather_pillar") as state_patch:
            minion_opts = self.get_temp_config("minion")
            state_obj = salt.state.State(minion_opts)
            with patch("os.path.exists") as path_mock:
                path_mock.return_value = True
                expected_result = {
                    "comment": "All files in creates exist",
                    "result": True,
                    "skip_watch": True,
                }
                return_result = state_obj._run_check_creates(low_data)
                self.assertEqual(expected_result, return_result)

                path_mock.return_value = False
                expected_result = {
                    "comment": "Creates files not found",
                    "result": False,
                }
                return_result = state_obj._run_check_creates(low_data)
                self.assertEqual(expected_result, return_result)

    def _expand_win_path(self, path):
        """
        Expand C:/users/admini~1/appdata/local/temp/salt-tests-tmpdir/...
        into C:/users/adminitrator/appdata/local/temp/salt-tests-tmpdir/...
        to prevent file.search from expanding the "~" with os.path.expanduser
        """
        if salt.utils.platform.is_windows():
            import win32file

            return win32file.GetLongPathName(path).replace("\\", "/")
        else:
            return path

    @with_tempfile()
    def test_verify_onlyif_parse_slots(self, name):
        with salt.utils.files.fopen(name, "w") as fp:
            fp.write("file-contents")
        low_data = {
            "onlyif": [
                {
                    "fun": "file.search",
                    "args": [
                        "__slot__:salt:test.echo({})".format(
                            self._expand_win_path(name)
                        ),
                    ],
                    "pattern": "__slot__:salt:test.echo(file-contents)",
                }
            ],
            "name": "mysql-server-5.7",
            "state": "debconf",
            "__id__": "set root password",
            "fun": "set",
            "__env__": "base",
            "__sls__": "debconf",
            "data": {
                "mysql-server/root_password": {"type": "password", "value": "temp123"}
            },
            "order": 10000,
        }
        expected_result = {"comment": "onlyif condition is true", "result": False}
        with patch("salt.state.State._gather_pillar") as state_patch:
            minion_opts = self.get_temp_config("minion")
            state_obj = salt.state.State(minion_opts)
            return_result = state_obj._run_check_onlyif(low_data, "")
            self.assertEqual(expected_result, return_result)

    def test_verify_onlyif_list_cmd(self):
        low_data = {
            "state": "cmd",
            "name": 'echo "something"',
            "__sls__": "tests.cmd",
            "__env__": "base",
            "__id__": "check onlyif",
            "onlyif": ["/bin/true", "/bin/false"],
            "order": 10001,
            "fun": "run",
        }
        expected_result = {
            "comment": "onlyif condition is false",
            "result": True,
            "skip_watch": True,
        }
        with patch("salt.state.State._gather_pillar") as state_patch:
            minion_opts = self.get_temp_config("minion")
            state_obj = salt.state.State(minion_opts)
            return_result = state_obj._run_check_onlyif(low_data, {})
            self.assertEqual(expected_result, return_result)

    def test_verify_onlyif_cmd_args(self):
        """
        Verify cmd.run state arguments are properly passed to cmd.retcode in onlyif
        """
        low_data = {
            "onlyif": "somecommand",
            "cwd": "acwd",
            "root": "aroot",
            "env": [{"akey": "avalue"}],
            "prepend_path": "apath",
            "umask": "0700",
            "success_retcodes": 1,
            "timeout": 5,
            "runas": "doesntexist",
            "name": "echo something",
            "shell": "/bin/dash",
            "state": "cmd",
            "__id__": "this is just a test",
            "fun": "run",
            "__env__": "base",
            "__sls__": "sometest",
            "order": 10000,
        }

        with patch("salt.state.State._gather_pillar") as state_patch:
            minion_opts = self.get_temp_config("minion")
            state_obj = salt.state.State(minion_opts)
            mock = MagicMock()
            with patch.dict(state_obj.functions, {"cmd.retcode": mock}):
                #  The mock handles the exception, but the runas dict is being passed as it would actually be
                return_result = state_obj._run_check(low_data)
                mock.assert_called_once_with(
                    "somecommand",
                    ignore_retcode=True,
                    python_shell=True,
                    cwd="acwd",
                    root="aroot",
                    runas="doesntexist",
                    env=[{"akey": "avalue"}],
                    prepend_path="apath",
                    umask="0700",
                    timeout=5,
                    success_retcodes=1,
                    shell="/bin/dash",
                )

    @with_tempfile()
    def test_verify_unless_parse_slots(self, name):
        with salt.utils.files.fopen(name, "w") as fp:
            fp.write("file-contents")
        low_data = {
            "unless": [
                {
                    "fun": "file.search",
                    "args": [
                        "__slot__:salt:test.echo({})".format(
                            self._expand_win_path(name)
                        ),
                    ],
                    "pattern": "__slot__:salt:test.echo(file-contents)",
                }
            ],
            "name": "mysql-server-5.7",
            "state": "debconf",
            "__id__": "set root password",
            "fun": "set",
            "__env__": "base",
            "__sls__": "debconf",
            "data": {
                "mysql-server/root_password": {"type": "password", "value": "temp123"}
            },
            "order": 10000,
        }
        expected_result = {
            "comment": "unless condition is true",
            "result": True,
            "skip_watch": True,
        }

        with patch("salt.state.State._gather_pillar") as state_patch:
            minion_opts = self.get_temp_config("minion")
            state_obj = salt.state.State(minion_opts)
            return_result = state_obj._run_check_unless(low_data, "")
            self.assertEqual(expected_result, return_result)

    def test_verify_retry_parsing(self):
        low_data = {
            "state": "file",
            "name": "/tmp/saltstack.README.rst",
            "__sls__": "demo.download",
            "__env__": "base",
            "__id__": "download sample data",
            "retry": {"attempts": 5, "interval": 5},
            "unless": ["test -f /tmp/saltstack.README.rst"],
            "source": [
                "https://raw.githubusercontent.com/saltstack/salt/develop/README.rst"
            ],
            "source_hash": "f2bc8c0aa2ae4f5bb5c2051686016b48",
            "order": 10000,
            "fun": "managed",
        }
        expected_result = {
            "__id__": "download sample data",
            "__run_num__": 0,
            "__sls__": "demo.download",
            "changes": {},
            "comment": "['unless condition is true']  The state would be retried every 5 "
            "seconds (with a splay of up to 0 seconds) a maximum of 5 times or "
            "until a result of True is returned",
            "name": "/tmp/saltstack.README.rst",
            "result": True,
            "skip_watch": True,
        }

        with patch("salt.state.State._gather_pillar") as state_patch:
            minion_opts = self.get_temp_config("minion")
            minion_opts["test"] = True
            minion_opts["file_client"] = "local"
            state_obj = salt.state.State(minion_opts)
            mock = {
                "result": True,
                "comment": ["unless condition is true"],
                "skip_watch": True,
            }
            with patch.object(state_obj, "_run_check", return_value=mock):
                self.assertDictContainsSubset(expected_result, state_obj.call(low_data))

    def test_render_requisite_require_disabled(self):
        """
        Test that the state compiler correctly deliver a rendering
        exception when a requisite cannot be resolved
        """
        with patch("salt.state.State._gather_pillar") as state_patch:
            high_data = {
                "step_one": OrderedDict(
                    [
                        (
                            "test",
                            [
                                OrderedDict(
                                    [("require", [OrderedDict([("test", "step_two")])])]
                                ),
                                "succeed_with_changes",
                                {"order": 10000},
                            ],
                        ),
                        ("__sls__", "test.disable_require"),
                        ("__env__", "base"),
                    ]
                ),
                "step_two": {
                    "test": ["succeed_with_changes", {"order": 10001}],
                    "__env__": "base",
                    "__sls__": "test.disable_require",
                },
            }

            minion_opts = self.get_temp_config("minion")
            minion_opts["disabled_requisites"] = ["require"]
            state_obj = salt.state.State(minion_opts)
            ret = state_obj.call_high(high_data)
            run_num = ret["test_|-step_one_|-step_one_|-succeed_with_changes"][
                "__run_num__"
            ]
            self.assertEqual(run_num, 0)

    def test_render_requisite_require_in_disabled(self):
        """
        Test that the state compiler correctly deliver a rendering
        exception when a requisite cannot be resolved
        """
        with patch("salt.state.State._gather_pillar") as state_patch:
            high_data = {
                "step_one": {
                    "test": ["succeed_with_changes", {"order": 10000}],
                    "__env__": "base",
                    "__sls__": "test.disable_require_in",
                },
                "step_two": OrderedDict(
                    [
                        (
                            "test",
                            [
                                OrderedDict(
                                    [
                                        (
                                            "require_in",
                                            [OrderedDict([("test", "step_one")])],
                                        )
                                    ]
                                ),
                                "succeed_with_changes",
                                {"order": 10001},
                            ],
                        ),
                        ("__sls__", "test.disable_require_in"),
                        ("__env__", "base"),
                    ]
                ),
            }

            minion_opts = self.get_temp_config("minion")
            minion_opts["disabled_requisites"] = ["require_in"]
            state_obj = salt.state.State(minion_opts)
            ret = state_obj.call_high(high_data)
            run_num = ret["test_|-step_one_|-step_one_|-succeed_with_changes"][
                "__run_num__"
            ]
            self.assertEqual(run_num, 0)

    def test_call_chunk_sub_state_run(self):
        """
        Test running a batch of states with an external runner
        that returns sub_state_run
        """
        low_data = {
            "state": "external",
            "name": "external_state_name",
            "__id__": "do_a_thing",
            "__sls__": "external",
            "order": 10000,
            "fun": "state",
        }
        mock_call_return = {
            "__run_num__": 0,
            "sub_state_run": [
                {
                    "changes": {},
                    "result": True,
                    "comment": "",
                    "low": {
                        "name": "external_state_name",
                        "__id__": "external_state_id",
                        "state": "external_state",
                        "fun": "external_function",
                    },
                }
            ],
        }
        expected_sub_state_tag = "external_state_|-external_state_id_|-external_state_name_|-external_function"
        with patch("salt.state.State._gather_pillar") as state_patch:
            with patch("salt.state.State.call", return_value=mock_call_return):
                minion_opts = self.get_temp_config("minion")
                minion_opts["disabled_requisites"] = ["require"]
                state_obj = salt.state.State(minion_opts)
                ret = state_obj.call_chunk(low_data, {}, {})
                sub_state = ret.get(expected_sub_state_tag)
                assert sub_state
                self.assertEqual(sub_state["__run_num__"], 1)
                self.assertEqual(sub_state["name"], "external_state_name")
                self.assertEqual(sub_state["__state_ran__"], True)
                self.assertEqual(sub_state["__sls__"], "external")


class HighStateTestCase(TestCase, AdaptedConfigurationTestCaseMixin):
    def setUp(self):
        root_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.state_tree_dir = os.path.join(root_dir, "state_tree")
        cache_dir = os.path.join(root_dir, "cachedir")
        for dpath in (root_dir, self.state_tree_dir, cache_dir):
            if not os.path.isdir(dpath):
                os.makedirs(dpath)

        overrides = {}
        overrides["root_dir"] = root_dir
        overrides["state_events"] = False
        overrides["id"] = "match"
        overrides["file_client"] = "local"
        overrides["file_roots"] = dict(base=[self.state_tree_dir])
        overrides["cachedir"] = cache_dir
        overrides["test"] = False
        self.config = self.get_temp_config("minion", **overrides)
        self.addCleanup(delattr, self, "config")
        self.highstate = salt.state.HighState(self.config)
        self.addCleanup(delattr, self, "highstate")
        self.highstate.push_active()

    def tearDown(self):
        self.highstate.pop_active()

    def test_top_matches_with_list(self):
        top = {"env": {"match": ["state1", "state2"], "nomatch": ["state3"]}}
        matches = self.highstate.top_matches(top)
        self.assertEqual(matches, {"env": ["state1", "state2"]})

    def test_top_matches_with_string(self):
        top = {"env": {"match": "state1", "nomatch": "state2"}}
        matches = self.highstate.top_matches(top)
        self.assertEqual(matches, {"env": ["state1"]})

    def test_matches_whitelist(self):
        matches = {"env": ["state1", "state2", "state3"]}
        matches = self.highstate.matches_whitelist(matches, ["state2"])
        self.assertEqual(matches, {"env": ["state2"]})

    def test_matches_whitelist_with_string(self):
        matches = {"env": ["state1", "state2", "state3"]}
        matches = self.highstate.matches_whitelist(matches, "state2,state3")
        self.assertEqual(matches, {"env": ["state2", "state3"]})

    def test_show_state_usage(self):
        # monkey patch sub methods
        self.highstate.avail = {"base": ["state.a", "state.b", "state.c"]}

        def verify_tops(*args, **kwargs):
            return []

        def get_top(*args, **kwargs):
            return None

        def top_matches(*args, **kwargs):
            return {"base": ["state.a", "state.b"]}

        self.highstate.verify_tops = verify_tops
        self.highstate.get_top = get_top
        self.highstate.top_matches = top_matches

        # get compile_state_usage() result
        state_usage_dict = self.highstate.compile_state_usage()

        self.assertEqual(state_usage_dict["base"]["count_unused"], 1)
        self.assertEqual(state_usage_dict["base"]["count_used"], 2)
        self.assertEqual(state_usage_dict["base"]["count_all"], 3)
        self.assertEqual(state_usage_dict["base"]["used"], ["state.a", "state.b"])
        self.assertEqual(state_usage_dict["base"]["unused"], ["state.c"])

    def test_find_sls_ids_with_exclude(self):
        """
        See https://github.com/saltstack/salt/issues/47182
        """
        sls_dir = "issue-47182"
        shutil.copytree(
            os.path.join(RUNTIME_VARS.BASE_FILES, sls_dir),
            os.path.join(self.state_tree_dir, sls_dir),
        )
        shutil.move(
            os.path.join(self.state_tree_dir, sls_dir, "top.sls"), self.state_tree_dir
        )
        # Manually compile the high data. We don't have to worry about all of
        # the normal error checking we do here since we know that all the SLS
        # files exist and there is no whitelist/blacklist being used.
        top = self.highstate.get_top()  # pylint: disable=assignment-from-none
        matches = self.highstate.top_matches(top)
        high, _ = self.highstate.render_highstate(matches)
        ret = salt.state.find_sls_ids("issue-47182.stateA.newer", high)
        self.assertEqual(ret, [("somestuff", "cmd")])


class MultiEnvHighStateTestCase(TestCase, AdaptedConfigurationTestCaseMixin):
    def setUp(self):
        root_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.base_state_tree_dir = os.path.join(root_dir, "base")
        self.other_state_tree_dir = os.path.join(root_dir, "other")
        cache_dir = os.path.join(root_dir, "cachedir")
        for dpath in (
            root_dir,
            self.base_state_tree_dir,
            self.other_state_tree_dir,
            cache_dir,
        ):
            if not os.path.isdir(dpath):
                os.makedirs(dpath)
        shutil.copy(
            os.path.join(RUNTIME_VARS.BASE_FILES, "top.sls"), self.base_state_tree_dir
        )
        shutil.copy(
            os.path.join(RUNTIME_VARS.BASE_FILES, "core.sls"), self.base_state_tree_dir
        )
        shutil.copy(
            os.path.join(RUNTIME_VARS.BASE_FILES, "test.sls"), self.other_state_tree_dir
        )
        overrides = {}
        overrides["root_dir"] = root_dir
        overrides["state_events"] = False
        overrides["id"] = "match"
        overrides["file_client"] = "local"
        overrides["file_roots"] = dict(
            base=[self.base_state_tree_dir], other=[self.other_state_tree_dir]
        )
        overrides["cachedir"] = cache_dir
        overrides["test"] = False
        self.config = self.get_temp_config("minion", **overrides)
        self.addCleanup(delattr, self, "config")
        self.highstate = salt.state.HighState(self.config)
        self.addCleanup(delattr, self, "highstate")
        self.highstate.push_active()

    def tearDown(self):
        self.highstate.pop_active()

    def test_lazy_avail_states_base(self):
        # list_states not called yet
        self.assertEqual(self.highstate.avail._filled, False)
        self.assertEqual(self.highstate.avail._avail, {"base": None})
        # After getting 'base' env available states
        self.highstate.avail["base"]  # pylint: disable=pointless-statement
        self.assertEqual(self.highstate.avail._filled, False)
        self.assertEqual(self.highstate.avail._avail, {"base": ["core", "top"]})

    def test_lazy_avail_states_other(self):
        # list_states not called yet
        self.assertEqual(self.highstate.avail._filled, False)
        self.assertEqual(self.highstate.avail._avail, {"base": None})
        # After getting 'other' env available states
        self.highstate.avail["other"]  # pylint: disable=pointless-statement
        self.assertEqual(self.highstate.avail._filled, True)
        self.assertEqual(self.highstate.avail._avail, {"base": None, "other": ["test"]})

    def test_lazy_avail_states_multi(self):
        # list_states not called yet
        self.assertEqual(self.highstate.avail._filled, False)
        self.assertEqual(self.highstate.avail._avail, {"base": None})
        # After getting 'base' env available states
        self.highstate.avail["base"]  # pylint: disable=pointless-statement
        self.assertEqual(self.highstate.avail._filled, False)
        self.assertEqual(self.highstate.avail._avail, {"base": ["core", "top"]})
        # After getting 'other' env available states
        self.highstate.avail["other"]  # pylint: disable=pointless-statement
        self.assertEqual(self.highstate.avail._filled, True)
        self.assertEqual(
            self.highstate.avail._avail, {"base": ["core", "top"], "other": ["test"]}
        )


@skipIf(pytest is None, "PyTest is missing")
class StateReturnsTestCase(TestCase):
    """
    TestCase for code handling state returns.
    """

    def test_state_output_check_changes_is_dict(self):
        """
        Test that changes key contains a dictionary.
        :return:
        """
        data = {"changes": []}
        out = statedecorators.OutputUnifier("content_check")(lambda: data)()
        assert "'Changes' should be a dictionary" in out["comment"]
        assert not out["result"]

    def test_state_output_check_return_is_dict(self):
        """
        Test for the entire return is a dictionary
        :return:
        """
        data = ["whatever"]
        out = statedecorators.OutputUnifier("content_check")(lambda: data)()
        assert (
            "Malformed state return. Data must be a dictionary type" in out["comment"]
        )
        assert not out["result"]

    def test_state_output_check_return_has_nrc(self):
        """
        Test for name/result/comment keys are inside the return.
        :return:
        """
        data = {"arbitrary": "data", "changes": {}}
        out = statedecorators.OutputUnifier("content_check")(lambda: data)()
        assert (
            " The following keys were not present in the state return: name, result, comment"
            in out["comment"]
        )
        assert not out["result"]

    def test_state_output_unifier_comment_is_not_list(self):
        """
        Test for output is unified so the comment is converted to a multi-line string
        :return:
        """
        data = {
            "comment": ["data", "in", "the", "list"],
            "changes": {},
            "name": None,
            "result": "fantastic!",
        }
        expected = {
            "comment": "data\nin\nthe\nlist",
            "changes": {},
            "name": None,
            "result": True,
        }
        assert statedecorators.OutputUnifier("unify")(lambda: data)() == expected

        data = {
            "comment": ["data", "in", "the", "list"],
            "changes": {},
            "name": None,
            "result": None,
        }
        expected = "data\nin\nthe\nlist"
        assert (
            statedecorators.OutputUnifier("unify")(lambda: data)()["comment"]
            == expected
        )

    def test_state_output_unifier_result_converted_to_true(self):
        """
        Test for output is unified so the result is converted to True
        :return:
        """
        data = {
            "comment": ["data", "in", "the", "list"],
            "changes": {},
            "name": None,
            "result": "Fantastic",
        }
        assert statedecorators.OutputUnifier("unify")(lambda: data)()["result"] is True

    def test_state_output_unifier_result_converted_to_false(self):
        """
        Test for output is unified so the result is converted to False
        :return:
        """
        data = {
            "comment": ["data", "in", "the", "list"],
            "changes": {},
            "name": None,
            "result": "",
        }
        assert statedecorators.OutputUnifier("unify")(lambda: data)()["result"] is False


@skipIf(pytest is None, "PyTest is missing")
class SubStateReturnsTestCase(TestCase):
    """
    TestCase for code handling state returns.
    """

    def test_sub_state_output_check_changes_is_dict(self):
        """
        Test that changes key contains a dictionary.
        :return:
        """
        data = {"changes": {}, "sub_state_run": [{"changes": []}]}
        out = statedecorators.OutputUnifier("content_check")(lambda: data)()
        assert "'Changes' should be a dictionary" in out["sub_state_run"][0]["comment"]
        assert not out["sub_state_run"][0]["result"]

    def test_sub_state_output_check_return_is_dict(self):
        """
        Test for the entire return is a dictionary
        :return:
        """
        data = {"sub_state_run": [["whatever"]]}
        out = statedecorators.OutputUnifier("content_check")(lambda: data)()
        assert (
            "Malformed state return. Data must be a dictionary type"
            in out["sub_state_run"][0]["comment"]
        )
        assert not out["sub_state_run"][0]["result"]

    def test_sub_state_output_check_return_has_nrc(self):
        """
        Test for name/result/comment keys are inside the return.
        :return:
        """
        data = {"sub_state_run": [{"arbitrary": "data", "changes": {}}]}
        out = statedecorators.OutputUnifier("content_check")(lambda: data)()
        assert (
            " The following keys were not present in the state return: name, result, comment"
            in out["sub_state_run"][0]["comment"]
        )
        assert not out["sub_state_run"][0]["result"]

    def test_sub_state_output_unifier_comment_is_not_list(self):
        """
        Test for output is unified so the comment is converted to a multi-line string
        :return:
        """
        data = {
            "sub_state_run": [
                {
                    "comment": ["data", "in", "the", "list"],
                    "changes": {},
                    "name": None,
                    "result": "fantastic!",
                }
            ]
        }
        expected = {
            "sub_state_run": [
                {
                    "comment": "data\nin\nthe\nlist",
                    "changes": {},
                    "name": None,
                    "result": True,
                }
            ]
        }
        assert statedecorators.OutputUnifier("unify")(lambda: data)() == expected

        data = {
            "sub_state_run": [
                {
                    "comment": ["data", "in", "the", "list"],
                    "changes": {},
                    "name": None,
                    "result": None,
                }
            ]
        }
        expected = "data\nin\nthe\nlist"
        assert (
            statedecorators.OutputUnifier("unify")(lambda: data)()["sub_state_run"][0][
                "comment"
            ]
            == expected
        )

    def test_sub_state_output_unifier_result_converted_to_true(self):
        """
        Test for output is unified so the result is converted to True
        :return:
        """
        data = {
            "sub_state_run": [
                {
                    "comment": ["data", "in", "the", "list"],
                    "changes": {},
                    "name": None,
                    "result": "Fantastic",
                }
            ]
        }
        assert (
            statedecorators.OutputUnifier("unify")(lambda: data)()["sub_state_run"][0][
                "result"
            ]
            is True
        )

    def test_sub_state_output_unifier_result_converted_to_false(self):
        """
        Test for output is unified so the result is converted to False
        :return:
        """
        data = {
            "sub_state_run": [
                {
                    "comment": ["data", "in", "the", "list"],
                    "changes": {},
                    "name": None,
                    "result": "",
                }
            ]
        }
        assert (
            statedecorators.OutputUnifier("unify")(lambda: data)()["sub_state_run"][0][
                "result"
            ]
            is False
        )


class StateFormatSlotsTestCase(TestCase, AdaptedConfigurationTestCaseMixin):
    """
    TestCase for code handling slots
    """

    def setUp(self):
        with patch("salt.state.State._gather_pillar"):
            minion_opts = self.get_temp_config("minion")
            self.state_obj = salt.state.State(minion_opts)

    def test_format_slots_no_slots(self):
        """
        Test the format slots keeps data without slots untouched.
        """
        cdata = {"args": ["arg"], "kwargs": {"key": "val"}}
        self.state_obj.format_slots(cdata)
        self.assertEqual(cdata, {"args": ["arg"], "kwargs": {"key": "val"}})

    @slowTest
    def test_format_slots_arg(self):
        """
        Test the format slots is calling a slot specified in args with corresponding arguments.
        """
        cdata = {
            "args": ["__slot__:salt:mod.fun(fun_arg, fun_key=fun_val)"],
            "kwargs": {"key": "val"},
        }
        mock = MagicMock(return_value="fun_return")
        with patch.dict(self.state_obj.functions, {"mod.fun": mock}):
            self.state_obj.format_slots(cdata)
        mock.assert_called_once_with("fun_arg", fun_key="fun_val")
        self.assertEqual(cdata, {"args": ["fun_return"], "kwargs": {"key": "val"}})

    @slowTest
    def test_format_slots_dict_arg(self):
        """
        Test the format slots is calling a slot specified in dict arg.
        """
        cdata = {
            "args": [{"subarg": "__slot__:salt:mod.fun(fun_arg, fun_key=fun_val)"}],
            "kwargs": {"key": "val"},
        }
        mock = MagicMock(return_value="fun_return")
        with patch.dict(self.state_obj.functions, {"mod.fun": mock}):
            self.state_obj.format_slots(cdata)
        mock.assert_called_once_with("fun_arg", fun_key="fun_val")
        self.assertEqual(
            cdata, {"args": [{"subarg": "fun_return"}], "kwargs": {"key": "val"}}
        )

    @slowTest
    def test_format_slots_listdict_arg(self):
        """
        Test the format slots is calling a slot specified in list containing a dict.
        """
        cdata = {
            "args": [[{"subarg": "__slot__:salt:mod.fun(fun_arg, fun_key=fun_val)"}]],
            "kwargs": {"key": "val"},
        }
        mock = MagicMock(return_value="fun_return")
        with patch.dict(self.state_obj.functions, {"mod.fun": mock}):
            self.state_obj.format_slots(cdata)
        mock.assert_called_once_with("fun_arg", fun_key="fun_val")
        self.assertEqual(
            cdata, {"args": [[{"subarg": "fun_return"}]], "kwargs": {"key": "val"}}
        )

    @slowTest
    def test_format_slots_liststr_arg(self):
        """
        Test the format slots is calling a slot specified in list containing a dict.
        """
        cdata = {
            "args": [["__slot__:salt:mod.fun(fun_arg, fun_key=fun_val)"]],
            "kwargs": {"key": "val"},
        }
        mock = MagicMock(return_value="fun_return")
        with patch.dict(self.state_obj.functions, {"mod.fun": mock}):
            self.state_obj.format_slots(cdata)
        mock.assert_called_once_with("fun_arg", fun_key="fun_val")
        self.assertEqual(cdata, {"args": [["fun_return"]], "kwargs": {"key": "val"}})

    @slowTest
    def test_format_slots_kwarg(self):
        """
        Test the format slots is calling a slot specified in kwargs with corresponding arguments.
        """
        cdata = {
            "args": ["arg"],
            "kwargs": {"key": "__slot__:salt:mod.fun(fun_arg, fun_key=fun_val)"},
        }
        mock = MagicMock(return_value="fun_return")
        with patch.dict(self.state_obj.functions, {"mod.fun": mock}):
            self.state_obj.format_slots(cdata)
        mock.assert_called_once_with("fun_arg", fun_key="fun_val")
        self.assertEqual(cdata, {"args": ["arg"], "kwargs": {"key": "fun_return"}})

    @slowTest
    def test_format_slots_multi(self):
        """
        Test the format slots is calling all slots with corresponding arguments when multiple slots
        specified.
        """
        cdata = {
            "args": [
                "__slot__:salt:test_mod.fun_a(a_arg, a_key=a_kwarg)",
                "__slot__:salt:test_mod.fun_b(b_arg, b_key=b_kwarg)",
            ],
            "kwargs": {
                "kw_key_1": "__slot__:salt:test_mod.fun_c(c_arg, c_key=c_kwarg)",
                "kw_key_2": "__slot__:salt:test_mod.fun_d(d_arg, d_key=d_kwarg)",
            },
        }
        mock_a = MagicMock(return_value="fun_a_return")
        mock_b = MagicMock(return_value="fun_b_return")
        mock_c = MagicMock(return_value="fun_c_return")
        mock_d = MagicMock(return_value="fun_d_return")
        with patch.dict(
            self.state_obj.functions,
            {
                "test_mod.fun_a": mock_a,
                "test_mod.fun_b": mock_b,
                "test_mod.fun_c": mock_c,
                "test_mod.fun_d": mock_d,
            },
        ):
            self.state_obj.format_slots(cdata)
        mock_a.assert_called_once_with("a_arg", a_key="a_kwarg")
        mock_b.assert_called_once_with("b_arg", b_key="b_kwarg")
        mock_c.assert_called_once_with("c_arg", c_key="c_kwarg")
        mock_d.assert_called_once_with("d_arg", d_key="d_kwarg")
        self.assertEqual(
            cdata,
            {
                "args": ["fun_a_return", "fun_b_return"],
                "kwargs": {"kw_key_1": "fun_c_return", "kw_key_2": "fun_d_return"},
            },
        )

    @slowTest
    def test_format_slots_malformed(self):
        """
        Test the format slots keeps malformed slots untouched.
        """
        sls_data = {
            "args": [
                "__slot__:NOT_SUPPORTED:not.called()",
                "__slot__:salt:not.called(",
                "__slot__:salt:",
                "__slot__:salt",
                "__slot__:",
                "__slot__",
            ],
            "kwargs": {
                "key3": "__slot__:NOT_SUPPORTED:not.called()",
                "key4": "__slot__:salt:not.called(",
                "key5": "__slot__:salt:",
                "key6": "__slot__:salt",
                "key7": "__slot__:",
                "key8": "__slot__",
            },
        }
        cdata = sls_data.copy()
        mock = MagicMock(return_value="return")
        with patch.dict(self.state_obj.functions, {"not.called": mock}):
            self.state_obj.format_slots(cdata)
        mock.assert_not_called()
        self.assertEqual(cdata, sls_data)

    @slowTest
    def test_slot_traverse_dict(self):
        """
        Test the slot parsing of dict response.
        """
        cdata = {
            "args": ["arg"],
            "kwargs": {"key": "__slot__:salt:mod.fun(fun_arg, fun_key=fun_val).key1"},
        }
        return_data = {"key1": "value1"}
        mock = MagicMock(return_value=return_data)
        with patch.dict(self.state_obj.functions, {"mod.fun": mock}):
            self.state_obj.format_slots(cdata)
        mock.assert_called_once_with("fun_arg", fun_key="fun_val")
        self.assertEqual(cdata, {"args": ["arg"], "kwargs": {"key": "value1"}})

    @slowTest
    def test_slot_append(self):
        """
        Test the slot parsing of dict response.
        """
        cdata = {
            "args": ["arg"],
            "kwargs": {
                "key": "__slot__:salt:mod.fun(fun_arg, fun_key=fun_val).key1 ~ thing~",
            },
        }
        return_data = {"key1": "value1"}
        mock = MagicMock(return_value=return_data)
        with patch.dict(self.state_obj.functions, {"mod.fun": mock}):
            self.state_obj.format_slots(cdata)
        mock.assert_called_once_with("fun_arg", fun_key="fun_val")
        self.assertEqual(cdata, {"args": ["arg"], "kwargs": {"key": "value1thing~"}})

    # Skip on windows like integration.modules.test_state.StateModuleTest.test_parallel_state_with_long_tag
    @skipIf(
        salt.utils.platform.is_windows(),
        "Skipped until parallel states can be fixed on Windows",
    )
    def test_format_slots_parallel(self):
        """
        Test if slots work with "parallel: true".
        """
        high_data = {
            "always-changes-and-succeeds": {
                "test": [
                    {"changes": True},
                    {"comment": "__slot__:salt:test.echo(fun_return)"},
                    {"parallel": True},
                    "configurable_test_state",
                    {"order": 10000},
                ],
                "__env__": "base",
                "__sls__": "parallel_slots",
            }
        }
        self.state_obj.jid = "123"
        res = self.state_obj.call_high(high_data)
        self.state_obj.jid = None
        [(_, data)] = res.items()
        self.assertEqual(data["comment"], "fun_return")
