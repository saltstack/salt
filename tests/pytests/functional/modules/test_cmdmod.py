import os
import random
import sys

import pytest

import salt.config
import salt.utils.path
import salt.utils.platform
import salt.utils.user
from tests.support.helpers import SKIP_INITIAL_PHOTONOS_FAILURES, dedent

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def cmdmod(modules):
    return modules.cmd


@pytest.fixture(scope="module")
def usermod(modules):
    return modules.user


@pytest.fixture(scope="module")
def available_python_executable():
    yield salt.utils.path.which_bin(
        ["python", "python3", "python3.8", "python3.9", "python3.10"]
    )


@pytest.fixture
def runas_usr():
    if salt.utils.platform.is_darwin():
        with pytest.helpers.create_account() as account:
            yield account.username
    else:
        yield "nobody"


@pytest.fixture
def running_username():
    """
    Return the username that is running the code.
    """
    return salt.utils.user.get_user()


@pytest.fixture
def script(state_tree):
    if sys.platform == "win32":
        _name = "script.bat"
        _contents = """
        @echo off
        echo %*
        """
    else:
        _name = "script.sh"
        _contents = """
        #!/bin/bash
        echo "$*"
        """

    with pytest.helpers.temp_file(_name, _contents, state_tree) as file:
        yield file


@pytest.fixture
def issue_56195_test_ps1(state_tree):
    _contents = """
    [CmdLetBinding()]
    Param(
      [SecureString] $SecureString
    )
    $Credential = New-Object System.Net.NetworkCredential("DummyId", $SecureString)
    $Credential.Password
    """

    with pytest.helpers.temp_file("issue_56195_test.ps1", _contents, state_tree):
        yield


@pytest.mark.slow_test
@pytest.mark.skip_on_windows(reason="Windows does not have grep and sed")
def test_run(cmdmod, grains):
    """
    cmd.run
    """
    shell = os.environ.get("SHELL")
    if shell is None:
        # Failed to get the SHELL var, don't run
        pytest.skip("Unable to get the SHELL environment variable")

    assert cmdmod.run("echo $SHELL")
    assert cmdmod.run("echo $SHELL", shell=shell, python_shell=True).rstrip() == shell
    assert cmdmod.run("ls / | grep etc", python_shell=True) == "etc"
    assert (
        cmdmod.run(
            'echo {{grains.id}} | awk "{print $1}"',
            template="jinja",
            python_shell=True,
        )
        == "func-tests-minion-opts"
    )
    assert cmdmod.run("grep f", stdin="one\ntwo\nthree\nfour\nfive\n") == "four\nfive"
    assert cmdmod.run('echo "a=b" | sed -e s/=/:/g', python_shell=True) == "a:b"


@pytest.mark.slow_test
def test_stdout(cmdmod):
    """
    cmd.run_stdout
    """
    assert (
        cmdmod.run_stdout('echo "cheese"').rstrip() == "cheese"
        if not salt.utils.platform.is_windows()
        else '"cheese"'
    )


@pytest.mark.slow_test
def test_stderr(cmdmod):
    """
    cmd.run_stderr
    """
    if sys.platform.startswith(("freebsd", "openbsd")):
        shell = "/bin/sh"
    else:
        shell = "/bin/bash"

    assert (
        cmdmod.run_stderr(
            'echo "cheese" 1>&2',
            shell=shell,
            python_shell=True,
        ).rstrip()
        == "cheese"
        if not salt.utils.platform.is_windows()
        else '"cheese"'
    )


@pytest.mark.slow_test
def test_run_all(cmdmod):
    """
    cmd.run_all
    """
    if sys.platform.startswith(("freebsd", "openbsd")):
        shell = "/bin/sh"
    else:
        shell = "/bin/bash"

    ret = cmdmod.run_all(
        'echo "cheese" 1>&2',
        shell=shell,
        python_shell=True,
    )
    assert "pid" in ret
    assert "retcode" in ret
    assert "stdout" in ret
    assert "stderr" in ret
    assert isinstance(ret.get("pid"), int)
    assert isinstance(ret.get("retcode"), int)
    assert isinstance(ret.get("stdout"), str)
    assert isinstance(ret.get("stderr"), str)
    assert (
        ret.get("stderr").rstrip() == "cheese"
        if not salt.utils.platform.is_windows()
        else '"cheese"'
    )


