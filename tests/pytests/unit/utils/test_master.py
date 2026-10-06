import os

import pytest

import salt.payload
import salt.utils.master
from tests.support.mock import mock_open, patch


@pytest.fixture
def proc_dir(tmp_path):
    path = tmp_path / "proc"
    path.mkdir()
    return str(path)


@pytest.fixture
def proc_file(proc_dir):
    path = os.path.join(proc_dir, "20240208071139934305")
    data = {
        "fun": "runner.state.orch",
        "jid": "20240208071139934305",
        "user": "vagrant",
        "fun_args": ["test_orch", {"orchestration_jid": "20240208071139934305"}],
        "_stamp": "2024-02-08T07:11:40.336362",
        "pid": 99999999,
    }
    with open(path, "wb") as fp:  # pylint: disable=resource-leakage
        fp.write(salt.payload.dumps(data))
    return path, data


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


def test_read_proc_file_empty():
    with patch("salt.utils.files.fopen", mock_open(read_data=b"")), patch(
        "os.remove"
    ) as mock_remove:
        path = "/var/cache/salt/minion/proc/20240208040218919013"
        assert salt.utils.master._read_proc_file(path, {}) is None
        mock_remove.assert_called_with(path)


def test_read_proc_file_empty_error():
    with patch("salt.utils.files.fopen", mock_open(read_data=b"")), patch(
        "os.remove", side_effect=OSError
    ):
        path = "/var/cache/salt/minion/proc/20240208040218919013"
        assert salt.utils.master._read_proc_file(path, {}) is None


def test_read_proc_file_not_dict():
    with patch("salt.utils.files.fopen", mock_open(read_data=b"x")), patch(
        "salt.payload.loads", return_value=[]
    ):
        path = "/var/cache/salt/minion/proc/20240208040218919013"
        assert salt.utils.master._read_proc_file(path, {}) is None


def test_read_proc_file_not_running(proc_file):
    assert os.path.isfile(proc_file[0])
    assert salt.utils.master._read_proc_file(proc_file[0], {}) is None
    assert os.path.exists(proc_file[0]) is False


def test_read_proc_file_running(proc_file):
    with patch("salt.utils.process.os_is_running", return_value=True), patch(
        "salt.utils.master._check_cmdline", return_value=True
    ):
        assert salt.utils.master._read_proc_file(proc_file[0], {}) == proc_file[1]
        assert os.path.exists(proc_file[0]) is True


def test_read_proc_file_running_not_salt(proc_file):
    with patch("salt.utils.process.os_is_running", return_value=True), patch(
        "salt.utils.master._check_cmdline", return_value=False
    ):
        assert salt.utils.master._read_proc_file(proc_file[0], {}) is None
        assert os.path.exists(proc_file[0]) is False


def test_read_proc_file_running_not_salt_error(proc_file):
    with patch("salt.utils.process.os_is_running", return_value=True), patch(
        "salt.utils.master._check_cmdline", return_value=False
    ), patch("os.remove", side_effect=OSError):
        assert salt.utils.master._read_proc_file(proc_file[0], {}) is None
        assert os.path.exists(proc_file[0]) is True


def test_clean_proc_dir_no_data(tmp_path, proc_file):
    with patch("salt.utils.master._read_proc_file", return_value=None):
        salt.utils.master.clean_proc_dir({"cachedir": str(tmp_path)})
        assert os.path.exists(proc_file[0]) is False


def test_clean_proc_dir_no_data_error(tmp_path, proc_file):
    with patch("salt.utils.master._read_proc_file", return_value=None), patch(
        "os.remove", side_effect=OSError
    ):
        salt.utils.master.clean_proc_dir({"cachedir": str(tmp_path)})
        assert os.path.exists(proc_file[0]) is True


def test_clean_proc_dir_running(tmp_path, proc_file):
    with patch("salt.utils.master._read_proc_file", return_value=proc_file[1]), patch(
        "salt.utils.master._check_cmdline", return_value=True
    ):
        salt.utils.master.clean_proc_dir({"cachedir": str(tmp_path)})
        assert os.path.exists(proc_file[0]) is True


def test_clean_proc_dir_running_read_error(tmp_path, proc_file):
    with patch("salt.utils.master._read_proc_file", side_effect=OSError):
        salt.utils.master.clean_proc_dir({"cachedir": str(tmp_path)})
        assert os.path.exists(proc_file[0]) is True


def test_clean_proc_dir_not_running(tmp_path, proc_file):
    with patch("salt.utils.master._read_proc_file", return_value=proc_file[1]), patch(
        "salt.utils.master._check_cmdline", return_value=False
    ):
        salt.utils.master.clean_proc_dir({"cachedir": str(tmp_path)})
        assert os.path.exists(proc_file[0]) is False


def test_clean_proc_dir_not_running_error(tmp_path, proc_file):
    with patch("salt.utils.master._read_proc_file", return_value=proc_file[1]), patch(
        "salt.utils.master._check_cmdline", return_value=False
    ), patch("os.remove", side_effect=OSError):
        salt.utils.master.clean_proc_dir({"cachedir": str(tmp_path)})
        assert os.path.exists(proc_file[0]) is True
