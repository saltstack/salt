import pytest

import salt.utils.platform

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.windows_whitelisted,
]


@pytest.fixture
def test_cmd():
    if salt.utils.platform.is_windows():
        cmd = 'whoami.exe /priv | find /c "Privilege"'
        expected = "ERROR: Invalid argument/option"
    else:
        cmd = "ls -al / | wc -l"
        expected = "ls: cannot access '|'"
    return cmd, expected


def test_run_default(modules, state_tree, test_cmd):
    """
    test cmd.run piping when called programmatically without passing
    python_shell (default behavior)
    """
    cmd, expected = test_cmd
    result = modules.cmd.run(cmd)
    assert expected in result


def test_run_python_shell_true(modules, state_tree, test_cmd):
    """
    test cmd.run piping when called programmatically with python_shell=True
    """
    cmd, _ = test_cmd
    result = modules.cmd.run(cmd, python_shell=True)
    assert int(result) > 20


def test_run_python_shell_false(modules, state_tree, test_cmd):
    """
    test cmd.run piping when called programmatically with python_shell=False
    """
    cmd, expected = test_cmd
    result = modules.cmd.run(cmd, python_shell=False)
    assert expected in result


def test_run_cli_default(modules, state_tree, test_cmd):
    """
    test cmd.run piping when run from the cli. When run from the cli, the
    __pub_jid parameter is set and it turns on python_shell
    """
    cmd, expected = test_cmd
    result = modules.cmd.run(cmd, __pub_jid="test")
    assert int(result) > 20


def test_run_cli_python_shell_false(modules, state_tree, test_cmd):
    """
    test cmd.run piping when called programmatically with python_shell=False.
    When run from the cli, the __pub_jid parameter is set and it turns on
    python_shell, unless python_shell is set.
    """
    cmd, expected = test_cmd
    result = modules.cmd.run(cmd, python_shell=False, __pub_jid="test")
    assert expected in result
