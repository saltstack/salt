import pytest

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture(scope="module")
def account():
    with pytest.helpers.create_account() as _account:
        yield _account


@pytest.mark.parametrize(
    "exit_code, return_code, result",
    [
        (300, 0, True),
        (299, 299, False),
    ],
)
def test_cmd_exitcode(modules, state_tree, exit_code, return_code, result):
    """
    Test receiving an exit code with cmd.run
    """
    ret = modules.state.single(
        "cmd.run",
        name=f"exit {exit_code}",
        shell="cmd",
        success_retcodes=[2, 44, 300],
    )
    assert ret.result is result
    assert ret.filtered["changes"]["retcode"] == return_code


@pytest.mark.parametrize(
    "exit_code, return_code, result",
    [
        (300, 0, True),
        (299, 299, False),
    ],
)
def test_cmd_exitcode_runas(
    modules, state_tree, exit_code, return_code, result, account
):
    ret = modules.state.single(
        "cmd.run",
        name=f"exit {exit_code}",
        shell="cmd",
        success_retcodes=[2, 44, 300],
        runas=account.username,
        password=account.password,
    )
    assert ret.result is result
    assert ret.filtered["changes"]["retcode"] == return_code


@pytest.mark.parametrize(
    "command, expected",
    [
        ("echo foo", "foo"),
        ("cmd /c echo foo", "foo"),
        ("whoami && echo foo", "foo"),
        ("echo \"foo 'bar'\"", "\"foo 'bar'\""),
        ('echo|set /p="foo" & echo|set /p="bar"', "foobar"),
        ('''echo "&<>[]|{}^=;!'+,`~ "''', '''"&<>[]|{}^=;!'+,`~ "'''),
    ],
)
def test_cmd_builtins(modules, command, expected):
    """
    Test builtin cmd.exe commands
    """
    result = modules.cmd.run(command, shell="cmd")
    assert expected in result


@pytest.mark.parametrize(
    "command, expected",
    [
        ("echo foo", "foo"),
        ("cmd /c echo foo", "foo"),
        ("whoami && echo foo", "foo"),
        ("echo \"foo 'bar'\"", "\"foo 'bar'\""),
        ('echo|set /p="foo" & echo|set /p="bar"', "foobar"),
        ('''echo "&<>[]|{}^=;!'+,`~ "''', '''"&<>[]|{}^=;!'+,`~ "'''),
    ],
)
def test_cmd_builtins_runas(modules, account, command, expected):
    """
    Test builtin cmd.exe commands with runas
    """
    result = modules.cmd.run(
        cmd=command, shell="cmd", runas=account.username, password=account.password
    )
    assert expected in result


@pytest.mark.parametrize(
    "command, expected",
    [
        (["whoami.exe", "/?"], 0),
        (["whoami.exe", "/foo"], 1),
        ("whoami.exe /?", 0),
        ("whoami.exe /foo", 1),
    ],
)
def test_binary(modules, command, expected):
    """
    Test running a binary with cmd.run_all
    """
    result = modules.cmd.run_all(cmd=command)
    assert isinstance(result["pid"], int)
    assert result["retcode"] == expected


@pytest.mark.parametrize(
    "command, expected",
    [
        (["whoami.exe", "/?"], 0),
        (["whoami.exe", "/foo"], 1),
        ("whoami.exe /?", 0),
        ("whoami.exe /foo", 1),
    ],
)
def test_binary_runas(modules, account, command, expected):
    """
    Test running a binary with cmd.run_all and runas
    """
    result = modules.cmd.run_all(
        cmd=command, runas=account.username, password=account.password
    )
    assert isinstance(result["pid"], int)
    assert result["retcode"] == expected


@pytest.mark.parametrize(
    "command, env, expected",
    [
        ("echo %a%%b%", {"a": "foo", "b": "bar"}, "foobar"),
    ],
)
def test_cmd_env(modules, command, env, expected):
    """
    Test cmd.run with environment variables
    """
    result = modules.cmd.run_all(command, shell="cmd", env=env)
    assert isinstance(result["pid"], int)
    assert result["retcode"] == 0
    assert result["stdout"] == expected
    assert result["stderr"] == ""


@pytest.mark.parametrize(
    "command, expected, redirect_stderr",
    [
        (["whoami.exe", "/foo"], "/foo", True),
        (["whoami.exe", "/foo"], "/foo", False),
    ],
)
def test_redirect_stderr(modules, command, expected, redirect_stderr):
    """
    Test redirection of stderr to stdout by running cmd.run_all with invalid commands
    """
    result = modules.cmd.run_all(command, redirect_stderr=redirect_stderr)
    assert isinstance(result["pid"], int)
    assert result["retcode"] == 1
    if redirect_stderr:
        assert expected in result["stdout"]
        assert result["stderr"] == ""
    else:
        assert result["stdout"] == ""
        assert expected in result["stderr"]
