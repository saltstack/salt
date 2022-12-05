"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import logging

import pytest

import salt.exceptions
import salt.state
import salt.utils.files
import salt.utils.platform
from salt.exceptions import CommandExecutionError
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


def test_format_log_non_ascii_character():
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


@pytest.mark.slow_test
def test_render_error_on_invalid_requisite(minion_opts):
    """
    Test that the state compiler correctly deliver a rendering
    exception when a requisite cannot be resolved
    """
    with patch("salt.state.State._gather_pillar"):
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
        minion_opts["pillar"] = {"git": OrderedDict([("test1", "test")])}
        state_obj = salt.state.State(minion_opts)
        with pytest.raises(salt.exceptions.SaltRenderError):
            state_obj.call_high(high_data)


def test_verify_onlyif_parse(minion_opts):
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
    for key in ("__sls__", "__id__", "name"):
        expected_result[key] = low_data.get(key)

    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        return_result = state_obj._run_check_onlyif(low_data, "")
        assert expected_result == return_result


def test_verify_onlyif_parse_deep_return(minion_opts):
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
    for key in ("__sls__", "__id__", "name"):
        expected_result[key] = low_data.get(key)

    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        return_result = state_obj._run_check_onlyif(low_data, "")
        assert expected_result == return_result


def test_verify_onlyif_cmd_error(minion_opts):
    """
    Simulates a failure in cmd.retcode from onlyif
    This could occur if runas is specified with a user that does not exist
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
    for key in ("__sls__", "__id__", "name"):
        expected_result[key] = low_data.get(key)

    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        mock = MagicMock(side_effect=CommandExecutionError("Boom!"))
        with patch.dict(state_obj.functions, {"cmd.retcode": mock}):
            #  The mock handles the exception, but the runas dict is being passed as it would actually be
            return_result = state_obj._run_check_onlyif(
                low_data, {"runas": "doesntexist"}
            )
            assert expected_result == return_result


def test_verify_unless_cmd_error(minion_opts):
    """
    Simulates a failure in cmd.retcode from unless
    This could occur if runas is specified with a user that does not exist
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
    for key in ("__sls__", "__id__", "name"):
        expected_result[key] = low_data.get(key)

    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        mock = MagicMock(side_effect=CommandExecutionError("Boom!"))
        with patch.dict(state_obj.functions, {"cmd.retcode": mock}):
            #  The mock handles the exception, but the runas dict is being passed as it would actually be
            return_result = state_obj._run_check_unless(
                low_data, {"runas": "doesntexist"}
            )
            assert expected_result == return_result


def test_verify_unless_list_cmd(minion_opts):
    """
    If any of the unless commands return False (non 0) then the state should
    run (no skip_watch).
    """
    low_data = {
        "state": "cmd",
        "name": 'echo "something"',
        "__sls__": "tests.cmd",
        "__env__": "base",
        "__id__": "check unless",
        "unless": ["exit 0", "exit 1"],
        "order": 10001,
        "fun": "run",
    }
    expected_result = {
        "comment": "unless condition is false",
        "result": False,
    }
    for key in ("__sls__", "__id__", "name"):
        expected_result[key] = low_data.get(key)
    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        return_result = state_obj._run_check_unless(low_data, {})
        assert expected_result == return_result


def test_verify_unless_list_cmd_different_order(minion_opts):
    """
    If any of the unless commands return False (non 0) then the state should
    run (no skip_watch). The order shouldn't matter.
    """
    low_data = {
        "state": "cmd",
        "name": 'echo "something"',
        "__sls__": "tests.cmd",
        "__env__": "base",
        "__id__": "check unless",
        "unless": ["exit 1", "exit 0"],
        "order": 10001,
        "fun": "run",
    }
    expected_result = {
        "comment": "unless condition is false",
        "result": False,
    }
    for key in ("__sls__", "__id__", "name"):
        expected_result[key] = low_data.get(key)
    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        return_result = state_obj._run_check_unless(low_data, {})
        assert expected_result == return_result


