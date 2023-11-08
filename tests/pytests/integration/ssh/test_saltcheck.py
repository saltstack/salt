import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


def test_saltcheck_run_test(salt_ssh_cli):
    """
    test saltcheck.run_test with salt-ssh
    """
    saltcheck_test = {
        "module_and_function": "test.echo",
        "assertion": "assertEqual",
        "expected-return": "Test Works",
        "args": ["Test Works"],
    }
    ret = salt_ssh_cli.run("saltcheck.run_test", test=saltcheck_test)
    assert ret.returncode == 0
    assert ret.data
    assert "status" in ret.data
    assert ret.data["status"] == "Pass"


@pytest.mark.skip_on_aarch64
def test_saltcheck_state(salt_ssh_cli):
    """
    saltcheck.run_state_tests
    """
    ret = salt_ssh_cli.run("saltcheck.run_state_tests", "validate-saltcheck")
    assert ret.returncode == 0
    assert ret.data
    assert ret.data[0]
    assert "validate-saltcheck" in ret.data[0]
    state_result = ret.data[0]["validate-saltcheck"]
    assert "echo_test_hello" in state_result
    assert "status" in state_result["echo_test_hello"]
    assert state_result["echo_test_hello"]["status"] == "Pass"
