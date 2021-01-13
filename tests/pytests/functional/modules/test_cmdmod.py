import os
import pathlib
import stat
import sys

import pytest
import salt.config
import salt.utils.path
import salt.utils.platform
import salt.utils.user
from salt.exceptions import CommandExecutionError
from saltfactories.utils import running_username
from tests.support.helpers import dedent

AVAILABLE_PYTHON_EXECUTABLE = salt.utils.path.which_bin(
    [
        "python",
        "python3",
        "python3.5",
        "python3.6",
        "python3.7",
        "python3.8",
        "pytohn3.9",
    ]
)

pytestmark = [
    pytest.mark.windows_whitelisted,
]


class Command:

    __slots__ = ("args", "kwargs")

    def __init__(self, args, **kwargs):
        self.args = args
        self.kwargs = dict(kwargs)

    def __repr__(self):
        ret = "{}(".format(self.__class__.__name__)
        if isinstance(self.args, list):
            ret += ", ".join(repr(arg) for arg in self.args)
        else:
            ret += self.args
        if self.kwargs:
            ret += ", "
            ret += ", ".join(
                "{}={!r}".format(key, value) for key, value in self.kwargs.items()
            )
        ret += ")"
        return ret


@pytest.fixture(scope="module")
def minion_opts(minion_opts):
    minion_opts["cmd_blacklist_glob"] = ["bad_command *", "second_bad_command *"]
    return minion_opts


@pytest.fixture(scope="module")
def cmdmod(modules):
    return modules.cmd


@pytest.mark.skip_if_binaries_missing("grep", "ls", "awk", "sed")
def test_run(cmdmod, subtests, minion_opts):
    """
    cmd.run
    """
    shell = os.environ.get("SHELL")
    if shell is None:
        # Failed to get the SHELL var, don't run
        pytest.skip("Unable to get the SHELL environment variable")

    cmd = Command("echo $SHELL")
    with subtests.test(cmd=cmd):
        ret = cmdmod.run(cmd.args, **cmd.kwargs)
        assert ret == "$SHELL"

    cmd = Command("echo $SHELL", shell=shell, python_shell=True)
    with subtests.test(cmd=cmd):
        ret = cmdmod.run(cmd.args, **cmd.kwargs).rstrip()
        assert ret == shell

    cmd = Command("ls / | grep etc", python_shell=True)
    with subtests.test(cmd=cmd):
        ret = cmdmod.run(cmd.args, **cmd.kwargs)
        assert ret == "etc"

    cmd = Command(
        'echo {{grains.id}} | awk "{print $1}"', template="jinja", python_shell=True
    )
    with subtests.test(cmd=cmd):
        ret = cmdmod.run(cmd.args, **cmd.kwargs)
        assert ret == minion_opts["id"]

    cmd = Command(
        "{} f".format(salt.utils.path.which("grep")),
        stdin="one\ntwo\nthree\nfour\nfive\n",
        python_shell=True,
    )
    with subtests.test(cmd=cmd):
        ret = cmdmod.run(cmd.args, **cmd.kwargs)
        assert ret == "four\nfive"

    cmd = Command('echo "a=b" | sed -e s/=/:/g', python_shell=True)
    with subtests.test(cmd=cmd):
        ret = cmdmod.run(cmd.args, **cmd.kwargs)
        assert ret == "a:b"


def test_stdout(cmdmod):
    """
    cmd.run_stdout
    """
    ret = cmdmod.run_stdout('echo "cheese"')
    assert ret == "cheese" if not salt.utils.platform.is_windows() else '"cheese"'


def test_stderr(cmdmod):
    """
    cmd.run_stderr
    """
    if sys.platform.startswith(("freebsd", "openbsd")):
        shell = "/bin/sh"
    else:
        shell = "/bin/bash"

    ret = cmdmod.run_stderr('echo "cheese" 1>&2', shell=shell, python_shell=True)
    assert ret == "cheese" if not salt.utils.platform.is_windows() else '"cheese"'


def test_run_all(cmdmod):
    """
    cmd.run_all
    """
    if sys.platform.startswith(("freebsd", "openbsd")):
        shell = "/bin/sh"
    else:
        shell = "/bin/bash"

    ret = cmdmod.run_all('echo "cheese" 1>&2', shell=shell, python_shell=True)
    assert "pid" in ret
    assert "retcode" in ret
    assert "stdout" in ret
    assert "stderr" in ret
    assert isinstance(ret.get("pid"), int) is True
    assert isinstance(ret.get("retcode"), int) is True
    assert isinstance(ret.get("stdout"), str) is True
    assert isinstance(ret.get("stderr"), str) is True
    assert (
        ret.get("stderr") == "cheese"
        if not salt.utils.platform.is_windows()
        else '"cheese"'
    )


