import pathlib

import pytest

from tests.support.runtests import RUNTIME_VARS


@pytest.fixture(scope="session", autouse=True)
def _create_old_tempdir():
    pathlib.Path(RUNTIME_VARS.TMP).mkdir(exist_ok=True, parents=True)
