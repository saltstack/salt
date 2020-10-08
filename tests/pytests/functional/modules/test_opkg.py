import os
import tempfile
from pathlib import Path

import pytest
import salt.modules.cmdmod as cmd
import salt.modules.opkg as opkg
import salt.utils.platform
from tests.support.mock import patch


@pytest.fixture(autouse=True)
def setup_loader(request):
    setup_loader_modules = {
        opkg: {"__salt__": {"cmd.shell": cmd.shell, "cmd.run_stdout": cmd.run_stdout}},
        cmd: {},
    }
    with pytest.helpers.loader_mock(request, setup_loader_modules) as loader_mock:
        yield loader_mock


def test_when_nisysapi_conf_d_path_does_not_exist_it_should_not_be_created_by_update_restart_check():
    with tempfile.TemporaryDirectory() as tempdir:
        conf_d_path = Path(tempdir, "conf.d.path")
        assert not conf_d_path.exists()
        with patch.object(opkg, "NILRT_RESTARTCHECK_STATE_PATH", tempdir), patch(
            "salt.modules.opkg._get_nisysapi_conf_d_path",
            autospec=True,
            return_value=str(conf_d_path),
        ):
            opkg._update_nilrt_restart_state()

            assert not conf_d_path.exists()


def test_when_nisysapi_conf_d_path_exists_and_no_files_exist_we_should_not_add_any_check_files():
    with tempfile.TemporaryDirectory() as tempdir:
        restartcheck_path = Path(tempdir)
        conf_d_path = restartcheck_path / "conf.d.path"
        conf_d_path.mkdir(parents=True, exist_ok=True)
        with patch.object(opkg, "NILRT_RESTARTCHECK_STATE_PATH", tempdir), patch(
            "salt.modules.opkg._get_nisysapi_conf_d_path",
            autospec=True,
            return_value=str(conf_d_path),
        ):
            opkg._update_nilrt_restart_state()

            assert not [
                path
                for path in restartcheck_path.iterdir()
                if path.suffix in (".timestamp", ".md5sum")
            ]


@pytest.mark.skipif(
    not salt.utils.platform.is_linux(),
    reason="Test requires GNU stat - not found on macOS",
)
def test_when_nisysapi_conf_d_path_exists_with_files_then_we_should_fingerprint_the_files():
    with tempfile.TemporaryDirectory() as tempdir:
        restartcheck_path = Path(tempdir)
        conf_d_path = restartcheck_path / "conf.d.path"
        conf_d_path.mkdir(parents=True, exist_ok=True)
        file_one = conf_d_path / "file_one"
        expected_md5sum = "d41d8cd98f00b204e9800998ecf8427e  {}\n".format(file_one)
        expected_timestamp = "10000\n"
        file_one.touch()
        os.utime(str(file_one), (int(expected_timestamp), int(expected_timestamp)))
        with patch.object(opkg, "NILRT_RESTARTCHECK_STATE_PATH", tempdir), patch(
            "salt.modules.opkg._get_nisysapi_conf_d_path",
            autospec=True,
            return_value=str(conf_d_path),
        ):
            opkg._update_nilrt_restart_state()

            timestamp = (
                restartcheck_path / file_one.with_suffix(suffix=".timestamp").name
            ).read_text()
            md5sum = (
                restartcheck_path / file_one.with_suffix(suffix=".md5sum").name
            ).read_text()
            assert timestamp == expected_timestamp
            assert md5sum == expected_md5sum
