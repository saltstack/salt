import pytest

import salt.utils.master
from tests.support.mock import mock_open, patch


@pytest.mark.skip_on_platforms(linux=True)
def test_check_cmdline_returns_true():
    assert salt.utils.master._check_cmdline({"pid": 99999999}) is True


@pytest.mark.skip_unless_on_linux
def test_check_cmdline_no_pid():
    assert salt.utils.master._check_cmdline({}) is False


def test_check_cmdline_no_proc_dir():
    with patch("salt.utils.platform.is_linux", return_value=True), patch(
        "os.path.isdir", return_value=False
    ):
        assert salt.utils.master._check_cmdline({"pid": 99999999}) is True


@pytest.mark.skip_unless_on_linux
def test_check_cmdline_no_proc_file():
    with patch("os.path.isfile", return_value=True) as mock_isfile:
        pid = 99999999
        assert salt.utils.master._check_cmdline({"pid": pid}) is False
        mock_isfile.assert_called_with(f"/proc/{pid}/cmdline")


@pytest.mark.skip_unless_on_linux
def test_check_cmdline_not_salt_process():
    with patch("os.path.isfile", return_value=True), patch(
        "salt.utils.files.fopen", mock_open(read_data=b"blah")
    ):
        assert salt.utils.master._check_cmdline({"pid": 99999999}) is False


@pytest.mark.skip_unless_on_linux
def test_check_cmdline_salt_process():
    with patch("os.path.isfile", return_value=True), patch(
        "salt.utils.files.fopen", mock_open(read_data=b"salt")
    ):
        assert salt.utils.master._check_cmdline({"pid": 99999999}) is True


@pytest.mark.skip_unless_on_linux
def test_check_cmdline_proc_vanishes():
    with patch("os.path.isfile", return_value=True), patch(
        "salt.utils.files.fopen", side_effect=OSError
    ):
        assert salt.utils.master._check_cmdline({"pid": 99999999}) is False
