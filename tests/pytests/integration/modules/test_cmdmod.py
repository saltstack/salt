import logging

import pytest

import salt.utils.user

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def non_root_account():
    with pytest.helpers.create_account() as account:
        yield account


@pytest.fixture
def running_username():
    """
    Return the username that is running the code.
    """
    return salt.utils.user.get_user()


@pytest.mark.skip_if_not_root
def test_exec_code_all(salt_call_cli, non_root_account):
    ret = salt_call_cli.run(
        "cmd.exec_code_all", "bash", "echo good", runas=non_root_account.username
    )
    assert ret.returncode == 0


def test_long_stdout(salt_cli, salt_minion):
    echo_str = "salt" * 1000
    ret = salt_cli.run(
        "cmd.run", f"echo {echo_str}", use_vt=True, minion_tgt=salt_minion.id
    )
    assert ret.returncode == 0
    assert len(ret.data.strip()) == len(echo_str)


@pytest.mark.skip_if_not_root
@pytest.mark.skip_on_windows(reason="Skip on Windows, uses unix commands")
def test_avoid_injecting_shell_code_as_root(
    salt_call_cli, non_root_account, running_username
):
    """
    cmd.run should execute the whole command as the "runas" user, not
    running substitutions as root.
    """
    cmd = "echo $(id -u)"

    ret = salt_call_cli.run("cmd.run_stdout", cmd)
    root_id = ret.json
    ret = salt_call_cli.run("cmd.run_stdout", cmd, runas=running_username)
    runas_root_id = ret.json

    ret = salt_call_cli.run("cmd.run_stdout", cmd, runas=non_root_account.username)
    user_id = ret.json

    assert user_id != root_id
    assert user_id != runas_root_id
    assert root_id == runas_root_id


@pytest.mark.slow_test
def test_blacklist_glob(salt_call_cli):
    """
    cmd_blacklist_glob
    """
    cmd = "bad_command --foo"
    ret = salt_call_cli.run(
        "cmd.run",
        cmd,
    )

    assert (
        ret.stderr.rstrip()
        == "Error running 'cmd.run': The shell command \"bad_command --foo\" is not permitted"
    )


@pytest.mark.slow_test
def test_hide_output(salt_call_cli):
    """
    Test the hide_output argument
    """
    ls_command = (
        ["ls", "/"] if not salt.utils.platform.is_windows() else ["dir", "c:\\"]
    )

    error_command = ["thiscommanddoesnotexist"]

    # cmd.run
    ret = salt_call_cli.run("cmd.run", ls_command, hide_output=True)
    assert ret.data == ""

    # cmd.shell
    ret = salt_call_cli.run("cmd.shell", ls_command, hide_output=True)
    assert ret.data == ""

    # cmd.run_stdout
    ret = salt_call_cli.run("cmd.run_stdout", ls_command, hide_output=True)
    assert ret.data == ""

    # cmd.run_stderr
    ret = salt_call_cli.run("cmd.shell", error_command, hide_output=True)
    assert ret.data == ""

    # cmd.run_all (command should have produced stdout)
    ret = salt_call_cli.run("cmd.run_all", ls_command, hide_output=True)
    assert ret.data["stdout"] == ""
    assert ret.data["stderr"] == ""

    # cmd.run_all (command should have produced stderr)
    ret = salt_call_cli.run("cmd.run_all", error_command, hide_output=True)
    assert ret.data["stdout"] == ""
    assert ret.data["stderr"] == ""