def test_verify_onlyif_list_cmd_different_order(minion_opts):
    low_data = {
        "state": "cmd",
        "name": 'echo "something"',
        "__sls__": "tests.cmd",
        "__env__": "base",
        "__id__": "check onlyif",
        "onlyif": ["exit 1", "exit 0"],
        "order": 10001,
        "fun": "run",
    }
    expected_result = {
        "comment": "onlyif condition is false",
        "result": True,
        "skip_watch": True,
    }
    for key in ("__sls__", "__id__", "name"):
        expected_result[key] = low_data.get(key)
    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        return_result = state_obj._run_check_onlyif(low_data, {})
        assert expected_result == return_result


def test_verify_unless_list_cmd_valid(minion_opts):
    """
    If any of the unless commands return False (non 0) then the state should
    run (no skip_watch). This tests all commands return False.
    """
    low_data = {
        "state": "cmd",
        "name": 'echo "something"',
        "__sls__": "tests.cmd",
        "__env__": "base",
        "__id__": "check unless",
        "unless": ["exit 1", "exit 1"],
        "order": 10001,
        "fun": "run",
    }
    expected_result = {"comment": "unless condition is false", "result": False}
    for key in ("__sls__", "__id__", "name"):
        expected_result[key] = low_data.get(key)
    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        return_result = state_obj._run_check_unless(low_data, {})
        assert expected_result == return_result


def test_verify_onlyif_list_cmd_valid(minion_opts):
    low_data = {
        "state": "cmd",
        "name": 'echo "something"',
        "__sls__": "tests.cmd",
        "__env__": "base",
        "__id__": "check onlyif",
        "onlyif": ["exit 0", "exit 0"],
        "order": 10001,
        "fun": "run",
    }
    expected_result = {"comment": "onlyif condition is true", "result": False}
    for key in ("__sls__", "__id__", "name"):
        expected_result[key] = low_data.get(key)
    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        return_result = state_obj._run_check_onlyif(low_data, {})
        assert expected_result == return_result


def test_verify_unless_list_cmd_invalid(minion_opts):
    """
    If any of the unless commands return False (non 0) then the state should
    run (no skip_watch). This tests all commands return True
    """
    low_data = {
        "state": "cmd",
        "name": 'echo "something"',
        "__sls__": "tests.cmd",
        "__env__": "base",
        "__id__": "check unless",
        "unless": ["exit 0", "exit 0"],
        "order": 10001,
        "fun": "run",
    }
    expected_result = {
        "comment": "unless condition is true",
        "result": True,
        "skip_watch": True,
    }
    for key in ("__sls__", "__id__", "name"):
        expected_result[key] = low_data.get(key)
    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        return_result = state_obj._run_check_unless(low_data, {})
        assert expected_result == return_result


def test_verify_onlyif_list_cmd_invalid(minion_opts):
    low_data = {
        "state": "cmd",
        "name": 'echo "something"',
        "__sls__": "tests.cmd",
        "__env__": "base",
        "__id__": "check onlyif",
        "onlyif": ["exit 1", "exit 1"],
        "order": 10001,
        "fun": "run",
    }
    expected_result = {
        "comment": "onlyif condition is false",
        "result": True,
        "skip_watch": True,
    }
    for key in ("__sls__", "__id__", "name"):
        expected_result[key] = low_data.get(key)
    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        return_result = state_obj._run_check_onlyif(low_data, {})
        assert expected_result == return_result


def test_verify_unless_parse(minion_opts):
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
    for key in ("__sls__", "__id__", "name"):
        expected_result[key] = low_data.get(key)

    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        return_result = state_obj._run_check_unless(low_data, "")
        assert expected_result == return_result


def test_verify_unless_parse_deep_return(minion_opts):
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
    for key in ("__sls__", "__id__", "name"):
        expected_result[key] = low_data.get(key)

    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        return_result = state_obj._run_check_unless(low_data, "")
        assert expected_result == return_result


