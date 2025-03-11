import os

import pytest


@pytest.fixture(scope="module")
def install():
    pytest.helpers.clean_env()
    # Create old config
    pytest.helpers.old_install()
    # Create a custom config
    pytest.helpers.custom_config()
    args = ["/custom-config=custom_conf"]
    pytest.helpers.install_salt(args)
    yield args
    pytest.helpers.clean_env()


def test_binaries_present_old_location(install):
    # This will show the contents of the directory on failure
    dir_contents = os.listdir(rf"{pytest.OLD_DIR}\bin")
    # Apparently we don't move the binaries even if they pass install-dir
    # TODO: Decide if this is expected behavior
    assert os.path.exists(rf"{pytest.OLD_DIR}\bin\ssm.exe")
    assert os.path.exists(rf"{pytest.OLD_DIR}\bin\python.exe")


def test_config_present_old_location(install):
    assert os.path.exists(rf"{pytest.OLD_DIR}\conf\minion")


def test_config_correct(install):
    # The config file should be the custom config, unchanged
    with open(rf"{pytest.SCRIPT_DIR}\custom_conf") as f:
        expected = f.readlines()

    with open(rf"{pytest.OLD_DIR}\conf\minion") as f:
        result = f.readlines()

    assert result == expected
