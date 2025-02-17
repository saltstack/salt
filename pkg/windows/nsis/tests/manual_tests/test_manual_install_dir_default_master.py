import os

import pytest


@pytest.fixture(scope="module")
def inst_dir():
    return "C:\\custom_location"


@pytest.fixture(scope="module")
def install(inst_dir):
    pytest.helpers.clean_env()
    args = [f"/install-dir={inst_dir}", "/master=cli_master"]
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
    # The config file should be the default config with only master set
    expected = [
        "# Default config from test suite line 1/6\n",
        "master: cli_master\n",
        "# Default config from test suite line 2/6\n",
        "#id:\n",
        "# Default config from test suite line 3/6\n",
        "# Default config from test suite line 4/6\n",
        "# Default config from test suite line 5/6\n",
        "# Default config from test suite line 6/6\n",
    ]

    with open(rf"{pytest.DATA_DIR}\conf\minion") as f:
        result = f.readlines()

    assert result == expected