def test_retcode(cmdmod, subtests):
    """
    cmd.retcode
    """
    cmd = Command("exit 0")
    with subtests.test(cmd=cmd):
        ret = cmdmod.retcode(cmd.args, python_shell=True)
        assert ret == 0

    cmd = Command("exit 1")
    with subtests.test(cmd=cmd):
        ret = cmdmod.retcode(cmd.args, python_shell=True)
        assert ret == 1


def test_run_all_with_success_retcodes(cmdmod):
    """
    cmd.run with success_retcodes
    """
    ret = cmdmod.run_all("exit 42", success_retcodes=[42], python_shell=True)
    assert "retcode" in ret
    assert ret["retcode"] == 0


def test_retcode_with_success_retcodes(cmdmod):
    """
    cmd.run with success_retcodes
    """
    ret = cmdmod.retcode("exit 42", success_retcodes=[42], python_shell=True)
    assert ret == 0


def test_blacklist_glob(cmdmod):
    """
    cmd_blacklist_glob
    """
    with pytest.raises(CommandExecutionError) as exc:
        cmdmod.run(
            "bad_command --foo",
            # To make salt believe this is a call coming from the master or the CLI we need the following kwarg set
            __pub_jid=1,
        )
    assert 'The shell command "bad_command --foo" is not permitted' in str(exc.value)


@pytest.fixture(scope="module")
def script(state_tree):
    script_contents = """
    #!/usr/bin/env python

    from __future__ import absolute_import

    import sys

    print(" ".join(sys.argv[1:]))
    """
    with pytest.helpers.temp_file(
        "script.py", script_contents, state_tree
    ) as script_path:
        os.chmod(str(script_path), script_path.stat().st_mode | stat.S_IEXEC)
        yield script_path


def test_script(cmdmod, script):
    """
    cmd.script
    """
    args = "saltines crackers biscuits=yes"
    ret = cmdmod.script("salt://{}".format(script.name), args)
    assert ret["stdout"] == args


def test_script_retcode(cmdmod, script):
    """
    cmd.script_retcode
    """
    ret = cmdmod.script_retcode("salt://{}".format(script.name))
    assert ret == 0


def test_script_cwd(cmdmod, script, tmp_path):
    """
    cmd.script with cwd
    """
    tmp_cwd = tmp_path / "cwd"
    tmp_cwd.mkdir()
    args = "saltines crackers biscuits=yes"
    ret = cmdmod.script("salt://{}".format(script.name), args, cwd=str(tmp_cwd))
    assert ret["stdout"] == args


def test_script_cwd_with_space(cmdmod, script, tmp_path):
    """
    cmd.script with cwd
    """
    tmp_cwd = tmp_path / "cwd with spaces"
    tmp_cwd.mkdir()
    args = "saltines crackers biscuits=yes"
    ret = cmdmod.script("salt://{}".format(script.name), args, cwd=str(tmp_cwd))
    assert ret["stdout"] == args


@pytest.mark.parametrize("tty_name", ["tty0", "pts3"])
def test_tty(cmdmod, tty_name):
    """
    cmd.tty
    """
    tty = os.path.join("/dev", tty_name)
    if not os.path.exists(tty):
        pytest.skip("{} does not exist".format(tty))
    ret = cmdmod.tty(tty_name, "apply salt liberally")
    assert "Success" in ret


@pytest.mark.skip_if_binaries_missing("which")
def test_which(cmdmod):
    """
    cmd.which
    """
    cmd_which = cmdmod.which("cat")
    assert isinstance(cmd_which, str)
    cmd_run = cmdmod.run("which cat")
    assert isinstance(cmd_run, str)
    assert cmd_which.strip() == cmd_run.strip()


@pytest.mark.skip_if_binaries_missing("which")
def test_which_bin(cmdmod):
    """
    cmd.which_bin
    """
    cmds = ["pip3", "pip2", "pip", "pip-python"]
    ret = cmdmod.which_bin(cmds)
    assert ret
    assert pathlib.Path(ret).name in cmds


def test_has_exec(cmdmod):
    """
    cmd.has_exec
    """
    assert cmdmod.has_exec(AVAILABLE_PYTHON_EXECUTABLE) is True


def test_has_exec_unknown_binary(cmdmod):
    """
    cmd.has_exec
    """
    assert cmdmod.has_exec("alllfsdfnwieulrrh9123857ygf") is False


