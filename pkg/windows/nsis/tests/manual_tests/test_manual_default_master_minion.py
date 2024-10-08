import os

import pytest


@pytest.fixture(scope="module")
def install():
    pytest.helpers.clean_env()
    args = ["/master=cli_master", "/minion-name=cli_minion"]
    pytest.helpers.install_salt(args)
    yield args
    pytest.helpers.clean_env()


def test_binaries_present(install):
    assert os.path.exists(f"{pytest.INST_DIR}\\ssm.exe")


def test_config_present(install):
    assert os.path.exists(f"{pytest.DATA_DIR}\\conf\\minion")


def test_config_correct(install):
    # The config file should be the default with master and minion set
    expected = [
        "# Default config from test suite line 1/6\n",
        "master: cli_master\n",
        "# Default config from test suite line 2/6\n",
        "id: cli_minion\n",
        "# Default config from test suite line 3/6\n",
        "# Default config from test suite line 4/6\n",
        "# Default config from test suite line 5/6\n",
        "# Default config from test suite line 6/6\n",
    ]

    with open(f"{pytest.DATA_DIR}\\conf\\minion") as f:
        result = f.readlines()

    assert result == expected
