import os
import pathlib
import re
import shutil
import sys
from contextlib import contextmanager

import pytest

import salt.utils.platform
from salt.exceptions import CommandNotFoundError
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES
from tests.support.helpers import VirtualEnv, patched_environ

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.requires_network,
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_if_binaries_missing(*KNOWN_BINARY_NAMES, check_all=False),
]


@pytest.fixture
def venv(tmp_path):
    with VirtualEnv(venv_dir=tmp_path / "the-venv") as venv:
        yield venv


@pytest.fixture
def pip(modules):
    with patched_environ(
        PIP_SOURCE_DIR="",
        PIP_BUILD_DIR="",
        __cleanup__=[k for k in os.environ if k.startswith("PIP_")],
    ):
        yield modules.pip


def _pip_successful_install(
    target,
    expect=(
        "irc3-plugins-test",
        "pep8",
    ),
):
    """
    Isolate regex for extracting `successful install` message from pip
    """

    expect = set(expect)
    expect_str = "|".join(expect)

    success = re.search(
        r"^.*Successfully installed\s([^\n]+)(?:Clean.*)?", target, re.M | re.S
    )

    success_for = (
        re.findall(rf"({expect_str})(?:-(?:[\d\.-]))?", success.groups()[0])
        if success
        else []
    )

    return expect.issubset(set(success_for))


@pytest.mark.parametrize(
    "pip_version",
    (
        pytest.param(
            "pip==9.0.3",
            marks=pytest.mark.skipif(
                sys.version_info >= (3, 10),
                reason="'pip==9.0.3' is not available on Py >= 3.10",
            ),
        ),
        "pip<20.0",
        "pip<21.0",
        "pip>=21.0",
    ),
)
def test_list_available_packages(pip, pip_version, tmp_path):
    with VirtualEnv(venv_dir=tmp_path, pip_requirement=pip_version) as virtualenv:
        virtualenv.install("-U", pip_version)
        package_name = "pep8"
        available_versions = pip.list_all_versions(
            package_name, bin_env=str(virtualenv.venv_bin_dir)
        )
        assert available_versions


@pytest.mark.parametrize(
    "pip_version",
    (
        "pip==9.0.3",
        "pip<20.0",
        "pip<21.0",
        "pip>=21.0",
    ),
)
def test_list_available_packages_with_index_url(pip, pip_version, tmp_path):
    if sys.version_info < (3, 6) and pip_version == "pip>=21.0":
        pytest.skip(f"{pip_version} is not available on Py3.5")
    if sys.version_info >= (3, 10) and pip_version == "pip==9.0.3":
        pytest.skip(f"{pip_version} is not available on Py3.10")
    with VirtualEnv(venv_dir=tmp_path, pip_requirement=pip_version) as virtualenv:
        virtualenv.install("-U", pip_version)
        package_name = "pep8"
        available_versions = pip.list_all_versions(
            package_name,
            bin_env=str(virtualenv.venv_bin_dir),
            index_url="https://pypi.python.org/simple",
        )
        assert available_versions


def test_issue_2087_missing_pip(venv, pip, modules):
    # Let's remove the pip binary
    pip_bin = venv.venv_bin_dir / "pip"
    site_dir = pathlib.Path(
        modules.virtualenv.get_distribution_path(str(venv.venv_dir), "pip")
    )
    if salt.utils.platform.is_windows():
        pip_bin = venv.venv_dir / "Scripts" / "pip.exe"
        site_dir = venv.venv_dir / "lib" / "site-packages"
    if not pip_bin.is_file():
        pytest.skip("Failed to find the pip binary to the test virtualenv")
    pip_bin.unlink()

    # Also remove the pip dir from site-packages
    # This is needed now that we're using python -m pip instead of the
    # pip binary directly. python -m pip will still work even if the
    # pip binary is missing
    shutil.rmtree(site_dir / "pip")

    with pytest.raises(CommandNotFoundError) as exc:
        pip.freeze(bin_env=str(venv.venv_dir))

    assert str(exc.value) == "Could not find a `pip` binary"

    with pytest.raises(CommandNotFoundError) as exc:
        pip.list(bin_env=str(venv.venv_dir))

    assert str(exc.value) == "Could not find a `pip` binary"