def test_verify_creates(minion_opts):
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

    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        with patch("os.path.exists") as path_mock:
            path_mock.return_value = True
            expected_result = {
                "comment": "/tmp/thing exists",
                "result": True,
                "skip_watch": True,
            }
            for key in ("__sls__", "__id__", "name"):
                expected_result[key] = low_data.get(key)
            return_result = state_obj._run_check_creates(low_data)
            assert expected_result == return_result

            path_mock.return_value = False
            expected_result = {
                "comment": "Creates files not found",
                "result": False,
            }
            for key in ("__sls__", "__id__", "name"):
                expected_result[key] = low_data.get(key)
            return_result = state_obj._run_check_creates(low_data)
            assert expected_result == return_result


def test_verify_creates_list(minion_opts):
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

    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        with patch("os.path.exists") as path_mock:
            path_mock.return_value = True
            expected_result = {
                "comment": "All files in creates exist",
                "result": True,
                "skip_watch": True,
            }
            for key in ("__sls__", "__id__", "name"):
                expected_result[key] = low_data.get(key)
            return_result = state_obj._run_check_creates(low_data)
            assert expected_result == return_result

            path_mock.return_value = False
            expected_result = {
                "comment": "Creates files not found",
                "result": False,
            }
            for key in ("__sls__", "__id__", "name"):
                expected_result[key] = low_data.get(key)
            return_result = state_obj._run_check_creates(low_data)
            assert expected_result == return_result


def _expand_win_path(path):
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


