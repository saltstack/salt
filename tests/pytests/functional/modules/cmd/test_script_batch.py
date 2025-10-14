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


@pytest.fixture
def echo_script(state_tree):
    contents = """@echo off
set a=%~1
set b=%~2
shift
shift
echo a: %a%, b: %b%
"""
    with pytest.helpers.temp_file("test.bat", contents, state_tree / "echo-script"):
        yield


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
    script = "salt://echo-script/test.bat"
    result = modules.cmd.script(script, args=args, shell="cmd")
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
    Test argument processing with a batch script and runas
    """
    script = "salt://echo-script/test.bat"
    result = modules.cmd.script(
        script,
        args=args,
        shell="cmd",
        runas=account.username,
        password=account.password,
    )
    assert result["stdout"] == expected