@pytest.mark.slow_test
def test_retcode(cmdmod):
    """
    cmd.retcode
    """
    assert cmdmod.retcode("exit 0", python_shell=True) == 0
    assert cmdmod.retcode("exit 1", python_shell=True) == 1


@pytest.mark.slow_test
def test_run_all_with_success_retcodes(cmdmod):
    """
    cmd.run with success_retcodes
    """
    ret = cmdmod.run_all("exit 42", success_retcodes=[42], python_shell=True)

    assert "retcode" in ret
    assert ret.get("retcode") == 0


@pytest.mark.slow_test
def test_retcode_with_success_retcodes(cmdmod):
    """
    cmd.run with success_retcodes
    """
    ret = cmdmod.retcode("exit 42", success_retcodes=[42], python_shell=True)

    assert ret == 0


@pytest.mark.slow_test
def test_run_all_with_success_stderr(cmdmod, tmp_path):
    """
    cmd.run with success_retcodes
    """
    random_file = str(tmp_path / f"{random.random()}")

    if salt.utils.platform.is_windows():
        func = "type"
        expected_stderr = "cannot find the file specified"
    else:
        func = "cat"
        expected_stderr = "No such file or directory"
    ret = cmdmod.run_all(
        f"{func} {random_file}",
        success_stderr=[expected_stderr],
        python_shell=True,
    )

    assert "retcode" in ret
    assert ret.get("retcode") == 0


@pytest.mark.slow_test
def test_script(cmdmod, script):
    """
    cmd.script
    """
    args = "saltines crackers biscuits=yes"
    script = f"salt://{os.path.basename(script)}"
    ret = cmdmod.script(script, args, saltenv="base")
    assert ret["stdout"] == args


@pytest.mark.slow_test
def test_script_query_string(cmdmod, script):
    """
    cmd.script
    """
    args = "saltines crackers biscuits=yes"
    script = f"salt://{os.path.basename(script)}?saltenv=base"
    ret = cmdmod.script(script, args, saltenv="base")
    assert ret["stdout"] == args


@pytest.mark.slow_test
def test_script_retcode(cmdmod, script):
    """
    cmd.script_retcode
    """
    script = f"salt://{os.path.basename(script)}"
    ret = cmdmod.script_retcode(script, saltenv="base")
    assert ret == 0


@pytest.mark.slow_test
def test_script_cwd(cmdmod, script, tmp_path):
    """
    cmd.script with cwd
    """
    tmp_cwd = str(tmp_path)
    args = "saltines crackers biscuits=yes"
    script = f"salt://{os.path.basename(script)}"
    ret = cmdmod.script(script, args, cwd=tmp_cwd, saltenv="base")
    assert ret["stdout"] == args


@pytest.mark.slow_test
def test_script_cwd_with_space(cmdmod, script, tmp_path):
    """
    cmd.script with cwd
    """
    tmp_cwd = str(tmp_path / "test 2")
    os.mkdir(tmp_cwd)

    args = "saltines crackers biscuits=yes"
    script = f"salt://{os.path.basename(script)}"
    ret = cmdmod.script(script, args, cwd=tmp_cwd, saltenv="base")
    assert ret["stdout"] == args


@pytest.mark.destructive_test
def test_tty(cmdmod):
    """
    cmd.tty
    """
    for tty in ("tty0", "pts3"):
        if os.path.exists(os.path.join("/dev", tty)):
            ret = cmdmod.tty(tty, "apply salt liberally")
            assert "Success" in ret


def test_which(cmdmod):
    """
    cmd.which
    """
    if sys.platform == "win32":
        search = "cmd"
        cmd = f"cmd /c where {search}"
    else:
        if not salt.utils.path.which("which"):
            pytest.skip("which cmd not installed")
        search = "cat"
        cmd = f"which {search}"
    cmd_which = cmdmod.which(search)
    assert isinstance(cmd_which, str)
    cmd_run = cmdmod.run(cmd)
    assert isinstance(cmd_run, str)
    assert cmd_which.rstrip().lower() == cmd_run.rstrip().lower()


def test_which_bin(cmdmod):
    """
    cmd.which_bin
    """
    cmds = ["pip3", "pip2", "pip", "pip-python"]
    ret = cmdmod.which_bin(cmds)
    assert os.path.splitext(os.path.basename(ret))[0] in cmds


