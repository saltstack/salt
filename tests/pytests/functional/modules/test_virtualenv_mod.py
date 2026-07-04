import shutil
import sys

import pytest

from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES

pytestmark = [
    pytest.mark.slow_test,
]

# The stdlib venv tests below do not need a virtualenv binary; only the
# tests driving one carry this marker.
requires_virtualenv = pytest.mark.skip_if_binaries_missing(
    *KNOWN_BINARY_NAMES, check_all=False
)


@pytest.fixture
def venv_dir(tmp_path):
    return tmp_path / "venv"


@pytest.fixture
def virtualenv(modules):
    return modules.virtualenv


@requires_virtualenv
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


@requires_virtualenv
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


@requires_virtualenv
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


@requires_virtualenv
def test_virtualenv_ver(virtualenv, venv_dir):
    ret = virtualenv.create(str(venv_dir))
    assert ret
    assert "retcode" in ret
    assert ret["retcode"] == 0
    ret = virtualenv.virtualenv_ver(str(venv_dir))
    assert isinstance(ret, tuple)
    assert all([isinstance(x, int) for x in ret])


def test_create_venv_module(virtualenv, venv_dir):
    """
    venv_bin="venv" builds the environment with the python standard library
    venv module.
    """
    ret = virtualenv.create(str(venv_dir), venv_bin="venv")
    assert ret
    assert ret["retcode"] == 0
    assert (venv_dir / "bin" / "python").exists()
    assert (venv_dir / "pyvenv.cfg").exists()


def test_create_venv_module_with_python(virtualenv, venv_dir):
    """
    venv_bin="venv" with an explicit python runs `<python> -m venv`.
    """
    ret = virtualenv.create(str(venv_dir), venv_bin="venv", python=sys.executable)
    assert ret
    assert ret["retcode"] == 0
    assert (venv_dir / "bin" / "python").exists()


def test_create_venv_interpreter_as_venv_bin(virtualenv, venv_dir):
    """
    A python interpreter passed as venv_bin also selects the venv module.
    """
    ret = virtualenv.create(str(venv_dir), venv_bin=sys.executable)
    assert ret
    assert ret["retcode"] == 0
    assert (venv_dir / "bin" / "python").exists()


def test_create_venv_module_prompt(virtualenv, venv_dir):
    """
    The prompt argument is passed through to the venv module.
    """
    ret = virtualenv.create(str(venv_dir), venv_bin="venv", prompt="salty-venv")
    assert ret
    assert ret["retcode"] == 0
    assert "salty-venv" in (venv_dir / "pyvenv.cfg").read_text()
