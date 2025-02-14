import os

import pytest


@pytest.fixture
def install():
    assert pytest.helpers.clean_env()
    args = ["/S"]
    pytest.helpers.install_salt(args)
    yield args
    assert pytest.helpers.clean_env()


@pytest.mark.parametrize("execution_number", range(100))
def test_repeatedly_install_uninstall(execution_number, install):
    # Make sure the binaries exists. If they don't, the install failed
    assert os.path.exists(
        f"{pytest.INST_DIR}\\python.exe"
    ), "Installation failed. `python.exe` not found"
    assert os.path.exists(
        f"{pytest.INST_DIR}\\ssm.exe"
    ), "Installation failed. `ssm.exe` not found"
    assert os.path.exists(
        f"{pytest.INST_DIR}\\uninst.exe"
    ), "Installation failed. `uninst.exe` not found"