@pytest.mark.slow_test
def test_has_exec(cmdmod, available_python_executable):
    """
    cmd.has_exec
    """
    assert cmdmod.has_exec(available_python_executable)
    assert not cmdmod.has_exec("alllfsdfnwieulrrh9123857ygf")


@pytest.mark.slow_test
def test_exec_code(cmdmod, available_python_executable):
    """
    cmd.exec_code
    """
    code = dedent(
        """
               import sys
               sys.stdout.write('cheese')
           """
    )
    assert cmdmod.exec_code(available_python_executable, code).rstrip() == "cheese"


@pytest.mark.slow_test
def test_exec_code_with_single_arg(cmdmod, available_python_executable):
    """
    cmd.exec_code
    """
    code = dedent(
        """
               import sys
               sys.stdout.write(sys.argv[1])
           """
    )
    arg = "cheese"
    assert cmdmod.exec_code(available_python_executable, code, args=arg).rstrip() == arg


@pytest.mark.slow_test
def test_exec_code_with_multiple_args(cmdmod, available_python_executable):
    """
    cmd.exec_code
    """
    code = dedent(
        """
               import sys
               sys.stdout.write(sys.argv[1])
           """
    )
    arg = "cheese"
    assert (
        cmdmod.exec_code(available_python_executable, code, args=[arg, "test"]).rstrip()
        == arg
    )


@pytest.mark.slow_test
def test_quotes(cmdmod):
    """
    cmd.run with quoted command
    """
    if sys.platform == "win32":
        # Some shell commands are not available through subprocess
        # So you need to start a shell first
        # There's also some different quoting in Windows
        cmd = 'cmd /c echo SELECT * FROM foo WHERE bar="baz" '
    else:
        cmd = """echo 'SELECT * FROM foo WHERE bar="baz"' """
    expected_result = 'SELECT * FROM foo WHERE bar="baz"'
    result = cmdmod.run_stdout(cmd).strip()
    assert result == expected_result


@pytest.mark.skip_if_not_root
@pytest.mark.skip_on_windows(reason="Skip on Windows, requires password")
def test_quotes_runas(cmdmod, running_username):
    """
    cmd.run with quoted command
    """
    cmd = """echo 'SELECT * FROM foo WHERE bar="baz"' """
    expected_result = 'SELECT * FROM foo WHERE bar="baz"'
    result = cmdmod.run_all(cmd, runas=running_username)
    errmsg = f"The command returned: {result}"
    assert result["retcode"] == 0, errmsg
    assert result["stdout"] == expected_result, errmsg


@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
@pytest.mark.skip_on_windows(reason="Skip on Windows, uses unix commands")
@pytest.mark.slow_test
def test_cwd_runas(cmdmod, usermod, runas_usr, tmp_path):
    """
    cmd.run should be able to change working directory correctly, whether
    or not runas is in use.
    """
    cmd = "pwd"
    tmp_cwd = str(tmp_path)
    os.chmod(tmp_cwd, 0o711)

    cwd_normal = cmdmod.run_stdout(cmd, cwd=tmp_cwd).rstrip("\n")
    assert tmp_cwd == cwd_normal

    cwd_runas = cmdmod.run_stdout(cmd, cwd=tmp_cwd, runas=runas_usr).rstrip("\n")
    assert tmp_cwd == cwd_runas


@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
@pytest.mark.skip_unless_on_darwin(reason="Applicable to MacOS only")
@pytest.mark.slow_test
def test_runas_env(cmdmod, usermod, runas_usr):
    """
    cmd.run should be able to change working directory correctly, whether
    or not runas is in use.
    """
    user_path = cmdmod.run_stdout('printf %s "$PATH"', runas=runas_usr)
    # XXX: Not sure of a better way. Environment starts out with
    # /bin:/usr/bin and should be populated by path helper and the bash
    # profile.
    assert "/bin:/usr/bin" != user_path