def test_exec_code(cmdmod):
    """
    cmd.exec_code
    """
    code = dedent(
        """
        import sys
        sys.stdout.write('cheese')
        """
    )
    ret = cmdmod.exec_code(AVAILABLE_PYTHON_EXECUTABLE, code)
    assert ret.strip() == "cheese"


def test_exec_code_with_single_arg(cmdmod):
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
    ret = cmdmod.exec_code(AVAILABLE_PYTHON_EXECUTABLE, code, args=arg)
    assert ret.strip() == arg


def test_exec_code_with_multiple_args(cmdmod):
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
    ret = cmdmod.exec_code(AVAILABLE_PYTHON_EXECUTABLE, code, args=[arg, "test"])
    assert ret.strip() == arg


@pytest.mark.skip_if_binaries_missing("sleep")
def test_timeout(cmdmod):
    """
    cmd.run trigger timeout
    """
    ret = cmdmod.run("sleep 2 && echo hello", timeout=1, python_shell=True)
    assert "Timed out" in ret


@pytest.mark.skip_if_binaries_missing("sleep")
def test_timeout_success(cmdmod):
    """
    cmd.run sufficient timeout to succeed
    """
    ret = cmdmod.run("sleep 1 && echo hello", timeout=2, python_shell=True)
    assert ret == "hello"


def test_quotes(cmdmod):
    """
    cmd.run with quoted command
    """
    cmd = """echo 'SELECT * FROM foo WHERE bar="baz"' """
    expected_result = 'SELECT * FROM foo WHERE bar="baz"'
    if salt.utils.platform.is_windows():
        expected_result = "'SELECT * FROM foo WHERE bar=\"baz\"'"
    ret = cmdmod.run_stdout(cmd).strip()
    assert ret == expected_result


@pytest.fixture(scope="module")
def runas():
    with pytest.helpers.create_account() as account:
        yield account


@pytest.mark.skip_if_not_root
@pytest.mark.skip_on_windows(reason="skip windows, requires password")
def test_quotes_runas(cmdmod, runas):
    """
    cmd.run with quoted command
    """
    cmd = """echo 'SELECT * FROM foo WHERE bar="baz"' """
    expected_result = 'SELECT * FROM foo WHERE bar="baz"'
    ret = cmdmod.run_all(cmd, runas=runas.username)
    assert ret["retcode"] == 0
    assert ret["stdout"] == expected_result


@pytest.mark.skip_if_not_root
@pytest.mark.skip_on_windows(reason="skip windows, uses unix commands")
def test_avoid_injecting_shell_code_as_root(cmdmod, runas):
    """
    cmd.run should execute the whole command as the "runas" user, not
    running substitutions as root.
    """
    cmd = "id -u"
    root_id = cmdmod.run_stdout(cmd, python_shell=True)
    runas_root_id = cmdmod.run_stdout(cmd, runas="root", python_shell=True)
    user_id = cmdmod.run_stdout(cmd, runas=runas.username, python_shell=True)
    assert user_id != root_id
    assert user_id != runas_root_id
    assert root_id == runas_root_id


@pytest.mark.skip_if_not_root
@pytest.mark.skip_on_windows(reason="skip windows, uses unix commands")
def test_cwd_runas(cmdmod, runas, tmp_path):
    """
    cmd.run should be able to change working directory correctly, whether
    or not runas is in use.
    """
    cmd = "pwd"
    tmp_cwd = tmp_path / "test-cwd"
    tmp_cwd.mkdir(mode=0o711)

    cwd_normal = cmdmod.run_stdout(cmd, cwd=str(tmp_cwd)).rstrip()
    cwd_runas = cmdmod.run_stdout(cmd, cwd=str(tmp_cwd), runas=runas.username).rstrip()

    assert str(tmp_cwd) == cwd_normal == cwd_runas


@pytest.mark.skip_if_not_root
@pytest.mark.skip_unless_on_darwin
def test_runas_env(cmdmod, runas):
    """
    cmd.run should be able to change working directory correctly, whether
    or not runas is in use.
    """
    user_path = cmdmod.run_stdout('printf %s "$PATH"', runas=runas.username)
    # XXX: Not sure of a better way. Environment starts out with
    # /bin:/usr/bin and should be populated by path helper and the bash
    # profile.
    assert user_path != "/bin:/usr/bin"


