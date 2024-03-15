"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.npm
"""

import textwrap

import pytest

import salt.modules.npm as npm
import salt.utils.json
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    with patch("salt.modules.npm._check_valid_version", MagicMock(return_value=True)):
        return {npm: {}}


# 'install' function tests: 4


def test_install():
    """
    Test if it installs an NPM package.
    """
    mock = MagicMock(return_value={"retcode": 1, "stderr": "error"})
    with patch.dict(npm.__salt__, {"cmd.run_all": mock}):
        pytest.raises(CommandExecutionError, npm.install, "coffee-script")

    # This is at least somewhat closer to the actual output format.
    mock_json_out = textwrap.dedent(
        """\
    [
      {
        "salt": "SALT"
      }
    ]"""
    )

    # Successful run, expected output format
    mock = MagicMock(return_value={"retcode": 0, "stderr": "", "stdout": mock_json_out})
    with patch.dict(npm.__salt__, {"cmd.run_all": mock}):
        assert npm.install("coffee-script") == [{"salt": "SALT"}]

    mock_json_out_extra = textwrap.dedent(
        """\
    Compilation output here

    [bcrypt] Success: "/tmp/node_modules/bcrypt/foo" is installed via remote"
    [grpc] Success: "/usr/lib/node_modules/@foo/bar" is installed via remote"
    [
       {
          "from" : "express@",
          "name" : "express",
          "dependencies" : {
             "escape-html" : {
                "from" : "escape-html@~1.0.3",
                "dependencies" : {},
                "version" : "1.0.3"
             }
          },
          "version" : "4.16.3"
       }
    ]"""
    )
    extra_expected = [
        {
            "dependencies": {
                "escape-html": {
                    "dependencies": {},
                    "from": "escape-html@~1.0.3",
                    "version": "1.0.3",
                }
            },
            "from": "express@",
            "name": "express",
            "version": "4.16.3",
        }
    ]

    # Successful run, expected output format with additional leading text
    mock = MagicMock(
        return_value={"retcode": 0, "stderr": "", "stdout": mock_json_out_extra}
    )
    with patch.dict(npm.__salt__, {"cmd.run_all": mock}):
        assert npm.install("coffee-script") == extra_expected

    # Successful run, unexpected output format
    mock = MagicMock(return_value={"retcode": 0, "stderr": "", "stdout": "SALT"})
    with patch.dict(npm.__salt__, {"cmd.run_all": mock}):
        mock_err = MagicMock(side_effect=ValueError())
        # When JSON isn't successfully parsed, return should equal input
        with patch.object(salt.utils.json, "loads", mock_err):
            assert npm.install("coffee-script") == "SALT"


# 'uninstall' function tests: 1


def test_uninstall():
    """
    Test if it uninstalls an NPM package.
    """
    mock = MagicMock(return_value={"retcode": 1, "stderr": "error"})
    with patch.dict(npm.__salt__, {"cmd.run_all": mock}):
        assert not npm.uninstall("coffee-script")

    mock = MagicMock(return_value={"retcode": 0, "stderr": ""})
    with patch.dict(npm.__salt__, {"cmd.run_all": mock}):
        assert npm.uninstall("coffee-script")


# 'list_' function tests: 1


def test_list():
    """
    Test if it list installed NPM packages.
    """
    mock = MagicMock(return_value={"retcode": 1, "stderr": "error"})
    with patch.dict(npm.__salt__, {"cmd.run_all": mock}):
        pytest.raises(CommandExecutionError, npm.list_, "coffee-script")

    mock = MagicMock(
        return_value={
            "retcode": 0,
            "stderr": "error",
            "stdout": '{"salt": ["SALT"]}',
        }
    )
    with patch.dict(npm.__salt__, {"cmd.run_all": mock}):
        mock_err = MagicMock(return_value={"dependencies": "SALT"})
        with patch.object(salt.utils.json, "loads", mock_err):
            assert npm.list_("coffee-script") == "SALT"


# 'cache_clean' function tests: 1


def test_cache_clean():
    """
    Test if it cleans the cached NPM packages.
    """
    mock = MagicMock(return_value={"retcode": 1, "stderr": "error"})
    with patch.dict(npm.__salt__, {"cmd.run_all": mock}):
        assert not npm.cache_clean()

    mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(npm.__salt__, {"cmd.run_all": mock}):
        assert npm.cache_clean()

    mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(npm.__salt__, {"cmd.run_all": mock}):
        assert npm.cache_clean("coffee-script")


# 'cache_list' function tests: 1


def test_cache_list():
    """
    Test if it lists the NPM cache.
    """
    mock = MagicMock(return_value={"retcode": 1, "stderr": "error"})
    with patch.dict(npm.__salt__, {"cmd.run_all": mock}):
        pytest.raises(CommandExecutionError, npm.cache_list)

    mock = MagicMock(
        return_value={"retcode": 0, "stderr": "error", "stdout": ["~/.npm"]}
    )
    with patch.dict(npm.__salt__, {"cmd.run_all": mock}):
        assert npm.cache_list() == ["~/.npm"]

    mock = MagicMock(return_value={"retcode": 0, "stderr": "error", "stdout": ""})
    with patch.dict(npm.__salt__, {"cmd.run_all": mock}):
        assert npm.cache_list("coffee-script") == ""


# 'cache_path' function tests: 1


def test_cache_path():
    """
    Test if it prints the NPM cache path.
    """
    mock = MagicMock(return_value={"retcode": 1, "stderr": "error"})
    with patch.dict(npm.__salt__, {"cmd.run_all": mock}):
        assert npm.cache_path() == "error"

    mock = MagicMock(
        return_value={"retcode": 0, "stderr": "error", "stdout": "/User/salt/.npm"}
    )
    with patch.dict(npm.__salt__, {"cmd.run_all": mock}):
        assert npm.cache_path() == "/User/salt/.npm"