def test_requirements_as_list_of_chains__cwd_set__absolute_file_path(
    venv, pip, tmp_path
):
    # Create a requirements file that depends on another one.
    req1_filename = tmp_path / "requirements1.txt"
    req1_filename.write_text("-r requirements1b.txt\n", encoding="utf-8")
    req1b_filename = tmp_path / "requirements1b.txt"
    req1b_filename.write_text("irc3-plugins-test\n", encoding="utf-8")
    req2_filename = tmp_path / "requirements2.txt"
    req2_filename.write_text("-r requirements2b.txt\n", encoding="utf-8")
    req2b_filename = tmp_path / "requirements2b.txt"
    req2b_filename.write_text("pep8\n", encoding="utf-8")

    ret = pip.install(
        requirements=[str(req1_filename), str(req2_filename)],
        bin_env=venv.venv_dir,
        cwd=tmp_path,
    )
    assert ret
    assert isinstance(ret, dict)
    assert ret["retcode"] == 0
    assert _pip_successful_install(ret["stdout"])


def test_requirements_as_list_of_chains__cwd_not_set__absolute_file_path(
    venv, pip, tmp_path
):
    # Create a requirements file that depends on another one.
    req1_filename = tmp_path / "requirements1.txt"
    req1_filename.write_text("-r requirements1b.txt\n", encoding="utf-8")
    req1b_filename = tmp_path / "requirements1b.txt"
    req1b_filename.write_text("irc3-plugins-test\n", encoding="utf-8")
    req2_filename = tmp_path / "requirements2.txt"
    req2_filename.write_text("-r requirements2b.txt\n", encoding="utf-8")
    req2b_filename = tmp_path / "requirements2b.txt"
    req2b_filename.write_text("pep8\n", encoding="utf-8")

    ret = pip.install(
        requirements=[str(req1_filename), str(req2_filename)],
        bin_env=venv.venv_dir,
    )
    assert ret
    assert isinstance(ret, dict)
    assert ret["retcode"] == 0
    assert _pip_successful_install(ret["stdout"])


def test_requirements_as_list__absolute_file_path(venv, pip, tmp_path):
    # Create a requirements file that depends on another one.
    req1_filename = tmp_path / "requirements1.txt"
    req1_filename.write_text("irc3-plugins-test\n", encoding="utf-8")
    req2_filename = tmp_path / "requirements2.txt"
    req2_filename.write_text("pep8\n", encoding="utf-8")

    ret = pip.install(
        requirements=[str(req1_filename), str(req2_filename)],
        bin_env=venv.venv_dir,
    )
    assert ret
    assert isinstance(ret, dict)
    assert ret["retcode"] == 0
    assert _pip_successful_install(ret["stdout"])


def test_requirements_as_list__non_absolute_file_path(venv, pip, tmp_path):
    # Create a requirements file that depends on another one.
    req1_filename = tmp_path / "requirements1.txt"
    req1_filename.write_text("irc3-plugins-test\n", encoding="utf-8")
    req2_filename = tmp_path / "requirements2.txt"
    req2_filename.write_text("pep8\n", encoding="utf-8")

    ret = pip.install(
        requirements=[str(req1_filename.name), str(req2_filename.name)],
        bin_env=venv.venv_dir,
        cwd=tmp_path,
    )
    assert ret
    assert isinstance(ret, dict)
    assert ret["retcode"] == 0
    assert _pip_successful_install(ret["stdout"])


def test_chained_requirements__absolute_file_path(venv, pip, tmp_path):
    # Create a requirements file that depends on another one.
    req1_filename = tmp_path / "requirements1.txt"
    req1_filename.write_text("-r requirements2.txt\n", encoding="utf-8")
    req2_filename = tmp_path / "requirements2.txt"
    req2_filename.write_text("pep8\n", encoding="utf-8")

    ret = pip.install(
        requirements=str(req1_filename),
        bin_env=venv.venv_dir,
    )
    assert ret
    assert isinstance(ret, dict)
    assert ret["retcode"] == 0
    assert "installed pep8" in ret["stdout"]