def test_verify_onlyif_parse_slots(tmp_path, minion_opts):
    name = str(tmp_path / "testfile.txt")
    with salt.utils.files.fopen(name, "w") as fp:
        fp.write("file-contents")
    low_data = {
        "onlyif": [
            {
                "fun": "file.search",
                "args": ["__slot__:salt:test.echo({})".format(_expand_win_path(name))],
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
    for key in ("__sls__", "__id__", "name"):
        expected_result[key] = low_data.get(key)
    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        return_result = state_obj._run_check_onlyif(low_data, "")
        assert expected_result == return_result


def test_verify_onlyif_list_cmd(minion_opts):
    low_data = {
        "state": "cmd",
        "name": 'echo "something"',
        "__sls__": "tests.cmd",
        "__env__": "base",
        "__id__": "check onlyif",
        "onlyif": ["exit 0", "exit 1"],
        "order": 10001,
        "fun": "run",
    }
    expected_result = {
        "comment": "onlyif condition is false",
        "result": True,
        "skip_watch": True,
    }
    for key in ("__sls__", "__id__", "name"):
        expected_result[key] = low_data.get(key)
    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        return_result = state_obj._run_check_onlyif(low_data, {})
        assert expected_result == return_result


def test_verify_onlyif_cmd_args(minion_opts):
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

    with patch("salt.state.State._gather_pillar"):
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


def test_verify_unless_parse_slots(tmp_path, minion_opts):
    name = str(tmp_path / "testfile.txt")
    with salt.utils.files.fopen(name, "w") as fp:
        fp.write("file-contents")
    low_data = {
        "unless": [
            {
                "fun": "file.search",
                "args": ["__slot__:salt:test.echo({})".format(_expand_win_path(name))],
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
    for key in ("__sls__", "__id__", "name"):
        expected_result[key] = low_data.get(key)

    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        return_result = state_obj._run_check_unless(low_data, "")
        assert expected_result == return_result


def test_verify_retry_parsing(minion_opts):
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
        "__run_num__": 0,
        "changes": {},
        "comment": "['unless condition is true']  The state would be retried every 5 "
        "seconds (with a splay of up to 0 seconds) a maximum of 5 times or "
        "until a result of True is returned",
        "result": True,
        "skip_watch": True,
    }
    for key in ("__sls__", "__id__", "name"):
        expected_result[key] = low_data.get(key)

    with patch("salt.state.State._gather_pillar"):
        minion_opts["test"] = True
        minion_opts["file_client"] = "local"
        state_obj = salt.state.State(minion_opts)
        mock = {
            "result": True,
            "comment": ["unless condition is true"],
            "skip_watch": True,
        }
        with patch.object(state_obj, "_run_check", return_value=mock):
            assert set(expected_result).issubset(set(state_obj.call(low_data)))


def test_render_requisite_require_disabled(minion_opts):
    """
    Test that the state compiler correctly deliver a rendering
    exception when a requisite cannot be resolved
    """
    with patch("salt.state.State._gather_pillar"):
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

        minion_opts["disabled_requisites"] = ["require"]
        state_obj = salt.state.State(minion_opts)
        ret = state_obj.call_high(high_data)
        run_num = ret["test_|-step_one_|-step_one_|-succeed_with_changes"][
            "__run_num__"
        ]
        assert run_num == 0


def test_render_requisite_require_in_disabled(minion_opts):
    """
    Test that the state compiler correctly deliver a rendering
    exception when a requisite cannot be resolved
    """
    with patch("salt.state.State._gather_pillar"):
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

        minion_opts["disabled_requisites"] = ["require_in"]
        state_obj = salt.state.State(minion_opts)
        ret = state_obj.call_high(high_data)
        run_num = ret["test_|-step_one_|-step_one_|-succeed_with_changes"][
            "__run_num__"
        ]
        assert run_num == 0


def test_call_chunk_sub_state_run(minion_opts):
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
    expected_sub_state_tag = (
        "external_state_|-external_state_id_|-external_state_name_|-external_function"
    )
    with patch("salt.state.State._gather_pillar"):
        with patch("salt.state.State.call", return_value=mock_call_return):
            minion_opts["disabled_requisites"] = ["require"]
            state_obj = salt.state.State(minion_opts)
            ret = state_obj.call_chunk(low_data, {}, {})
            sub_state = ret.get(expected_sub_state_tag)
            assert sub_state
            assert sub_state["__run_num__"] == 1
            assert sub_state["name"] == "external_state_name"
            assert sub_state["__state_ran__"]
            assert sub_state["__sls__"] == "external"


def test_aggregate_requisites(minion_opts):
    """
    Test to ensure that the requisites are included in the aggregated low state.
    """
    # The low that is returned from _mod_aggregrate
    low = {
        "state": "pkg",
        "name": "other_pkgs",
        "__sls__": "47628",
        "__env__": "base",
        "__id__": "other_pkgs",
        "pkgs": ["byobu", "vim", "tmux", "google-cloud-sdk"],
        "aggregate": True,
        "order": 10002,
        "fun": "installed",
        "__agg__": True,
    }

    # Chunks that have been processed through the pkg mod_aggregate function
    chunks = [
        {
            "state": "file",
            "name": "/tmp/install-vim",
            "__sls__": "47628",
            "__env__": "base",
            "__id__": "/tmp/install-vim",
            "order": 10000,
            "fun": "managed",
        },
        {
            "state": "file",
            "name": "/tmp/install-tmux",
            "__sls__": "47628",
            "__env__": "base",
            "__id__": "/tmp/install-tmux",
            "order": 10001,
            "fun": "managed",
        },
        {
            "state": "pkg",
            "name": "other_pkgs",
            "__sls__": "47628",
            "__env __": "base",
            "__id__": "other_pkgs",
            "pkgs": ["byobu"],
            "aggregate": True,
            "order": 10002,
            "fun": "installed",
        },
        {
            "state": "pkg",
            "name": "bc",
            "__sls__": "47628",
            "__env__": "base",
            "__id__": "bc",
            "hold": True,
            "__agg__": True,
            "order": 10003,
            "fun": "installed",
        },
        {
            "state": "pkg",
            "name": "vim",
            "__sls__": "47628",
            "__env__": "base",
            "__agg__": True,
            "__id__": "vim",
            "require": ["/tmp/install-vim"],
            "order": 10004,
            "fun": "installed",
        },
        {
            "state": "pkg",
            "name": "tmux",
            "__sls__": "47628",
            "__env__": "base",
            "__agg__": True,
            "__id__": "tmux",
            "require": ["/tmp/install-tmux"],
            "order": 10005,
            "fun": "installed",
        },
        {
            "state": "pkgrepo",
            "name": "deb https://packages.cloud.google.com/apt cloud-sdk main",
            "__sls__": "47628",
            "__env__": "base",
            "__id__": "google-cloud-repo",
            "humanname": "Google Cloud SDK",
            "file": "/etc/apt/sources.list.d/google-cloud-sdk.list",
            "key_url": "https://packages.cloud.google.com/apt/doc/apt-key.gpg",
            "order": 10006,
            "fun": "managed",
        },
        {
            "state": "pkg",
            "name": "google-cloud-sdk",
            "__sls__": "47628",
            "__env__": "base",
            "__agg__": True,
            "__id__": "google-cloud-sdk",
            "require": ["google-cloud-repo"],
            "order": 10007,
            "fun": "installed",
        },
    ]

    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        low_ret = state_obj._aggregate_requisites(low, chunks)

        # Ensure the low returned contains require
        assert "require" in low_ret

        # Ensure all the requires from pkg states are in low
        assert low_ret["require"] == [
            "/tmp/install-vim",
            "/tmp/install-tmux",
            "google-cloud-repo",
        ]


def test_mod_aggregate(minion_opts):
    """
    Test to ensure that the requisites are included in the aggregated low state.
    """
    # The low that is returned from _mod_aggregrate
    low = {
        "state": "pkg",
        "name": "sl",
        "__sls__": "test.62439",
        "__env__": "base",
        "__id__": "sl",
        "require_in": [OrderedDict([("file", "/tmp/foo")])],
        "order": 10002,
        "aggregate": True,
        "fun": "installed",
    }

    # Chunks that have been processed through the pkg mod_aggregate function
    chunks = [
        {
            "state": "file",
            "name": "/tmp/foo",
            "__sls__": "test.62439",
            "__env__": "base",
            "__id__": "/tmp/foo",
            "content": "This is some content",
            "order": 10000,
            "require": [{"pkg": "sl"}],
            "fun": "managed",
        },
        {
            "state": "pkg",
            "name": "figlet",
            "__sls__": "test.62439",
            "__env__": "base",
            "__id__": "figlet",
            "__agg__": True,
            "require": [OrderedDict([("file", "/tmp/foo")])],
            "order": 10001,
            "aggregate": True,
            "fun": "installed",
        },
        {
            "state": "pkg",
            "name": "sl",
            "__sls__": "test.62439",
            "__env__": "base",
            "__id__": "sl",
            "require_in": [OrderedDict([("file", "/tmp/foo")])],
            "order": 10002,
            "aggregate": True,
            "fun": "installed",
        },
    ]

    running = {}

    mock_pkg_mod_aggregate = {
        "state": "pkg",
        "name": "sl",
        "__sls__": "test.62439",
        "__env__": "base",
        "__id__": "sl",
        "require_in": [OrderedDict([("file", "/tmp/foo")])],
        "order": 10002,
        "fun": "installed",
        "__agg__": True,
        "pkgs": ["figlet", "sl"],
    }

    with patch("salt.state.State._gather_pillar"):
        state_obj = salt.state.State(minion_opts)
        with patch.dict(
            state_obj.states,
            {"pkg.mod_aggregate": MagicMock(return_value=mock_pkg_mod_aggregate)},
        ):
            low_ret = state_obj._mod_aggregate(low, running, chunks)

            # Ensure the low returned contains require
            assert "require_in" in low_ret

            # Ensure all the requires from pkg states are in low
            assert low_ret["require_in"] == [OrderedDict([("file", "/tmp/foo")])]

            # Ensure that the require requisite from the
            # figlet state doesn't find its way into this state
            assert "require" not in low_ret

            # Ensure pkgs were aggregated
            assert low_ret["pkgs"] == ["figlet", "sl"]
