import pytest

pytestmark = [
    pytest.mark.skip_on_windows,
]


@pytest.fixture
def salt_systemd_setup(
    salt_call_cli,
    install_salt,
):
    """
    Fixture to set systemd for salt packages to enabled and active
    Note: assumes Salt packages already installed
    """
    install_salt.install()

    # ensure known state, enabled and active
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl enable {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

        test_cmd = f"systemctl restart {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0


@pytest.mark.parametrize("output_fmt", ["yaml", "json"])
def test_salt_output(salt_systemd_setup, salt_cli, salt_minion, output_fmt):
    """
    Test --output
    """
    # setup systemd to enabled and active for Salt packages
    # pylint: disable=pointless-statement
    salt_systemd_setup

    ret = salt_cli.run(
        f"--output={output_fmt}", "test.fib", "7", minion_tgt=salt_minion.id
    )
    if output_fmt == "json":
        assert 13 in ret.data
    else:
        ret.stdout.matcher.fnmatch_lines(["*- 13*"])
