import os

import pytest


@pytest.fixture(scope="module")
def inst_dir():
    return "C:\\custom_location"


@pytest.fixture(scope="module")
def install(inst_dir):
    pytest.helpers.clean_env()
    args = [f"/install-dir={inst_dir}"]
    pytest.helpers.install_salt(args)
    yield args
    pytest.helpers.clean_env(inst_dir)


def test_binaries_present(install, inst_dir):
    # This will show the contents of the directory on failure
    inst_dir_exists = os.path.exists(inst_dir)
    dir_contents = os.listdir(inst_dir)
    assert os.path.exists(rf"{inst_dir}\ssm.exe")


def test_config_present(install):
    assert os.path.exists(rf"{pytest.DATA_DIR}\conf\minion")


def test_config_correct(install):
    # The config file should be the default config, unchanged
    with open(rf"{pytest.SCRIPT_DIR}\_files\minion") as f:
        expected = f.readlines()

    with open(rf"{pytest.DATA_DIR}\conf\minion") as f:
        result = f.readlines()

    assert result == expected
