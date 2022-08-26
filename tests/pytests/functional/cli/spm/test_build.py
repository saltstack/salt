"""
Tests for the spm build utility
"""
import shutil

import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


def test_spm_force(salt_spm_cli, installed_spm_file_path, installed_spm_formula_path):
    """
    test spm install with -f arg
    """
    assert installed_spm_formula_path.exists()
    # check if it forces the install after its already been installed it
    ret = salt_spm_cli.run("install", "-y", "-f", str(installed_spm_file_path))
    assert ret.returncode == 0
    assert "... installing apache" in ret.stdout


@pytest.fixture
def big_spm_file(salt_spm_cli, spm_formulas_dir, loaders, spm_file_path, shell):
    fallocate = shutil.which("fallocate")
    if fallocate is None:
        pytest.skip("The 'fallocate' binary was not found installed.")

    # check to make sure there is enough space to run this test
    ret = loaders.modules.status.diskusage("/tmp")
    space = ret["/tmp"]["available"]
    if space < 3000000000:
        pytest.skip("Not enough space on host to run this test")

    ret = shell.run(
        fallocate, "-l", "1G", str(spm_formulas_dir / "apache" / "bigfile.txt")
    )
    assert ret.returncode == 0
    ret = salt_spm_cli.run(
        "build",
        str(spm_formulas_dir),
    )
    assert ret.returncode == 0
    return spm_file_path


@pytest.mark.skip_if_binaries_missing("fallocate")
def test_spm_build_big_file(salt_spm_cli, big_spm_file):
    """
    test spm build with a big file
    """
    ret = salt_spm_cli.run(
        "install",
        "-y",
        str(big_spm_file),
    )
    assert ret.returncode == 0

    ret = salt_spm_cli.run("files", "apache")
    assert ret.returncode == 0
    assert "apache.sls" in ret.stdout
    assert "bigfile.txt" in ret.stdout


@pytest.fixture
def exclude_spm_files(spm_formulas_dir):
    paths = []
    exlude_dir = spm_formulas_dir / "apache" / ".git"
    exlude_dir.mkdir(exist_ok=True, parents=True)
    for n in range(3):
        path = exlude_dir / "exclude-{}.txt".format(n)
        path.touch()
        paths.append(path)

    return paths


@pytest.fixture
def excludes_spm_file(
    salt_spm_cli, spm_formulas_dir, loaders, spm_file_path, exclude_spm_files
):
    spm_excludes_config = """
    spm_build_exclude:
      - "apache/.git"
    """
    with pytest.helpers.temp_file(
        "spm.d/excludes.conf", spm_excludes_config, salt_spm_cli.config_dir
    ):
        ret = salt_spm_cli.run(
            "build",
            str(spm_formulas_dir),
        )
        assert ret.returncode == 0
        yield spm_file_path


def test_spm_build_exclude(
    salt_spm_cli, spm_formulas_dir, excludes_spm_file, exclude_spm_files
):
    """
    test spm build while excluding directory
    """
    ret = salt_spm_cli.run(
        "install",
        "-y",
        str(excludes_spm_file),
    )
    assert ret.returncode == 0

    ret = salt_spm_cli.run("files", "apache")
    assert ret.returncode == 0
    for path in exclude_spm_files:
        assert path.name not in ret.stdout
