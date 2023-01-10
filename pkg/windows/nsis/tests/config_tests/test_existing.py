import os

import pytest


@pytest.fixture(scope="module")
def install():
    pytest.helpers.clean_env()

    # Create an existing config
    pytest.helpers.existing_config()

    pytest.helpers.run_command([pytest.INST_BIN, "/S"])
    yield
    pytest.helpers.clean_env()


def test_binaries_present(install):
    assert os.path.exists(rf"{pytest.INST_DIR}\ssm.exe")


def test_config_present(install):
    assert os.path.exists(rf"{pytest.DATA_DIR}\conf\minion")


def test_config_correct(install):
    # The config file should be the existing config, unchanged
    expected = pytest.EXISTING_CONTENT

    with open(rf"{pytest.DATA_DIR}\conf\minion") as f:
        result = f.readlines()

    assert result == expected
