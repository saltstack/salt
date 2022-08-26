import pytest

from salt.defaults import exitcodes

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


def test_spm_help(salt_spm_cli):
    """
    test --help argument for spm
    """
    expected_cli_flags = ["--version", "--assume-yes", "--help"]
    ret = salt_spm_cli.run("--help")
    assert ret.returncode == 0
    for cli_flag in expected_cli_flags:
        assert cli_flag in ret.stdout


def test_spm_bad_arg(salt_spm_cli):
    """
    test correct output when bad argument passed
    """
    expected_cli_flags = ["--version", "--assume-yes", "--help"]
    ret = salt_spm_cli.run("does-not-exist")
    assert ret.returncode == exitcodes.EX_USAGE
    for cli_flag in expected_cli_flags:
        assert cli_flag in ret.stdout


def test_spm_assume_yes(salt_spm_cli, spm_file, installed_spm_formula_path):
    """
    test spm install with -y arg
    """
    ret = salt_spm_cli.run(
        "install",
        "-y",
        str(spm_file),
    )
    assert ret.returncode == 0
    assert installed_spm_formula_path.exists()
