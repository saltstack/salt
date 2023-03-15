import os

import pytest


@pytest.fixture(scope="module")
def install():
    pytest.helpers.clean_env()

    # Create old config
    pytest.helpers.old_install()

    pytest.helpers.run_command(
        [pytest.INST_BIN, "/S", "/default-config", "/minion-name=cli_minion"]
    )
    yield
    pytest.helpers.clean_env()


def test_ssm_present_old_location(install):
    assert os.path.exists(rf"{pytest.OLD_DIR}\bin\ssm.exe")


def test_binaries_present_old_location(install):
    assert os.path.exists(rf"{pytest.OLD_DIR}\bin\python.exe")


def test_config_present_old_location(install):
    assert os.path.exists(rf"{pytest.OLD_DIR}\conf\minion")


def test_config_correct(install):
    # The config file should be the default with only minion set
    expected = [
        "# Default config from test suite line 1/6\n",
        "#master: salt\n",
        "# Default config from test suite line 2/6\n",
        "id: cli_minion\n",
        "# Default config from test suite line 3/6\n",
        "# Default config from test suite line 4/6\n",
        "# Default config from test suite line 5/6\n",
        "# Default config from test suite line 6/6\n",
    ]

    with open(rf"{pytest.OLD_DIR}\conf\minion") as f:
        result = f.readlines()

    assert result == expected
