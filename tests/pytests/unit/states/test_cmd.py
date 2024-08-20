"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.cmd as cmd
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {cmd: {"__env__": "base"}}


# 'wait' function tests: 1


def test_wait():
    """
    Test to run the given command only if the watch statement calls it.
    """
    name = "cmd.script"

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    assert cmd.wait(name) == ret


# 'wait_script' function tests: 1


def test_wait_script():
    """
    Test to download a script from a remote source and execute it
    only if a watch statement calls it.
    """
    name = "cmd.script"

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    assert cmd.wait_script(name) == ret


# 'run' function tests: 1


def test_run():
    """
    Test to run a command if certain circumstances are met.
    """
    name = "cmd.script"

    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    with patch.dict(cmd.__opts__, {"test": False}):
        comt = "Invalidly-formatted 'env' parameter. See documentation."
        ret.update({"comment": comt})
        assert cmd.run(name, env="salt") == ret

    with patch.dict(cmd.__grains__, {"shell": "shell"}):
        with patch.dict(cmd.__opts__, {"test": False}):
            mock = MagicMock(side_effect=[CommandExecutionError, {"retcode": 1}])
            with patch.dict(cmd.__salt__, {"cmd.run_all": mock}):
                ret.update({"comment": "", "result": False})
                assert cmd.run(name) == ret

                ret.update(
                    {
                        "comment": 'Command "cmd.script" run',
                        "result": False,
                        "changes": {"retcode": 1},
                    }
                )
                assert cmd.run(name) == ret

        with patch.dict(cmd.__opts__, {"test": True}):
            comt = 'Command "cmd.script" would have been executed'
            ret.update(
                {"comment": comt, "result": None, "changes": {"cmd": "cmd.script"}}
            )
            assert cmd.run(name) == ret


def test_run_root():
    """
    Test to run a command with a different root
    """
    name = "cmd.script"

    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    with patch.dict(cmd.__grains__, {"shell": "shell"}):
        with patch.dict(cmd.__opts__, {"test": False}):
            mock = MagicMock(side_effect=[CommandExecutionError, {"retcode": 1}])
            with patch.dict(cmd.__salt__, {"cmd.run_chroot": mock}):
                ret.update({"comment": "", "result": False})
                assert cmd.run(name, root="/mnt") == ret

                ret.update(
                    {
                        "comment": 'Command "cmd.script" run',
                        "result": False,
                        "changes": {"retcode": 1},
                    }
                )
                assert cmd.run(name, root="/mnt") == ret


# 'script' function tests: 1


def test_script():
    """
    Test to download a script and execute it with specified arguments.
    """
    name = "cmd.script"

    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    with patch.dict(cmd.__opts__, {"test": False}):
        comt = "Invalidly-formatted 'env' parameter. See documentation."
        ret.update({"comment": comt})
        assert cmd.script(name, env="salt") == ret

    with patch.dict(cmd.__grains__, {"shell": "shell"}):
        with patch.dict(cmd.__opts__, {"test": True}):
            comt = "Command 'cmd.script' would have been executed"
            ret.update({"comment": comt, "result": None, "changes": {}})
            assert cmd.script(name) == ret

        with patch.dict(cmd.__opts__, {"test": False}):
            mock = MagicMock(side_effect=[CommandExecutionError, {"retcode": 1}])
            with patch.dict(cmd.__salt__, {"cmd.script": mock}):
                ret.update({"comment": "", "result": False})
                assert cmd.script(name) == ret

                ret.update(
                    {
                        "comment": "Command 'cmd.script' run",
                        "result": False,
                        "changes": {"retcode": 1},
                    }
                )
                assert cmd.script(name) == ret


