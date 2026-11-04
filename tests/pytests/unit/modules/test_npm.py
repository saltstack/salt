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


# '_check_valid_version' function tests: 3


def test_check_valid_version_disables_update_notifier_59520():
    """
    _check_valid_version runs at module-load from __virtual__. It must pass
    NO_UPDATE_NOTIFIER=1 to the `npm --version` call so npm does not contact
    the registry (which stalls for minutes behind a firewall/proxy). It calls
    the module-level import salt.modules.cmdmod.run directly, so patch that,
    not __salt__["cmd.run_all"].
    """
    mock_run = MagicMock(return_value="6.14.0")
    with (
        patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/npm")),
        patch("salt.modules.cmdmod.run", mock_run),
    ):
        npm._check_valid_version()
    mock_run.assert_called_once_with(
        "/usr/bin/npm --version",
        output_loglevel="quiet",
        env={"NO_UPDATE_NOTIFIER": "1"},
    )


def test_check_valid_version_raises_on_old_npm_59520():
    """
    Inverse / must-not-regress: adding the env kwarg is purely additive and
    must not disturb the version gate. An npm older than 1.2 must still raise
    CommandExecutionError. This passes with and without the fix.
    """
    mock_run = MagicMock(return_value="1.1.0")
    with (
        patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/npm")),
        patch("salt.modules.cmdmod.run", mock_run),
    ):
        pytest.raises(CommandExecutionError, npm._check_valid_version)


def test_check_valid_version_accepts_recent_npm_59520():
    """
    Peripheral coverage: an npm at or above the minimum version returns without
    raising.
    """
    mock_run = MagicMock(return_value="1.2")
    with (
        patch("salt.utils.path.which", MagicMock(return_value="/usr/bin/npm")),
        patch("salt.modules.cmdmod.run", mock_run),
    ):
        assert npm._check_valid_version() is None
