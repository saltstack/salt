import os
import shlex
import stat
import time
from textwrap import dedent

import pytest

import salt.utils.platform

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.windows_whitelisted,
]


def _cmd_path_for_run(path):
    """
    Local path for :func:`cmd.run` after POSIX ``shlex`` split: quote so one token.
    On Windows, use the raw path — :func:`prepend_cmd` with
    ``msvc_quote_bare_path_string`` already applies ``list2cmdline`` for
    ``runas``; extra ``"..."`` here would double-wrap and break execution.
    """
    s = str(path)
    if salt.utils.platform.is_windows():
        return s
    return shlex.quote(s)


@pytest.fixture(scope="module")
def account():
    with pytest.helpers.create_account() as _account:
        yield _account


@pytest.fixture
def echo_script_contents():
    if salt.utils.platform.is_windows():
        contents = dedent(
            """\
            @echo off
            set a=%~1
            set b=%~2
            echo a: %a%, b: %b%
            """
        )
    else:
        contents = dedent(
            """\
            #!/bin/bash
            a="$1"
            b="$2"
            echo "a: $a, b: $b"
            """
        )
    return contents


@pytest.fixture
def echo_script(state_tree, echo_script_contents):
    if salt.utils.platform.is_windows():
        file_name = "echo_script.bat"
    else:
        file_name = "echo_script.sh"
    with pytest.helpers.temp_file(file_name, echo_script_contents, state_tree):
        yield file_name


@pytest.fixture
def echo_script_with_space(state_tree, echo_script_contents):
    if salt.utils.platform.is_windows():
        file_name = "echo script space.bat"
    else:
        file_name = "echo script space.sh"
    with pytest.helpers.temp_file(file_name, echo_script_contents, state_tree):
        yield file_name


@pytest.fixture
def pipe_script_contents():
    if salt.utils.platform.is_windows():
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
    return contents


@pytest.fixture
def pipe_script(pipe_script_contents, state_tree):
    if salt.utils.platform.is_windows():
        file_name = "pipe_script.bat"
    else:
        file_name = "pipe_script.sh"
    with pytest.helpers.temp_file(file_name, pipe_script_contents, state_tree) as f:
        if not salt.utils.platform.is_windows():
            current_perms = f.stat().st_mode
            new_perms = current_perms | stat.S_IXUSR
            f.chmod(new_perms)
            f.chmod(0o755)
        yield f


@pytest.fixture
def pipe_script_with_space(pipe_script_contents, state_tree):
    if salt.utils.platform.is_windows():
        file_name = "pipe script space.bat"
    else:
        file_name = "pipe script space.sh"
    with pytest.helpers.temp_file(file_name, pipe_script_contents, state_tree) as f:
        if not salt.utils.platform.is_windows():
            current_perms = f.stat().st_mode
            new_perms = current_perms | stat.S_IXUSR
            f.chmod(new_perms)
            f.chmod(0o755)
        yield f


@pytest.fixture
def pipe_script_with_space_runas(pipe_script_contents, state_tree_for_runas):
    if salt.utils.platform.is_windows():
        file_name = "pipe script space.bat"
    else:
        file_name = "pipe script space.sh"
    with pytest.helpers.temp_file(
        file_name, pipe_script_contents, state_tree_for_runas
    ) as f:
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
def test_script_args(modules, echo_script, args, expected):
    """
    Test argument processing with a batch script
    """
    script = f"salt://{echo_script}"
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
def test_script_args_with_space(modules, echo_script_with_space, args, expected):
    """
    Test argument processing with a batch script
    """
    script = f"salt://{echo_script_with_space}"
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
def test_script_args_runas(modules, account, echo_script, args, expected):
    """
    Test argument processing with a batch/bash script and runas
    """
    script = f"salt://{echo_script}"
    result = modules.cmd.script(
        script,
        args=args,
        runas=account.username,
        password=account.password,
    )
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
def test_script_args_runas_with_space(
    modules, account, echo_script_with_space, args, expected
):
    """
    Test argument processing with a batch/bash script and runas
    """
    script = f"salt://{echo_script_with_space}"
    result = modules.cmd.script(
        script,
        args=args,
        runas=account.username,
        password=account.password,
    )
    assert result["stdout"] == expected


