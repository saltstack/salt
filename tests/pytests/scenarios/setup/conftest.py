import os
import pathlib
import shutil

import pytest
from tests.support.helpers import VirtualEnv
from tests.support.runtests import RUNTIME_VARS


@pytest.fixture(scope="package")
def setup_tests_path(tmp_path_factory):
    if os.environ.get("CI_RUN", "0") == "0":
        directory = tmp_path_factory.mktemp("setup-tests")
    else:
        # Under CI, on some platforms, Arch, Fedora 33, FreeBSD 12, we run out of disk space on /tmp
        # Use a subdirectory in the current user's home directory
        directory = pathlib.Path.home() / "setup-tests"
    directory.mkdir(parents=True, exist_ok=True)
    try:
        yield directory
    finally:
        shutil.rmtree(str(directory), ignore_errors=True)


@pytest.fixture
def virtualenv(setup_tests_path, pip_temp_dir):
    venv_dir = setup_tests_path / ".venv"
    try:
        yield VirtualEnv(venv_dir=venv_dir, env={"TMPDIR": str(pip_temp_dir)})
    finally:
        shutil.rmtree(str(venv_dir), ignore_errors=True)


@pytest.fixture
def cache_dir(setup_tests_path):
    _cache_dir = setup_tests_path / ".cache"
    _cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield _cache_dir
    finally:
        shutil.rmtree(str(_cache_dir), ignore_errors=True)


@pytest.fixture(scope="package")
def pip_temp_dir(setup_tests_path):
    temp_dir_path = setup_tests_path / "temp-dir"
    temp_dir_path.mkdir()
    return temp_dir_path


@pytest.fixture(scope="package")
def src_dir(setup_tests_path):
    if os.environ.get("CI_RUN", "0") == "0":
        return RUNTIME_VARS.CODE_DIR

    _src_dir = setup_tests_path / "src"
    shutil.copytree(
        RUNTIME_VARS.CODE_DIR,
        str(_src_dir),
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", "*.pyo", ".coverage.*", ".nox"
        ),
    )
    return str(_src_dir)
