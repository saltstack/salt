"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import errno
import os

import pytest
import salt.modules.puppet as puppet
import salt.utils.args
import salt.utils.files
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, mock_open, patch


@pytest.fixture
def configure_loader_modules():
    return {puppet: {}}


def test_run():
    """
    Test to execute a puppet run
    """
    mock = MagicMock(return_value={"A": "B"})
    with patch.object(salt.utils.args, "clean_kwargs", mock):
        mock = MagicMock(return_value={"retcode": 0})
        mock_lst = MagicMock(return_value=[])
        with patch.dict(puppet.__salt__, {"cmd.run_all": mock, "cmd.run": mock_lst}):
            assert puppet.run()


def test_noop():
    """
    Test to execute a puppet noop run
    """
    mock = MagicMock(return_value={"stderr": "A", "stdout": "B"})
    with patch.object(puppet, "run", mock):
        assert puppet.noop() == {"stderr": "A", "stdout": "B"}


def test_enable():
    """
    Test to enable the puppet agent
    """
    mock_lst = MagicMock(return_value=[])
    with patch.dict(puppet.__salt__, {"cmd.run": mock_lst}):
        mock = MagicMock(return_value=True)
        with patch.object(os.path, "isfile", mock):
            mock = MagicMock(return_value=True)
            with patch.object(os, "remove", mock):
                assert puppet.enable()
            with patch.object(os, "remove", MagicMock(side_effect=IOError)):
                pytest.raises(CommandExecutionError, puppet.enable)

        assert not puppet.enable()


def test_disable():
    """
    Test to disable the puppet agent
    """
    mock_lst = MagicMock(return_value=[])
    with patch.dict(puppet.__salt__, {"cmd.run": mock_lst}):
        mock = MagicMock(side_effect=[True, False])
        with patch.object(os.path, "isfile", mock):
            assert not puppet.disable()

            with patch("salt.utils.files.fopen", mock_open()):
                assert puppet.disable()

            try:
                with patch("salt.utils.files.fopen", mock_open()) as m_open:
                    m_open.side_effect = IOError(13, "Permission denied:", "/file")
                    pytest.raises(CommandExecutionError, puppet.disable)
            except StopIteration:
                pass


def test_status():
    """
    Test to display puppet agent status
    """
    mock_lst = MagicMock(return_value=[])
    with patch.dict(puppet.__salt__, {"cmd.run": mock_lst}):
        mock = MagicMock(side_effect=[True])
        with patch.object(os.path, "isfile", mock):
            assert puppet.status() == "Administratively disabled"

        mock = MagicMock(side_effect=[False, True])
        with patch.object(os.path, "isfile", mock):
            with patch("salt.utils.files.fopen", mock_open(read_data="1")):
                mock = MagicMock(return_value=True)
                with patch.object(os, "kill", mock):
                    assert puppet.status() == "Applying a catalog"

        mock = MagicMock(side_effect=[False, True])
        with patch.object(os.path, "isfile", mock):
            with patch("salt.utils.files.fopen", mock_open()):
                mock = MagicMock(return_value=True)
                with patch.object(os, "kill", mock):
                    assert puppet.status() == "Stale lockfile"

        mock = MagicMock(side_effect=[False, False, True])
        with patch.object(os.path, "isfile", mock):
            with patch("salt.utils.files.fopen", mock_open(read_data="1")):
                mock = MagicMock(return_value=True)
                with patch.object(os, "kill", mock):
                    assert puppet.status() == "Idle daemon"

        mock = MagicMock(side_effect=[False, False, True])
        with patch.object(os.path, "isfile", mock):
            with patch("salt.utils.files.fopen", mock_open()):
                mock = MagicMock(return_value=True)
                with patch.object(os, "kill", mock):
                    assert puppet.status() == "Stale pidfile"

        mock = MagicMock(side_effect=[False, False, False])
        with patch.object(os.path, "isfile", mock):
            assert puppet.status() == "Stopped"


def test_summary():
    """
    Test to show a summary of the last puppet agent run
    """
    mock_lst = MagicMock(return_value=[])
    with patch.dict(puppet.__salt__, {"cmd.run": mock_lst}):
        with patch("salt.utils.files.fopen", mock_open(read_data="resources: 1")):
            assert puppet.summary() == {"resources": 1}

        permission_error = IOError(errno.EACCES, "Permission denied:", "/file")
        with patch(
            "salt.utils.files.fopen", mock_open(read_data=permission_error)
        ) as m_open:
            pytest.raises(CommandExecutionError, puppet.summary)


def test_plugin_sync():
    """
    Test to runs a plugin synch between the puppet master and agent
    """
    mock_lst = MagicMock(return_value=[])
    with patch.dict(puppet.__salt__, {"cmd.run": mock_lst}):
        mock_lst = MagicMock(side_effect=[False, True])
        with patch.dict(puppet.__salt__, {"cmd.run": mock_lst}):
            assert puppet.plugin_sync() == ""

            assert puppet.plugin_sync()


def test_facts():
    """
    Test to run facter and return the results
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": "1\n2"})
    with patch.dict(puppet.__salt__, {"cmd.run_all": mock}):
        mock = MagicMock(side_effect=[["a", "b"], ["c", "d"]])
        with patch.object(puppet, "_format_fact", mock):
            assert puppet.facts() == {"a": "b", "c": "d"}


def test_fact():
    """
    Test to run facter for a specific fact
    """
    mock = MagicMock(
        side_effect=[
            {"retcode": 0, "stdout": False},
            {"retcode": 0, "stdout": True},
        ]
    )
    with patch.dict(puppet.__salt__, {"cmd.run_all": mock}):
        assert puppet.fact("salt") == ""

        assert puppet.fact("salt")
