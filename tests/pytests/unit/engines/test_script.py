"""
unit tests for the script engine
"""

import pytest
import salt.config
import salt.engines.script as script
from salt.exceptions import CommandExecutionError
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    opts = salt.config.DEFAULT_MASTER_OPTS
    return {script: {"__opts__": opts}}


def test__get_serializer():
    """
    Test known serializer is returned or exception is raised
    if unknown serializer
    """
    for serializers in ("json", "yaml", "msgpack"):
        assert script._get_serializer(serializers)

    with pytest.raises(CommandExecutionError):
        script._get_serializer("bad")


def test__read_stdout():
    """
    Test we can yield stdout
    """
    with patch("subprocess.Popen") as popen_mock:
        popen_mock.stdout.readline.return_value = "test"
        assert next(script._read_stdout(popen_mock)) == "test"


def test__read_stdout_terminates_properly():
    """
    Test that _read_stdout terminates with the sentinel
    """
    with patch("subprocess.Popen") as popen_mock:
        popen_mock.stdout.readline.return_value = b""
        with pytest.raises(StopIteration):
            next(script._read_stdout(popen_mock))
