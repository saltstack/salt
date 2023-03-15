import shutil

import pytest

from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing(*KNOWN_BINARY_NAMES, check_all=False),
]


@pytest.fixture
def venv_dir(tmp_path):
    return tmp_path / "venv"


@pytest.fixture
def virtualenv(modules):
    return modules.virtualenv


def test_create_defaults(virtualenv, venv_dir):
    """
    virtualenv.managed
    """
    ret = virtualenv.create(str(venv_dir))
    assert ret
    assert "retcode" in ret
    assert ret["retcode"] == 0
    pip_binary = venv_dir / "bin" / "pip"
    assert pip_binary.exists()


def test_site_packages(virtualenv, venv_dir, modules):
    ret = virtualenv.create(str(venv_dir), system_site_packages=True)
    assert ret
    assert "retcode" in ret
    assert ret["retcode"] == 0
    pip_binary = venv_dir / "bin" / "pip"
    with_site = modules.pip.freeze(bin_env=str(pip_binary))
    shutil.rmtree(venv_dir)
    ret = virtualenv.create(str(venv_dir))
    assert ret
    assert "retcode" in ret
    assert ret["retcode"] == 0
    without_site = modules.pip.freeze(bin_env=str(pip_binary))
    assert with_site != without_site


def test_clear(virtualenv, venv_dir, modules):
    ret = virtualenv.create(str(venv_dir))
    assert ret
    assert "retcode" in ret
    assert ret["retcode"] == 0
    pip_binary = venv_dir / "bin" / "pip"
    modules.pip.install("pep8", bin_env=str(pip_binary))
    ret = virtualenv.create(str(venv_dir), clear=True)
    assert ret
    assert "retcode" in ret
    assert ret["retcode"] == 0
    packages = modules.pip.list(prefix="pep8", bin_env=str(pip_binary))
    assert "pep8" not in packages


def test_virtualenv_ver(virtualenv, venv_dir):
    ret = virtualenv.create(str(venv_dir))
    assert ret
    assert "retcode" in ret
    assert ret["retcode"] == 0
    ret = virtualenv.virtualenv_ver(str(venv_dir))
    assert isinstance(ret, tuple)
    assert all([isinstance(x, int) for x in ret])
