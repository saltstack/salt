import pytest

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def account():
    with pytest.helpers.create_account() as _account:
        yield _account


@pytest.mark.skip_unless_on_windows(reason="Minion is not Windows")
@pytest.mark.parametrize(
    "exit_code, return_code, result",
    [
        (300, 0, True),
        (299, 299, False),
    ],
)
def test_windows_script_exitcode(modules, state_tree, exit_code, return_code, result):
    ret = modules.state.single(
        "cmd.run", name=f"cmd.exe /c exit {exit_code}", success_retcodes=[2, 44, 300]
    )
    assert ret.result is result
    assert ret.filtered["changes"]["retcode"] == return_code


@pytest.mark.skip_unless_on_windows(reason="Minion is not Windows")
@pytest.mark.parametrize(
    "exit_code, return_code, result",
    [
        (300, 0, True),
        (299, 299, False),
    ],
)
def test_windows_script_exitcode_runas(
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
