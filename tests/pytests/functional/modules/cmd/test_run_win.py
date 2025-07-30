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
def test_script_exitcode(modules, state_tree, exit_code, return_code, result):
    ret = modules.state.single(
        "cmd.run", name=f"cmd.exe /c exit {exit_code}", success_retcodes=[2, 44, 300]
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
def test_script_exitcode_runas(
    modules, state_tree, exit_code, return_code, result, account
):
    ret = modules.state.single(
        "cmd.run",
        name=f"cmd.exe /c exit {exit_code}",
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
        ("cmd /c whoami && echo foo", "foo"),
    ],
)
def test_run_builtins(modules, command, expected):
    result = modules.cmd.run(command)
    assert expected in result


@pytest.mark.parametrize(
    "command, expected",
    [
        ("echo foo", "foo"),
        ("cmd /c echo foo", "foo"),
        ("whoami && echo foo", "foo"),
        ("cmd /c whoami && echo foo", "foo"),
    ],
)
def test_run_builtins_runas(modules, account, command, expected):
    result = modules.cmd.run(
        cmd=command, runas=account.username, password=account.password
    )
    assert expected in result