def test_run_pipe_python_shell_true(modules, pipe_script):
    if salt.utils.platform.is_windows():
        cmd = f'{str(pipe_script)} | find /c /v ""'
    else:
        cmd = f"{str(pipe_script)} | wc -l"
    result = modules.cmd.run(cmd, python_shell=True)
    assert result == "1"


def test_run_pipe_python_shell_false(modules, pipe_script):
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


def test_run_pipe_default(modules, pipe_script):
    if salt.utils.platform.is_windows():
        cmd = f'{str(pipe_script)} | find /c /v ""'
    else:
        cmd = f"{str(pipe_script)} | wc -l"
    # We need to mock running from the CLI by passing __pub_jid
    # Normally this is populated when run from the CLI, but when run from the
    # test suite, the value is empty
    result = modules.cmd.run(cmd, __pub_jid="test")
    assert result == "1"


def test_run_pipe_shell(modules, pipe_script):
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


def test_run_spaces(modules, pipe_script_with_space):
    cmd = _cmd_path_for_run(pipe_script_with_space)
    result = modules.cmd.run(cmd)
    assert result == "fine"


def test_run_spaces_runas(modules, pipe_script_with_space_runas, account):
    cmd = _cmd_path_for_run(pipe_script_with_space_runas)
    result = modules.cmd.run(
        cmd,
        runas=account.username,
        password=account.password,
    )
    assert result == "fine"


@pytest.mark.skip_unless_on_windows
def test_script_pipe_spaces(modules, pipe_script_with_space):
    # ``cmd.script`` treats ``source`` as a path (splitext, cache_file) — not a
    # shell line, so do not use shell-style quoting.
    cmd = f"{str(pipe_script_with_space)}"
    if salt.utils.platform.is_windows():
        args = '| find /c /v ""'
    else:
        args = "| wc -l"
    result = modules.cmd.script(cmd, args=args)
    assert result["stdout"] == "1"


@pytest.mark.skip_unless_on_windows
def test_script_pipe_spaces_runas(modules, pipe_script_with_space_runas, account):
    cmd = f"{str(pipe_script_with_space_runas)}"
    if salt.utils.platform.is_windows():
        args = '| find /c /v ""'
    else:
        args = "| wc -l"
    result = modules.cmd.script(
        cmd,
        args=args,
        runas=account.username,
        password=account.password,
    )
    assert result["stdout"] == "1"


@pytest.fixture
def bg_marker_script(state_tree, tmp_path):
    """
    Script that writes a marker file (and its own path) for bg=True tests.
    """
    marker = tmp_path / "bg_marker.txt"
    if salt.utils.platform.is_windows():
        file_name = "bg_marker.bat"
        # %~f0 is the full path to this bat file
        contents = dedent(
            f"""\
            @echo off
            echo bg-ok^|%~f0>"{marker}"
            """
        )
    else:
        file_name = "bg_marker.sh"
        contents = dedent(
            f"""\
            #!/bin/sh
            printf 'bg-ok|%s\\n' "$0" > "{marker}"
            """
        )
    with pytest.helpers.temp_file(file_name, contents, state_tree) as script_path:
        if not salt.utils.platform.is_windows():
            script_path.chmod(0o755)
        yield file_name, marker


def _wait_for_marker(marker_path, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if marker_path.is_file() and marker_path.stat().st_size > 0:
            return marker_path.read_text(encoding="utf-8").strip()
        time.sleep(0.1)
    raise AssertionError(f"Marker file not written within {timeout}s: {marker_path}")


def _wait_until_gone(path, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not os.path.exists(path):
            return
        time.sleep(0.1)
    raise AssertionError(f"Temp path still present after {timeout}s: {path}")


def test_script_bg_writes_marker_and_cleans_temp(modules, bg_marker_script):
    """
    Regression for #69959 / #50273: cmd.script with bg=True must leave the
    tempfile in place until the child runs, then clean it up.
    """
    file_name, marker = bg_marker_script
    ret = modules.cmd.script(f"salt://{file_name}", bg=True)
    assert isinstance(ret["pid"], int)
    contents = _wait_for_marker(marker)
    payload, script_path = contents.split("|", 1)
    assert payload == "bg-ok"
    _wait_until_gone(script_path)
