import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


def test_ssh_raw(salt_ssh_cli):
    """
    test salt-ssh with -r argument
    """
    msg = "password: foo"
    ret = salt_ssh_cli.run("--raw", "echo", msg, _timeout=60)
    assert ret.returncode == 0
    assert ret.data
    assert "retcode" in ret.data
    assert ret.data["retcode"] == 0
    assert "stdout" in ret.data
    assert ret.data["stdout"] == msg + "\n"
