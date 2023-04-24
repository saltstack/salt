import os

import pytest


@pytest.fixture(scope="module")
def inst_dir():
    return r"C:\custom_location"


@pytest.fixture(scope="module")
def install(inst_dir):
    pytest.helpers.clean_env()

    # Create old install
    pytest.helpers.old_install()

    pytest.helpers.run_command(
        [pytest.INST_BIN, "/S", f"/install-dir={inst_dir}", "/move-config"]
    )
    yield
    pytest.helpers.clean_env()


def test_binaries_present_old_location(install):
    # Apparently we don't move the binaries even if they pass install-dir
    # TODO: Decide if this is expected behavior
    assert os.path.exists(rf"{pytest.OLD_DIR}\bin\ssm.exe")
    assert os.path.exists(rf"{pytest.OLD_DIR}\bin\python.exe")


def test_config_present(install):
    assert os.path.exists(rf"{pytest.DATA_DIR}\conf\minion")


def test_config_correct(install):
    # The config file should be the existing config in the new location, unchanged
    expected = pytest.OLD_CONTENT

    with open(rf"{pytest.DATA_DIR}\conf\minion") as f:
        result = f.readlines()

    assert result == expected
