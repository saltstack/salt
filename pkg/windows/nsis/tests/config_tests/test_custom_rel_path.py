import os

import pytest


@pytest.fixture(scope="module")
def install():
    pytest.helpers.clean_env()

    # Create a custom config
    pytest.helpers.custom_config()

    pytest.helpers.run_command([pytest.INST_BIN, "/S", "/custom-config=custom_conf"])
    yield
    pytest.helpers.clean_env()


def test_binaries_present(install):
    assert os.path.exists(rf"{pytest.INST_DIR}\ssm.exe")


def test_config_present(install):
    assert os.path.exists(rf"{pytest.DATA_DIR}\conf\minion")


def test_config_correct(install):
    # The config file should be the custom config, unchanged
    with open(rf"{pytest.REPO_DIR}\custom_conf") as f:
        expected = f.readlines()

    with open(rf"{pytest.DATA_DIR}\conf\minion") as f:
        result = f.readlines()

    assert result == expected
