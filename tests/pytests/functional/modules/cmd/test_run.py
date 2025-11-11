import pytest

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.windows_whitelisted,
]


def test_run(modules, state_tree):
    cmd = 'whoami.exe /priv | find /c "Privilege"'
    expected = "ERROR: Invalid argument/option"
    result = modules.cmd.run(cmd)
    assert expected in result


def test_run_python_shell(modules, state_tree):
    cmd = 'whoami.exe /priv | find /c "Privilege"'
    result = modules.cmd.run(cmd, python_shell=True)
    assert int(result) > 20