import logging
import os
import tempfile

import pytest

import salt.config

pytestmark = [
    pytest.mark.windows_whitelisted,
]

log = logging.getLogger(__name__)


def test_minion_config_type_check(caplog):
    msg = "Config option 'ipc_write_buffer' with value"
    caplog.set_level(logging.WARNING)
    fd, path = tempfile.mkstemp()
    try:
        with os.fdopen(fd, "w") as tmp:
            tmp.write("ipc_write_buffer: 'dynamic'\n")
        salt.config.minion_config(path)

        assert msg not in caplog.text
    finally:
        os.remove(path)


def test_cloud_config_relative_logfile(tmp_path):
    root_path = tmp_path
    config_path = tmp_path / "conf"
    config_path.mkdir()
    cloud_config = config_path / "cloud"
    cloud_config.write_text("")
    master_config = config_path / "master"
    master_config = config_path / "master"
    master_config.write_text(f"root_dir: {root_path}")
    opts = salt.config.cloud_config(cloud_config)
    assert opts["log_file"] == str(root_path / "var" / "log" / "salt" / "cloud")
