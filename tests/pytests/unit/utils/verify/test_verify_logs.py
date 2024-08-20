import getpass
import os
import pathlib

import pytest

import salt.utils.verify
from tests.support.mock import MagicMock, patch


def test_verify_logs_filter():
    filtered = salt.utils.verify.verify_logs_filter(
        ["udp://foo", "tcp://bar", "/tmp/foo", "file://tmp/bar"]
    )
    assert filtered == ["/tmp/foo"], filtered


@pytest.mark.skip_on_windows(reason="Not applicable on Windows")
def test_verify_log_files_udp_scheme():
    salt.utils.verify.verify_log_files(["udp://foo"], getpass.getuser())
    assert not pathlib.Path(os.getcwd(), "udp:").is_dir()


@pytest.mark.skip_on_windows(reason="Not applicable on Windows")
def test_verify_log_files_tcp_scheme():
    salt.utils.verify.verify_log_files(["udp://foo"], getpass.getuser())
    assert not pathlib.Path(os.getcwd(), "tcp:").is_dir()


@pytest.mark.skip_on_windows(reason="Not applicable on Windows")
def test_verify_log_files_file_scheme():
    salt.utils.verify.verify_log_files(["file://{}"], getpass.getuser())
    assert not pathlib.Path(os.getcwd(), "file:").is_dir()


@pytest.mark.skip_on_windows(reason="Not applicable on Windows")
def test_verify_log_files(tmp_path):
    path = tmp_path / "foo" / "bar.log"
    assert not path.exists()
    salt.utils.verify.verify_log_files([str(path)], getpass.getuser())
    assert path.exists()


def test_verify_log():
    """
    Test that verify_log works as expected
    """
    message = "Insecure logging configuration detected! Sensitive data may be logged."

    mock_cheese = MagicMock()
    with patch.object(salt.utils.verify.log, "warning", mock_cheese):
        salt.utils.verify.verify_log({"log_level": "cheeseshop"})
        mock_cheese.assert_called_once_with(message)

    mock_trace = MagicMock()
    with patch.object(salt.utils.verify.log, "warning", mock_trace):
        salt.utils.verify.verify_log({"log_level": "trace"})
        mock_trace.assert_called_once_with(message)

    mock_none = MagicMock()
    with patch.object(salt.utils.verify.log, "warning", mock_none):
        salt.utils.verify.verify_log({})
        mock_none.assert_called_once_with(message)

    mock_info = MagicMock()
    with patch.object(salt.utils.verify.log, "warning", mock_info):
        salt.utils.verify.verify_log({"log_level": "info"})
        assert mock_info.call_count == 0


def test_insecure_log():
    """
    test insecure_log that it returns accurate insecure log levels
    """
    ret = salt.utils.verify.insecure_log()
    assert ret == ["all", "debug", "garbage", "profile", "trace"]