@pytest.mark.skip_unless_on_windows(reason="Test is only applicable to Windows.")
def test_script_runas_no_password():
    """
    Test to download a script and execute it, specifically on windows.
    Make sure that when using runas, and a password is not supplied we check.
    """
    name = "cmd.script"
    ret = {
        "name": "cmd.script",
        "changes": {},
        "result": False,
        "comment": "Must supply a password if runas argument is used on Windows.",
    }

    patch_opts = patch.dict(cmd.__opts__, {"test": False})
    patch_shell = patch.dict(cmd.__grains__, {"shell": "shell"})

    # Fake the execution module call
    mock = MagicMock(side_effect=[CommandExecutionError, {"retcode": 1}])
    patch_call = patch.dict(cmd.__salt__, {"cmd.script": mock})

    with patch_opts, patch_shell, patch_call:
        assert cmd.script(name, runas="User") == ret


@pytest.mark.skip_unless_on_windows(reason="Test is only applicable to Windows.")
def test_script_runas_password():
    """
    Test to download a script and execute it, specifically on windows.
    Make sure that when we do supply a password, we get into the function call.
    """
    name = "cmd.script"
    ret = {"changes": {}, "comment": "", "name": "cmd.script", "result": False}

    patch_opts = patch.dict(cmd.__opts__, {"test": False})
    patch_shell = patch.dict(cmd.__grains__, {"shell": "shell"})

    # Fake the execution module call
    mock = MagicMock(side_effect=[CommandExecutionError, {"retcode": 1}])
    patch_call = patch.dict(cmd.__salt__, {"cmd.script": mock})

    with patch_opts, patch_shell, patch_call:
        assert cmd.script(name, runas="User", password="Test") == ret


# 'call' function tests: 1


def test_call():
    """
    Test to invoke a pre-defined Python function with arguments
    specified in the state declaration.
    """
    name = "cmd.script"
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    flag = None

    def func():
        """
        Mock func method
        """
        if flag:
            return {}
        else:
            return []

    with patch.dict(cmd.__grains__, {"shell": "shell"}):
        flag = True
        assert cmd.call(name, func) == ret

        flag = False
        ret.update({"comment": "", "result": False, "changes": {"retval": []}})
        assert cmd.call(name, func) == ret


# 'wait_call' function tests: 1


def test_wait_call():
    """
    Test to run wait_call.
    """
    name = "cmd.script"
    func = "myfunc"

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    assert cmd.wait_call(name, func) == ret


# 'mod_watch' function tests: 1


def test_mod_watch():
    """
    Test to execute a cmd function based on a watch call
    """
    name = "cmd.script"

    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    def func():
        """
        Mock func method
        """
        return {}

    with patch.dict(cmd.__grains__, {"shell": "shell"}):
        with patch.dict(cmd.__opts__, {"test": False}):
            mock = MagicMock(return_value={"retcode": 1})
            with patch.dict(cmd.__salt__, {"cmd.run_all": mock}):
                assert cmd.mod_watch(name, sfun="wait", stateful=True) == ret

                comt = 'Command "cmd.script" run'
                ret.update({"comment": comt, "changes": {"retcode": 1}})
                assert cmd.mod_watch(name, sfun="wait", stateful=False) == ret

            with patch.dict(cmd.__salt__, {"cmd.script": mock}):
                ret.update({"comment": "", "changes": {}})
                assert cmd.mod_watch(name, sfun="script", stateful=True) == ret

                comt = "Command 'cmd.script' run"
                ret.update({"comment": comt, "changes": {"retcode": 1}})
                assert cmd.mod_watch(name, sfun="script", stateful=False) == ret

            with patch.dict(cmd.__salt__, {"cmd.script": mock}):
                ret.update({"comment": "", "changes": {}})
                assert cmd.mod_watch(name, sfun="call", func=func) == ret

                comt = "cmd.call needs a named parameter func"
                ret.update({"comment": comt})
                assert cmd.mod_watch(name, sfun="call") == ret

            comt = (
                "cmd.salt does not work with the watch requisite,"
                " please use cmd.wait or cmd.wait_script"
            )
            ret.update({"comment": comt})
            assert cmd.mod_watch(name, sfun="salt") == ret
