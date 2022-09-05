import os

import pytest

import salt.modules.cmdmod as cmd
import salt.modules.opkg as opkg
from tests.support.mock import patch

pytestmark = [
    pytest.mark.skip_if_binaries_missing("stat", "md5sum", "uname"),
]


@pytest.fixture
def configure_loader_modules():
    return {
        opkg: {"__salt__": {"cmd.shell": cmd.shell, "cmd.run_stdout": cmd.run_stdout}},
        cmd: {},
    }


def test_conf_d_path_does_not_exist_not_created_by_restart_check(tmp_path):
    """
    Test when nisysapi ``conf.d.path`` does not exist it should not be created by update restart check
    """
    conf_d_path = tmp_path / "conf.d.path"
    assert not conf_d_path.exists()
    with patch.object(opkg, "NILRT_RESTARTCHECK_STATE_PATH", str(tmp_path)), patch(
        "salt.modules.opkg._get_nisysapi_conf_d_path",
        autospec=True,
        return_value=str(conf_d_path),
    ):
        opkg._update_nilrt_restart_state()

        assert not conf_d_path.exists()


def test_conf_d_path_exists_with_no_files(tmp_path):
    """
    Test when nisysapi ``conf.d.path`` exists and no files exist we should not add any check files
    """
    conf_d_path = tmp_path / "conf.d.path"
    conf_d_path.mkdir(parents=True, exist_ok=True)
    with patch.object(opkg, "NILRT_RESTARTCHECK_STATE_PATH", str(tmp_path)), patch(
        "salt.modules.opkg._get_nisysapi_conf_d_path",
        autospec=True,
        return_value=str(conf_d_path),
    ):
        opkg._update_nilrt_restart_state()

        assert not [
            path
            for path in tmp_path.iterdir()
            if path.suffix in (".timestamp", ".md5sum") and path.stem != "modules.dep"
        ]


@pytest.mark.skip_unless_on_linux(reason="Test requires GNU stat")
def test_conf_d_path_exists_with_files(tmp_path):
    """
    Test when nisysapi ``conf.d.path`` exists with files then we should fingerprint the files
    """
    conf_d_path = tmp_path / "conf.d.path"
    conf_d_path.mkdir(parents=True, exist_ok=True)
    file_one = conf_d_path / "file_one"
    expected_md5sum = "d41d8cd98f00b204e9800998ecf8427e  {}\n".format(file_one)
    expected_timestamp = "10000\n"
    file_one.touch()
    os.utime(str(file_one), (int(expected_timestamp), int(expected_timestamp)))
    with patch.object(opkg, "NILRT_RESTARTCHECK_STATE_PATH", str(tmp_path)), patch(
        "salt.modules.opkg._get_nisysapi_conf_d_path",
        autospec=True,
        return_value=str(conf_d_path),
    ):
        opkg._update_nilrt_restart_state()

        assert [
            path
            for path in tmp_path.iterdir()
            if path.suffix in (".timestamp", ".md5sum") and path.stem != "modules.dep"
        ]

        timestamp = (
            tmp_path / file_one.with_suffix(suffix=".timestamp").name
        ).read_text()
        md5sum = (tmp_path / file_one.with_suffix(suffix=".md5sum").name).read_text()
        assert timestamp == expected_timestamp
        assert md5sum == expected_md5sum