def test_chained_requirements__non_absolute_file_path(venv, pip, tmp_path):
    # Create a requirements file that depends on another one.
    req1_filename = tmp_path / "requirements1.txt"
    req1_filename.write_text("-r requirements2.txt\n", encoding="utf-8")
    req2_filename = tmp_path / "requirements2.txt"
    req2_filename.write_text("pep8\n", encoding="utf-8")

    ret = pip.install(
        requirements=str(req1_filename.name), bin_env=venv.venv_dir, cwd=tmp_path
    )
    assert ret
    assert isinstance(ret, dict)
    assert ret["retcode"] == 0
    assert "installed pep8" in ret["stdout"]


@pytest.fixture
def installed_requirement(venv, pip):

    @contextmanager
    def _install(version=None):
        requirement = requirement_name = "pep8"
        if version is not None:
            requirement += f"=={version}"
        ret = pip.install(pkgs=requirement, bin_env=venv.venv_dir)
        assert ret
        assert isinstance(ret, dict)
        assert ret["retcode"] == 0
        assert "installed pep8" in ret["stdout"]
        print(444, pip.freeze(bin_env=venv.venv_dir))
        yield requirement_name

    return _install


def test_pip_uninstall(venv, pip, installed_requirement):
    with installed_requirement() as requirement:
        ret = pip.uninstall(pkgs=requirement, bin_env=venv.venv_dir)
        assert f"uninstalled {requirement}" in ret["stdout"]


def test_pip_install_upgrade(venv, pip, installed_requirement):
    with installed_requirement(version="1.3.4") as requirement:
        ret = pip.install(
            pkgs=requirement,
            bin_env=venv.venv_dir,
            upgrade=True,
        )
        assert f"installed {requirement}" in ret["stdout"]


def test_pip_install_multiple_editables(venv, pip):
    editables = [
        "git+https://github.com/saltstack/istr.git@v1.0.1#egg=iStr",
        "git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting",
    ]
    ret = pip.install(editable=editables, bin_env=venv.venv_dir)
    assert _pip_successful_install(ret["stdout"], ("iStr", "SaltTesting"))


def test_pip_install_multiple_editables_and_pkgs(venv, pip):
    editables = [
        "git+https://github.com/saltstack/istr.git@v1.0.1#egg=iStr",
        "git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting",
    ]
    ret = pip.install(pkgs="pep8", editable=editables, bin_env=venv.venv_dir)
    assert _pip_successful_install(ret["stdout"], ("iStr", "SaltTesting", "pep8"))


@pytest.mark.parametrize("touch", [True, False])
def test_pip_non_existent_log_file(venv, pip, tmp_path, touch):
    log_file = tmp_path / "tmp-pip-install.log"
    if touch:
        log_file.touch()
    ret = pip.install(pkgs="pep8", log=str(log_file), bin_env=venv.venv_dir)
    assert _pip_successful_install(ret["stdout"], ("pep8",))
    assert log_file.exists()
    assert "pep8" in log_file.read_text()


@pytest.mark.skipif(
    shutil.which("/bin/pip3") is None, reason="Could not find /bin/pip3"
)
@pytest.mark.destructive_test
@pytest.mark.skip_on_windows(reason="test specific for linux usage of /bin/python")
@pytest.mark.skip_initial_gh_actions_failure(
    reason="This was skipped on older golden images and is failing on newer."
)
def test_system_pip3(pip):
    pkg = "lazyimport"
    pkgver = f"{pkg}==0.0.1"
    ret = pip.install(pkgs=pkgver, bin_env="/bin/pip3")
    assert ret
    assert isinstance(ret, dict)
    assert ret["retcode"] == 0
    assert f"installed {pkg}" in ret["stdout"]

    ret = pip.freeze(bin_env="/bin/pip3")
    assert pkgver in ret

    ret = pip.uninstall(pkgs=pkg, bin_env="/bin/pip3")
    assert ret
    assert isinstance(ret, dict)
    assert ret["retcode"] == 0
    assert f"uninstalled {pkg}" in ret["stdout"]

    ret = pip.freeze(bin_env="/bin/pip3")
    assert pkg not in ret
