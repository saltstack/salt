import os

import pytest


@pytest.fixture(scope="module")
def install():
    pytest.helpers.clean_env()

    # Create an existing config
    pytest.helpers.existing_config()

    pytest.helpers.run_command([pytest.INST_BIN, "/default-config"])
    yield
    pytest.helpers.clean_env()


def test_binaries_present(install):
    assert os.path.exists(f"{pytest.INST_DIR}\\ssm.exe")


def test_config_present(install):
    assert os.path.exists(f"{pytest.DATA_DIR}\\conf\\minion")


def test_config_correct(install):
    # The config file should be the default, unchanged
    with open(f"{pytest.REPO_DIR}\\tests\\_files\\minion") as f:
        expected = f.readlines()

    with open(f"{pytest.DATA_DIR}\\conf\\minion") as f:
        result = f.readlines()

    assert result == expected