@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
@pytest.mark.skip_unless_on_darwin(reason="Applicable to MacOS only")
@pytest.mark.slow_test
def test_runas_complex_command_bad_cwd(cmdmod, usermod, runas_usr, tmp_path):
    """
    cmd.run should not accidentally run parts of a complex command when
    given a cwd which cannot be used by the user the command is run as.
    Due to the need to use `su -l` to login to another user on MacOS, we
    cannot cd into directories that the target user themselves does not
    have execute permission for. To an extent, this test is testing that
    buggy behaviour, but its purpose is to ensure that the greater bug of
    running commands after failing to cd does not occur.
    """
    tmp_cwd = str(tmp_path)
    os.chmod(tmp_cwd, 0o700)
    cmd_result = cmdmod.run_all(
        'pwd; pwd; : $(echo "You have failed the test" >&2)',
        cwd=tmp_cwd,
        runas=runas_usr,
    )
    assert "" == cmd_result["stdout"]
    assert "You have failed the test" not in cmd_result["stderr"]
    assert 0 != cmd_result["retcode"]


@SKIP_INITIAL_PHOTONOS_FAILURES
@pytest.mark.skip_on_windows
@pytest.mark.skip_if_not_root
@pytest.mark.destructive_test
@pytest.mark.slow_test
def test_runas(cmdmod, usermod, runas_usr):
    """
    Ensure that the env is the runas user's
    """
    out = cmdmod.run("env", runas=runas_usr).splitlines()
    assert f"USER={runas_usr}" in out


def test_timeout(cmdmod):
    """
    cmd.run trigger timeout
    """
    if sys.platform == "win32":
        cmd = 'Start-Sleep 2; Write-Host "hello"'
        out = cmdmod.run(cmd, timeout=1, python_shell=True, shell="powershell")
    else:
        if not salt.utils.path.which("sleep"):
            pytest.skip("sleep cmd not installed")
        cmd = "sleep 2 && echo hello"
        out = cmdmod.run(cmd, timeout=1, python_shell=True)

    assert "Timed out" in out


def test_timeout_success(cmdmod):
    """
    cmd.run sufficient timeout to succeed
    """
    if sys.platform == "win32":
        cmd = 'Start-Sleep 1; Write-Host "hello"'
        out = cmdmod.run(cmd, timeout=5, python_shell=True, shell="powershell")
    else:
        if not salt.utils.path.which("sleep"):
            pytest.skip("sleep cmd not installed")
        cmd = "sleep 1 && echo hello"
        out = cmdmod.run(cmd, timeout=2, python_shell=True)

    assert out == "hello"


@pytest.mark.slow_test
def test_cmd_run_whoami(cmdmod, running_username):
    """
    test return of whoami
    """
    if not salt.utils.platform.is_windows():
        user = running_username
    else:
        user = salt.utils.user.get_specific_user()
    if user.startswith("sudo_"):
        user = user.replace("sudo_", "")
    cmd = cmdmod.run("whoami")
    assert user.lower() == cmd.lower()


@pytest.mark.slow_test
@pytest.mark.skip_unless_on_windows(reason="Minion is not Windows")
def test_windows_env_handling(cmdmod):
    """
    Ensure that nt.environ is used properly with cmd.run*
    """
    out = cmdmod.run("cmd /c set", env={"abc": "123", "ABC": "456"}).splitlines()
    assert "abc=123" in out
    assert "ABC=456" in out


@pytest.mark.slow_test
@pytest.mark.skip_unless_on_windows(reason="Minion is not Windows")
def test_windows_powershell_script_args(cmdmod, issue_56195_test_ps1):
    """
    Ensure that powershell processes inline script in args
    """
    val = "i like cheese"
    args = (
        '-SecureString (ConvertTo-SecureString -String "{}" -AsPlainText -Force)'
        " -ErrorAction Stop".format(val)
    )
    script = "salt://issue_56195_test.ps1"
    ret = cmdmod.script(script, args=args, shell="powershell", saltenv="base")
    assert ret["stdout"] == val


@pytest.mark.slow_test
@pytest.mark.skip_unless_on_windows(reason="Minion is not Windows")
@pytest.mark.skip_if_binaries_missing("pwsh")
def test_windows_powershell_script_args_pwsh(cmdmod, issue_56195_test_ps1):
    """
    Ensure that powershell processes inline script in args with powershell
    core
    """
    val = "i like cheese"
    args = (
        '-SecureString (ConvertTo-SecureString -String "{}" -AsPlainText -Force)'
        " -ErrorAction Stop".format(val)
    )
    script = "salt://issue_56195_test.ps1"
    ret = cmdmod.script(script, args=args, shell="pwsh", saltenv="base")
    assert ret["stdout"] == val
