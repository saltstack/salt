"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.rsyn
"""

import pytest

import salt.modules.rsync as rsync
from salt.exceptions import CommandExecutionError, SaltInvocationError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {rsync: {}}


def test_rsync():
    """
    Test for rsync files from src to dst
    """
    with patch.dict(rsync.__salt__, {"config.option": MagicMock(return_value=False)}):
        pytest.raises(SaltInvocationError, rsync.rsync, "", "")

    with patch.dict(
        rsync.__salt__,
        {
            "config.option": MagicMock(return_value="A"),
            "cmd.run_all": MagicMock(side_effect=[OSError(1, "f"), "A"]),
        },
    ):
        with patch.object(rsync, "_check", return_value=["A"]):
            pytest.raises(CommandExecutionError, rsync.rsync, "a", "b")

            assert rsync.rsync("src", "dst") == "A"


def test_version():
    """
    Test for return rsync version
    """
    mock = MagicMock(side_effect=[OSError(1, "f"), "A B C\n"])
    with patch.dict(rsync.__salt__, {"cmd.run_stdout": mock}):
        pytest.raises(CommandExecutionError, rsync.version)

        assert rsync.version() == "C"


def test_rsync_excludes_list():
    """
    Test for rsync files from src to dst with a list of excludes
    """
    mock = {
        "config.option": MagicMock(return_value=False),
        "cmd.run_all": MagicMock(),
    }
    with patch.dict(rsync.__salt__, mock):
        rsync.rsync("src", "dst", exclude=["test/one", "test/two"])
    mock["cmd.run_all"].assert_called_once_with(
        [
            "rsync",
            "-avz",
            "--exclude",
            "test/one",
            "--exclude",
            "test/two",
            "src",
            "dst",
        ],
        python_shell=False,
    )


def test_rsync_excludes_str():
    """
    Test for rsync files from src to dst with one exclude
    """
    mock = {
        "config.option": MagicMock(return_value=False),
        "cmd.run_all": MagicMock(),
    }
    with patch.dict(rsync.__salt__, mock):
        rsync.rsync("src", "dst", exclude="test/one")
    mock["cmd.run_all"].assert_called_once_with(
        ["rsync", "-avz", "--exclude", "test/one", "src", "dst"],
        python_shell=False,
    )
