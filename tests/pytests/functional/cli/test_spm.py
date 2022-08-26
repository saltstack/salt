import pathlib
import shutil

import pytest

from salt.defaults import exitcodes

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


@pytest.fixture
def _spm_clenaup(salt_spm_cli):
    try:
        yield
    finally:
        for key in (
            "spm_build_dir",
            "spm_cache_dir",
            "spm_db",
            "spm_repos_config",
            "spm_share_dir",
        ):
            path = pathlib.Path(salt_spm_cli.config[key])
            if not path.exists():
                continue
            elif path.is_file():
                path.unlink()
            else:
                shutil.rmtree(str(path), ignore_errors=True)


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


@pytest.fixture
def spm_formulas_dir(salt_master_factory, _spm_clenaup):
    formula_sls = """
    install-apache:
      pkg.installed:
        - name: apache2
    """
    formula = """
     name: apache
     os: RedHat, Debian, Ubuntu, Suse, FreeBSD
     os_family: RedHat, Debian, Suse, FreeBSD
     version: 201506
     release: 2
     summary: Formula for installing Apache
     description: Formula for installing Apache
    """
    with salt_master_factory.state_tree.base.temp_file(
        "formulas/apache/apache.sls", formula_sls
    ), salt_master_factory.state_tree.base.temp_file("formulas/FORMULA", formula):
        yield salt_master_factory.state_tree.base.write_path / "formulas"


@pytest.fixture
def installed_spm_formula_path(spm_formulas_dir, salt_spm_cli):
    return pathlib.Path(salt_spm_cli.config["formula_path"]) / "apache" / "apache.sls"


@pytest.fixture
def spm_file_path(salt_spm_cli, _spm_clenaup):
    return pathlib.Path(salt_spm_cli.config["spm_build_dir"]) / "apache-201506-2.spm"


@pytest.fixture
def spm_file(salt_spm_cli, spm_file_path, spm_formulas_dir):
    ret = salt_spm_cli.run(
        "build",
        str(spm_formulas_dir),
    )
    assert ret.returncode == 0
    return spm_file_path


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


@pytest.fixture
def installed_spm_file_path(salt_spm_cli, spm_file, installed_spm_formula_path):
    ret = salt_spm_cli.run(
        "install",
        "-y",
        str(spm_file),
    )
    assert ret.returncode == 0
    assert installed_spm_formula_path.exists()
    return spm_file


def test_spm_force(salt_spm_cli, installed_spm_file_path, installed_spm_formula_path):
    """
    test spm install with -f arg
    """
    assert installed_spm_formula_path.exists()
    # check if it forces the install after its already been installed it
    ret = salt_spm_cli.run("install", "-y", "-f", str(installed_spm_file_path))
    assert ret.returncode == 0
    assert "... installing apache" in ret.stdout