@pytest.mark.skip_if_not_root
@pytest.mark.skip_unless_on_darwin
def test_runas_complex_command_bad_cwd(cmdmod, runas, tmp_path):
    """
    cmd.run should not accidentally run parts of a complex command when
    given a cwd which cannot be used by the user the command is run as.

    Due to the need to use `su -l` to login to another user on MacOS, we
    cannot cd into directories that the target user themselves does not
    have execute permission for. To an extent, this test is testing that
    buggy behaviour, but its purpose is to ensure that the greater bug of
    running commands after failing to cd does not occur.
    """
    tmp_cwd = tmp_path / "test-cwd"
    tmp_cwd.mkdir(mode=0o700)

    ret = cmdmod.run_all(
        'pwd; pwd; : $(echo "You have failed the test" >&2)',
        cwd=str(tmp_cwd),
        runas=runas.username,
    )
    assert ret["stdout"] == ""
    assert "You have failed the test" not in ret["stderr"]
    assert ret["retcode"] != 0


@pytest.mark.skip_on_windows
@pytest.mark.skip_if_not_root
def test_runas(cmdmod, runas):
    """
    Ensure that the env is the runas user's
    """
    ret = cmdmod.run("env", runas=runas.username)
    assert "USER={}".format(runas.username) in ret


def test_hide_output(cmdmod, subtests):
    """
    Test the hide_output argument
    """
    ls_command = (
        ["ls", "/"] if not salt.utils.platform.is_windows() else ["dir", "c:\\"]
    )

    with subtests.test("cmd.run({}, hide_output=True)".format(ls_command)):
        # cmd.run
        out = cmdmod.run(ls_command, hide_output=True)
        assert out == ""

    with subtests.test("cmd.shell({}, hide_output=True)".format(ls_command)):
        # cmd.shell
        out = cmdmod.shell(ls_command, hide_output=True)
        assert out == ""

    with subtests.test("cmd.run_stdout({}, hide_output=True)".format(ls_command)):
        # cmd.run_stdout
        out = cmdmod.run_stdout(ls_command, hide_output=True)
        assert out == ""

    error_command = ["which", "---help"]
    with subtests.test(
        "cmd.run_stderr({}, hide_output=True, python_shell=True)".format(error_command)
    ):
        # cmd.run_stderr
        out = cmdmod.run_stderr(error_command, hide_output=True)
        assert out == ""

    with subtests.test("cmd.run_all({}, hide_output=True)".format(ls_command)):
        # cmd.run_all (command should have produced stdout)
        out = cmdmod.run_all(ls_command, hide_output=True)
        assert out["stdout"] == ""
        assert out["stderr"] == ""

    with subtests.test("cmd.run_all({}, hide_output=True)".format(error_command)):
        # cmd.run_all (command should have produced stderr)
        out = cmdmod.run_all(error_command, hide_output=True)
        assert out["retcode"] != 0
        assert out["stdout"] == ""
        assert out["stderr"] == ""


def test_cmd_run_whoami(cmdmod):
    """
    test return of whoami
    """
    ret = cmdmod.run("whoami")
    assert ret.lower() == running_username()


@pytest.mark.skip_unless_on_windows
def test_windows_env_handling(cmdmod):
    """
    Ensure that nt.environ is used properly with cmd.run*
    """
    env = {"abc": "123", "ABC": "456"}
    out = cmdmod.run("set", env=env)
    for key, value in env.items():
        assert "{}={}".format(key, value) in out


@pytest.mark.skip_unless_on_windows
def test_windows_cmd_powershell_list(cmdmod):
    """
    Ensure that cmd.run_all supports running shell='powershell' with cmd passed
    as a list
    """
    out = cmdmod.run_all(["echo", "salt"], python_shell=False, shell="powershell")
    assert out["stdout"] == "salt"


@pytest.mark.skip_unless_on_windows
def test_windows_cmd_powershell_string(cmdmod):
    """
    Ensure that cmd.run_all supports running shell='powershell' with cmd passed
    as a string
    """
    out = cmdmod.run_all("echo salt", python_shell=False, shell="powershell")
    assert out["stdout"] == "salt"


@pytest.mark.skip_unless_on_windows
def test_windows_powershell_script_args(cmdmod, state_tree):
    """
    Ensure that powershell processes inline script in args
    """
    script_contents = """
    [CmdLetBinding()]
    Param(
      [SecureString] $SecureString
    )

    $Credential = New-Object System.Net.NetworkCredential("DummyId", $SecureString)
    $Credential.Password
    """
    with pytest.helpers.temp_file(
        "issue-56195.ps1", script_contents, state_tree
    ) as script_path:
        val = "i like cheese"
        args = '-SecureString (ConvertTo-SecureString -String "{}" -AsPlainText -Force) -ErrorAction Stop'.format(
            val
        )
        script = "salt://{}".format(script_path.name)
        ret = cmdmod.script(script, args=args, shell="powershell")
        assert ret["stdout"] == val
