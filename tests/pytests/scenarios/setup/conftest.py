import os
import pathlib
import shutil

import pytest
from tests.support.helpers import VirtualEnv


@pytest.fixture
def virtualenv(tmp_path):
    return VirtualEnv(venv_dir=str(tmp_path / ".venv"))


@pytest.fixture
def cache_dir(tmp_path):
    if "CI_RUN" in os.environ and os.environ["CI_RUN"] == "1":
        # Some of our golden images, at least, Arch Linux and Fedora 33, mount /tmp as a tmpfs.
        # These setup tests will currently consume all of the freespace on /tmp in these distributions.
        # To bypass that issue, we'll use the users `.cache` directory to store the downloads we need
        # to run these tests.
        _cache_dir = pathlib.Path.home() / ".cache" / "salt-setup-tests"
    else:
        _cache_dir = tmp_path / ".cache"
    _cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield _cache_dir
    finally:
        shutil.rmtree(str(_cache_dir), ignore_errors=True)
