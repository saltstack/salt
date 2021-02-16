import os
import pathlib
import shutil

import pytest
from tests.support.helpers import VirtualEnv


@pytest.fixture
def setup_tests_path(tmp_path):
    if os.environ.get("CI_RUN", "0") == "0":
        directory = tmp_path / "setup-tests"
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
def virtualenv(setup_tests_path):
    return VirtualEnv(venv_dir=str(setup_tests_path / ".venv"))


@pytest.fixture
def cache_dir(setup_tests_path):
    _cache_dir = setup_tests_path / ".cache"
    _cache_dir.mkdir(parents=True, exist_ok=True)
    return _cache_dir
