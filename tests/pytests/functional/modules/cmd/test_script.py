import stat
from textwrap import dedent

import pytest

import salt.utils.platform

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def account():
    with pytest.helpers.create_account() as _account:
        yield _account


@pytest.fixture
def echo_script(state_tree):
    if salt.utils.platform.is_windows():
        file_name = "echo_script.bat"
        contents = dedent(
            """\
            @echo off
            set a=%~1
            set b=%~2
            echo a: %a%, b: %b%
            """
        )
    else:
        file_name = "echo_script.sh"
        contents = dedent(
            """\
            #!/bin/bash
            a="$1"
            b="$2"
            echo "a: $a, b: $b"
            """
        )
    with pytest.helpers.temp_file(file_name, contents, state_tree / "echo-script"):
        yield file_name


@pytest.fixture
def pipe_script(state_tree):
    if salt.utils.platform.is_windows():
        file_name = "pipe_script.bat"
        contents = dedent(
            """\
            @echo off
            IF "%1" == "|" (
                echo b0rken
            ) ELSE (
                echo fine
            )
            """
        )
    else:
        file_name = "pipe_script.sh"
        contents = dedent(
            """\
            #!/bin/bash
            if [ "$1" == '|' ]; then
                echo b0rken
            else
                echo fine
            fi
            """
        )
    with pytest.helpers.temp_file(file_name, contents, state_tree / "echo-script") as f:
        if not salt.utils.platform.is_windows():
            current_perms = f.stat().st_mode
            new_perms = current_perms | stat.S_IXUSR
            f.chmod(new_perms)
            f.chmod(0o755)
        yield f


@pytest.mark.parametrize(
    "args, expected",
    [
        ("foo bar", "a: foo, b: bar"),
        ('foo "bar bar"', "a: foo, b: bar bar"),
        (["foo", "bar"], "a: foo, b: bar"),
        (["foo foo", "bar bar"], "a: foo foo, b: bar bar"),
    ],
)
def test_echo(modules, echo_script, args, expected):
    """
    Test argument processing with a batch script
    """
    script = f"salt://echo-script/{echo_script}"
    result = modules.cmd.script(script, args=args)
    assert result["stdout"] == expected


@pytest.mark.parametrize(
    "args, expected",
    [
        ("foo bar", "a: foo, b: bar"),
        ('foo "bar bar"', "a: foo, b: bar bar"),
        (["foo", "bar"], "a: foo, b: bar"),
        (["foo foo", "bar bar"], "a: foo foo, b: bar bar"),
    ],
)
def test_echo_runas(modules, account, echo_script, args, expected):
    """
    Test argument processing with a batch/bash script and runas
    """
    script = f"salt://echo-script/{echo_script}"
    result = modules.cmd.script(
        script,
        args=args,
        runas=account.username,
        password=account.password,
    )
    assert result["stdout"] == expected


def test_pipe_run_python_shell_true(modules, pipe_script):
    if salt.utils.platform.is_windows():
        cmd = f'{str(pipe_script)} | find /c /v ""'
    else:
        cmd = f"{str(pipe_script)} | wc -l"
    result = modules.cmd.run(cmd, python_shell=True)
    assert result == "1"


def test_pipe_run_python_shell_false(modules, pipe_script):
    if salt.utils.platform.is_windows():
        cmd = f'{str(pipe_script)} | find /c /v ""'
        # Behavior is different on Windows, I think it has to do with how cmd
        # deals with args vs bash... or maybe how args are passed on Windows
        expected = "1"
    else:
        cmd = f"{str(pipe_script)} | wc -l"
        expected = "b0rken"
    result = modules.cmd.run(cmd, python_shell=False)
    assert result == expected


def test_pipe_run_default(modules, pipe_script):
    if salt.utils.platform.is_windows():
        cmd = f'{str(pipe_script)} | find /c /v ""'
    else:
        cmd = f"{str(pipe_script)} | wc -l"
    # We need to mock running from the CLI by passing __pub_jid
    # Normally this is populated when run from the CLI, but when run from the
    # test suite, the value is empty
    result = modules.cmd.run(cmd, __pub_jid="test")
    assert result == "1"


def test_pipe_run_shell(modules, pipe_script):
    if salt.utils.platform.is_windows():
        cmd = f'{str(pipe_script)} | find /c /v ""'
        shell = "cmd"
    else:
        cmd = f"{str(pipe_script)} | wc -l"
        shell = "/bin/bash"
    # We need to mock running from the CLI by passing __pub_jid
    # Normally this is populated when run from the CLI, but when run from the
    # test suite, the value is empty
    result = modules.cmd.run(cmd, shell=shell, __pub_jid="test")
    assert result == "1"
