import logging
import os
import tempfile

import pytest

import salt.config
import salt.utils.platform

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


def test_cloud_config_relative_to_root_dir(tmp_path):
    root_path = tmp_path
    config_path = tmp_path / "conf"
    config_path.mkdir()
    cloud_config = config_path / "cloud"
    cloud_config.write_text("")
    master_config = config_path / "master"
    master_config.write_text(f"root_dir: {root_path}")
    opts = salt.config.cloud_config(cloud_config)
    assert opts["log_file"] == str(root_path / "var" / "log" / "salt" / "cloud")
    assert opts["cachedir"] == str(root_path / "var" / "cache" / "salt" / "cloud")


def test_master_config_relative_to_root_dir(tmp_path):
    root_path = tmp_path
    config_path = tmp_path / "conf"
    config_path.mkdir()
    master_config = config_path / "master"
    master_config.write_text(f"root_dir: {root_path}")
    opts = salt.config.master_config(master_config)
    if salt.utils.platform.is_windows():
        assert opts["pki_dir"] == str(root_path / "conf" / "pki" / "master")
    else:
        assert opts["pki_dir"] == str(root_path / "etc" / "salt" / "pki" / "master")
    assert opts["cachedir"] == str(root_path / "var" / "cache" / "salt" / "master")
    assert opts["pidfile"] == str(root_path / "var" / "run" / "salt-master.pid")
    assert opts["sock_dir"] == str(root_path / "var" / "run" / "salt" / "master")
    assert opts["extension_modules"] == str(
        root_path / "var" / "cache" / "salt" / "master" / "extmods"
    )
    assert opts["token_dir"] == str(
        root_path / "var" / "cache" / "salt" / "master" / "tokens"
    )
    assert opts["syndic_dir"] == str(
        root_path / "var" / "cache" / "salt" / "master" / "syndics"
    )
    assert opts["sqlite_queue_dir"] == str(
        root_path / "var" / "cache" / "salt" / "master" / "queues"
    )
    assert opts["log_file"] == str(root_path / "var" / "log" / "salt" / "master")
    assert opts["key_logfile"] == str(root_path / "var" / "log" / "salt" / "key")
    assert opts["ssh_log_file"] == str(root_path / "var" / "log" / "salt" / "ssh")

    # These are not tested because we didn't define them in the master config.
    # assert opts["autosign_file"] == str(root_path / "var" / "run" / "salt"/ "master")
    # assert opts["autoreject_file"] == str(root_path / "var" / "run" / "salt"/ "master")
    # assert opts["autosign_grains_dir"] == str(root_path / "var" / "run" / "salt"/ "master")


def test_minion_config_relative_to_root_dir(tmp_path):
    root_path = tmp_path
    config_path = tmp_path / "conf"
    config_path.mkdir()
    minion_config = config_path / "minion"
    minion_config.write_text(f"root_dir: {root_path}")
    opts = salt.config.minion_config(minion_config)
    if salt.utils.platform.is_windows():
        assert opts["pki_dir"] == str(root_path / "conf" / "pki" / "minion")
    else:
        assert opts["pki_dir"] == str(root_path / "etc" / "salt" / "pki" / "minion")
    assert opts["cachedir"] == str(root_path / "var" / "cache" / "salt" / "minion")
    assert opts["pidfile"] == str(root_path / "var" / "run" / "salt-minion.pid")
    assert opts["sock_dir"] == str(root_path / "var" / "run" / "salt" / "minion")
    assert opts["extension_modules"] == str(
        root_path / "var" / "cache" / "salt" / "minion" / "extmods"
    )
    assert opts["log_file"] == str(root_path / "var" / "log" / "salt" / "minion")


def test_api_config_relative_to_root_dir(tmp_path):
    root_path = tmp_path
    config_path = tmp_path / "conf"
    config_path.mkdir()
    master_config = config_path / "master"
    master_config.write_text(f"root_dir: {root_path}")
    opts = salt.config.api_config(master_config)
    assert opts["pidfile"] == str(root_path / "var" / "run" / "salt-api.pid")
    assert opts["log_file"] == str(root_path / "var" / "log" / "salt" / "api")
    assert opts["api_pidfile"] == str(root_path / "var" / "run" / "salt-api.pid")
    assert opts["api_logfile"] == str(root_path / "var" / "log" / "salt" / "api")


def test_spm_config_relative_to_root_dir(tmp_path):
    root_path = tmp_path
    config_path = tmp_path / "conf"
    config_path.mkdir()
    spm_config = config_path / "spm"
    spm_config.write_text(f"root_dir: {root_path}")
    opts = salt.config.spm_config(spm_config)

    assert opts["formula_path"] == str(root_path / "srv" / "spm" / "salt")
    assert opts["pillar_path"] == str(root_path / "srv" / "spm" / "pillar")
    assert opts["reactor_path"] == str(root_path / "srv" / "spm" / "reactor")
    assert opts["spm_cache_dir"] == str(root_path / "var" / "cache" / "salt" / "spm")
    assert opts["spm_build_dir"] == str(root_path / "srv" / "spm_build")
    assert opts["spm_logfile"] == str(root_path / "var" / "log" / "salt" / "spm")


def test_syndic_config_relative_to_root_dir(tmp_path):
    root_path = tmp_path
    config_path = tmp_path / "conf"
    config_path.mkdir()
    master_config = config_path / "master"
    master_config.write_text(f"root_dir: {root_path}")
    minion_config = config_path / "master"
    minion_config.write_text(f"root_dir: {root_path}")
    opts = salt.config.syndic_config(master_config, minion_config)
    if salt.utils.platform.is_windows():
        assert opts["pki_dir"] == str(root_path / "conf" / "pki" / "minion")
    else:
        assert opts["pki_dir"] == str(root_path / "etc" / "salt" / "pki" / "minion")
    assert opts["cachedir"] == str(root_path / "var" / "cache" / "salt" / "master")
    assert opts["pidfile"] == str(root_path / "var" / "run" / "salt-syndic.pid")
    assert opts["sock_dir"] == str(root_path / "var" / "run" / "salt" / "minion")
    assert opts["extension_modules"] == str(
        root_path / "var" / "cache" / "salt" / "minion" / "extmods"
    )
    assert opts["token_dir"] == str(
        root_path / "var" / "cache" / "salt" / "master" / "tokens"
    )
    assert opts["log_file"] == str(root_path / "var" / "log" / "salt" / "syndic")
    assert opts["key_logfile"] == str(root_path / "var" / "log" / "salt" / "key")
    assert opts["syndic_log_file"] == str(root_path / "var" / "log" / "salt" / "syndic")
