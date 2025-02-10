import os

import pytest


@pytest.fixture(scope="module")
def install():
    pytest.helpers.clean_env()
    # Create old config
    pytest.helpers.old_install()
    args = ["/move-config"]
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


def test_config_present_new_location(install):
    assert os.path.exists(rf"{pytest.DATA_DIR}\conf\minion")


def test_config_correct(install):
    # The config file should be the old existing config in the new location, unchanged
    expected = pytest.OLD_CONTENT

    with open(rf"{pytest.DATA_DIR}\conf\minion") as f:
        result = f.readlines()

    assert result == expected
