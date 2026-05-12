import os

import pytest


@pytest.fixture(scope="module")
def install():
    pytest.helpers.clean_env()
    # Create a custom config
    full_path_conf = pytest.helpers.custom_config()
    # Install salt with custom config
    args = ["/S", f"/custom-config={full_path_conf}"]
    pytest.helpers.install_salt(args)
    yield args
    pytest.helpers.clean_env()


def test_binaries_present(install):
    # This will show the contents of the directory on failure
    inst_dir = pytest.INST_DIR
    inst_dir_exists = os.path.exists(inst_dir)
    dir_contents = os.listdir(inst_dir)
    assert os.path.exists(rf"{inst_dir}\ssm.exe")


def test_config_present(install):
    data_dir = pytest.DATA_DIR
    data_dir_exists = os.path.exists(data_dir)
    assert os.path.exists(rf"{data_dir}\conf\minion")


def test_config_correct(install):
    # The config file should be the custom config, unchanged
    script_dir = pytest.SCRIPT_DIR
    script_dir_exists = os.path.exists(script_dir)
    with open(rf"{script_dir}\custom_conf") as f:
        expected = f.readlines()

    data_dir = pytest.DATA_DIR
    data_dir_exists = os.path.exists(data_dir)
    with open(rf"{pytest.DATA_DIR}\conf\minion") as f:
        result = f.readlines()

    assert result == expected
