import pathlib
import shutil

import pytest


@pytest.fixture
def salt_spm_cli(salt_master_factory):
    """
    The ``spm`` CLI as a fixture against the configured master
    """
    _spm_cli = salt_master_factory.salt_spm_cli()
    try:
        yield _spm_cli
    finally:
        for key in (
            "formula_path",
            "spm_build_dir",
            "spm_cache_dir",
            "spm_db",
            "spm_repos_config",
            "spm_share_dir",
        ):
            path = pathlib.Path(_spm_cli.config[key])
            if not path.exists():
                continue
            elif path.is_file():
                path.unlink()
            else:
                shutil.rmtree(str(path), ignore_errors=True)


@pytest.fixture
def spm_formulas_dir(salt_master_factory):
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
def spm_file_path(salt_spm_cli):
    return pathlib.Path(salt_spm_cli.config["spm_build_dir"]) / "apache-201506-2.spm"


@pytest.fixture
def spm_file(salt_spm_cli, spm_file_path, spm_formulas_dir):
    ret = salt_spm_cli.run(
        "build",
        str(spm_formulas_dir),
    )
    assert ret.returncode == 0
    return spm_file_path


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
